#!/usr/bin/env python3
"""Reserve L3 access at disconnected groups; list any required capped vias.

Ordinary dogbones are preferred. A pad escape requiring resin fill and copper
capping is explicit in the output and must enter the fabrication coordinate list.
"""

import math
import argparse
import sys
import pcbnew
import pcb_common as pc
from fanout_product import Geometry, connected_groups, pad_layer
from product_config import PLANE_NETS, PROTECTED_NETS, USB_REAR_GND_WINDOW, contains, inflate

# A via inside this rectangle cannot reach L3: same +0.25 mm as the grid router.
L3_ACCESS_KEEPOUT = inflate(USB_REAR_GND_WINDOW, 0.25)


def reaches_l3(x, y):
    return not contains(L3_ACCESS_KEEPOUT, x, y)


def inner_access(item):
    if item.GetClass() == "PCB_VIA" or (
        item.GetClass() == "PAD" and item.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
    ):
        p = item.GetPosition()
        return reaches_l3(pc.to_mm(p.x), pc.to_mm(p.y))
    return item.GetClass() == "PCB_TRACK" and item.GetLayer() == pcbnew.In2_Cu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-vippo", action="store_true")
    parser.add_argument("nets", nargs="*")
    args = parser.parse_args()
    board = pcbnew.LoadBoard(pc.PCB)
    geometry = Geometry(board)
    special = []
    selected = args.nets or [
        n.GetNetname()
        for n in board.GetNetsByName().values()
        if n.GetNetname() not in ("",) + PLANE_NETS + PROTECTED_NETS
        and not n.GetNetname().startswith("unconnected")
    ]
    for net in selected:
        groups = connected_groups(geometry, net)
        if len(groups) < 2:
            continue
        for group in groups:
            if any(inner_access(it) for it in group):
                continue
            pads = [it for it in group if it.GetClass() == "PAD"]
            candidates = []
            for pad in pads:
                p = pad.GetPosition()
                x, y = pc.to_mm(p.x), pc.to_mm(p.y)
                for n in range(6, 41):
                    for i in range(8):
                        d = n * 0.1
                        a = i * math.pi / 4
                        end = pc.pt(round(x + d * math.cos(a), 3), round(y + d * math.sin(a), 3))
                        candidates.append((d, pad, end, False))
                # Non-radial dogbones can leave a fine-pitch row through the
                # pad's long axis and bend before reaching the via pocket.
                for dx in range(-15, 16):
                    for dy in range(-15, 16):
                        d = math.hypot(dx, dy) * 0.2
                        if not dx or not dy or d < 0.6 or d > 3:
                            continue
                        candidates.append((d + 0.15, pad, pc.pt(x + dx * 0.2, y + dy * 0.2), False))
                if args.allow_vippo and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    for dx in range(-5, 6):
                        for dy in range(-3, 4):
                            end = pc.pt(x + dx * 0.1, y + dy * 0.1)
                            shape = pad.GetEffectiveShape(pad_layer(pad))
                            # Keep the drill centre within the intended pad.
                            if not pcbnew.SHAPE.Collide(shape, end, 0):
                                continue
                            candidates.append((10 + math.hypot(dx, dy), pad, end, True))
            for _, pad, end, capped in sorted(candidates, key=lambda c: c[0]):
                x, y = pc.to_mm(end.x), pc.to_mm(end.y)
                if not reaches_l3(x, y):
                    continue
                allow = (pad.m_Uuid.AsString(),) if capped else ()
                if not geometry.free_via(net, end, allow):
                    continue
                start = pad.GetPosition()
                paths = [
                    (start, end),
                    (start, pcbnew.VECTOR2I(start.x, end.y), end),
                    (start, pcbnew.VECTOR2I(end.x, start.y), end),
                ]
                path = next(
                    (
                        path
                        for path in paths
                        if all(
                            geometry.free_track(net, pad_layer(pad), a, b, 0.15)
                            for a, b in zip(path, path[1:])
                        )
                    ),
                    None,
                )
                if path is None:
                    continue
                for t in pc.add_track(board, pad.GetNet(), pad_layer(pad), path, 0.15, locked=True):
                    geometry.add(t)
                geometry.add(pc.add_via(board, pad.GetNet(), end, 0.5, 0.3, locked=True))
                ref = pad.GetParentFootprint().GetReference() + "." + pad.GetNumber()
                print(
                    f"{net} {ref}: {x:.4f},{y:.4f} "
                    + ("VIPPO required" if capped else "ordinary dogbone"),
                    flush=True,
                )
                if capped:
                    special.append((ref, x, y))
                break
            else:
                print(
                    net,
                    "no escape for",
                    [
                        pad.GetParentFootprint().GetReference() + "." + pad.GetNumber()
                        for pad in pads
                    ],
                    flush=True,
                )
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("VIPPO:", special, flush=True)


if __name__ == "__main__":
    main()
