#!/usr/bin/env python3
"""Reserve clearance-checked MCU escapes before general routing."""

import pcbnew
import pcb_common as pc
from fanout_product import Geometry, on_plane
from product_config import MCU_CENTER, PROTECTED_NETS


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    geometry = Geometry(board)
    fp = pc.footprint_by_ref(board, "U1")
    # Hand-routed nets keep their own escapes (OSC_XO has no U1 pad anyway).
    pads = [
        pad
        for pad in fp.Pads()
        if pad.GetNetname()
        and not pad.GetNetname().startswith("unconnected")
        and pad.GetNetname() not in PROTECTED_NETS
    ]
    # The crowded west USB/SPI row has fewer escape alternatives.
    pads.sort(key=lambda pad: (0 if 33 <= int(pad.GetNumber()) <= 48 else 1, int(pad.GetNumber())))
    failed = []
    for pad in pads:
        pos = pad.GetPosition()
        x, y = pc.to_mm(pos.x), pc.to_mm(pos.y)
        if abs(x - MCU_CENTER[0]) > abs(y - MCU_CENTER[1]):
            dx = 1 if x > MCU_CENTER[0] else -1
            dy = 0
        else:
            dx = 0
            dy = 1 if y > MCU_CENTER[1] else -1
        options = [(n * 0.1, sign) for n in range(11, 51) for sign in (-1, 1)]
        for distance, sign in options:
            end = pc.pt(round(x + sign * distance * dx, 3), round(y + sign * distance * dy, 3))
            if pad.GetNetname() == "+3V3" and not on_plane("+3V3", end):
                continue
            if not geometry.free_via(pad.GetNetname(), end):
                continue
            if not geometry.free_track(pad.GetNetname(), pcbnew.F_Cu, pos, end, 0.15):
                continue
            for t in pc.add_track(board, pad.GetNet(), pcbnew.F_Cu, (pos, end), 0.15, locked=True):
                geometry.add(t)
            geometry.add(pc.add_via(board, pad.GetNet(), end, 0.5, 0.3, locked=True))
            print(
                f"U1.{pad.GetNumber()} {pad.GetNetname()} -> {pc.to_mm(end.x):.3f},{pc.to_mm(end.y):.3f}"
            )
            break
        else:
            failed.append((pad.GetNumber(), pad.GetNetname()))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB, board)
    print("MCU escapes still needed:", failed)


if __name__ == "__main__":
    main()
