#!/usr/bin/env python3
"""Export Specctra DSN for freerouting."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc

import pcbnew

DSN = "/tmp/ailink.dsn"

board = pcbnew.LoadBoard(pc.PCB)
ok = pcbnew.ExportSpecctraDSN(board, DSN)

# Mark the inner plane layers as "power" so freerouting keeps signals off them
txt = open(DSN).read()
for lay in ("In1.Cu", "In2.Cu"):
    txt = txt.replace(f"(layer {lay}\n      (type signal)",
                      f"(layer {lay}\n      (type power)")
    txt = txt.replace(f"(layer {lay} (type signal)",
                      f"(layer {lay} (type power)")
open(DSN, "w").write(txt)
n_power = txt.count("(type power)")
print("DSN export:", ok, DSN, os.path.getsize(DSN), "power layers:", n_power)
