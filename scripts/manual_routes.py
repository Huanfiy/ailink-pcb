#!/usr/bin/env python3
"""Hand-designed routes for the nets the grid router could not finish."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

W = 0.2

ROUTES = {
    "B_RX": [
        ("F", [(134.175, 116.75), (143.2, 116.75), (147.71, 113.8)]),
    ],
    "B_TX": [
        ("F", [(134.175, 117.25), (143.8, 117.25), (147.71, 115.6)]),
    ],
    "LED1": [
        ("F", [(122.825, 117.75), (122.0, 117.75), (121.4, 118.35),
               (121.4, 118.9)]),
        ("V", (121.4, 118.9)),
        ("B", [(121.4, 118.9), (121.4, 105.4), (127.0, 105.4)]),
        ("V", (127.0, 105.4)),
        ("F", [(127.0, 105.4), (128.19, 106.5), (128.19, 107.6)]),
    ],
    "LED3": [
        ("F", [(122.825, 118.75), (122.0, 118.75), (120.2, 119.95)]),
        ("V", (120.2, 119.95)),
        ("B", [(120.2, 119.95), (120.2, 104.6), (133.4, 104.6)]),
        ("V", (133.4, 104.6)),
        ("F", [(133.4, 104.6), (134.19, 105.9), (134.19, 107.6)]),
    ],
    "CON_RX": [
        ("F", [(124.75, 123.675), (124.35, 124.075), (124.35, 125.3)]),
        ("V", (124.35, 125.3)),
        ("B", [(124.35, 125.3), (126.6, 127.8), (130.2, 130.9),
               (133.9, 132.35), (136.21, 132.8)]),
    ],
    "CON_TX": [
        ("F", [(122.825, 121.75), (123.85, 122.775), (123.85, 124.75)]),
        ("V", (123.85, 124.75)),
        ("B", [(123.85, 124.75), (126.2, 127.6), (129.8, 130.5),
               (133.5, 131.9), (135.4, 131.9), (136.21, 131.0)]),
    ],
    "LED2": [
        ("F", [(122.825, 118.25), (127.9, 118.25), (130.4, 115.75),
               (132.15, 113.95), (132.9, 113.55), (134.6, 113.55),
               (135.3, 112.85), (135.3, 112.6)]),
        ("V", (135.3, 112.6)),
        ("B", [(135.3, 112.6), (135.3, 108.6), (132.7, 106.35),
               (132.2, 106.35)]),
        ("V", (132.2, 106.35)),
        ("F", [(132.2, 106.35), (131.19, 107.35), (131.19, 107.6)]),
    ],
    "LED3": [
        ("F", [(122.825, 118.75), (124.5, 118.75), (124.5, 119.9),
               (124.0, 120.4), (124.0, 120.7)]),
        ("V", (124.0, 120.7)),
        ("B", [(124.0, 120.7), (126.8, 123.5), (129.3, 126.0),
               (131.5, 129.3), (133.8, 131.3), (140.5, 131.3),
               (142.6, 129.2), (142.6, 111.4), (140.2, 109.0),
               (135.2, 106.4), (133.7, 104.9)]),
        ("V", (133.7, 104.9)),
        ("F", [(133.7, 104.9), (134.19, 105.7), (134.19, 107.6)]),
    ],
}


def main(only=None):
    board = pcbnew.LoadBoard(pc.PCB)
    for net, items in ROUTES.items():
        if only and net not in only:
            continue
        n = board.GetNetsByName()[net]
        for kind, data in items:
            if kind == "V":
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pt(*data))
                v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(n)
                board.Add(v)
            else:
                layer = pcbnew.F_Cu if kind == "F" else pcbnew.B_Cu
                for a, b in zip(data, data[1:]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pt(*a)); t.SetEnd(pt(*b))
                    t.SetWidth(mm(W)); t.SetLayer(layer)
                    t.SetNet(n)
                    board.Add(t)
        print(f"manual: {net}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("saved")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
