#!/usr/bin/env python3
"""Board-level product acceptance checks complementing native ERC/DRC."""

import math
import sys
import pcbnew
import pcb_common as pc
from fanout_product import collides
from gen_pcb import PLACEMENT
from product_config import (
    CLOCK_NETS,
    HEADER_Y,
    HSE_BODY,
    J2_PINS,
    USB_NETS,
    USB_REAR_GND_WINDOW,
    contains,
    j2_row,
)

FACE = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    failures = []
    checks = 0

    def check(ok, message):
        nonlocal checks
        checks += 1
        print(("PASS " if ok else "FAIL ") + message)
        if not ok:
            failures.append(message)

    components = pc.load_netlist()[0]
    check(set(fps) == set(components), f"{len(components)} product footprints match the schematic")
    check(
        not any(ref.startswith(("SW", "H")) for ref in fps),
        "No user buttons or mounting-hole footprints",
    )
    check(board.GetCopperLayerCount() == 4, "Four copper layers")
    check(
        abs(pc.to_mm(board.GetDesignSettings().GetBoardThickness()) - 1.6) < 0.001,
        "1.6 mm board thickness",
    )
    for ref in ("D1", "U2", "U3", "U4", "U5", "J5", "J6"):
        check(fps[ref].GetLayer() == pcbnew.B_Cu, ref + " on back")
    for ref in ("D9", "D8"):
        x, y, _, side = PLACEMENT[ref]
        p = fps[ref].GetPosition()
        check(
            fps[ref].GetLayer() == FACE[side]
            and abs(pc.to_mm(p.x) - x) < 0.001
            and abs(pc.to_mm(p.y) - y) < 0.001,
            ref + " beside USB",
        )
    pads = {int(p.GetNumber()): p for p in fps["J2"].Pads()}
    check(set(pads) == {pin for pin, *_ in J2_PINS}, "J2 exactly 2 x 6 independently numbered pads")
    for pin, net, face, _label in J2_PINS:
        pad = pads[pin]
        other = FACE["B" if face == "F" else "F"]
        check(
            pad.GetNetname() == net and pad.IsOnLayer(FACE[face]) and not pad.IsOnLayer(other),
            f"J2.{pin} {net} correct face",
        )
        check(
            abs(pc.to_mm(pad.GetPosition().y) - HEADER_Y[j2_row(pin)]) < 0.001,
            f"J2.{pin} 2.54 mm pitch",
        )
    for ref, pin in [("D10", 1), ("D11", 3), ("D12", 7), ("D13", 9)]:
        check(
            fps[ref].GetLayer() == pcbnew.F_Cu
            and abs(fps[ref].GetPosition().y - pads[pin].GetPosition().y) < 1000,
            f"{ref} directly aligned with J2.{pin}",
        )
    for ref in ("J3", "J4"):
        ps = list(fps[ref].Pads())
        check(
            len(ps) == 4 and all(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in ps),
            ref + " exactly four GPIO holes",
        )
        check(bool(fps[ref].GetAttributes() & pcbnew.FP_DNP), ref + " header not populated")
    tracks = list(board.GetTracks())
    clock = set(CLOCK_NETS)
    check(
        all(
            t.GetClass() != "PCB_VIA" and t.GetLayer() == pcbnew.F_Cu
            for t in tracks
            if t.GetNetname() in clock
        ),
        "HSE all F.Cu, no signal vias",
    )
    crystal = pc.rect_shape(HSE_BODY)
    foreign = []
    for t in tracks:
        if t.GetNetname() in clock | {"GND"}:
            continue
        if t.GetClass() == "PCB_VIA":
            shape = pcbnew.SHAPE_CIRCLE(t.GetPosition(), t.GetFrontWidth() // 2)
        elif t.GetLayer() == pcbnew.F_Cu:
            shape = pcbnew.SHAPE_SEGMENT(t.GetStart(), t.GetEnd(), t.GetWidth())
        else:
            continue
        if collides(shape, crystal, 0):
            foreign.append(t.GetNetname())
    check(
        not foreign, "No unrelated front copper through crystal body: " + str(sorted(set(foreign)))
    )
    check(
        not any(t.GetClass() != "PCB_VIA" and t.GetLayer() == pcbnew.In1_Cu for t in tracks),
        "L2 ground reference has no signal tracks",
    )
    window = pc.rect_shape(USB_REAR_GND_WINDOW)
    bad = []
    for t in tracks:
        if t.GetClass() == "PCB_VIA" or t.GetLayer() != pcbnew.In2_Cu:
            continue
        shape = pcbnew.SHAPE_SEGMENT(t.GetStart(), t.GetEnd(), t.GetWidth())
        if collides(shape, window, 0):
            bad.append(t.GetNetname())
    check(not bad, "L3 rear USB reference has no crossing tracks: " + str(sorted(set(bad))))
    ground = [v for v in tracks if v.GetClass() == "PCB_VIA" and v.GetNetname() == "GND"]
    for v in tracks:
        if v.GetClass() != "PCB_VIA" or v.GetNetname() not in USB_NETS:
            continue
        a = v.GetPosition()
        near = [
            math.hypot(g.GetPosition().x - a.x, g.GetPosition().y - a.y) / 1e6
            for g in ground
            if contains(
                USB_REAR_GND_WINDOW, pc.to_mm(g.GetPosition().x), pc.to_mm(g.GetPosition().y)
            )
        ]
        check(
            bool(near) and min(near) <= 1.5,
            "USB return via within 1.5 mm at " + str((pc.to_mm(a.x), pc.to_mm(a.y))),
        )
    in_pad = []
    smd = [
        pad
        for fp in fps.values()
        for pad in fp.Pads()
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
    ]
    for v in (t for t in tracks if t.GetClass() == "PCB_VIA"):
        hole = pcbnew.SHAPE_CIRCLE(v.GetPosition(), v.GetDrillValue() // 2)
        for pad in smd:
            if any(
                pad.IsOnLayer(layer) and collides(hole, pad.GetEffectiveShape(layer), 0.025)
                for layer in (pcbnew.F_Cu, pcbnew.B_Cu)
            ):
                in_pad.append(
                    (
                        pad.GetParentFootprint().GetReference(),
                        pad.GetNumber(),
                        round(pc.to_mm(v.GetPosition().x), 4),
                        round(pc.to_mm(v.GetPosition().y), 4),
                    )
                )
    check(not in_pad, "No drill openings in or within 0.025 mm of SMT pads: " + str(in_pad))
    print(f"{checks} product checks; {len(failures)} failed")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
