#!/usr/bin/env python3
"""Silkscreen cleanup:
- hide reference designators of passives/testpoints (fab layer keeps them)
- keep refs for U/D/J/SW/F1/FB1/X1 and nudge the crowded ones
- enlarge/keep pin-label and warning texts
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

HIDE_PREFIX = ("R", "C", "TP", "H")
KEEP = {"FB1", "F1"}   # keep these even though they match prefixes

# manual nudges for kept refs: ref -> (dx, dy) mm relative to footprint pos
NUDGE = {
    "U1": (0, 0),
    "U2": (0, 2.6),
    "U3": (0, -2.2),
    "D1": (0, 2.6),
    "D2": (2.8, 0),
    "D3": (2.8, 0),
    "D4": (2.8, 0),
    "D5": (2.8, 0),
    "D6": (2.8, 0),
    "D7": (0, -2.2),
    "D8": (0, -2.4),
    "D9": (0, -1.8),
    "F1": (0, -2.0),
    "FB1": (0, 1.6),
    "X1": (0, -2.4),
    "SW1": (0, -3.0),
    "SW2": (0, -3.0),
    "J1": (0, -7.5),
    "J2": (5.5, 1.8),
    "J3": (-4.6, -5.2),
    "J4": (-4.6, -7.6),
    "J5": (-6.4, 0),
    "J6": (-6.4, 0),
}


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        r = fp.Reference()
        if ref in KEEP:
            pass
        elif any(ref.startswith(p) and ref[len(p):].isdigit()
                 for p in HIDE_PREFIX):
            r.SetVisible(False)
            continue
        r.SetVisible(True)
        r.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        r.SetTextThickness(mm(0.13))
        r.SetTextAngleDegrees(0)
        if ref in NUDGE:
            dx, dy = NUDGE[ref]
            pos = fp.GetPosition()
            r.SetPosition(pcbnew.VECTOR2I(pos.x + mm(dx), pos.y + mm(dy)))
    pcbnew.SaveBoard(pc.PCB, board)
    print("silk refs cleaned")


if __name__ == "__main__":
    main()
