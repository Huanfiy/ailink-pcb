#!/usr/bin/env python3
"""Comprehensive fix for the flash pull-up cluster and C4 via:
- delete the misplaced fanouts from the previous attempt
- re-place R7/R8/C14 horizontally with sane pitch
- re-place the C4 fanout via clear of TGPIO5
- add fresh fanouts using RUNTIME pad positions
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

DEL_VIAS = [(119.9, 128.4), (120.0, 130.0), (118.85, 125.675),
            (121.5, 124.125), (133.0, 123.1)]
DEL_SEG_ENDS = [(121.0, 127.625), (121.0, 129.425), (120.2, 125.675),
                (120.2, 124.125), (133.0, 121.775)]
MOVES = {
    "R7":  (121.6, 126.6, 0),
    "R8":  (121.6, 128.4, 0),
    "C14": (119.8, 125.3, 0),
}


def near(p, q, tol=0.06):
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
            if any(near(s, q) or near(e, q) for q in DEL_SEG_ENDS):
                doomed.append(t)
            elif any(near(s, v) or near(e, v) for v in DEL_VIAS):
                doomed.append(t)
    seen = set()
    uniq = [t for t in doomed if id(t) not in seen and not seen.add(id(t))]
    for t in uniq:
        board.Remove(t)
    print(f"removed {len(uniq)} stale items")

    for ref, (x, y, rot) in MOVES.items():
        for fp in board.GetFootprints():
            if fp.GetReference() == ref:
                fp.SetPosition(pt(x, y))
                fp.SetOrientationDegrees(rot)

    # runtime pad positions
    def pad(ref, num):
        for fp in board.GetFootprints():
            if fp.GetReference() == ref:
                for p in fp.Pads():
                    if str(p.GetNumber()) == num:
                        q = p.GetPosition()
                        return (round(pc.to_mm(q.x), 3), round(pc.to_mm(q.y), 3))
        raise KeyError(ref + "-" + num)

    def seg(netname, a, b, layer=pcbnew.F_Cu, w=0.3):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pt(*a)); t.SetEnd(pt(*b))
        t.SetWidth(mm(w)); t.SetLayer(layer)
        t.SetNet(board.GetNetsByName()[netname])
        board.Add(t)

    def via(netname, x, y):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(x, y))
        v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(board.GetNetsByName()[netname])
        board.Add(v)

    r7_1 = pad("R7", "1"); r8_1 = pad("R8", "1")
    c14_1 = pad("C14", "1"); c14_2 = pad("C14", "2")
    print("R7-1", r7_1, "R8-1", r8_1, "C14-1", c14_1, "C14-2", c14_2)
    seg("+3V3", r7_1, (119.7, 127.3)); via("+3V3", 119.7, 127.3)
    seg("+3V3", r8_1, (119.7, 129.1)); via("+3V3", 119.7, 129.1)
    seg("+3V3", c14_1, (118.5, 125.1)); via("+3V3", 118.5, 125.1)
    seg("GND", c14_2, (121.4, 124.5)); via("GND", 121.4, 124.5)

    # C4 fanout via, clear of the TGPIO5 diagonal this time
    seg("+3V3", (133.0, 121.775), (132.6, 123.9), layer=pcbnew.B_Cu)
    via("+3V3", 132.6, 123.9)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("saved")


if __name__ == "__main__":
    main()
