#!/usr/bin/env python3
"""Reserve clearance-checked MCU escapes before general routing."""
import pcbnew
import pcb_common as pc
from fanout_product import Geometry,on_plane
from product_config import MCU_CENTER


def main():
    board=pcbnew.LoadBoard(pc.PCB)
    geometry=Geometry(board)
    fp=next(fp for fp in board.GetFootprints() if fp.GetReference()=='U1')
    pads=[pad for pad in fp.Pads() if pad.GetNetname() and
          not pad.GetNetname().startswith('unconnected') and
          pad.GetNetname() not in ('USB_DP','USB_DM','OSC_IN','OSC_OUT')]
    # The crowded west USB/SPI row has fewer escape alternatives.
    pads.sort(key=lambda pad:(0 if 33<=int(pad.GetNumber())<=48 else 1,int(pad.GetNumber())))
    failed=[]
    for pad in pads:
        pos=pad.GetPosition();x,y=pc.to_mm(pos.x),pc.to_mm(pos.y)
        if abs(x-MCU_CENTER[0])>abs(y-MCU_CENTER[1]):
            dx=1 if x>MCU_CENTER[0] else -1;dy=0
        else:
            dx=0;dy=1 if y>MCU_CENTER[1] else -1
        options=[(n*.1,sign) for n in range(11,51) for sign in (-1,1)]
        for distance,sign in options:
            end=pc.pt(round(x+sign*distance*dx,3),round(y+sign*distance*dy,3))
            if pad.GetNetname()=='+3V3' and not on_plane('+3V3',end):continue
            if not geometry.free_via(pad.GetNetname(),end):continue
            if not geometry.free_track(pad.GetNetname(),pcbnew.F_Cu,pos,end,.15):continue
            t=pcbnew.PCB_TRACK(board)
            t.SetStart(pos);t.SetEnd(end);t.SetWidth(pc.mm(.15));t.SetLayer(pcbnew.F_Cu);t.SetNet(pad.GetNet())
            t.SetLocked(True);board.Add(t);geometry.add(t)
            v=pcbnew.PCB_VIA(board)
            v.SetPosition(end);v.SetWidth(pc.mm(.5));v.SetDrill(pc.mm(.3))
            v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(pad.GetNet())
            v.SetLocked(True);board.Add(v);geometry.add(v)
            print(f'U1.{pad.GetNumber()} {pad.GetNetname()} -> {pc.to_mm(end.x):.3f},{pc.to_mm(end.y):.3f}')
            break
        else:failed.append((pad.GetNumber(),pad.GetNetname()))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB,board)
    print('MCU escapes still needed:',failed)


if __name__=='__main__':main()
