#!/usr/bin/env python3
"""Connect isolated power groups to planes using clearance-checked short vias.

Uses KiCad's actual copper shapes, including opposite-face pads and drill
clearances. Does not place holes in SMT pads or weaken project DRC rules.
"""
import math
import pcbnew
import pcb_common as pc
from pcb_common import mm,pt
from product_config import (X0,Y0,X1,Y1,CLOCK_NETS,HSE_BODY,PLANE_NETS,
                            USB_REAR_GND_WINDOW,contains,inflate)

LAYERS = (pcbnew.F_Cu,pcbnew.B_Cu)
COPPER_LAYERS = (pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu)
VIA_D,DRILL,WIDTH = .5,.3,.2
# Via centre keep-out around the crystal: body plus one via radius.
HSE_VIA_KEEPOUT = inflate(HSE_BODY,VIA_D/2)
# Plane-side keep-out for +3V3 fanout vias: window plus antipad allowance.
PLANE_HOLE_KEEPOUT = inflate(USB_REAR_GND_WINDOW,.4)


def collides(a,b,clearance):
    return pcbnew.SHAPE.Collide(a,b,mm(clearance))


def pad_layer(pad):
    # PAD.GetLayer() returns the padstack primary layer (F.Cu), even for
    # flipped SMD pads in KiCad 10. Query the actual layer set instead.
    return pcbnew.B_Cu if pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.F_Cu


class Geometry:
    def __init__(self,board,skip_unlocked_nets=(),skip_track_uuids=()):
        self.board=board
        self.items=[]
        self.buckets={}
        self.holes=[]
        self.smd=[]
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                shapes={layer:pad.GetEffectiveShape(layer) for layer in COPPER_LAYERS if pad.IsOnLayer(layer)}
                self.register(pad,pad.GetNetname(),shapes)
                if pad.GetAttribute()==pcbnew.PAD_ATTRIB_SMD:
                    self.smd.append(pad)
                else:
                    self.holes.append((pad.GetPosition(),max(pad.GetDrillSize().x,pad.GetDrillSize().y)/2))
        for item in board.GetTracks():
            if item.m_Uuid.AsString() in skip_track_uuids:continue
            if item.GetNetname() in skip_unlocked_nets and not item.IsLocked():continue
            self.add(item)

    def add(self,item):
        if item.GetClass()=='PCB_VIA':
            shape=pcbnew.SHAPE_CIRCLE(item.GetPosition(),item.GetFrontWidth()//2)
            shapes={layer:shape for layer in COPPER_LAYERS}
            self.holes.append((item.GetPosition(),item.GetDrillValue()/2))
        else:
            shapes={item.GetLayer():pcbnew.SHAPE_SEGMENT(item.GetStart(),item.GetEnd(),item.GetWidth())}
        self.register(item,item.GetNetname(),shapes)

    def register(self,item,net,shapes):
        index=len(self.items)
        self.items.append((item,net,shapes))
        for shape in shapes.values():
            bb=pcbnew.SHAPE.BBox(shape)
            for x in range(math.floor(pc.to_mm(bb.GetLeft())-.5),math.floor(pc.to_mm(bb.GetRight())+.5)+1):
                for y in range(math.floor(pc.to_mm(bb.GetTop())-.5),math.floor(pc.to_mm(bb.GetBottom())+.5)+1):
                    self.buckets.setdefault((x,y),set()).add(index)

    def near(self,shape):
        bb=pcbnew.SHAPE.BBox(shape);indices=set()
        for x in range(math.floor(pc.to_mm(bb.GetLeft())),math.floor(pc.to_mm(bb.GetRight()))+1):
            for y in range(math.floor(pc.to_mm(bb.GetTop())),math.floor(pc.to_mm(bb.GetBottom()))+1):
                indices.update(self.buckets.get((x,y),()))
        return [self.items[i] for i in indices]

    def free_via(self,net,point,allow_smd=()):
        x,y=pc.to_mm(point.x),pc.to_mm(point.y)
        if net!='GND' and contains(HSE_VIA_KEEPOUT,x,y):return False
        if not (X0+.65<x<X1-.65 and Y0+.65<y<Y1-.65):return False
        if (x<X0+2 or x>X1-2) and (y<Y0+2 or y>Y1-2):
            hx=X0+2 if x<X0+2 else X1-2
            hy=Y0+2 if y<Y0+2 else Y1-2
            if math.dist((x,y),(hx,hy))>1.35:return False
        shape=pcbnew.SHAPE_CIRCLE(point,mm(VIA_D/2))
        nearby=self.near(shape)
        for _,name,shapes in nearby:
            if name!=net and any(collides(shape,other,.155) for other in shapes.values()):return False
        for pad,_,shapes in nearby:
            if pad.GetClass()=='PAD' and pad.GetAttribute()==pcbnew.PAD_ATTRIB_SMD:
                if pad.m_Uuid.AsString() in allow_smd:continue
                hole=pcbnew.SHAPE_CIRCLE(point,mm(DRILL/2))
                if any(collides(other,hole,.075) for other in shapes.values()):return False
        for center,radius in self.holes:
            if math.hypot(point.x-center.x,point.y-center.y)<radius+mm(DRILL/2+.255):return False
        return True

    def free_track(self,net,layer,a,b,width=WIDTH):
        shape=pcbnew.SHAPE_SEGMENT(a,b,mm(width))
        if layer==pcbnew.F_Cu and net!='GND' and net not in CLOCK_NETS:
            if collides(shape,pc.rect_shape(HSE_BODY),0):return False
        if layer==pcbnew.In2_Cu and net!='GND':
            # .175 = plane clearance so an L3 escape never touches the GND pour.
            if collides(shape,pc.rect_shape(USB_REAR_GND_WINDOW),.175):return False
        return not any(name!=net and layer in shapes and collides(shape,shapes[layer],
                       .255 if item.GetClass()=='PAD' and item.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH else .155)
                       for item,name,shapes in self.near(shape))


def connected_groups(geometry,net,with_zones=False):
    items=[entry for entry in geometry.items if entry[1]==net]
    if with_zones:
        for zone in geometry.board.Zones():
            if zone.GetIsRuleArea() or zone.GetNetname()!=net:continue
            for layer in COPPER_LAYERS:
                if not zone.IsOnLayer(layer):continue
                filled=zone.GetFilledPolysList(layer)
                for i in range(filled.OutlineCount()):
                    items.append((None,net,{layer:filled.UnitSet(i)}))
    parent=list(range(len(items)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,(_,_,shapes) in enumerate(items):
        for j in range(i):
            if root(i)==root(j):continue
            other=items[j][2]
            if any(layer in other and collides(shape,other[layer],.001) for layer,shape in shapes.items()):
                parent[root(i)]=root(j)
    groups={}
    for i,(item,_,_) in enumerate(items):
        if item is not None:groups.setdefault(root(i),[]).append(item)
    return list(groups.values())


def on_plane(net,position):
    x,y=pc.to_mm(position.x),pc.to_mm(position.y)
    if net=='GND':return True
    return not contains(PLANE_HOLE_KEEPOUT,x,y)


def main():
    board=pcbnew.LoadBoard(pc.PCB)
    geometry=Geometry(board)
    added=0;failed=[]
    for net in PLANE_NETS:
        for group in connected_groups(geometry,net):
            if any((item.GetClass()=='PCB_VIA' or
                    (item.GetClass()=='PAD' and item.GetAttribute()==pcbnew.PAD_ATTRIB_PTH))
                   and on_plane(net,item.GetPosition()) for item in group):continue
            pads=[item for item in group if item.GetClass()=='PAD']
            candidates=[]
            for pad in pads:
                for n in range(5,36):
                    distance=n*.1
                    for i in range(8):
                        angle=i*math.pi/4
                        p=pad.GetPosition()
                        end=pt(round(pc.to_mm(p.x)+distance*math.cos(angle),3),
                               round(pc.to_mm(p.y)+distance*math.sin(angle),3))
                        candidates.append((distance,pad,end))
                p=pad.GetPosition()
                for dx in range(-20,21):
                    for dy in range(-20,21):
                        if not dx or not dy:continue
                        distance=(abs(dx)+abs(dy))*.2
                        if distance>4.5:continue
                        end=pt(round(pc.to_mm(p.x)+dx*.2,3),round(pc.to_mm(p.y)+dy*.2,3))
                        candidates.append((distance,pad,end))
            candidates.sort(key=lambda candidate:candidate[0])
            for _,pad,end in candidates:
                if not on_plane(net,end) or not geometry.free_via(net,end):continue
                start=pad.GetPosition()
                paths=[(start,end),
                       (start,pcbnew.VECTOR2I(end.x,start.y),end),
                       (start,pcbnew.VECTOR2I(start.x,end.y),end)]
                path=next((path for path in paths if all(
                    geometry.free_track(net,pad_layer(pad),a,b) for a,b in zip(path,path[1:]))),None)
                if path is None:continue
                for a,b in zip(path,path[1:]):
                    if a==b:continue
                    track=pcbnew.PCB_TRACK(board)
                    track.SetStart(a);track.SetEnd(b)
                    track.SetLayer(pad_layer(pad));track.SetWidth(mm(WIDTH));track.SetNet(pad.GetNet())
                    board.Add(track);geometry.add(track)
                via=pcbnew.PCB_VIA(board)
                via.SetPosition(end);via.SetWidth(mm(VIA_D));via.SetDrill(mm(DRILL))
                via.SetLayerPair(*LAYERS);via.SetNet(pad.GetNet())
                board.Add(via);geometry.add(via)
                added+=1
                print(f'{net} {pad.GetParentFootprint().GetReference()}.{pad.GetNumber()} -> '
                      f'({pc.to_mm(end.x):.3f},{pc.to_mm(end.y):.3f})')
                break
            else:
                failed.append([f'{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}' for pad in pads])
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB,board)
    print(f'Added {added} short power vias; groups needing manual escape: {failed}')


if __name__=='__main__':main()
