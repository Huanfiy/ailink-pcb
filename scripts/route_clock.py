#!/usr/bin/env python3
"""Lock the short HSE island on the front, without signal vias."""
import pcbnew
import pcb_common as pc
from product_config import CLOCK_NETS


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    names = CLOCK_NETS
    old_tracks = list(board.GetTracks())
    for item in old_tracks:
        if item.GetNetname() in names:
            board.Remove(item)
    def pad(ref, pin):
        return pc.pad_pos(board, ref, pin)
    def trace(name, points):
        pc.add_track(board, name, pcbnew.F_Cu, points, .2)
    trace('OSC_IN', [pad('U1','5'), (125.6,112.75), (126.5,111.85)])
    trace('OSC_IN', [pad('X1','3'), pad('C10','1')])
    trace('OSC_OUT', [pad('U1','6'), (125.3,112.25), (125.3,107.89), pad('R6','2')])
    trace('OSC_XO', [pad('R6','1'), (125.9,108.8), (127.35,108.8), pad('X1','1')])
    trace('OSC_XO', [pad('X1','1'), (130.475,110.15), pad('C11','1')])
    for item in board.GetTracks():
        if item.GetNetname() in names:
            item.SetLocked(True)
    pcbnew.SaveBoard(pc.PCB, board)
    print('HSE island: front copper only; signal routes locked')


if __name__ == '__main__':
    main()
