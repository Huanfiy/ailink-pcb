#!/usr/bin/env python3
"""Grid A* router for the leftover connections freerouting could not finish.

- Builds an obstacle grid (0.25 mm) for F.Cu / B.Cu from existing copper.
- Deletes the partial tracks of the target nets, then routes each net
  pad-to-pad (8-direction, via switching allowed).
- Emits 0.2 mm tracks and 0.6/0.3 vias.
"""
import heapq
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

STEP = 0.25
from product_config import (X0, Y0, X1, Y1, MCU_CENTER, HSE_BODY, PLANE_NETS,
                            PROTECTED_NETS, USB_REAR_GND_WINDOW, contains, inflate)
NX = int((X1 - X0) / STEP) + 1
NY = int((Y1 - Y0) / STEP) + 1
TRACK_W = 0.2
CLR = 0.16
VIA_D, VIA_DRILL = 0.5, 0.3
# Grid cells whose centre falls inside these rectangles are never routable.
# HSE: half of a 0.15 mm track so the edge of the trace stays off the body.
HSE_TRACK_KEEPOUT = inflate(HSE_BODY, 0.075)
# L3: window plus 0.25 mm (track half-width + clearance at the finest grid).
L3_TRACK_KEEPOUT = inflate(USB_REAR_GND_WINDOW, 0.25)


def set_step(step, clr):
    global STEP, NX, NY, CLR
    STEP = step
    CLR = clr
    NX = int((X1 - X0) / STEP) + 1
    NY = int((Y1 - Y0) / STEP) + 1

F, B = 0, 1
LAYER_ID = {F: pcbnew.F_Cu, B: pcbnew.B_Cu}


def enable_inner_signals():
    """Allow short L3 escapes; L2 and the rear USB reference stay continuous."""
    LAYER_ID[2] = pcbnew.In2_Cu


def cell(x, y):
    return (int(round((x - X0) / STEP)), int(round((y - Y0) / STEP)))


def coord(c):
    return (round(X0 + c[0] * STEP, 3), round(Y0 + c[1] * STEP, 3))


class Grid:
    def __init__(self):
        self.blocked = [[bytearray(NY) for _ in range(NX)] for _ in LAYER_ID]
        self.via_bad = [bytearray(NY) for _ in range(NX)]
        self.soft = {}          # (layer, i, j) -> netname (rippable copper)

    def track_allowed(self, layer, i, j):
        if self.blocked[layer][i][j]:return False
        if layer == F:
            if contains(HSE_TRACK_KEEPOUT, *coord((i,j))):return False
        if layer == 2:
            # Protect actual L3 GND plus 0.25 mm. Through vias may cross the
            # plane with antipads; F/B switching is distinct from routing L3.
            if contains(L3_TRACK_KEEPOUT, *coord((i,j))):return False
        return True

    def soft_disc(self, layer, x, y, r, netname):
        c0 = cell(x - r, y - r)
        c1 = cell(x + r, y + r)
        for i in range(max(0, c0[0]), min(NX, c1[0] + 1)):
            for j in range(max(0, c0[1]), min(NY, c1[1] + 1)):
                px, py = coord((i, j))
                if (px - x) ** 2 + (py - y) ** 2 <= r * r:
                    self.soft[(layer, i, j)] = netname

    def soft_seg(self, layer, x1, y1, x2, y2, r, netname):
        length = math.dist((x1, y1), (x2, y2))
        n = max(1, int(length / (STEP / 2)))
        for k in range(n + 1):
            t = k / n
            self.soft_disc(layer, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t,
                           r, netname)

    def block_via_disc(self, x, y, r):
        c0 = cell(x - r, y - r)
        c1 = cell(x + r, y + r)
        for i in range(max(0, c0[0]), min(NX, c1[0] + 1)):
            for j in range(max(0, c0[1]), min(NY, c1[1] + 1)):
                px, py = coord((i, j))
                if (px - x) ** 2 + (py - y) ** 2 <= r * r:
                    self.via_bad[i][j] = 1

    def block_disc(self, layer, x, y, r):
        c0 = cell(x - r, y - r)
        c1 = cell(x + r, y + r)
        for i in range(max(0, c0[0]), min(NX, c1[0] + 1)):
            for j in range(max(0, c0[1]), min(NY, c1[1] + 1)):
                px, py = coord((i, j))
                if (px - x) ** 2 + (py - y) ** 2 <= r * r:
                    self.blocked[layer][i][j] = 1

    def block_seg(self, layer, x1, y1, x2, y2, r):
        length = math.dist((x1, y1), (x2, y2))
        n = max(1, int(length / (STEP / 2)))
        for k in range(n + 1):
            t = k / n
            self.block_disc(layer, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r)

    def block_rect(self, layer, cx, cy, hw, hh, r):
        c0 = cell(cx - hw - r, cy - hh - r)
        c1 = cell(cx + hw + r, cy + hh + r)
        for i in range(max(0, c0[0]), min(NX, c1[0] + 1)):
            for j in range(max(0, c0[1]), min(NY, c1[1] + 1)):
                px, py = coord((i, j))
                dx = max(abs(px - cx) - hw, 0)
                dy = max(abs(py - cy) - hh, 0)
                if dx * dx + dy * dy <= r * r:
                    self.blocked[layer][i][j] = 1

    def block_shape(self, layer, shape, margin):
        """Rasterize actual KiCad pad copper, not its rectangular envelope.

        Bounding boxes close valid channels beside circular/oval/rounded pads.
        The native shape test keeps those channels while retaining clearance.
        """
        bbox = pcbnew.SHAPE.BBox(shape)
        lo = cell(pc.to_mm(bbox.GetLeft()) - margin, pc.to_mm(bbox.GetTop()) - margin)
        hi = cell(pc.to_mm(bbox.GetRight()) + margin, pc.to_mm(bbox.GetBottom()) + margin)
        clearance = mm(margin)
        for i in range(max(0, lo[0]), min(NX, hi[0] + 1)):
            for j in range(max(0, lo[1]), min(NY, hi[1] + 1)):
                if pcbnew.SHAPE.Collide(shape, pt(*coord((i, j))), clearance):
                    self.blocked[layer][i][j] = 1

    def is_free(self, layer, c):
        return not self.blocked[layer][c[0]][c[1]]

    def via_ok(self, c):
        """Via needs room on both layers plus hole spacing.

        blocked[] is already inflated by track-half + clearance, so we only
        need extra neighbourhood for the via being fatter than a track.
        """
        if not (0 <= c[0] < NX and 0 <= c[1] < NY):
            return False
        if self.via_bad[c[0]][c[1]]:
            return False
        extra = max(1, int(math.ceil((VIA_D - TRACK_W) / 2.0 / STEP)))
        r2 = ((VIA_D - TRACK_W) / 2.0 / STEP) ** 2
        for layer in LAYER_ID:
            for di in range(-extra, extra + 1):
                for dj in range(-extra, extra + 1):
                    if di * di + dj * dj > r2:
                        continue
                    i, j = c[0] + di, c[1] + dj
                    if not (0 <= i < NX and 0 <= j < NY):
                        return False
                    if self.blocked[layer][i][j]:
                        return False
        return True


# Never ripped up during soft-obstacle search: locked nets, planes, and the
# two debug-critical MCU lines.
HARD_NETS = PROTECTED_NETS + PLANE_NETS + ("NRST", "MCU_SWDIO")
MCU_CX, MCU_CY = MCU_CENTER


def via_dia(t):
    """KiCad 10: PCB_VIA.GetWidth() requires a layer and spams asserts."""
    return pc.to_mm(t.GetFrontWidth())


def track_w(t):
    if t.GetClass() == "PCB_VIA":
        return via_dia(t)
    return pc.to_mm(t.GetWidth())


def build_grid(board, skip_nets, soft_signals=False):
    """soft_signals: other signal nets' tracks become rip-able soft cost."""
    g = Grid()
    # coarse grids need the half-cell fudge; fine grids can run exact
    fudge = STEP * 0.51 if STEP > 0.08 else 0.0
    margin = TRACK_W / 2 + CLR + fudge
    # board edge
    for i in range(NX):
        for j in range(NY):
            px, py = coord((i, j))
            if px < X0 + 0.55 or px > X1 - 0.55 or py < Y0 + 0.55 or py > Y1 - 0.55:
                for layer in LAYER_ID:
                    g.blocked[layer][i][j] = 1
    for t in all_tracks(board):
        net = t.GetNetname()
        if net in skip_nets:
            continue
        rippable = (soft_signals and net not in HARD_NETS
                    and not t.IsLocked() and not net.startswith("unconnected"))
        if t.GetClass() == "PCB_VIA":
            x, y = pc.to_mm(t.GetPosition().x), pc.to_mm(t.GetPosition().y)
            r = via_dia(t) / 2 + margin
            if rippable:
                for layer in LAYER_ID:g.soft_disc(layer, x, y, r, net)
            else:
                for layer in LAYER_ID:g.block_disc(layer, x, y, r)
                g.block_via_disc(x, y, 0.62)
        else:
            lay = t.GetLayerName()
            if t.GetLayer() not in LAYER_ID.values():
                continue
            layer = next(i for i,layer_id in LAYER_ID.items() if t.GetLayer()==layer_id)
            r = pc.to_mm(t.GetWidth()) / 2 + margin
            x1, y1 = pc.to_mm(t.GetStart().x), pc.to_mm(t.GetStart().y)
            x2, y2 = pc.to_mm(t.GetEnd().x), pc.to_mm(t.GetEnd().y)
            if rippable:
                g.soft_seg(layer, x1, y1, x2, y2, r, net)
            else:
                g.block_seg(layer, x1, y1, x2, y2, r)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            pos = pad.GetPosition()
            x, y = pc.to_mm(pos.x), pc.to_mm(pos.y)
            sz = pad.GetSize(pcbnew.PADSTACK.ALL_LAYERS)
            hw = pc.to_mm(sz.x) / 2
            hh = pc.to_mm(sz.y) / 2
            rot = pad.GetOrientationDegrees() % 180
            if abs(rot - 90) < 45:
                hw, hh = hh, hw
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                layers = [F] if fp.GetLayer() == pcbnew.F_Cu else [B]
                if pad.GetLayerSet().Contains(pcbnew.B_Cu) \
                        and pad.GetLayerSet().Contains(pcbnew.F_Cu):
                    layers = [F, B]
                elif pad.GetLayerSet().Contains(pcbnew.B_Cu):
                    layers = [B]
                elif pad.GetLayerSet().Contains(pcbnew.F_Cu):
                    layers = [F]
                # keep via holes away from all SMD pads (hole clearance)
                c0=cell(x-hw-VIA_DRILL/2-.075,y-hh-VIA_DRILL/2-.075)
                c1=cell(x+hw+VIA_DRILL/2+.075,y+hh+VIA_DRILL/2+.075)
                for i in range(max(0,c0[0]),min(NX,c1[0]+1)):
                    for j in range(max(0,c0[1]),min(NY,c1[1]+1)):
                        px,py=coord((i,j))
                        dx=max(abs(px-x)-hw,0);dy=max(abs(py-y)-hh,0)
                        if dx*dx+dy*dy<(VIA_DRILL/2+.075)**2:g.via_bad[i][j]=1
            else:
                layers = list(LAYER_ID)
                g.block_via_disc(x, y, 0.9)
            if net in skip_nets:
                continue
            for layer in layers:
                pad_margin=max(margin,TRACK_W/2+.255+fudge) if pad.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH else margin
                g.block_shape(layer, pad.GetEffectiveShape(LAYER_ID[layer]), pad_margin)
    # Rule areas (keepouts): A* otherwise ignores them and re-enters.
    for z in board.Zones():
        if not z.GetIsRuleArea():
            continue
        ban_trk = z.GetDoNotAllowTracks()
        ban_via = z.GetDoNotAllowVias()
        if not (ban_trk or ban_via):
            continue
        layers = []
        if z.IsOnLayer(pcbnew.F_Cu):
            layers.append(F)
        if z.IsOnLayer(pcbnew.B_Cu):
            layers.append(B)
        if not layers:
            continue
        try:
            bb = z.GetBoundingBox()
            x0 = pc.to_mm(bb.GetLeft())
            y0 = pc.to_mm(bb.GetTop())
            x1 = pc.to_mm(bb.GetRight())
            y1 = pc.to_mm(bb.GetBottom())
        except Exception:
            continue
        pad = TRACK_W / 2 + CLR
        if ban_trk:
            for layer in layers:
                g.block_rect(layer, (x0 + x1) / 2, (y0 + y1) / 2,
                             (x1 - x0) / 2, (y1 - y0) / 2, pad)
        if ban_via:
            c0 = cell(x0 - 0.3, y0 - 0.3)
            c1 = cell(x1 + 0.3, y1 + 0.3)
            for i in range(max(0, c0[0]), min(NX, c1[0] + 1)):
                for j in range(max(0, c0[1]), min(NY, c1[1] + 1)):
                    px, py = coord((i, j))
                    if x0 - 0.15 <= px <= x1 + 0.15 and y0 - 0.15 <= py <= y1 + 0.15:
                        g.via_bad[i][j] = 1
    return g


DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]


def astar(g, starts, goals):
    """starts/goals: set of (layer, cx, cy). Returns node path or None."""
    goal_set = set(goals)
    gx = {}
    openq = []
    for s in starts:
        gx[s] = 0.0
        heapq.heappush(openq, (0.0, s, None))
    came = {}
    seen = set()
    gxy = [(c[1], c[2]) for c in goals]

    def h(n):
        return min(abs(n[1] - a) + abs(n[2] - b) for a, b in gxy) * 0.9

    soft = g.soft
    # cheap enough to cross a blocker rather than wander forever, expensive
    # enough to prefer a free 2 mm detour over ripping a net
    soft_cost = 6.0
    while openq:
        f, node, parent = heapq.heappop(openq)
        if node in seen:
            continue
        seen.add(node)
        came[node] = parent
        if node in goal_set:
            path = [node]
            while came[path[-1]] is not None:
                path.append(came[path[-1]])
            return list(reversed(path))
        layer, ci, cj = node
        base = gx[node]
        for di, dj, w in DIRS:
            ni, nj = ci + di, cj + dj
            if not (0 <= ni < NX and 0 <= nj < NY):
                continue
            if not g.track_allowed(layer,ni,nj):
                continue
            nn = (layer, ni, nj)
            ng = base + w + (soft_cost if (layer, ni, nj) in soft else 0)
            if nn not in gx or ng < gx[nn] - 1e-9:
                gx[nn] = ng
                heapq.heappush(openq, (ng + h(nn), nn, node))
        # via
        if g.via_ok((ci, cj)):
            for other_layer in LAYER_ID:
                if other_layer == layer:continue
                if not g.track_allowed(other_layer,ci,cj):continue
                nn = (other_layer, ci, cj)
                ng = base + 12
                if nn not in gx or ng < gx[nn] - 1e-9:
                    gx[nn] = ng
                    heapq.heappush(openq, (ng + h(nn), nn, node))
    return None


def path_to_geometry(path):
    """Collapse path into polyline segments per layer + via points."""
    out_segs = []   # (layer, [pts])
    vias = []
    cur_layer = path[0][0]
    pts = [coord((path[0][1], path[0][2]))]
    prev = path[0]
    for node in path[1:]:
        if node[0] != cur_layer:
            vias.append(coord((node[1], node[2])))
            out_segs.append((cur_layer, pts))
            cur_layer = node[0]
            pts = [coord((node[1], node[2]))]
        else:
            pts.append(coord((node[1], node[2])))
        prev = node
    out_segs.append((cur_layer, pts))
    # collapse collinear points
    slim = []
    for layer, ps in out_segs:
        if len(ps) < 2:
            slim.append((layer, ps))
            continue
        keep = [ps[0]]
        for i in range(1, len(ps) - 1):
            ax, ay = keep[-1]
            bx, by = ps[i]
            cx2, cy2 = ps[i + 1]
            # Coordinates are decimal millimetres: exact float comparison
            # leaves dozens of artificial bends on a straight grid run.
            cross = (bx - ax) * (cy2 - by) - (by - ay) * (cx2 - bx)
            if abs(cross) > 1e-9:
                keep.append(ps[i])
        keep.append(ps[-1])
        slim.append((layer, keep))
    return slim, vias


def add_route(board, netname, segs, vias):
    net = board.GetNetsByName()[netname]
    for layer, ps in segs:
        for a, b in zip(ps, ps[1:]):
            if a == b:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pt(*a)); t.SetEnd(pt(*b))
            t.SetWidth(mm(TRACK_W))
            t.SetLayer(LAYER_ID[layer])
            t.SetNet(net)
            board.Add(t)
    for x, y in vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(x, y))
        v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(net)
        board.Add(v)


def _pad_hw_hh(pad):
    sz = pad.GetSize(pcbnew.PADSTACK.ALL_LAYERS)
    hw = pc.to_mm(sz.x) / 2
    hh = pc.to_mm(sz.y) / 2
    rot = pad.GetOrientationDegrees() % 180
    if abs(rot - 90) < 45:
        hw, hh = hh, hw
    return hw, hh


def pad_escape(x, y, hw, hh):
    """Start just beyond an LQFP pad tip, away from the MCU body.

    Adjacent 0.5 mm-pitch pads inflate each other into a keep-out sausage;
    routing from the pad centre therefore dies.  Escaping along the long
    axis lands in the west / south / north channel.
    """
    # only LQFP-style needles (1.55×0.30), never 0402 (0.80×0.95)
    if max(hw, hh) < 0.55 or max(hw, hh) / max(min(hw, hh), 0.01) < 2.5:
        return (x, y)
    if hw >= hh:
        sign = -1.0 if x < MCU_CX else 1.0
        return (round(x + sign * (hw + 0.38), 3), y)
    sign = -1.0 if y < MCU_CY else 1.0
    return (x, round(y + sign * (hh + 0.38), 3))


def pad_cells(board, netname):
    """All pads of net -> list of (node, escape_xy, pad_xy)."""
    seeds = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != netname:
                continue
            pos = pad.GetPosition()
            x, y = pc.to_mm(pos.x), pc.to_mm(pos.y)
            hw, hh = _pad_hw_hh(pad)
            ex, ey = pad_escape(x, y, hw, hh)
            c = cell(ex, ey)
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                layer = B if pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu) else F
                layers = [layer]
            else:
                layers = [F, B]
            for l in layers:
                seeds.append(((l, c[0], c[1]), (ex, ey), (x, y)))
    return seeds


def _carve_disc(grid, layer, x, y, r):
    c0 = cell(x - r, y - r)
    c1 = cell(x + r, y + r)
    r2 = r * r
    for i in range(max(0, c0[0]), min(NX, c1[0] + 1)):
        for j in range(max(0, c0[1]), min(NY, c1[1] + 1)):
            px, py = coord((i, j))
            if (px - x) ** 2 + (py - y) ** 2 <= r2:
                grid.blocked[layer][i][j] = 0


def carve_seeds(grid, seeds):
    """Unblock a capsule from pad centre to the escape tip (not a big disc)."""
    for (layer, ci, cj), esc, pad in seeds:
        x1, y1 = pad
        x2, y2 = esc
        length = math.dist((x1, y1), (x2, y2))
        n = max(1, int(length / max(STEP / 2, 0.03)))
        for k in range(n + 1):
            t = k / n
            _carve_disc(grid, layer,
                        x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, 0.20)


def seed_nodes(grid, node):
    """A small cloud of free cells around a seed so A* can leave the pad."""
    layer, ci, cj = node
    out = set()
    for di in range(-2, 3):
        for dj in range(-2, 3):
            i, j = ci + di, cj + dj
            if 0 <= i < NX and 0 <= j < NY and not grid.blocked[layer][i][j]:
                out.add((layer, i, j))
    if not out:
        out.add(node)
    return out


def net_copper_nodes(board, netname):
    """Existing same-net tracks/vias as graph nodes (they are live copper)."""
    nodes = set()
    for t in all_tracks(board):
        if t.GetNetname() != netname:
            continue
        if t.GetClass() == "PCB_VIA":
            x, y = pc.to_mm(t.GetPosition().x), pc.to_mm(t.GetPosition().y)
            c = cell(x, y)
            nodes.add((F, c[0], c[1]))
            nodes.add((B, c[0], c[1]))
        elif t.GetLayerName() in ("F.Cu", "B.Cu"):
            layer = F if t.GetLayerName() == "F.Cu" else B
            for p in (t.GetStart(), t.GetEnd()):
                c = cell(pc.to_mm(p.x), pc.to_mm(p.y))
                nodes.add((layer, c[0], c[1]))
    return nodes


def route_net(board, grid, netname):
    seeds = pad_cells(board, netname)
    if len(seeds) < 2:
        print(f"{netname}: less than 2 pads?", flush=True)
        return True
    copper = net_copper_nodes(board, netname)

    def has_copper(seed):
        (l, ci, cj), esc, pad = seed
        return any(abs(n[1] - ci) <= 2 and abs(n[2] - cj) <= 2 and n[0] == l
                   for n in copper)
    seeds.sort(key=lambda s: 0 if has_copper(s) else 1)
    carve_seeds(grid, seeds)
    done_nodes = set(copper)
    first = seeds[0]
    done_nodes |= seed_nodes(grid, first[0])
    ok_all = True
    for k in range(1, len(seeds)):
        start = seeds[k]
        starts = seed_nodes(grid, start[0])
        path = astar(grid, starts, done_nodes)
        if path is None:
            print(f"    leg FAILED: from {start[1]} (layer{start[0][0]})",
                  flush=True)
            ok_all = False
            continue
        segs, vias = path_to_geometry(path)
        head = path[0]
        tail = path[-1]
        # pad → escape → first grid cell (one polyline, no orphan stub)
        head_pts = [start[2]]
        if start[1] != start[2]:
            head_pts.append(start[1])
        head_pts.append(coord((head[1], head[2])))
        segs = [(head[0], head_pts)] + segs
        # Only stub to the first pad when the path actually ended next to it.
        # A long F.Cu jump from a distant via to pad0 used to slash through U1.
        tail_xy = coord((tail[1], tail[2]))
        if math.dist(tail_xy, first[2]) < 2.5:
            tail_pts = [tail_xy]
            if first[1] != first[2]:
                tail_pts.append(first[1])
            tail_pts.append(first[2])
            segs.append((tail[0], tail_pts))
        add_route(board, netname, segs, vias)
        for node in path:
            done_nodes.add(node)
    return ok_all


def all_tracks(board):
    """KiCad 10 SWIG: GetTracks() can decay to a non-iterable proxy."""
    try:
        ts = board.GetTracks()
        return list(ts)
    except TypeError:
        pass
    try:
        return list(board.Tracks())
    except TypeError:
        out = []
        t = board.GetTracks()
        # last resort: index through TRACKS container
        n = t.GetCount() if hasattr(t, "GetCount") else 0
        for i in range(n):
            out.append(t.Get(i) if hasattr(t, "Get") else t[i])
        return out


def rip_net(board, netname, tracks=None):
    doomed = [t for t in (tracks if tracks is not None else all_tracks(board))
              if t.GetNetname() == netname]
    for t in doomed:
        board.Remove(t)


def main(netnames):
    board = pcbnew.LoadBoard(pc.PCB)
    for n in netnames:
        rip_net(board, n)

    ladder = [(0.25, 0.16), (0.125, 0.16), (0.125, 0.13)]
    pending = list(netnames)
    for step, clr in ladder:
        if not pending:
            break
        set_step(step, clr)
        grid = build_grid(board, skip_nets=set(pending))
        nxt = []
        for netname in pending:
            ok = route_net(board, grid, netname)
            print(f"[step={step} clr={clr}] {netname}: "
                  f"{'OK' if ok else 'FAILED'}")
            if not ok:
                rip_net(board, netname)
                nxt.append(netname)
            else:
                # block the fresh copper for the remaining nets
                for t in all_tracks(board):
                    if t.GetNetname() != netname:
                        continue
                    if t.GetClass() == "PCB_VIA":
                        x = pc.to_mm(t.GetPosition().x)
                        y = pc.to_mm(t.GetPosition().y)
                        r = VIA_D / 2 + TRACK_W / 2 + CLR
                        grid.block_disc(F, x, y, r)
                        grid.block_disc(B, x, y, r)
                    elif t.GetLayerName() in ("F.Cu", "B.Cu"):
                        layer = F if t.GetLayerName() == "F.Cu" else B
                        grid.block_seg(
                            layer,
                            pc.to_mm(t.GetStart().x), pc.to_mm(t.GetStart().y),
                            pc.to_mm(t.GetEnd().x), pc.to_mm(t.GetEnd().y),
                            track_w(t) / 2 + TRACK_W / 2 + CLR)
        pending = nxt
    if pending:
        print("STILL UNROUTED:", pending)
    pcbnew.SaveBoard(pc.PCB, board)
    print("saved")


def rip_only(netname):
    board = pcbnew.LoadBoard(pc.PCB)
    rip_net(board, netname)
    pcbnew.SaveBoard(pc.PCB, board)
    print(f"ripped {netname}")


def _seg_pt_dist(a, b, p):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    if ll < 1e-12:
        return math.dist(a, p)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ll))
    return math.dist((ax + t * dx, ay + t * dy), p)


def _seg_seg_dist(a1, a2, b1, b2):
    """True 2D segment-segment distance (handles crossings)."""
    ax, ay = a1
    bx, by = a2
    cx, cy = b1
    dx, dy = b2
    ux, uy = bx - ax, by - ay
    vx, vy = dx - cx, dy - cy
    wx, wy = ax - cx, ay - cy
    uu = ux * ux + uy * uy
    vv = vx * vx + vy * vy
    uv = ux * vx + uy * vy
    uw = ux * wx + uy * wy
    vw = vx * wx + vy * wy
    denom = uu * vv - uv * uv
    if denom < 1e-18:
        return min(_seg_pt_dist(a1, a2, b1), _seg_pt_dist(a1, a2, b2),
                   _seg_pt_dist(b1, b2, a1), _seg_pt_dist(b1, b2, a2))
    s = (uv * vw - vv * uw) / denom
    t = (uu * vw - uv * uw) / denom
    s = max(0.0, min(1.0, s))
    t = max(0.0, min(1.0, t))
    # clamp independently then snap to edges
    p = (ax + s * ux, ay + s * uy)
    q = (cx + t * vx, cy + t * vy)
    # after independent clamp the pair may not be closest; also check ends
    return min(math.dist(p, q),
               _seg_pt_dist(a1, a2, b1), _seg_pt_dist(a1, a2, b2),
               _seg_pt_dist(b1, b2, a1), _seg_pt_dist(b1, b2, a2))


def _net_items_geo(board, netname, tracks=None):
    out = []
    for t in (tracks if tracks is not None else all_tracks(board)):
        if t.GetNetname() != netname:
            continue
        if t.GetClass() == "PCB_VIA":
            p = _pt_xy(t.GetPosition())
            out.append(("via", p, p, via_dia(t) / 2))
        elif t.GetLayerName() in ("F.Cu", "B.Cu"):
            s = _pt_xy(t.GetStart())
            e = _pt_xy(t.GetEnd())
            out.append((t.GetLayerName(), s, e, pc.to_mm(t.GetWidth()) / 2))
    return out


def fill_zones(board):
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())


def _pt_xy(p):
    try:
        return (pc.to_mm(p.x), pc.to_mm(p.y))
    except AttributeError:
        return (pc.to_mm(p.GetX()), pc.to_mm(p.GetY()))


def _collect_signals(board):
    out = set()
    for nc in range(board.GetNetCount()):
        net = board.FindNet(nc)
        if net is None:
            continue
        nm = net.GetNetname()
        if nm and nm not in HARD_NETS and not nm.startswith("unconnected"):
            out.add(nm)
    return out


def ripup_one(netname, protect):
    """Route one net in a fresh process, rip overlapping victims, save.

    protect: net names treated as hard (not rippable) during soft search.
    Prints a last line: RIPUP_RESULT ok=0|1 victims=a,b
    """
    global TRACK_W, HARD_NETS
    TRACK_W = 0.15
    extra_hard = tuple(p for p in protect if p and p != netname)
    if extra_hard:
        HARD_NETS = HARD_NETS + extra_hard
    board = pcbnew.LoadBoard(pc.PCB)
    signals = _collect_signals(board)
    rip_net(board, netname)
    routed = False
    used_soft = False
    for step, clr, soft in ((0.1, 0.162, False), (0.1, 0.162, True),
                            (0.075, 0.158, True)):
        set_step(step, clr)
        grid = build_grid(board, skip_nets={netname}, soft_signals=soft)
        ok = route_net(board, grid, netname)
        print(f"    step={step} soft={soft}: "
              f"{'OK' if ok else 'FAIL'}", flush=True)
        if ok:
            routed = True
            used_soft = soft
            break
        rip_net(board, netname)
    if not routed:
        pcbnew.SaveBoard(pc.PCB, board)
        print("RIPUP_RESULT ok=0 victims=", flush=True)
        return 1
    pcbnew.SaveBoard(pc.PCB, board)
    board = pcbnew.LoadBoard(pc.PCB)
    snap = all_tracks(board)
    mine = _net_items_geo(board, netname, snap)
    victims = set()
    if used_soft:
        by_net = {}
        for t in snap:
            by_net.setdefault(t.GetNetname(), []).append(t)
        for other, items in by_net.items():
            if other == netname or other in HARD_NETS:
                continue
            if other not in signals:
                continue
            ogeo = _net_items_geo(board, other, items)
            hit = False
            for o in ogeo:
                for m in mine:
                    lay_o, s1, e1, r1 = o
                    lay_m, s2, e2, r2 = m
                    if lay_o != lay_m and "via" not in (lay_o, lay_m):
                        continue
                    if _seg_seg_dist(s1, e1, s2, e2) < r1 + r2 + 0.12:
                        victims.add(other)
                        hit = True
                        break
                if hit:
                    break
        for v in victims:
            rip_net(board, v, snap)
        pcbnew.SaveBoard(pc.PCB, board)
    print("RIPUP_RESULT ok=1 victims=" + ",".join(sorted(victims)),
          flush=True)
    return 0


def ripup_route(netnames):
    """Parent: one subprocess per net so pcbnew SWIG never decays."""
    leftovers = list(netnames)
    leftover_set = set(leftovers)
    pending = list(netnames)
    attempts = {}
    failed = []
    here = os.path.abspath(__file__)
    for it in range(110):
        if not pending:
            break
        n = pending.pop(0)
        attempts[n] = attempts.get(n, 0) + 1
        if attempts[n] > 6:
            print(f"[ripup] giving up {n}", flush=True)
            if n not in failed:
                failed.append(n)
            continue
        protect = []
        if n not in leftover_set:
            # ripped existing routes must go around the leftover nets
            protect = list(leftover_set)
        print(f"[ripup] it={it+1} try {n} (#{attempts[n]}) "
              f"protect={protect} queue={pending}", flush=True)
        cmd = [sys.executable, here, "--ripup-one", n]
        if protect:
            cmd.append("--protect")
            cmd.extend(protect)
        r = subprocess.run(cmd, capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        sys.stdout.flush()
        if r.returncode not in (0, 1) or "RIPUP_RESULT" not in (r.stdout or ""):
            print(f"[ripup] worker crash rc={r.returncode}", flush=True)
            if r.stderr:
                sys.stderr.write(r.stderr[-2000:])
            if attempts[n] < 4:
                pending.append(n)
            else:
                failed.append(n)
            continue
        line = [ln for ln in r.stdout.splitlines() if ln.startswith("RIPUP_RESULT")][-1]
        ok = "ok=1" in line
        victims = []
        if "victims=" in line:
            vs = line.split("victims=", 1)[1].strip()
            if vs:
                victims = [v for v in vs.split(",") if v]
        if not ok:
            print(f"[ripup] {n}: NO PATH even soft", flush=True)
            if n in leftover_set and attempts[n] < 4:
                pending.append(n)
            elif n not in leftover_set and attempts[n] < 6 and protect:
                # retry without protecting leftovers
                leftover_set.discard("__dummy__")
                pending.append(n)
                # next try: allow ripping leftovers by pretending it's a leftover
                leftover_set.add(n)
            else:
                failed.append(n)
            continue
        for v in victims:
            if v not in pending:
                pending.append(v)
            if v in failed:
                failed.remove(v)
        print(f"[ripup] {n}: OK"
              + (f", ripped {sorted(victims)}" if victims else ""),
              flush=True)
    # zone refill in its own process
    subprocess.run([sys.executable, here, "--fill-zones"], check=False)
    if pending or failed:
        left = list(dict.fromkeys(failed + pending))
        print("[ripup] LEFT UNROUTED:", left, flush=True)
    else:
        print("[ripup] ALL ROUTED", flush=True)


def fill_zones_cli():
    board = pcbnew.LoadBoard(pc.PCB)
    fill_zones(board)
    pcbnew.SaveBoard(pc.PCB, board)
    print("zones refilled", flush=True)


def route_only(netname, width=None):
    global TRACK_W
    if width:
        TRACK_W = width
    board = pcbnew.LoadBoard(pc.PCB)
    ladder = [(0.25, 0.16), (0.125, 0.16), (0.1, 0.162),
              (0.075, 0.162), (0.06, 0.158)]
    for step, clr in ladder:
        set_step(step, clr)
        grid = build_grid(board, skip_nets={netname})
        ok = route_net(board, grid, netname)
        print(f"[step={step} clr={clr}] {netname}: {'OK' if ok else 'FAILED'}",
              flush=True)
        if ok:
            fill_zones(board)
            pcbnew.SaveBoard(pc.PCB, board)
            return 0
        rip_net(board, netname)
    pcbnew.SaveBoard(pc.PCB, board)
    return 1


def probe_net(netname, soft=False):
    """BFS reachability report (no board writes)."""
    global TRACK_W
    TRACK_W = 0.15
    board = pcbnew.LoadBoard(pc.PCB)
    set_step(0.1, 0.155)
    grid = build_grid(board, skip_nets={netname}, soft_signals=soft)
    seeds = pad_cells(board, netname)
    carve_seeds(grid, seeds)
    from collections import deque
    starts = seed_nodes(grid, seeds[0][0])
    goals = set()
    for s in seeds[1:]:
        goals |= seed_nodes(grid, s[0])
    print(f"probe {netname} soft={soft} start={seeds[0][1]} "
          f"escapes={[s[1] for s in seeds]} starts={len(starts)} "
          f"goals={len(goals)}", flush=True)
    q = deque(starts)
    seen = set(starts)
    while q:
        layer, ci, cj = q.popleft()
        if (layer, ci, cj) in goals:
            print(f"  HIT at {coord((ci, cj))} layer{layer} "
                  f"seen={len(seen)}", flush=True)
            return 0
        for di, dj, _ in DIRS:
            ni, nj = ci + di, cj + dj
            if not (0 <= ni < NX and 0 <= nj < NY):
                continue
            if grid.blocked[layer][ni][nj]:
                continue
            nn = (layer, ni, nj)
            if nn in seen:
                continue
            seen.add(nn)
            q.append(nn)
        if grid.via_ok((ci, cj)):
            nn = (1 - layer, ci, cj)
            if nn not in seen:
                seen.add(nn)
                q.append(nn)
    print(f"  MISS seen={len(seen)}", flush=True)
    return 1


if __name__ == "__main__":
    if sys.argv[1] == "--rip":
        rip_only(sys.argv[2])
    elif sys.argv[1] == "--ripup":
        ripup_route(sys.argv[2:])
    elif sys.argv[1] == "--ripup-one":
        net = sys.argv[2]
        prot = []
        if "--protect" in sys.argv:
            prot = sys.argv[sys.argv.index("--protect") + 1:]
        sys.exit(ripup_one(net, prot))
    elif sys.argv[1] == "--fill-zones":
        fill_zones_cli()
    elif sys.argv[1] == "--route":
        w = float(sys.argv[3]) if len(sys.argv) > 3 else None
        sys.exit(route_only(sys.argv[2], width=w))
    elif sys.argv[1] == "--probe":
        soft = "--soft" in sys.argv
        nets = [a for a in sys.argv[2:] if a != "--soft"]
        rc = 0
        for n in nets:
            rc |= probe_net(n, soft=soft)
        sys.exit(rc)
    elif sys.argv[1] == "--dump":
        # --dump NET x0 y0 x1 y1 : write blocked maps as PNG
        from PIL import Image
        netname = sys.argv[2]
        bx0, by0, bx1, by1 = map(float, sys.argv[3:7])
        set_step(0.06, 0.152)
        board = pcbnew.LoadBoard(pc.PCB)
        grid = build_grid(board, skip_nets={netname})
        c0 = cell(bx0, by0); c1 = cell(bx1, by1)
        w_ = c1[0] - c0[0] + 1
        h_ = c1[1] - c0[1] + 1
        for lname, lidx in (("F", F), ("B", B)):
            im = Image.new("RGB", (w_, h_), "white")
            px = im.load()
            for i in range(w_):
                for j in range(h_):
                    blocked = grid.blocked[lidx][c0[0] + i][c0[1] + j]
                    vb = grid.via_bad[c0[0] + i][c0[1] + j]
                    if blocked:
                        px[i, j] = (200, 40, 40)
                    elif vb:
                        px[i, j] = (255, 210, 150)
            im = im.resize((w_ * 4, h_ * 4), Image.NEAREST)
            im.save(f"/tmp/grid_{lname}.png")
        print("dumped /tmp/grid_F.png /tmp/grid_B.png")
    else:
        main(sys.argv[1:])
