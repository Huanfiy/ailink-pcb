#!/usr/bin/env python3
"""Manual fanout for the LQFP64 VSS/VDD pad pairs (0.5mm pitch)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew


def add_seg(board, net, a, b, width=0.3):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(*a)); t.SetEnd(pt(*b))
    t.SetWidth(mm(width)); t.SetLayer(pcbnew.F_Cu)
    t.SetNet(net)
    board.Add(t)


def add_via(board, net, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    board.Add(v)


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    gnd = board.GetNetsByName()["GND"]
    v33 = board.GetNetsByName()["+3V3"]

    # bottom row pairs: 18/19 and 31/32  (y+ = outward)
    for vss_x, vdd_x in ((125.25, 125.75), (131.75, 132.25)):
        y = 123.675
        add_seg(board, gnd, (vss_x, y), (vss_x, 125.4))
        add_via(board, gnd, vss_x, 125.4)
        add_seg(board, v33, (vdd_x, y), (vdd_x, 124.9))
        add_seg(board, v33, (vdd_x, 124.9), (vdd_x + 0.6, 125.5))
        add_via(board, v33, vdd_x + 0.6, 125.5)

    # right column pair: 47 (GND, y=114.75) / 48 (+3V3, y=114.25)
    x = 134.175
    add_seg(board, gnd, (x, 114.75), (135.9, 114.75))
    add_via(board, gnd, 135.9, 114.75)
    add_seg(board, v33, (x, 114.25), (135.1, 114.25))
    add_seg(board, v33, (135.1, 114.25), (135.9, 113.45))
    add_via(board, v33, 135.9, 113.45)

    # top row pair: 63 (GND, x=125.25) / 64 (+3V3, x=124.75), fan into the
    # empty interior area under the chip body
    add_seg(board, gnd, (125.25, 112.325), (125.25, 114.6))
    add_seg(board, gnd, (125.25, 114.6), (126.1, 114.6))
    add_via(board, gnd, 126.1, 114.6)
    add_seg(board, v33, (124.75, 112.325), (124.75, 114.85))
    add_seg(board, v33, (124.75, 114.85), (124.3, 115.3))
    add_via(board, v33, 124.3, 115.3)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("MCU power fanout added")


if __name__ == "__main__":
    main()
