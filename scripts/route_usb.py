#!/usr/bin/env python3
"""Hand-route the USB differential pair (coupled 0.35/0.15) on F.Cu.

Topology (fixed by placement):
  J1 (left edge, rot270; pad row vertical at x~107.6)
    DP exits from A6, DM exits from B7; B6 tees into the DP line on F.Cu;
    A7 joins the DM line through a short B.Cu hop (2 vias, behind the row).
  D1 USBLC6 rot0 flow-through: DM pins 1(L)/6(R) top row, DP 3(L)/4(R) bottom.
  Corridor above the MCU: DM upper (y=109.7), DP lower (y=110.2).
  Diagonal descent right of the MCU into PA12/PA11 (pads 45/44), entering
  the pads horizontally from the right.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

W = 0.35          # track width
GAP = 0.15        # coupled gap  -> pitch 0.5
Y_DM = 110.0      # corridor rows
Y_DP = 110.5


def seg_len(pts):
    import math
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def add_track(board, net, layer, pts, width=W):
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pt(*a))
        t.SetEnd(pt(*b))
        t.SetWidth(mm(width))
        t.SetLayer(layer)
        t.SetNet(net)
        board.Add(t)


def add_via(board, net, x, y, dia=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetWidth(mm(dia))
    v.SetDrill(mm(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    board.Add(v)


def pad_pos(board, ref, number):
    for fp in board.GetFootprints():
        if fp.GetReference() == ref:
            for p in fp.Pads():
                if str(p.GetNumber()) == number:
                    pos = p.GetPosition()
                    return (round(pc.to_mm(pos.x), 3), round(pc.to_mm(pos.y), 3))
    raise KeyError(f"{ref}-{number}")


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    nets = board.GetNetsByName()
    n_dp = nets["USB_DP"]
    n_dm = nets["USB_DM"]

    a6 = pad_pos(board, "J1", "A6")   # DP
    b6 = pad_pos(board, "J1", "B6")   # DP
    a7 = pad_pos(board, "J1", "A7")   # DM
    b7 = pad_pos(board, "J1", "B7")   # DM
    d1_1 = pad_pos(board, "D1", "1")  # DM in (left top)
    d1_6 = pad_pos(board, "D1", "6")  # DM out (right top)
    d1_3 = pad_pos(board, "D1", "3")  # DP in (left bottom)
    d1_4 = pad_pos(board, "D1", "4")  # DP out (right bottom)
    u44 = pad_pos(board, "U1", "44")  # DM  (lower)
    u45 = pad_pos(board, "U1", "45")  # DP  (upper)
    print("J1:", a6, b6, a7, b7)
    print("D1:", d1_1, d1_6, d1_3, d1_4)
    print("U1:", u44, u45)

    # ---------- J1 fanout ----------
    # DP: A6 -> horizontal past the pad column -> 45 deg down -> pin3;
    #     B6 tees into the diagonal section (same net, T-join).
    dp_elbow = (108.6, a6[1])
    dp_knee = (round(108.6 + (d1_3[1] - a6[1]), 3), d1_3[1])
    dp_start = [a6, dp_elbow, dp_knee, d1_3]
    x_meet = round(108.6 + (b6[1] - a6[1]), 3)
    dp_b6 = [b6, (x_meet, b6[1])]
    # DM: B7 -> horizontal -> through via2 point -> D1 pin1
    via2 = (109.15, 116.64)
    dm_start = [b7, (108.5, b7[1]), via2, d1_1]
    # A7 hop: short stub behind the row, B.Cu diagonal to via2
    via1 = (106.6, a7[1])
    dm_a7_f = [a7, via1]
    dm_hop_b = [via1, via2]

    # ---------- D1 -> corridor ----------
    x_dm_climb = d1_6[0]              # straight up from pin 6
    x_dp_climb = round(d1_4[0] + 1.61, 3)   # right jog then climb
    dm_mid = [d1_6, (x_dm_climb, Y_DM)]
    dp_mid = [d1_4, (x_dp_climb, d1_4[1]), (x_dp_climb, Y_DP)]

    # ---------- corridor + descent (parameter search) ----------
    # DP: corridor y=Y_DP until x1, 45-degree descent to u45's row,
    #     then horizontal left into pad 45.
    # DM: corridor y=Y_DM until x2, descent to u44's row, left into pad 44.
    import math
    best = None
    for x1_i in range(1332, 1420, 2):          # 133.2 .. 142.0
        x1 = x1_i / 10.0
        for dx2_i in range(5, 40, 1):          # x2 = x1 + 0.5 .. 4.0
            x2 = round(x1 + dx2_i / 10.0, 2)
            dp_desc_end_x = round(x1 + (u45[1] - Y_DP), 2)
            dm_desc_end_x = round(x2 + (u44[1] - Y_DM), 2)
            if dp_desc_end_x < u45[0] + 0.8 or dm_desc_end_x < u44[0] + 0.8:
                continue
            # no-cross conditions
            # DM diag line: y = Y_DM + (x - x2); DP horiz at y=Y_DP ends x1
            x_dm_at_ydp = x2 + (Y_DP - Y_DM)
            if x_dm_at_ydp < x1 + 0.5:         # DM diag hits DP corridor
                continue
            # diag separation (parallel 45 lines): |c1-c2|/sqrt2 >= 0.5
            c_dp = Y_DP - x1
            c_dm = Y_DM - x2
            sep = abs(c_dp - c_dm) / math.sqrt(2)
            if sep < 0.49:
                continue
            # keep diagonals clear of the top-row pad 49 (x .. 132.4)
            if x1 < 133.1 or x2 < 133.1:
                continue
            # DM entry horizontal must stay right of DP descent end
            dp_path = [(x_dp_climb, Y_DP), (x1, Y_DP),
                       (dp_desc_end_x, u45[1]), u45]
            dm_path = [(x_dm_climb, Y_DM), (x2, Y_DM),
                       (dm_desc_end_x, u44[1]), u44]
            l_dp = (seg_len(dp_start) + seg_len(dp_mid) + seg_len(dp_path))
            l_dm = (seg_len(dm_start) + seg_len(dm_mid) + seg_len(dm_path))
            dl = abs(l_dp - l_dm)
            score = dl + max(0, dp_desc_end_x - 141) + max(0, dm_desc_end_x - 141)
            if best is None or score < best[0]:
                best = (score, x1, x2, dp_path, dm_path, l_dp, l_dm)
    _, x1, x2, dp_path, dm_path, l_dp, l_dm = best
    print(f"chosen x1={x1} x2={x2}  len DP={l_dp:.2f} DM={l_dm:.2f} "
          f"dL={abs(l_dp-l_dm):.2f} mm")

    # ---------- write tracks ----------
    add_track(board, n_dp, pcbnew.F_Cu, dp_start)
    add_track(board, n_dp, pcbnew.F_Cu, dp_b6)
    add_track(board, n_dm, pcbnew.F_Cu, dm_start)
    add_track(board, n_dm, pcbnew.F_Cu, dm_a7_f, width=0.25)
    add_track(board, n_dm, pcbnew.B_Cu, dm_hop_b, width=0.25)
    add_via(board, n_dm, *via1, dia=0.6, drill=0.3)
    add_via(board, n_dm, *via2, dia=0.6, drill=0.3)
    add_track(board, n_dm, pcbnew.F_Cu, dm_mid)
    add_track(board, n_dp, pcbnew.F_Cu, dp_mid)
    add_track(board, n_dp, pcbnew.F_Cu, dp_path)
    add_track(board, n_dm, pcbnew.F_Cu, dm_path)

    # USBLC6 flow-through links (chip-internal connection still needs copper)
    add_track(board, n_dm, pcbnew.F_Cu, [d1_1, d1_6])
    add_track(board, n_dp, pcbnew.F_Cu, [d1_3, d1_4])
    # test point stubs onto the pair
    tp6 = pad_pos(board, "TP6", "1")
    tp7 = pad_pos(board, "TP7", "1")
    add_track(board, n_dp, pcbnew.F_Cu,
              [tp6, (tp6[0], round(d1_3[1] + 0.64, 3)), d1_3], width=0.25)
    add_track(board, n_dm, pcbnew.F_Cu,
              [tp7, (x_dm_climb, tp7[1])], width=0.25)

    # escape for the caged middle-row pads of D1:
    # GND pin2 -> via-in-pad straight to the In1 plane
    n_gnd = nets["GND"]
    n_vbp = nets["VBUS_P"]
    p2 = pad_pos(board, "D1", "2")    # GND, left mid
    p5 = pad_pos(board, "D1", "5")    # VBUS_P, right mid
    add_via(board, n_gnd, *p2, dia=0.6, drill=0.3)
    add_track(board, n_vbp, pcbnew.F_Cu,
              [p5, (113.5, p5[1])], width=0.25)
    add_via(board, n_vbp, 113.5, p5[1], dia=0.6, drill=0.3)

    pcbnew.SaveBoard(pc.PCB, board)
    print("USB pair routed and saved.")


if __name__ == "__main__":
    main()
