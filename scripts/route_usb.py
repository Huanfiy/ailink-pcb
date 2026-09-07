#!/usr/bin/env python3
"""Hand-route the v0.4 USB path through rear D1 (F/B/F).

D1 is flipped and rotated 180 degrees: left pads 6/4 -> right pads 1/3.
The short Type-C A/B fanout includes one extra DM bridge. Back copper
requires the dedicated In2 GND reference region from post_route.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import pt, pad_pos
from product_config import USB_NETS

import pcbnew

W = 0.35          # track width
VIA_D, VIA_DRILL = 0.6, 0.3


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    old_tracks = list(board.GetTracks())
    for t in old_tracks:
        if t.GetNetname() in USB_NETS:
            board.Remove(t)
    F,B=pcbnew.F_Cu,pcbnew.B_Cu
    def track(name,layer,points,width=W):
        pc.add_track(board,name,layer,points,width)
    def via(name,p):
        pc.add_via(board,name,p,VIA_D,VIA_DRILL)
    dp,dm="USB_DP","USB_DM"
    # Type-C reversed contacts: A6/B6 join on F, A7 crosses under the row.
    track(dp,F,[pad_pos(board,"J1","A6"),(108.7,110.75),(109.9,111.95),(109.6,112.8)])
    track(dp,F,[pad_pos(board,"J1","B6"),(109.7,111.75)])
    via(dp,(109.6,112.8))
    track(dp,B,[(109.6,112.8),(109,112.2),pad_pos(board,"D1","4")])
    track(dm,F,[pad_pos(board,"J1","B7"),(108.65,110.25),(109.35,109.55),(109.35,107.4)])
    via(dm,(109.35,107.4))
    track(dm,B,[(109.35,107.4),(109.35,109),pad_pos(board,"D1","6")])
    track(dm,F,[pad_pos(board,"J1","A7"),(106.6,111.25)],.25)
    via(dm,(106.6,111.25))
    track(dm,B,[(106.6,111.25),(106.6,110.2),(107.4,109.4),(108.95,109.4),(109.35,109)],.25)
    # D1 is flipped and rotated 180 degrees. Keep both protection channels
    # directly on the signal path and copper-connect the flow-through pads.
    track(dm,B,[pad_pos(board,"D1","6"),pad_pos(board,"D1","1")],.25)
    track(dp,B,[pad_pos(board,"D1","4"),pad_pos(board,"D1","3")],.25)
    track(dm,B,[pad_pos(board,"D1","1"),(111.4,109.2)])
    via(dm,(111.4,109.2))
    track(dm,F,[(111.4,109.2),(111.4,112.75),pad_pos(board,"U1","44")])
    tp=pad_pos(board,"TP6","1")
    track(dp,B,[pad_pos(board,"D1","3"),(111.8,112.6125),(111.8,113.9),
                tp,(109.4,113.9)])
    via(dp,(109.4,113.9))
    track(dp,F,[(109.4,113.9),(110.05,113.25),pad_pos(board,"U1","45")])
    track(dm,B,[pad_pos(board,"TP7","1"),(109.35,108),(109.35,109)],.2)
    if not any(t.GetClass() == 'PCB_VIA' and t.GetPosition() == pt(110,111)
               for t in board.GetTracks()):
        via("GND",(110,111))
        track("GND",B,[(110,111),pad_pos(board,"D1","2")],.25)
    for t in board.GetTracks():
        if t.GetNetname() in USB_NETS: t.SetLocked(True)
    pcbnew.SaveBoard(pc.PCB,board)
    print("v0.4 USB F/B/F routes added; run DRC and SI before release")


if __name__ == "__main__":
    main()
