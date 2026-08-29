#!/usr/bin/env python3
"""Small targeted fixes:
- replace D1 pin2 GND escape (trace+via) with a via-in-pad
- enlarge the three 0.5mm USB-area vias to 0.6mm
- move R6 up to clear the C10 courtyard (its nets get re-routed after)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

board = pcbnew.LoadBoard(pc.PCB)

# --- 1. remove old D1-2 escape (trace 0.25 ending at via 109.6,117.2 + via)
old_via = pt(109.6, 117.2)
doomed = []
for t in board.GetTracks():
    if t.GetClass() == "PCB_VIA" and t.GetPosition() == old_via:
        doomed.append(t)
    elif t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND":
        if t.GetStart() == old_via or t.GetEnd() == old_via:
            doomed.append(t)
        else:
            # the two escape segments from pad2
            s, e = t.GetStart(), t.GetEnd()
            pts = {(round(pc.to_mm(s.x), 3), round(pc.to_mm(s.y), 3)),
                   (round(pc.to_mm(e.x), 3), round(pc.to_mm(e.y), 3))}
            if (110.362, 117.5) in pts or (109.962, 117.2) in pts:
                doomed.append(t)
seen_ids = set()
uniq = []
for t in doomed:
    if id(t) not in seen_ids:
        seen_ids.add(id(t))
        uniq.append(t)
for t in uniq:
    board.Remove(t)
print(f"removed {len(uniq)} old escape items")

# via-in-pad on D1 pin2
gnd = board.GetNetsByName()["GND"]
for fp in board.GetFootprints():
    if fp.GetReference() == "D1":
        for pad in fp.Pads():
            if str(pad.GetNumber()) == "2":
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pad.GetPosition())
                v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(gnd)
                board.Add(v)
                print("via-in-pad added on D1-2")

# --- 2. enlarge the 0.5 vias
for x, y in ((113.5, 117.5), (106.6, 117.75), (109.15, 116.64)):
    target = pt(x, y)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetPosition() == target:
            t.SetWidth(mm(0.6))
            print(f"via ({x},{y}) -> 0.6mm")

# --- 3. move R6 up
for fp in board.GetFootprints():
    if fp.GetReference() == "R6":
        fp.SetPosition(pt(118.8, 112.1))
        print("R6 moved to (118.8, 112.1)")

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(pc.PCB, board)
print("saved")
