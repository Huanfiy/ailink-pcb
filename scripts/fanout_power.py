#!/usr/bin/env python3
"""Fanout every GND / +3V3 SMD pad to the inner planes with stub+via.

DRC-driven retry: place all fanouts, run DRC, replace offenders with the
next candidate direction until clean or out of candidates.
"""
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

POWER_NETS = ("GND", "+3V3")
VIA_D, VIA_DRILL = 0.6, 0.3
STUB_W = 0.3
DIST = 1.4

STATE = "/tmp/fanout_state.json"


def all_power_smd_pads(board):
    out = []
    for fp in board.GetFootprints():
        fc = fp.GetPosition()
        for pad in fp.Pads():
            if pad.GetNetname() not in POWER_NETS:
                continue
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            pos = pad.GetPosition()
            key = f"{fp.GetReference()}-{pad.GetNumber()}-" \
                  f"{round(pc.to_mm(pos.x),2)}-{round(pc.to_mm(pos.y),2)}"
            layer = "B" if fp.GetLayer() == pcbnew.B_Cu else "F"
            out.append({
                "key": key,
                "net": pad.GetNetname(),
                "x": pc.to_mm(pos.x), "y": pc.to_mm(pos.y),
                "fx": pc.to_mm(fc.x), "fy": pc.to_mm(fc.y),
                "layer": layer,
            })
    return out


def candidate_dirs(p):
    """Directions to try: outward from footprint center first, then others."""
    ang0 = math.atan2(p["y"] - p["fy"], p["x"] - p["fx"])
    if p["x"] == p["fx"] and p["y"] == p["fy"]:
        ang0 = 0
    # snap to 45 deg
    base = round(ang0 / (math.pi / 4)) * (math.pi / 4)
    offs = [0, 1, -1, 2, -2, 3, -3, 4]
    return [base + o * math.pi / 4 for o in offs]


def place(board, p, dir_idx):
    ang = candidate_dirs(p)[dir_idx]
    vx = round(p["x"] + DIST * math.cos(ang), 3)
    vy = round(p["y"] + DIST * math.sin(ang), 3)
    net = board.GetNetsByName()[p["net"]]
    layer = pcbnew.B_Cu if p["layer"] == "B" else pcbnew.F_Cu
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(p["x"], p["y"])); t.SetEnd(pt(vx, vy))
    t.SetWidth(mm(STUB_W)); t.SetLayer(layer); t.SetNet(net)
    board.Add(t)
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(vx, vy))
    v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    board.Add(v)
    return (vx, vy)


def remove_fanout(board, rec):
    """Remove the stub+via recorded at rec position."""
    vx, vy = rec["via"]
    target = pt(vx, vy)
    doomed = []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetPosition() == target:
            doomed.append(t)
        elif t.GetClass() == "PCB_TRACK" and t.GetEnd() == target \
                and t.GetWidth() == mm(STUB_W):
            doomed.append(t)
    for t in doomed:
        board.Remove(t)


def run_drc():
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all",
                    "--format", "json", "-o", "/tmp/drc_fanout.json", pc.PCB],
                   check=True, capture_output=True)
    return json.load(open("/tmp/drc_fanout.json"))


def offenders(drc, state):
    """fanout keys whose via/stub shows up in copper violations."""
    bad = set()
    pos_of = {k: v["via"] for k, v in state.items()}
    for v in drc["violations"]:
        if v["type"] not in ("clearance", "shorting_items", "hole_clearance",
                             "tracks_crossing", "hole_near_hole"):
            continue
        for item in v["items"]:
            p = item.get("pos")
            if not p:
                continue
            for k, (vx, vy) in pos_of.items():
                if math.dist((p["x"], p["y"]), (vx, vy)) < 0.71:
                    bad.add(k)
    return bad


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    pads = all_power_smd_pads(board)
    # skip pads already having copper attached (pre-routed escapes)
    conn = board.GetConnectivity()
    print(f"{len(pads)} power SMD pads")
    state = {}
    for p in pads:
        vx, vy = place(board, p, 0)
        state[p["key"]] = {"pad": p, "dir": 0, "via": (vx, vy)}
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)

    for round_no in range(8):
        drc = run_drc()
        bad = offenders(drc, state)
        print(f"round {round_no}: {len(bad)} offending fanouts")
        if not bad:
            break
        board = pcbnew.LoadBoard(pc.PCB)
        for k in bad:
            rec = state[k]
            remove_fanout(board, rec)
            nxt = rec["dir"] + 1
            if nxt >= 8:
                print(f"  giving up on {k}")
                del state[k]
                continue
            vx, vy = place(board, rec["pad"], nxt)
            state[k] = {"pad": rec["pad"], "dir": nxt, "via": (vx, vy)}
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(pc.PCB, board)
    json.dump({k: v["via"] for k, v in state.items()}, open(STATE, "w"))
    print("fanout done:", len(state), "vias")


if __name__ == "__main__":
    main()
