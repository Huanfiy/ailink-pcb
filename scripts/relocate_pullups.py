#!/usr/bin/env python3
"""Structural fix for the flash pocket: move R7/R8 pull-ups + C14 to the
left side of U2, next to the pins they serve; refresh their power fanouts."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

MOVES = {
    "R7":  (121.0, 126.8, 90),
    "R8":  (121.0, 128.6, 90),
    "C14": (120.2, 124.9, 90),
}
# old pad positions whose attached stubs/vias must go
OLD_PAD_POS = [
    (135.3, 124.71), (135.3, 126.29),      # R7 pads
    (137.1, 124.71), (137.1, 126.29),      # R8 pads
    (122.0, 125.61), (122.0, 127.19),      # C14 pads
]
# new fanouts: (net, stub pts, via pos)
NEW_FANOUT = [
    ("+3V3", [(120.21, 126.8), (119.3, 126.2)], (119.3, 126.2)),   # R7-1
    ("+3V3", [(120.21, 128.6), (119.3, 129.0)], (119.3, 129.0)),   # R8-1
    ("+3V3", [(120.2, 124.11), (118.85, 124.11)], (118.85, 124.11)),  # C14-1
    ("GND",  [(120.2, 125.69), (121.5, 125.69), (121.5, 124.6)],
     (121.5, 124.6)),                                              # C14-2
]


def near(p, q, tol=0.01):
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def main():
    board = pcbnew.LoadBoard(pc.PCB)

    # 1. collect stubs attached to old pad positions, plus their vias
    doomed = []
    via_at = []
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK":
            continue
        s = (pc.to_mm(t.GetStart().x), pc.to_mm(t.GetStart().y))
        e = (pc.to_mm(t.GetEnd().x), pc.to_mm(t.GetEnd().y))
        for op in OLD_PAD_POS:
            if near(s, op) or near(e, op):
                doomed.append(t)
                other = e if near(s, op) else s
                via_at.append(other)
                break
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = (pc.to_mm(t.GetPosition().x), pc.to_mm(t.GetPosition().y))
            for vp in via_at:
                if near(p, vp):
                    doomed.append(t)
                    break
    seen = set()
    uniq = [t for t in doomed if id(t) not in seen and not seen.add(id(t))]
    for t in uniq:
        board.Remove(t)
    print(f"removed {len(uniq)} old stubs/vias")

    # 2. move the parts
    for ref, (x, y, rot) in MOVES.items():
        for fp in board.GetFootprints():
            if fp.GetReference() == ref:
                fp.SetPosition(pt(x, y))
                fp.SetOrientationDegrees(rot)
                print(f"{ref} -> ({x},{y}) rot{rot}")

    # 3. fresh fanouts
    for netname, pts, via in NEW_FANOUT:
        net = board.GetNetsByName()[netname]
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pt(*a)); t.SetEnd(pt(*b))
            t.SetWidth(mm(0.3)); t.SetLayer(pcbnew.F_Cu)
            t.SetNet(net)
            board.Add(t)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(*via))
        v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(net)
        board.Add(v)
    print("new fanouts added")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("saved")


if __name__ == "__main__":
    main()
