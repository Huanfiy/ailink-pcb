#!/usr/bin/env python3
"""Post-route step tool. Usage: post_route.py [clear-usb|zones]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

X0, Y0, X1, Y1 = 100.3, 100.3, 164.7, 134.7


def clear_usb():
    board = pcbnew.LoadBoard(pc.PCB)
    doomed = [t for t in board.GetTracks()
              if t.GetNetname() in ("USB_DP", "USB_DM")]
    for t in doomed:
        board.Remove(t)
    pcbnew.SaveBoard(pc.PCB, board)
    print(f"removed {len(doomed)} USB tracks")


def add_zone(board, netname, layer, prio):
    net = board.GetNetsByName()[netname]
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(prio)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.2))
    z.SetThermalReliefGap(mm(0.3))
    z.SetThermalReliefSpokeWidth(mm(0.4))
    pts = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in pts:
        chain.Append(pt(x, y))
    chain.SetClosed(True)
    z.Outline().AddOutline(chain)
    board.Add(z)


def zones_inner():
    board = pcbnew.LoadBoard(pc.PCB)
    add_zone(board, "GND", pcbnew.In1_Cu, 0)
    add_zone(board, "+3V3", pcbnew.In2_Cu, 0)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("inner plane zones added and filled")


def zones_outer():
    board = pcbnew.LoadBoard(pc.PCB)
    add_zone(board, "GND", pcbnew.F_Cu, 0)
    add_zone(board, "GND", pcbnew.B_Cu, 0)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("outer GND pours added and filled")


def zones_outer_remove():
    board = pcbnew.LoadBoard(pc.PCB)
    doomed = [z for z in board.Zones()
              if z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
    for z in doomed:
        board.Remove(z)
    pcbnew.SaveBoard(pc.PCB, board)
    print(f"removed {len(doomed)} outer zones")


if __name__ == "__main__":
    {"clear-usb": clear_usb, "zones-inner": zones_inner,
     "zones-outer": zones_outer,
     "zones-outer-remove": zones_outer_remove}[sys.argv[1]]()
