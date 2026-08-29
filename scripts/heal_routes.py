#!/usr/bin/env python3
"""Heal leftover connectivity: explicit fixes + hair-gap bridging."""
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew


def pad_pos(board, ref, number):
    for fp in board.GetFootprints():
        if fp.GetReference() == ref:
            for p in fp.Pads():
                if str(p.GetNumber()) == number:
                    pos = p.GetPosition()
                    return (round(pc.to_mm(pos.x), 3), round(pc.to_mm(pos.y), 3))
    raise KeyError(f"{ref}-{number}")


def add_seg(board, netname, layer, a, b, width=0.25):
    if a == b:
        return
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(*a)); t.SetEnd(pt(*b))
    t.SetWidth(mm(width)); t.SetLayer(layer)
    t.SetNet(board.GetNetsByName()[netname])
    board.Add(t)


def add_via(board, netname, x, y, dia=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetWidth(mm(dia)); v.SetDrill(mm(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(board.GetNetsByName()[netname])
    board.Add(v)


def explicit_fixes(board):
    # USBLC6 flow-through links (pins are internally connected in the chip,
    # but copper connectivity is still required)
    p1 = pad_pos(board, "D1", "1"); p6 = pad_pos(board, "D1", "6")
    p3 = pad_pos(board, "D1", "3"); p4 = pad_pos(board, "D1", "4")
    add_seg(board, "USB_DM", pcbnew.F_Cu, p1, p6, 0.35)
    add_seg(board, "USB_DP", pcbnew.F_Cu, p3, p4, 0.35)
    # test point stubs onto the pair
    tp6 = pad_pos(board, "TP6", "1"); tp7 = pad_pos(board, "TP7", "1")
    add_seg(board, "USB_DP", pcbnew.F_Cu, tp6, (tp6[0], round(p3[1] + 0.63, 3)), 0.25)
    add_seg(board, "USB_DP", pcbnew.F_Cu, (tp6[0], round(p3[1] + 0.63, 3)), p3, 0.25)
    add_seg(board, "USB_DM", pcbnew.F_Cu, tp7, (112.638, tp7[1]), 0.25)
    # FLASH_HOLD: U2-7 -> R9-2
    u27 = pad_pos(board, "U2", "7"); r92 = pad_pos(board, "R9", "2")
    add_seg(board, "FLASH_HOLD", pcbnew.F_Cu, u27, (r92[0], u27[1]), 0.2)
    add_seg(board, "FLASH_HOLD", pcbnew.F_Cu, (r92[0], u27[1]), r92, 0.2)
    # GND fanout vias for stacked VSS pads and C7
    for ref, num, dy in (("U1", "31", 1.0), ("U1", "63", -1.0)):
        p = pad_pos(board, ref, num)
        tgt = (p[0], round(p[1] + dy, 3))
        add_seg(board, "GND", pcbnew.F_Cu, p, tgt, 0.3)
        add_via(board, "GND", *tgt)
    c72 = pad_pos(board, "C7", "2")
    tgt = (round(c72[0] + 1.0, 3), c72[1])
    add_seg(board, "GND", pcbnew.B_Cu, c72, tgt, 0.3)
    add_via(board, "GND", *tgt)


def bridge_hair_gaps(board, drc_json):
    d = json.load(open(drc_json))
    n = 0
    for u in d.get("unconnected_items", []):
        items = u["items"]
        if len(items) != 2:
            continue
        (a, b) = items
        pa = (a["pos"]["x"], a["pos"]["y"])
        pb = (b["pos"]["x"], b["pos"]["y"])
        dist = math.dist(pa, pb)
        if dist > 1.2 or dist == 0:
            continue
        # net name from description: text inside [...]
        m = re.search(r"\[([^\]]+)\]", a["description"])
        if not m:
            continue
        net = m.group(1)
        if net.startswith("unconnected"):
            continue
        layer = pcbnew.B_Cu if ("B.Cu" in a["description"]
                                and "B.Cu" in b["description"]) else pcbnew.F_Cu
        add_seg(board, net, layer, pa, pb, 0.2)
        n += 1
    print(f"bridged {n} hair gaps")


def remove_dangling(board, drc_json):
    d = json.load(open(drc_json))
    doomed = []
    for v in d.get("violations", []):
        if v["type"] not in ("track_dangling", "via_dangling"):
            continue
        p = v["items"][0]["pos"]
        target = pt(p["x"], p["y"])
        for t in board.GetTracks():
            if t.GetStart() == target or t.GetEnd() == target \
               or t.GetPosition() == target:
                doomed.append(t)
                break
    for t in set(doomed):
        board.Remove(t)
    print(f"removed {len(doomed)} dangling items")


def refill(board):
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    board = pcbnew.LoadBoard(pc.PCB)
    if mode in ("all", "explicit"):
        explicit_fixes(board)
    if mode in ("all", "bridge") and len(sys.argv) > 2:
        bridge_hair_gaps(board, sys.argv[2])
    if mode == "dangling" and len(sys.argv) > 2:
        remove_dangling(board, sys.argv[2])
    refill(board)
    pcbnew.SaveBoard(pc.PCB, board)
    print("healed & saved")
