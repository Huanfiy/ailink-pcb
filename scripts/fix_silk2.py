#!/usr/bin/env python3
"""Final silkscreen polish on the routed board (moves texts in place)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew


def near(v, x, tol=1.2):
    return abs(v - x) <= tol


def main():
    board = pcbnew.LoadBoard(pc.PCB)

    texts = [t for t in board.GetDrawings()
             if isinstance(t, pcbnew.PCB_TEXT)]

    def find(s, x=None, y=None):
        out = []
        for t in texts:
            if t.GetText() != s:
                continue
            p = t.GetPosition()
            px, py = pc.to_mm(p.x), pc.to_mm(p.y)
            if x is not None and not near(px, x):
                continue
            if y is not None and not near(py, y):
                continue
            out.append(t)
        return out

    moved = 0

    def move(s, ox, oy, nx, ny):
        nonlocal moved
        for t in find(s, ox, oy):
            t.SetPosition(pt(nx, ny))
            moved += 1

    # big warning text: shorten + relocate, add second line at bottom
    for t in find("3V3 ONLY / NO POWER OUT"):
        t.SetText("3V3 ONLY")
        t.SetPosition(pt(152.8, 118.9))
        moved += 1
    t2 = pcbnew.PCB_TEXT(board)
    t2.SetText("NO POWER OUT")
    t2.SetPosition(pt(118.0, 134.1))
    t2.SetLayer(pcbnew.F_SilkS)
    t2.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
    t2.SetTextThickness(mm(0.13))
    board.Add(t2)

    move("USB", 103.5, 112.3, 102.4, 110.8)
    move("BOOT", 112.5, 129.2, 112.5, 134.1)
    move("RST", 120.5, 129.2, 120.5, 134.1)

    # J2 pin labels above the pads (clear of D2 below)
    for s, x in (("GND", 149.0), ("CLK", 151.54), ("DIO", 154.08),
                 ("RST", 156.62)):
        move(s, x, 105.6, x, 101.3)

    # J5 labels: below pads near the edge
    for s, x in (("TX", 144.5), ("RX", 147.04), ("GND", 149.58)):
        move(s, x, 130.8, x, 134.1)

    # J4 even-column labels between rows (off the pads)
    for s, y in (("G4", 120.54), ("G5", 123.08), ("G6", 125.62),
                 ("G7", 128.16), ("GND", 130.7)):
        move(s, 163.04, y + 1.7, 163.04, y - 1.27)
    # J4 odd-column labels a bit further out
    for s, y in (("G0", 120.54), ("G1", 123.08), ("G2", 125.62),
                 ("G3", 128.16), ("GND", 130.7)):
        move(s, 158.1, y, 157.5, y)

    # J3 labels
    for s, y in (("ATX", 110.0), ("ARX", 112.54), ("GND", 115.08)):
        move(s, 157.9, y, 157.3, y)
    move("BTX", 163.04, 108.4, 163.04, 108.73)
    move("BRX", 163.04, 114.24, 163.04, 111.27)
    move("GND", 163.04, 116.78, 163.04, 113.81)

    # J6 labels -> single back-side legend
    for s, x in (("3V3", 127.0), ("DIO", 129.54), ("CLK", 132.08),
                 ("GND", 134.62)):
        for t in find(s, x, 131.4):
            board.Remove(t)
            moved += 1
    tb = pcbnew.PCB_TEXT(board)
    tb.SetText("J6: 3V3 DIO CLK GND")
    tb.SetPosition(pt(130.8, 132.3))
    tb.SetLayer(pcbnew.B_SilkS)
    tb.SetMirrored(True)
    tb.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
    tb.SetTextThickness(mm(0.13))
    board.Add(tb)

    # reference nudges / hides
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref in ("SW1", "SW2"):
            fp.Reference().SetVisible(False)
        elif ref == "U2":
            fp.Reference().SetPosition(pt(133.6, 126.2))
        elif ref == "J2":
            fp.Reference().SetPosition(pt(146.0, 102.2))
        elif ref == "J3":
            fp.Reference().SetPosition(pt(157.5, 107.3))
        elif ref == "J4":
            fp.Reference().SetPosition(pt(158.4, 117.8))
        elif ref == "D3":
            fp.Reference().SetPosition(pt(154.5, 110.0))

    pcbnew.SaveBoard(pc.PCB, board)
    print(f"silk polish: {moved} texts adjusted")


if __name__ == "__main__":
    main()
