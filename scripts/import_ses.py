#!/usr/bin/env python3
"""Import freerouting SES, verify USB pair survived, report unrouted."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc

import pcbnew

SES = "/tmp/ailink.ses"

board = pcbnew.LoadBoard(pc.PCB)
before = {n: 0 for n in ("USB_DP", "USB_DM")}
for t in board.GetTracks():
    n = t.GetNetname()
    if n in before:
        before[n] += 1
ok = pcbnew.ImportSpecctraSES(board, SES)
print("SES import:", ok)
after = {n: 0 for n in ("USB_DP", "USB_DM")}
total = 0
for t in board.GetTracks():
    total += 1
    n = t.GetNetname()
    if n in after:
        after[n] += 1
print(f"tracks total={total}  USB before={before} after={after}")
pcbnew.SaveBoard(pc.PCB, board)
