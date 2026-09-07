#!/usr/bin/env python3
"""Create the inner planes. Usage: post_route.py zones-inner

L2 is a continuous GND plane. L3 carries +3V3 plus a dedicated GND window
under the rear USB segment; the explicit cutout keeps Specctra export honest.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

from product_config import (X0 as BX0, Y0 as BY0, X1 as BX1, Y1 as BY1,
                            USB_REAR_GND_WINDOW, inflate, rect_corners)
X0,Y0,X1,Y1=BX0+.3,BY0+.3,BX1-.3,BY1-.3


def add_zone(board, netname, layer, prio, polygon=None, hole=None):
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
    pts = polygon or [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in pts:
        chain.Append(pt(x, y))
    chain.SetClosed(True)
    z.Outline().AddOutline(chain)
    if hole:
        hole_id = z.Outline().NewHole(0)
        for x, y in hole:
            z.Outline().Append(pt(x, y), 0, hole_id)
    board.Add(z)


def zones_inner():
    board = pcbnew.LoadBoard(pc.PCB)
    old_zones = list(board.Zones())
    for z in old_zones:
        if z.GetLayer() in (pcbnew.In1_Cu,pcbnew.In2_Cu): board.Remove(z)
    add_zone(board, "GND", pcbnew.In1_Cu, 0)
    # Explicit cutout is also respected by Specctra; priorities alone are not.
    # +0.3 mm keeps the 3.3 V pour one zone clearance away from the GND window.
    add_zone(board, "+3V3", pcbnew.In2_Cu, 0,
             hole=rect_corners(inflate(USB_REAR_GND_WINDOW, .3)))
    add_zone(board, "GND", pcbnew.In2_Cu, 1, rect_corners(USB_REAR_GND_WINDOW))
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("inner plane zones added and filled")


if __name__ == "__main__":
    if sys.argv[1:] != ["zones-inner"]:
        raise SystemExit(__doc__.splitlines()[0])
    zones_inner()
