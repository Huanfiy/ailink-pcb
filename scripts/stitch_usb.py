#!/usr/bin/env python3
"""Add nearby L2/L3 ground-return vias for the USB layer transitions."""
import math
import pcbnew
import pcb_common as pc
from fanout_product import Geometry


def main():
    board=pcbnew.LoadBoard(pc.PCB)
    geometry=Geometry(board)
    usb=[v for v in board.GetTracks() if v.GetClass()=='PCB_VIA' and v.GetNetname() in ('USB_DP','USB_DM')]
    ground=[v.GetPosition() for v in board.GetTracks() if v.GetClass()=='PCB_VIA' and v.GetNetname()=='GND']
    missing=[]
    for signal in usb:
        origin=signal.GetPosition()
        def distance(p):return math.hypot(p.x-origin.x,p.y-origin.y)/1e6
        if any(distance(p)<=1.5 and 105.8<pc.to_mm(p.x)<113.3 and 106.9<pc.to_mm(p.y)<115 for p in ground):continue
        candidates=[]
        for dx in range(-15,16):
            for dy in range(-15,16):
                p=pc.pt(round(pc.to_mm(origin.x)+dx*.1,3),round(pc.to_mm(origin.y)+dy*.1,3))
                if distance(p)>1.5:continue
                if not (105.8<pc.to_mm(p.x)<113.3 and 106.9<pc.to_mm(p.y)<115):continue
                candidates.append(p)
        candidates.sort(key=distance)
        for p in candidates:
            if not geometry.free_via('GND',p):continue
            via=pcbnew.PCB_VIA(board)
            via.SetPosition(p);via.SetWidth(pc.mm(.5));via.SetDrill(pc.mm(.3))
            via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);via.SetNet(board.GetNetsByName()['GND'])
            board.Add(via);geometry.add(via);ground.append(p)
            print(f'USB return via: {pc.to_mm(p.x):.3f},{pc.to_mm(p.y):.3f}, distance {distance(p):.2f} mm')
            break
        else:missing.append((pc.to_mm(origin.x),pc.to_mm(origin.y)))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB,board)
    if missing:raise RuntimeError(f'USB transitions without a nearby return via: {missing}')


if __name__=='__main__':main()
