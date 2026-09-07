#!/usr/bin/env python3
"""Manual grid-router CLI on top of grid_router (the pipeline uses finish_routes).

  astar_router.py NET [NET ...]        rip the nets, route each pad-to-pad on a
                                       coarse-to-fine ladder, save the board
  astar_router.py --probe [--soft] NET reachability report only, no board writes
  astar_router.py --dump NET x0 y0 x1 y1
                                       blocked/via maps as PNG (needs Pillow)

Board selection follows pcb_common (AILINK_HW / AILINK_PCB). Not part of
run_pipeline.sh; keep it for diagnosing why a net cannot be completed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
import grid_router as gr
from grid_router import F, B, RouterConfig

import pcbnew

LADDER = ((0.25, 0.16), (0.125, 0.16), (0.125, 0.13))   # (step, clearance)


def block_fresh_copper(board, grid, netname):
    """Block a just-routed net's copper so the remaining nets avoid it."""
    cfg = grid.config
    for t in gr.all_tracks(board):
        if t.GetNetname() != netname:
            continue
        if t.GetClass() == "PCB_VIA":
            x = pc.to_mm(t.GetPosition().x)
            y = pc.to_mm(t.GetPosition().y)
            r = cfg.via_d / 2 + cfg.track_w / 2 + cfg.clearance
            grid.block_disc(F, x, y, r)
            grid.block_disc(B, x, y, r)
        elif t.GetLayerName() in ("F.Cu", "B.Cu"):
            layer = F if t.GetLayerName() == "F.Cu" else B
            grid.block_seg(
                layer,
                pc.to_mm(t.GetStart().x), pc.to_mm(t.GetStart().y),
                pc.to_mm(t.GetEnd().x), pc.to_mm(t.GetEnd().y),
                gr.track_w(t) / 2 + cfg.track_w / 2 + cfg.clearance)


def main(netnames):
    board = pcbnew.LoadBoard(pc.PCB)
    for n in netnames:
        gr.rip_net(board, n)
    pending = list(netnames)
    for step, clr in LADDER:
        if not pending:
            break
        cfg = RouterConfig(step=step, clearance=clr)
        grid = gr.build_grid(board, cfg, skip_nets=set(pending))
        nxt = []
        for netname in pending:
            ok = gr.route_net(board, grid, netname)
            print(f"[step={step} clr={clr}] {netname}: "
                  f"{'OK' if ok else 'FAILED'}")
            if not ok:
                gr.rip_net(board, netname)
                nxt.append(netname)
            else:
                block_fresh_copper(board, grid, netname)
        pending = nxt
    if pending:
        print("STILL UNROUTED:", pending)
    pcbnew.SaveBoard(pc.PCB, board)
    print("saved")


def probe_net(netname, soft=False):
    """BFS reachability report (no board writes)."""
    from collections import deque
    board = pcbnew.LoadBoard(pc.PCB)
    cfg = RouterConfig(step=0.1, clearance=0.155, track_w=0.15)
    grid = gr.build_grid(board, cfg, skip_nets={netname}, soft_signals=soft)
    seeds = gr.pad_cells(board, cfg, netname)
    gr.carve_seeds(grid, seeds)
    starts = gr.seed_nodes(grid, seeds[0][0])
    goals = set()
    for s in seeds[1:]:
        goals |= gr.seed_nodes(grid, s[0])
    print(f"probe {netname} soft={soft} start={seeds[0][1]} "
          f"escapes={[s[1] for s in seeds]} starts={len(starts)} "
          f"goals={len(goals)}", flush=True)
    q = deque(starts)
    seen = set(starts)
    while q:
        layer, ci, cj = q.popleft()
        if (layer, ci, cj) in goals:
            print(f"  HIT at {cfg.coord((ci, cj))} layer{layer} "
                  f"seen={len(seen)}", flush=True)
            return 0
        for di, dj, _ in gr.DIRS:
            ni, nj = ci + di, cj + dj
            if not cfg.in_bounds(ni, nj):
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


def dump_maps(netname, bx0, by0, bx1, by1, out_dir):
    """Write blocked (red) and via-forbidden (orange) maps as PNG per layer."""
    from PIL import Image
    cfg = RouterConfig(step=0.06, clearance=0.152, track_w=0.15)
    board = pcbnew.LoadBoard(pc.PCB)
    grid = gr.build_grid(board, cfg, skip_nets={netname})
    c0 = cfg.cell(bx0, by0); c1 = cfg.cell(bx1, by1)
    w_ = c1[0] - c0[0] + 1
    h_ = c1[1] - c0[1] + 1
    paths = []
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
        path = os.path.join(out_dir, f"grid_{lname}.png")
        im.save(path)
        paths.append(path)
    print("dumped", *paths)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    if args[0] == "--probe":
        soft = "--soft" in args
        nets = [a for a in args[1:] if a != "--soft"]
        rc = 0
        for n in nets:
            rc |= probe_net(n, soft=soft)
        sys.exit(rc)
    if args[0] == "--dump":
        dump_maps(args[1], *map(float, args[2:6]), out_dir=pc.HW)
    else:
        main(args)
