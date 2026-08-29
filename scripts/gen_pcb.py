#!/usr/bin/env python3
"""Build ailink.kicad_pcb: outline, 4-layer setup, placement, net binding.

Board frame: (100,100)-(165,135) = 65 x 35 mm, M2 holes in corners.
USB-C on the left edge, target headers on right/top/bottom-right (MR-02).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

X0, Y0, X1, Y1 = 100.0, 100.0, 165.0, 135.0
CORNER_R = 2.0

# ref: (x, y, rot_deg, side)  side: 'F' top, 'B' bottom
PLACEMENT = {
    # --- USB / power (left) ---
    "J1":  (103.6, 117.5, 270, "F"),
    "D1":  (111.5, 117.5, 0,   "F"),
    "R1":  (104.5, 124.4, 90,  "B"),
    "R2":  (106.5, 124.4, 90,  "B"),
    "R3":  (104.5, 128.2, 90,  "B"),
    "C13": (106.5, 128.2, 90,  "B"),
    "TP7": (111.0, 112.5, 0,   "F"),
    "TP6": (111.0, 122.5, 0,   "F"),
    "F1":  (108.5, 104.0, 0,   "F"),
    "D7":  (115.5, 104.0, 0,   "F"),
    "U3":  (123.0, 104.4, 0,   "F"),
    "C1":  (120.2, 108.2, 90,  "F"),
    "C2":  (124.0, 108.2, 90,  "F"),
    "TP1": (111.0, 107.6, 0,   "F"),
    "TP2": (137.2, 106.3, 0,   "F"),
    "TP3": (137.2, 109.8, 0,   "F"),
    # --- LEDs (top) ---
    "D8":  (128.6, 103.4, 0,   "F"),
    "R27": (127.4, 107.6, 0,   "F"),
    "R28": (130.4, 107.6, 0,   "F"),
    "R29": (133.4, 107.6, 0,   "F"),
    "D9":  (134.8, 103.2, 0,   "F"),
    "R30": (137.2, 103.4, 90,  "F"),
    # --- MCU core ---
    "U1":  (128.5, 118.0, 0,   "F"),
    "X1":  (118.8, 116.5, 0,   "F"),
    "R6":  (118.8, 112.1, 0,   "F"),
    "C10": (116.2, 113.6, 0,   "F"),
    "C11": (115.8, 119.6, 0,   "F"),
    "FB1": (119.5, 121.8, 0,   "F"),
    "C8":  (115.8, 121.8, 0,   "F"),
    "C9":  (115.8, 123.6, 0,   "F"),
    # decoupling under the MCU on the bottom side
    "C3":  (125.5, 121.5, 0,   "B"),
    "C4":  (133.0, 121.0, 90,  "B"),
    "C5":  (132.5, 114.0, 90,  "B"),
    "C6":  (125.5, 113.5, 0,   "B"),
    "C7":  (130.2, 123.4, 0,   "B"),
    "R5":  (126.6, 124.2, 0,   "B"),
    # --- buttons / reset ---
    "SW1": (112.5, 131.5, 0,   "F"),
    "SW2": (120.5, 131.5, 0,   "F"),
    "R4":  (108.6, 127.4, 90,  "F"),
    "C12": (118.2, 127.2, 90,  "F"),
    "TP5": (105.0, 127.5, 0,   "F"),
    "TP4": (114.8, 127.6, 0,   "F"),
    # --- SPI NOR (CS/WP pull-ups sit left of U2, next to their pins) ---
    "U2":  (128.5, 128.2, 0,   "F"),
    "R7":  (121.6, 126.6, 0,   "F"),
    "R8":  (121.6, 128.4, 0,   "F"),
    "R9":  (138.9, 125.5, 90,  "F"),
    "C14": (116.2, 124.8, 0,   "F"),
    # --- J2 target SWD (top edge, right) ---
    "J2":  (149.0, 103.6, 90,  "F"),
    "D2":  (150.5, 107.5, 0,   "F"),
    "R10": (144.5, 106.0, 0,   "F"),
    "R11": (144.5, 107.8, 0,   "F"),
    "R12": (144.5, 109.6, 0,   "F"),
    # --- J3 UART (right edge) ---
    "J3":  (160.5, 110.0, 0,   "F"),
    "D3":  (154.5, 112.5, 0,   "F"),
    "R13": (148.5, 110.2, 0,   "F"),
    "R14": (148.5, 112.0, 0,   "F"),
    "R15": (148.5, 113.8, 0,   "F"),
    "R16": (148.5, 115.6, 0,   "F"),
    # --- J4 GPIO (right edge, lower) ---
    "J4":  (160.5, 120.5, 0,   "F"),
    "D4":  (152.5, 121.5, 0,   "F"),
    "D5":  (152.5, 126.5, 0,   "F"),
    # R22/R24 swapped so TGPIO7 (high pin row) gets the upper slot
    "R17": (146.5, 117.4, 0,   "F"),
    "R18": (146.5, 119.2, 0,   "F"),
    "R19": (146.5, 121.0, 0,   "F"),
    "R20": (146.5, 122.8, 0,   "F"),
    "R21": (146.5, 124.6, 0,   "F"),
    "R22": (146.5, 130.0, 0,   "F"),
    "R23": (146.5, 128.2, 0,   "F"),
    "R24": (146.5, 126.4, 0,   "F"),
    # --- J5 console (bottom edge) ---
    "J5":  (144.5, 132.8, 90,  "F"),
    "D6":  (140.3, 128.8, 0,   "F"),
    "R25": (137.0, 131.0, 0,   "B"),
    "R26": (137.0, 132.8, 0,   "B"),
    # --- J6 self-SWD pads (bottom edge) ---
    "J6":  (127.0, 133.4, 90,  "F"),
    # --- mounting ---
    "H1":  (103.0, 103.0, 0,   "F"),
    "H2":  (162.0, 103.0, 0,   "F"),
    "H3":  (103.0, 132.0, 0,   "F"),
    "H4":  (154.5, 132.0, 0,   "F"),
}

SILK_TEXTS = [
    # (text, x, y, size)
    ("ailink v0.3", 128.5, 111.0, 0.9),
    ("3V3 ONLY / NO POWER OUT", 150.5, 116.9, 0.8),
    ("USB", 103.5, 112.3, 0.8),
    ("BOOT", 112.5, 129.2, 0.8),
    ("RST", 120.5, 129.2, 0.8),
]

# per-pin silk labels: (jref, pad, text, dx, dy)
PIN_LABELS = [
    ("J2", "1", "GND", 0, 2.0), ("J2", "2", "CLK", 0, 2.0),
    ("J2", "3", "DIO", 0, 2.0), ("J2", "4", "RST", 0, 2.0),
    ("J3", "1", "ATX", -2.6, 0), ("J3", "3", "ARX", -2.6, 0),
    ("J3", "5", "GND", -2.6, 0),
    ("J3", "2", "BTX", 0, -1.6), ("J3", "4", "BRX", 0, 1.7),
    ("J3", "6", "GND", 0, 1.7),
    ("J4", "1", "G0", -2.4, 0), ("J4", "3", "G1", -2.4, 0),
    ("J4", "5", "G2", -2.4, 0), ("J4", "7", "G3", -2.4, 0),
    ("J4", "9", "GND", -2.4, 0),
    ("J4", "2", "G4", 0, -1.6), ("J4", "4", "G5", 0, 1.7),
    ("J4", "6", "G6", 0, 1.7), ("J4", "8", "G7", 0, 1.7),
    ("J4", "10", "GND", 0, 1.7),
    ("J5", "1", "TX", 0, -2.0), ("J5", "2", "RX", 0, -2.0),
    ("J5", "3", "GND", 0, -2.0),
    ("J6", "1", "3V3", 0, -2.0), ("J6", "2", "DIO", 0, -2.0),
    ("J6", "3", "CLK", 0, -2.0), ("J6", "4", "GND", 0, -2.0),
]


def build():
    board = pcbnew.NewBoard(pc.PCB)
    bds = board.GetDesignSettings()
    bds.SetCopperLayerCount(4)
    bds.SetBoardThickness(mm(1.6))
    # sensible manufacturing minimums (JLC 4-layer capable)
    bds.m_TrackMinWidth = mm(0.15)
    bds.m_ViasMinSize = mm(0.45)
    bds.m_MinThroughDrill = mm(0.3)
    bds.m_HoleClearance = mm(0.25)
    bds.m_MinClearance = mm(0.15)
    bds.m_CopperEdgeClearance = mm(0.3)

    # ---- outline: rounded rect ----
    r = CORNER_R
    segs = [
        ((X0 + r, Y0), (X1 - r, Y0)),
        ((X1, Y0 + r), (X1, Y1 - r)),
        ((X1 - r, Y1), (X0 + r, Y1)),
        ((X0, Y1 - r), (X0, Y0 + r)),
    ]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)
    arcs = [  # start, mid, end (clockwise corners)
        ((X0, Y0 + r), (X0 + r * 0.2929, Y0 + r * 0.2929), (X0 + r, Y0)),
        ((X1 - r, Y0), (X1 - r * 0.2929, Y0 + r * 0.2929), (X1, Y0 + r)),
        ((X1, Y1 - r), (X1 - r * 0.2929, Y1 - r * 0.2929), (X1 - r, Y1)),
        ((X0 + r, Y1), (X0 + r * 0.2929, Y1 - r * 0.2929), (X0, Y1 - r)),
    ]
    for a, m_, b in arcs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(pt(*a), pt(*m_), pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)

    # ---- nets ----
    comps, nets = pc.load_netlist()
    netmap = {}
    for name in sorted(nets):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netmap[name] = ni
    pad2net = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            pad2net[(ref, pin)] = name

    # ---- footprints ----
    missing = []
    for ref, meta in sorted(comps.items()):
        if ref not in PLACEMENT:
            missing.append(ref)
            continue
        x, y, rot, side = PLACEMENT[ref]
        fp = pc.load_footprint(meta["footprint"])
        fp.SetReference(ref)
        fp.SetValue(meta["value"])
        board.Add(fp)
        fp.SetPosition(pt(x, y))
        if side == "B":
            fp.Flip(fp.GetPosition(), False)
        fp.SetOrientationDegrees(rot)
        # bind nets
        for pad in fp.Pads():
            key = (ref, str(pad.GetNumber()))
            if key in pad2net:
                pad.SetNet(netmap[pad2net[key]])
        # tidy reference text
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        fp.Reference().SetTextThickness(mm(0.13))
        if ref.startswith("H"):
            fp.Reference().SetVisible(False)
        if meta["dnp"]:
            fp.SetAttributes(fp.GetAttributes()
                             | pcbnew.FP_EXCLUDE_FROM_BOM
                             | pcbnew.FP_DNP)
    if missing:
        print("WARNING: no placement for:", missing)

    # ---- silk texts ----
    for text, x, y, size in SILK_TEXTS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(pt(x, y))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(max(0.12, size * 0.15)))
        board.Add(t)
    # per-pin labels
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for jref, pad_no, text, dx, dy in PIN_LABELS:
        fp = fps.get(jref)
        if not fp:
            continue
        pad = next(p for p in fp.Pads() if str(p.GetNumber()) == pad_no)
        pos = pad.GetPosition()
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(pcbnew.VECTOR2I(pos.x + mm(dx), pos.y + mm(dy)))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        t.SetTextThickness(mm(0.13))
        board.Add(t)

    board.BuildListOfNets()
    pcbnew.SaveBoard(pc.PCB, board)
    print(f"saved {pc.PCB}: {len(list(board.GetFootprints()))} footprints, "
          f"{board.GetNetCount()} nets")
    return board


if __name__ == "__main__":
    build()
