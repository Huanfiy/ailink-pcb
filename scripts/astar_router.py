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
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

STEP = 0.25
X0, Y0, X1, Y1 = 100.0, 100.0, 165.0, 135.0
NX = int((X1 - X0) / STEP) + 1
NY = int((Y1 - Y0) / STEP) + 1
TRACK_W = 0.2
CLR = 0.16
VIA_D, VIA_DRILL = 0.6, 0.3


def set_step(step, clr):
    global STEP, NX, NY, CLR
    STEP = step
    CLR = clr
    NX = int((X1 - X0) / STEP) + 1
    NY = int((Y1 - Y0) / STEP) + 1

F, B = 0, 1
LAYER_ID = {F: pcbnew.F_Cu, B: pcbnew.B_Cu}


def cell(x, y):
    return (int(round((x - X0) / STEP)), int(round((y - Y0) / STEP)))


def coord(c):
    return (round(X0 + c[0] * STEP, 3), round(Y0 + c[1] * STEP, 3))


class Grid:
    def __init__(self):
        self.blocked = [[bytearray(NY) for _ in range(NX)],
                        [bytearray(NY) for _ in range(NX)]]
        self.via_bad = [bytearray(NY) for _ in range(NX)]
        self.soft = {}          # (layer, i, j) -> netname (rippable copper)

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

    def is_free(self, layer, c):
        return not self.blocked[layer][c[0]][c[1]]

    def via_ok(self, c):
        """Via needs room on both layers plus hole spacing."""
        if self.via_bad[c[0]][c[1]]:
            return False
        ring = max(1, int(math.ceil(0.22 / STEP)))
        for layer in (F, B):
            for di in range(-ring, ring + 1):
                for dj in range(-ring, ring + 1):
                    i, j = c[0] + di, c[1] + dj
                    if not (0 <= i < NX and 0 <= j < NY):
                        return False
                    if self.blocked[layer][i][j]:
                        return False
        return True


HARD_NETS = ("GND", "+3V3", "USB_DP", "USB_DM")


def build_grid(board, skip_nets, soft_signals=False):
    """soft_signals: other signal nets' tracks become rip-able soft cost."""
    g = Grid()
    # coarse grids need the half-cell fudge; fine grids can run exact
    fudge = STEP * 0.51 if STEP > 0.08 else 0.02
    margin = TRACK_W / 2 + CLR + fudge
    # board edge
    for i in range(NX):
        for j in range(NY):
            px, py = coord((i, j))
            if px < X0 + 0.55 or px > X1 - 0.55 or py < Y0 + 0.55 or py > Y1 - 0.55:
                g.blocked[F][i][j] = 1
                g.blocked[B][i][j] = 1
    for t in board.GetTracks():
        net = t.GetNetname()
        if net in skip_nets:
            continue
        rippable = (soft_signals and net not in HARD_NETS
                    and not net.startswith("unconnected"))
        if t.GetClass() == "PCB_VIA":
            x, y = pc.to_mm(t.GetPosition().x), pc.to_mm(t.GetPosition().y)
            r = pc.to_mm(t.GetWidth()) / 2 + margin
            if rippable:
                g.soft_disc(F, x, y, r, net)
                g.soft_disc(B, x, y, r, net)
            else:
                g.block_disc(F, x, y, r)
                g.block_disc(B, x, y, r)
                g.block_via_disc(x, y, 0.62)
        else:
            lay = t.GetLayerName()
            if lay not in ("F.Cu", "B.Cu"):
                continue
            layer = F if lay == "F.Cu" else B
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
                g.block_via_disc(x, y, max(hw, hh) + 0.42)
            else:
                layers = [F, B]
                g.block_via_disc(x, y, 0.9)
            if net in skip_nets:
                continue
            for layer in layers:
                g.block_rect(layer, x, y, hw, hh, margin)
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
    soft_cost = 9.0
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
            if g.blocked[layer][ni][nj]:
                continue
            nn = (layer, ni, nj)
            ng = base + w + (soft_cost if (layer, ni, nj) in soft else 0)
            if nn not in gx or ng < gx[nn] - 1e-9:
                gx[nn] = ng
                heapq.heappush(openq, (ng + h(nn), nn, node))
        # via
        if g.via_ok((ci, cj)):
            nn = (1 - layer, ci, cj)
            ng = base + 14
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
            if (bx - ax) * (cy2 - by) - (by - ay) * (cx2 - bx) != 0:
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


def pad_cells(board, netname):
    """All pads of net -> list of (layer,ci,cj) node seeds + stub info."""
    seeds = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != netname:
                continue
            pos = pad.GetPosition()
            x, y = pc.to_mm(pos.x), pc.to_mm(pos.y)
            c = cell(x, y)
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                layer = F if fp.GetLayer() == pcbnew.F_Cu else B
                layers = [layer]
            else:
                layers = [F, B]
            for l in layers:
                seeds.append(((l, c[0], c[1]), (x, y)))
    return seeds


def carve_seeds(grid, seeds):
    """Free a small disc around each seed so the start cell is reachable."""
    for (layer, ci, cj), (x, y) in seeds:
        c0 = cell(x - 0.28, y - 0.28)
        c1 = cell(x + 0.28, y + 0.28)
        for i in range(max(0, c0[0]), min(NX, c1[0] + 1)):
            for j in range(max(0, c0[1]), min(NY, c1[1] + 1)):
                grid.blocked[layer][i][j] = 0


def net_copper_nodes(board, netname):
    """Existing same-net tracks/vias as graph nodes (they are live copper)."""
    nodes = set()
    for t in board.GetTracks():
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
        print(f"{netname}: less than 2 pads?")
        return True
    # pads that already have copper attached go first (their stubs/vias
    # become part of the target cluster instead of needing a fresh leg)
    copper = net_copper_nodes(board, netname)

    def has_copper(seed):
        (l, ci, cj), _ = seed
        return any(abs(n[1] - ci) <= 2 and abs(n[2] - cj) <= 2 and n[0] == l
                   for n in copper)
    seeds.sort(key=lambda s: 0 if has_copper(s) else 1)
    carve_seeds(grid, seeds)
    done_nodes = set(copper)
    stubs = {}
    first = seeds[0]
    done_nodes.add(first[0])
    stubs[first[0]] = first[1]
    ok_all = True
    for k in range(1, len(seeds)):
        start = seeds[k]
        path = astar(grid, {start[0]}, done_nodes)
        if path is None:
            print(f"    leg FAILED: from {start[1]} (layer{start[0][0]})")
            ok_all = False
            continue
        segs, vias = path_to_geometry(path)
        head = path[0]
        tail = path[-1]
        segs = [(head[0], [start[1], coord((head[1], head[2]))])] + segs
        if tail in stubs:
            segs.append((tail[0], [coord((tail[1], tail[2])), stubs[tail]]))
        add_route(board, netname, segs, vias)
        for node in path:
            done_nodes.add(node)
    return ok_all


def rip_net(board, netname):
    doomed = [t for t in board.GetTracks() if t.GetNetname() == netname]
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
                for t in board.GetTracks():
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
                            pc.to_mm(t.GetWidth()) / 2 + TRACK_W / 2 + CLR)
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
    return min(_seg_pt_dist(a1, a2, b1), _seg_pt_dist(a1, a2, b2),
               _seg_pt_dist(b1, b2, a1), _seg_pt_dist(b1, b2, a2))


def _net_items_geo(board, netname):
    out = []
    for t in board.GetTracks():
        if t.GetNetname() != netname:
            continue
        if t.GetClass() == "PCB_VIA":
            p = (pc.to_mm(t.GetPosition().x), pc.to_mm(t.GetPosition().y))
            out.append(("via", p, p, pc.to_mm(t.GetWidth()) / 2))
        elif t.GetLayerName() in ("F.Cu", "B.Cu"):
            s = (pc.to_mm(t.GetStart().x), pc.to_mm(t.GetStart().y))
            e = (pc.to_mm(t.GetEnd().x), pc.to_mm(t.GetEnd().y))
            out.append((t.GetLayerName(), s, e, pc.to_mm(t.GetWidth()) / 2))
    return out


def ripup_route(netnames):
    pending = list(netnames)
    attempts = {}
    for it in range(40):
        if not pending:
            break
        # fresh board object per iteration: avoids SWIG proxy decay
        board = pcbnew.LoadBoard(pc.PCB)
        all_signals = set()
        for nc in range(board.GetNetCount()):
            net = board.FindNet(nc)
            if net is None:
                continue
            nm = net.GetNetname()
            if nm and nm not in HARD_NETS \
                    and not nm.startswith("unconnected"):
                all_signals.add(nm)
        n = pending.pop(0)
        attempts[n] = attempts.get(n, 0) + 1
        if attempts[n] > 4:
            print(f"[ripup] giving up {n}")
            continue
        rip_net(board, n)
        routed = False
        for step, clr, soft in ((0.1, 0.155, False), (0.1, 0.155, True),
                                (0.075, 0.152, True)):
            set_step(step, clr)
            grid = build_grid(board, skip_nets={n}, soft_signals=soft)
            ok = route_net(board, grid, n)
            if ok:
                routed = True
                break
            rip_net(board, n)
        if not routed:
            print(f"[ripup] {n}: NO PATH even soft")
            pcbnew.SaveBoard(pc.PCB, board)
            continue
        mine = _net_items_geo(board, n)
        victims = set()
        for other in all_signals:
            if other == n:
                continue
            for o in _net_items_geo(board, other):
                if other in victims:
                    break
                for m in mine:
                    lay_o, s1, e1, r1 = o
                    lay_m, s2, e2, r2 = m
                    if lay_o != lay_m and "via" not in (lay_o, lay_m):
                        continue
                    if _seg_seg_dist(s1, e1, s2, e2) < r1 + r2 + 0.15:
                        victims.add(other)
                        break
        for v in victims:
            rip_net(board, v)
            if v not in pending:
                pending.append(v)
        pcbnew.SaveBoard(pc.PCB, board)
        print(f"[ripup] {n}: OK"
              + (f", ripped {sorted(victims)}" if victims else ""))
    if pending:
        print("[ripup] LEFT UNROUTED:", pending)
    else:
        print("[ripup] ALL ROUTED")


def route_only(netname, width=None):
    global TRACK_W
    if width:
        TRACK_W = width
    board = pcbnew.LoadBoard(pc.PCB)
    ladder = [(0.25, 0.16), (0.125, 0.16), (0.1, 0.155),
              (0.075, 0.155), (0.06, 0.152)]
    for step, clr in ladder:
        set_step(step, clr)
        grid = build_grid(board, skip_nets={netname})
        ok = route_net(board, grid, netname)
        print(f"[step={step} clr={clr}] {netname}: {'OK' if ok else 'FAILED'}")
        if ok:
            pcbnew.SaveBoard(pc.PCB, board)
            return 0
        rip_net(board, netname)
    pcbnew.SaveBoard(pc.PCB, board)
    return 1


if __name__ == "__main__":
    if sys.argv[1] == "--rip":
        rip_only(sys.argv[2])
    elif sys.argv[1] == "--ripup":
        ripup_route(sys.argv[2:])
    elif sys.argv[1] == "--route":
        w = float(sys.argv[3]) if len(sys.argv) > 3 else None
        sys.exit(route_only(sys.argv[2], width=w))
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
