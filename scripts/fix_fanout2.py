#!/usr/bin/env python3
"""Remove the misplaced/orphaned fanouts and add correct ones for the
relocated R7/R8/C14 (vertical pads: pad1 bottom, pad2 top)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

DEL_SEGS = [
    ((120.21, 126.8), (119.3, 126.2)),
    ((120.21, 128.6), (119.3, 129.0)),
    ((120.2, 124.11), (118.85, 124.11)),
    ((120.2, 125.69), (121.5, 125.69)),
    ((121.5, 125.69), (121.5, 124.6)),
    ((122.0, 125.625), (122.0, 124.225)),
    ((122.0, 127.175), (122.0, 128.575)),
    ((135.3, 126.325), (135.3, 127.725)),
    ((137.1, 126.325), (137.1, 127.725)),
]
DEL_VIAS = [
    (119.3, 126.2), (119.3, 129.0), (118.85, 124.11), (121.5, 124.6),
    (122.0, 124.225), (122.0, 128.575), (135.3, 127.725), (137.1, 127.725),
]
NEW = [
    ("+3V3", [(121.0, 127.625), (119.9, 128.4)], (119.9, 128.4)),   # R7-1
    ("+3V3", [(121.0, 129.425), (120.0, 130.0)], (120.0, 130.0)),   # R8-1
    ("+3V3", [(120.2, 125.675), (118.85, 125.675)], (118.85, 125.675)),  # C14-1
    ("GND",  [(120.2, 124.125), (121.5, 124.125)], (121.5, 124.125)),    # C14-2
]


def near(p, q, tol=0.05):
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    doomed = []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = (pc.to_mm(t.GetPosition().x), pc.to_mm(t.GetPosition().y))
            if any(near(p, v) for v in DEL_VIAS):
                doomed.append(t)
        else:
            s = (pc.to_mm(t.GetStart().x), pc.to_mm(t.GetStart().y))
            e = (pc.to_mm(t.GetEnd().x), pc.to_mm(t.GetEnd().y))
            for a, b in DEL_SEGS:
                if (near(s, a) and near(e, b)) or (near(s, b) and near(e, a)):
                    doomed.append(t)
                    break
    seen = set()
    uniq = [t for t in doomed if id(t) not in seen and not seen.add(id(t))]
    for t in uniq:
        board.Remove(t)
    print(f"removed {len(uniq)} bad items")

    for netname, pts, via in NEW:
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
    print("correct fanouts added")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("saved")


if __name__ == "__main__":
    main()
