"""Grid A* router library: obstacle grid, search and copper emission.

Every entry point takes a RouterConfig; there is no module-level mutable state,
so callers (finish_routes, the astar_router CLI, tests) can mix grid steps and
track widths freely. Layer indices are F=0, B=1, IN2=2; a config's ``layers``
tuple decides which of them exist in a grid.
"""
from dataclasses import dataclass
import heapq
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt
from product_config import (X0, Y0, X1, Y1, MCU_CENTER, HSE_BODY, PLANE_NETS,
                            PROTECTED_NETS, USB_REAR_GND_WINDOW, contains, inflate)

import pcbnew

F, B, IN2 = 0, 1, 2
LAYER_ID = {F: pcbnew.F_Cu, B: pcbnew.B_Cu, IN2: pcbnew.In2_Cu}
OUTER = (F, B)
WITH_INNER = (F, B, IN2)

# Never ripped up during soft-obstacle search: locked nets, planes, and the
# two debug-critical MCU lines.
HARD_NETS = PROTECTED_NETS + PLANE_NETS + ("NRST", "MCU_SWDIO")
MCU_CX, MCU_CY = MCU_CENTER

# Grid cells whose centre falls inside these rectangles are never routable.
# HSE: half of a 0.15 mm track so the edge of the trace stays off the body.
HSE_TRACK_KEEPOUT = inflate(HSE_BODY, 0.075)
# L3: window plus 0.25 mm (track half-width + clearance at the finest grid).
L3_TRACK_KEEPOUT = inflate(USB_REAR_GND_WINDOW, 0.25)

DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]


@dataclass(frozen=True)
class RouterConfig:
    step: float = 0.25
    clearance: float = 0.16
    track_w: float = 0.2
    layers: tuple = OUTER
    via_d: float = 0.5
    via_drill: float = 0.3

    @property
    def nx(self):
        return int((X1 - X0) / self.step) + 1

    @property
    def ny(self):
        return int((Y1 - Y0) / self.step) + 1

    def cell(self, x, y):
        return (int(round((x - X0) / self.step)), int(round((y - Y0) / self.step)))

    def coord(self, c):
        return (round(X0 + c[0] * self.step, 3), round(Y0 + c[1] * self.step, 3))

    def in_bounds(self, i, j):
        return 0 <= i < self.nx and 0 <= j < self.ny

    def layer_index(self, layer_id):
        """Grid layer index for a pcbnew layer id, or None if not routed."""
        for index in self.layers:
            if LAYER_ID[index] == layer_id:
                return index
        return None


class Grid:
    def __init__(self, config):
        self.config = config
        nx, ny = config.nx, config.ny
        self.blocked = {layer: [bytearray(ny) for _ in range(nx)] for layer in config.layers}
        self.via_bad = [bytearray(ny) for _ in range(nx)]
        self.soft = {}          # (layer, i, j) -> netname (rippable copper)

    @property
    def layers(self):
        return self.config.layers

    def cell(self, x, y):
        return self.config.cell(x, y)

    def coord(self, c):
        return self.config.coord(c)

    def track_allowed(self, layer, i, j):
        if self.blocked[layer][i][j]:return False
        if layer == F:
            if contains(HSE_TRACK_KEEPOUT, *self.coord((i,j))):return False
        if layer == IN2:
            # Protect actual L3 GND plus 0.25 mm. Through vias may cross the
            # plane with antipads; F/B switching is distinct from routing L3.
            if contains(L3_TRACK_KEEPOUT, *self.coord((i,j))):return False
        return True

    def _disc_span(self, x, y, r):
        """Inclusive cell index ranges covering a disc, clamped to the grid."""
        c0 = self.cell(x - r, y - r)
        c1 = self.cell(x + r, y + r)
        return (range(max(0, c0[0]), min(self.config.nx, c1[0] + 1)),
                range(max(0, c0[1]), min(self.config.ny, c1[1] + 1)))

    def _paint_disc(self, target, x, y, r, value):
        """target[i][j] = value for every cell centre within r of (x, y)."""
        coord = self.coord
        r2 = r * r
        cols, rows = self._disc_span(x, y, r)
        for i in cols:
            column = target[i]
            for j in rows:
                px, py = coord((i, j))
                if (px - x) ** 2 + (py - y) ** 2 <= r2:
                    column[j] = value

    def soft_disc(self, layer, x, y, r, netname):
        cols, rows = self._disc_span(x, y, r)
        for i in cols:
            for j in rows:
                px, py = self.coord((i, j))
                if (px - x) ** 2 + (py - y) ** 2 <= r * r:
                    self.soft[(layer, i, j)] = netname

    def soft_seg(self, layer, x1, y1, x2, y2, r, netname):
        length = math.dist((x1, y1), (x2, y2))
        n = max(1, int(length / (self.config.step / 2)))
        for k in range(n + 1):
            t = k / n
            self.soft_disc(layer, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t,
                           r, netname)

    def block_via_disc(self, x, y, r):
        self._paint_disc(self.via_bad, x, y, r, 1)

    def block_disc(self, layer, x, y, r):
        self._paint_disc(self.blocked[layer], x, y, r, 1)

    def carve_disc(self, layer, x, y, r):
        self._paint_disc(self.blocked[layer], x, y, r, 0)

    def block_seg(self, layer, x1, y1, x2, y2, r):
        length = math.dist((x1, y1), (x2, y2))
        n = max(1, int(length / (self.config.step / 2)))
        for k in range(n + 1):
            t = k / n
            self.block_disc(layer, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r)

    def block_rect(self, layer, cx, cy, hw, hh, r):
        c0 = self.cell(cx - hw - r, cy - hh - r)
        c1 = self.cell(cx + hw + r, cy + hh + r)
        nx, ny = self.config.nx, self.config.ny
        for i in range(max(0, c0[0]), min(nx, c1[0] + 1)):
            for j in range(max(0, c0[1]), min(ny, c1[1] + 1)):
                px, py = self.coord((i, j))
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
        lo = self.cell(pc.to_mm(bbox.GetLeft()) - margin, pc.to_mm(bbox.GetTop()) - margin)
        hi = self.cell(pc.to_mm(bbox.GetRight()) + margin, pc.to_mm(bbox.GetBottom()) + margin)
        clearance = mm(margin)
        nx, ny = self.config.nx, self.config.ny
        for i in range(max(0, lo[0]), min(nx, hi[0] + 1)):
            for j in range(max(0, lo[1]), min(ny, hi[1] + 1)):
                if pcbnew.SHAPE.Collide(shape, pt(*self.coord((i, j))), clearance):
                    self.blocked[layer][i][j] = 1

    def is_free(self, layer, c):
        return not self.blocked[layer][c[0]][c[1]]

    def via_ok(self, c):
        """Via needs room on both layers plus hole spacing.

        blocked[] is already inflated by track-half + clearance, so we only
        need extra neighbourhood for the via being fatter than a track.
        """
        cfg = self.config
        if not cfg.in_bounds(c[0], c[1]):
            return False
        if self.via_bad[c[0]][c[1]]:
            return False
        extra = max(1, int(math.ceil((cfg.via_d - cfg.track_w) / 2.0 / cfg.step)))
        r2 = ((cfg.via_d - cfg.track_w) / 2.0 / cfg.step) ** 2
        for layer in cfg.layers:
            for di in range(-extra, extra + 1):
                for dj in range(-extra, extra + 1):
                    if di * di + dj * dj > r2:
                        continue
                    i, j = c[0] + di, c[1] + dj
                    if not cfg.in_bounds(i, j):
                        return False
                    if self.blocked[layer][i][j]:
                        return False
        return True


def via_dia(t):
    """KiCad 10: PCB_VIA.GetWidth() requires a layer and spams asserts."""
    return pc.to_mm(t.GetFrontWidth())


def track_w(t):
    if t.GetClass() == "PCB_VIA":
        return via_dia(t)
    return pc.to_mm(t.GetWidth())


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


def build_grid(board, config, skip_nets, soft_signals=False):
    """soft_signals: other signal nets' tracks become rip-able soft cost."""
    g = Grid(config)
    step, track_half, clr = config.step, config.track_w / 2, config.clearance
    layers = config.layers
    # coarse grids need the half-cell fudge; fine grids can run exact
    fudge = step * 0.51 if step > 0.08 else 0.0
    margin = track_half + clr + fudge
    # board edge
    for i in range(config.nx):
        for j in range(config.ny):
            px, py = config.coord((i, j))
            if px < X0 + 0.55 or px > X1 - 0.55 or py < Y0 + 0.55 or py > Y1 - 0.55:
                for layer in layers:
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
                for layer in layers:g.soft_disc(layer, x, y, r, net)
            else:
                for layer in layers:g.block_disc(layer, x, y, r)
                g.block_via_disc(x, y, 0.62)
        else:
            layer = config.layer_index(t.GetLayer())
            if layer is None:
                continue
            r = pc.to_mm(t.GetWidth()) / 2 + margin
            x1, y1 = pc.to_mm(t.GetStart().x), pc.to_mm(t.GetStart().y)
            x2, y2 = pc.to_mm(t.GetEnd().x), pc.to_mm(t.GetEnd().y)
            if rippable:
                g.soft_seg(layer, x1, y1, x2, y2, r, net)
            else:
                g.block_seg(layer, x1, y1, x2, y2, r)
    via_drill = config.via_drill
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            pos = pad.GetPosition()
            x, y = pc.to_mm(pos.x), pc.to_mm(pos.y)
            hw, hh = _pad_hw_hh(pad)
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                pad_layers = [F] if fp.GetLayer() == pcbnew.F_Cu else [B]
                if pad.GetLayerSet().Contains(pcbnew.B_Cu) \
                        and pad.GetLayerSet().Contains(pcbnew.F_Cu):
                    pad_layers = [F, B]
                elif pad.GetLayerSet().Contains(pcbnew.B_Cu):
                    pad_layers = [B]
                elif pad.GetLayerSet().Contains(pcbnew.F_Cu):
                    pad_layers = [F]
                # keep via holes away from all SMD pads (hole clearance)
                c0=config.cell(x-hw-via_drill/2-.075,y-hh-via_drill/2-.075)
                c1=config.cell(x+hw+via_drill/2+.075,y+hh+via_drill/2+.075)
                for i in range(max(0,c0[0]),min(config.nx,c1[0]+1)):
                    for j in range(max(0,c0[1]),min(config.ny,c1[1]+1)):
                        px,py=config.coord((i,j))
                        dx=max(abs(px-x)-hw,0);dy=max(abs(py-y)-hh,0)
                        if dx*dx+dy*dy<(via_drill/2+.075)**2:g.via_bad[i][j]=1
            else:
                pad_layers = list(layers)
                g.block_via_disc(x, y, 0.9)
            if net in skip_nets:
                continue
            for layer in pad_layers:
                pad_margin=max(margin,track_half+.255+fudge) if pad.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH else margin
                g.block_shape(layer, pad.GetEffectiveShape(LAYER_ID[layer]), pad_margin)
    # Rule areas (keepouts): A* otherwise ignores them and re-enters.
    for z in board.Zones():
        if not z.GetIsRuleArea():
            continue
        ban_trk = z.GetDoNotAllowTracks()
        ban_via = z.GetDoNotAllowVias()
        if not (ban_trk or ban_via):
            continue
        zone_layers = []
        if z.IsOnLayer(pcbnew.F_Cu):
            zone_layers.append(F)
        if z.IsOnLayer(pcbnew.B_Cu):
            zone_layers.append(B)
        if not zone_layers:
            continue
        try:
            bb = z.GetBoundingBox()
            x0 = pc.to_mm(bb.GetLeft())
            y0 = pc.to_mm(bb.GetTop())
            x1 = pc.to_mm(bb.GetRight())
            y1 = pc.to_mm(bb.GetBottom())
        except Exception:
            continue
        pad_r = track_half + clr
        if ban_trk:
            for layer in zone_layers:
                g.block_rect(layer, (x0 + x1) / 2, (y0 + y1) / 2,
                             (x1 - x0) / 2, (y1 - y0) / 2, pad_r)
        if ban_via:
            c0 = config.cell(x0 - 0.3, y0 - 0.3)
            c1 = config.cell(x1 + 0.3, y1 + 0.3)
            for i in range(max(0, c0[0]), min(config.nx, c1[0] + 1)):
                for j in range(max(0, c0[1]), min(config.ny, c1[1] + 1)):
                    px, py = config.coord((i, j))
                    if x0 - 0.15 <= px <= x1 + 0.15 and y0 - 0.15 <= py <= y1 + 0.15:
                        g.via_bad[i][j] = 1
    return g


def astar(g, starts, goals):
    """starts/goals: set of (layer, cx, cy). Returns node path or None."""
    cfg = g.config
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
            if not cfg.in_bounds(ni, nj):
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
            for other_layer in cfg.layers:
                if other_layer == layer:continue
                if not g.track_allowed(other_layer,ci,cj):continue
                nn = (other_layer, ci, cj)
                ng = base + 12
                if nn not in gx or ng < gx[nn] - 1e-9:
                    gx[nn] = ng
                    heapq.heappush(openq, (ng + h(nn), nn, node))
    return None


def path_to_geometry(config, path):
    """Collapse a node path into polyline segments per layer + via points."""
    coord = config.coord
    out_segs = []   # (layer, [pts])
    vias = []
    cur_layer = path[0][0]
    pts = [coord((path[0][1], path[0][2]))]
    for node in path[1:]:
        if node[0] != cur_layer:
            vias.append(coord((node[1], node[2])))
            out_segs.append((cur_layer, pts))
            cur_layer = node[0]
            pts = [coord((node[1], node[2]))]
        else:
            pts.append(coord((node[1], node[2])))
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


def add_route(board, config, netname, segs, vias):
    net = board.GetNetsByName()[netname]
    for layer, ps in segs:
        pc.add_track(board, net, LAYER_ID[layer], ps, config.track_w)
    for xy in vias:
        pc.add_via(board, net, xy, config.via_d, config.via_drill)


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


def pad_cells(board, config, netname):
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
            c = config.cell(ex, ey)
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                layer = B if pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu) else F
                pad_layers = [layer]
            else:
                pad_layers = [F, B]
            for l in pad_layers:
                seeds.append(((l, c[0], c[1]), (ex, ey), (x, y)))
    return seeds


def carve_seeds(grid, seeds):
    """Unblock a capsule from pad centre to the escape tip (not a big disc)."""
    step = grid.config.step
    for (layer, ci, cj), esc, pad in seeds:
        x1, y1 = pad
        x2, y2 = esc
        length = math.dist((x1, y1), (x2, y2))
        n = max(1, int(length / max(step / 2, 0.03)))
        for k in range(n + 1):
            t = k / n
            grid.carve_disc(layer, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, 0.20)


def seed_nodes(grid, node):
    """A small cloud of free cells around a seed so A* can leave the pad."""
    layer, ci, cj = node
    out = set()
    for di in range(-2, 3):
        for dj in range(-2, 3):
            i, j = ci + di, cj + dj
            if grid.config.in_bounds(i, j) and not grid.blocked[layer][i][j]:
                out.add((layer, i, j))
    if not out:
        out.add(node)
    return out


def net_copper_nodes(board, config, netname):
    """Existing same-net tracks/vias as graph nodes (they are live copper)."""
    nodes = set()
    for t in all_tracks(board):
        if t.GetNetname() != netname:
            continue
        if t.GetClass() == "PCB_VIA":
            x, y = pc.to_mm(t.GetPosition().x), pc.to_mm(t.GetPosition().y)
            c = config.cell(x, y)
            nodes.add((F, c[0], c[1]))
            nodes.add((B, c[0], c[1]))
        elif t.GetLayerName() in ("F.Cu", "B.Cu"):
            layer = F if t.GetLayerName() == "F.Cu" else B
            for p in (t.GetStart(), t.GetEnd()):
                c = config.cell(pc.to_mm(p.x), pc.to_mm(p.y))
                nodes.add((layer, c[0], c[1]))
    return nodes


def rip_net(board, netname, tracks=None):
    doomed = [t for t in (tracks if tracks is not None else all_tracks(board))
              if t.GetNetname() == netname]
    for t in doomed:
        board.Remove(t)


def route_net(board, grid, netname):
    """Connect all pads of a net from scratch on a prepared grid."""
    config = grid.config
    seeds = pad_cells(board, config, netname)
    if len(seeds) < 2:
        print(f"{netname}: less than 2 pads?", flush=True)
        return True
    copper = net_copper_nodes(board, config, netname)

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
        segs, vias = path_to_geometry(config, path)
        head = path[0]
        tail = path[-1]
        # pad → escape → first grid cell (one polyline, no orphan stub)
        head_pts = [start[2]]
        if start[1] != start[2]:
            head_pts.append(start[1])
        head_pts.append(config.coord((head[1], head[2])))
        segs = [(head[0], head_pts)] + segs
        # Only stub to the first pad when the path actually ended next to it.
        # A long F.Cu jump from a distant via to pad0 used to slash through U1.
        tail_xy = config.coord((tail[1], tail[2]))
        if math.dist(tail_xy, first[2]) < 2.5:
            tail_pts = [tail_xy]
            if first[1] != first[2]:
                tail_pts.append(first[1])
            tail_pts.append(first[2])
            segs.append((tail[0], tail_pts))
        add_route(board, config, netname, segs, vias)
        for node in path:
            done_nodes.add(node)
    return ok_all
