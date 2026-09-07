#!/usr/bin/env python3
"""Add nearby L2/L3 ground-return vias for the USB layer transitions."""
import math
import pcbnew
import pcb_common as pc
from fanout_product import Geometry
from product_config import USB_NETS,USB_REAR_GND_WINDOW,contains,inflate

# Return vias must land fully inside the L3 GND pour: window minus 0.3 mm so
# the via annulus is surrounded by copper, not by the pour clearance.
RETURN_VIA_AREA=inflate(USB_REAR_GND_WINDOW,-.3)


def in_window(p):
    return contains(RETURN_VIA_AREA,pc.to_mm(p.x),pc.to_mm(p.y))


def main():
    board=pcbnew.LoadBoard(pc.PCB)
    geometry=Geometry(board)
    usb=[v for v in board.GetTracks() if v.GetClass()=='PCB_VIA' and v.GetNetname() in USB_NETS]
    ground=[v.GetPosition() for v in board.GetTracks() if v.GetClass()=='PCB_VIA' and v.GetNetname()=='GND']
    missing=[]
    for signal in usb:
        origin=signal.GetPosition()
        def distance(p):return math.hypot(p.x-origin.x,p.y-origin.y)/1e6
        if any(distance(p)<=1.5 and in_window(p) for p in ground):continue
        candidates=[]
        for dx in range(-15,16):
            for dy in range(-15,16):
                p=pc.pt(round(pc.to_mm(origin.x)+dx*.1,3),round(pc.to_mm(origin.y)+dy*.1,3))
                if distance(p)>1.5:continue
                if not in_window(p):continue
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
