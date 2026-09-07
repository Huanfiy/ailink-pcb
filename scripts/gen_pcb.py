#!/usr/bin/env python3
"""Build ailink.kicad_pcb: outline, 4-layer setup, placement, net binding.

Board frame: (100,100)-(142,122) = 42 x 22 mm, R2 corners, no mounting holes.
USB left; front UART, rear SWD/power, two optional GPIO hole rows.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from pcb_common import mm, pt

import pcbnew

from product_config import X0, Y0, X1, Y1, CORNER_R, HEADER_Y, J2_PINS, REVISION

# Fixed anchors implement the approved front layout; B coordinates are front projections.
PLACEMENT = {
    "J1": (103.6,111,270,"F"), "J2": (142,111,0,"F"),
    "J3": (114,101.8,90,"F"), "J4": (114,120.2,90,"F"),
    "U1": (118.5,111,180,"F"), "X1": (127.6,111,180,"F"),
    "C10": (126.5,114.4,270,"F"), "C11": (130.6,109.5,90,"F"), "R6": (125.9,107.8,90,"F"),
    "D8": (104,119.2,0,"F"), "D9": (104,102.8,0,"F"),
    "D10": (135.7,HEADER_Y[0],0,"F"), "D11": (135.7,HEADER_Y[1],0,"F"),
    "D12": (135.7,HEADER_Y[3],0,"F"), "D13": (135.7,HEADER_Y[4],0,"F"),
    "D1": (110,111,180,"B"), "U2": (118.5,111,0,"B"),
    "C12": (106.6,112.8,0,"B"),
    "F1": (102.8,102.5,0,"B"), "D7": (109,102.5,0,"B"),
    "U3": (103.5,111,0,"B"),
    "D4": (118.5,104.7,0,"B"), "D5": (118.5,117.3,0,"B"),
    "D3": (133.5,103.5,0,"B"), "D2": (133.5,108,0,"B"),
    "U4": (133.5,112.5,0,"B"), "U5": (133.5,117,0,"B"),
}

# Desired centres for the smaller back components. The packer only resolves
# courtyard and through-hole conflicts; it does not claim routing feasibility.
BACK_ANCHORS = {
    "C1": (103.5,108), "C2": (103.5,114), "C3": (122,105),
    "C4": (114.3,107), "C5": (113,115), "C6": (122.8,116.8),
    "C7": (114.3,103.9), "FB1": (124.5,106.8), "C8": (124.5,108.5), "C9": (124.5,110.2),
    "C14": (123.7,113.4), "R7": (112.8,112), "R8": (112.8,113.7), "R9": (124,111.9),
    "R1": (103,106), "R2": (105,106), "R3": (102.5,116), "C13": (102.5,118),
    "R4": (108.7,117), "R5": (113.8,106.8), "R31": (109,115),
    "R27": (107,120.5), "R28": (110,120.5), "R29": (109,118.7), "R30": (125.5,102),
    "J6": (103,120.8), "J5": (124,101.2), "D6": (126,104.5),
    "R25": (126,106.8), "R26": (126,108.3),
    "TP1": (106,104), "TP6": (110.5,113.9), "TP7": (110,108),
    "R10": (129,106.2), "R11": (129,108), "R12": (129,109.8),
    "R13": (128,101.3), "R14": (128,103), "R15": (129,104.6), "R16": (129,111.4),
    "R17": (115,107), "R18": (118,107), "R19": (121,107), "R20": (124,103),
    "R21": (115,115), "R22": (118,115), "R23": (121,115), "R24": (124.5,119.8),
    "R32": (136.2,102), "R33": (136.2,107), "R34": (136.2,111.7), "R35": (136.2,119.8),
    "R36": (131,114), "R37": (131,119), "R38": (129,113.3),
    "C15": (130,111.5), "C16": (136.3,113.5), "C17": (130,116), "C18": (136.3,118.5),
}


def bounds(fp, side):
    layer = pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd
    boxes = [i.GetBoundingBox() for i in fp.GraphicalItems() if i.GetLayer() == layer]
    if not boxes:
        boxes = [p.GetBoundingBox() for p in fp.Pads()]
    return (min(pc.to_mm(b.GetLeft()) for b in boxes), min(pc.to_mm(b.GetTop()) for b in boxes),
            max(pc.to_mm(b.GetRight()) for b in boxes), max(pc.to_mm(b.GetBottom()) for b in boxes))


def overlaps(a,b, gap=0.08):
    return a[0] < b[2]+gap and a[2] > b[0]-gap and a[1] < b[3]+gap and a[3] > b[1]-gap


def place_all(comps):
    # Keep an independent actual-footprint collision check in the build.
    scratch = pcbnew.BOARD()
    scratch.GetDesignSettings().SetCopperLayerCount(4)
    fps = {}
    occupied = {"F": [], "B": []}
    for ref,(x,y,rot,side) in PLACEMENT.items():
        fp=pc.load_footprint(comps[ref]["footprint"])
        scratch.Add(fp)
        fp.SetPosition(pt(x,y))
        if side=="B": fp.Flip(fp.GetPosition(),False)
        fp.SetOrientationDegrees(rot)
        fps[ref]=fp
        box=bounds(fp,side)
        occupied[side].append((ref,box))
        if ref=='J2': occupied['B'].append((ref,bounds(fp,'B')))
        for pad in fp.Pads():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                bb=pad.GetBoundingBox()
                b=(pc.to_mm(bb.GetLeft())-.2,pc.to_mm(bb.GetTop())-.2,
                   pc.to_mm(bb.GetRight())+.2,pc.to_mm(bb.GetBottom())+.2)
                occupied['B' if side=='F' else 'F'].append((ref+' hole',b))
    for side, entries in occupied.items():
        for i,(ref,a) in enumerate(entries):
            for ref2,b in entries[i+1:]:
                if ref==ref2: continue
                if overlaps(a,b,0): raise ValueError(f'{side} fixed overlap {ref}/{ref2}: {a} / {b}')
    occupied['B'].append(('USB corridor',(107.6,108.7,113.0,114.0)))
    occupied['B'].append(('Header labels',(135.75,103.8,138.6,118.3)))
    occupied['B'].append(('Top GPIO labels',(112.9,100.1,122.8,100.9)))
    occupied['B'].append(('Bottom GPIO labels',(112.9,121.1,122.8,121.9)))
    order = sorted(BACK_ANCHORS, key=lambda ref: 0 if ref in ('C3','C4','C5','C6','C7','C8','C9','C14','FB1','TP6','TP7') else (1 if ref.startswith(('D','J')) else 2))
    for ref in order:
        x,y = BACK_ANCHORS[ref]
        fp=pc.load_footprint(comps[ref]['footprint'])
        scratch.Add(fp)
        fp.Flip(fp.GetPosition(),False)
        best=None
        # Fixed spacing, no scaling/shrinking; score prioritises local placement.
        for rot in (0,90):
            fp.SetOrientationDegrees(rot)
            fp.SetPosition(pt(0,0))
            bb=bounds(fp,'B')
            for ix in range(-40,41):
                for iy in range(-40,41):
                    xx,yy=x+ix*.2,y+iy*.2
                    b=(bb[0]+xx,bb[1]+yy,bb[2]+xx,bb[3]+yy)
                    if b[0]<X0+.4 or b[2]>X1-.4 or b[1]<Y0+.4 or b[3]>Y1-.4: continue
                    if any(overlaps(b,ob) for owner,ob in occupied['B']
                           if not (owner=='USB corridor' and ref in ('TP6','TP7'))): continue
                    score=ix*ix+iy*iy+(0.1 if rot else 0)
                    if best is None or score<best[0]: best=(score,xx,yy,rot,b)
        if best is None: raise ValueError(f'No legal back placement for {ref}')
        _,xx,yy,rot,box=best
        PLACEMENT[ref]=(round(xx,3),round(yy,3),rot,'B')
        occupied['B'].append((ref,box))
        if abs(xx-x)+abs(yy-y)>3:
            print(f'Placement review: {ref} moved from ({x},{y}) to ({xx:.1f},{yy:.1f})')
    assert set(PLACEMENT)==set(comps), (set(comps)-set(PLACEMENT),set(PLACEMENT)-set(comps))


SILK_TEXTS = [
    ("ailink", 109.4,104,1.1,"F"), ("PWR",104,101.3,.7,"F"),
    ("STATUS",104,121.4,.7,"F"), ("IO 3V3",109,120,.7,"F"),
    ("UART",135,101.3,.8,"F"), (REVISION,128,120.5,.7,"F"),
]
PIN_LABELS = []
for face, dx in (("F", -7), ("B", -3.1)):
    for pin, _net, pin_face, label in J2_PINS:
        if pin_face == face:
            PIN_LABELS.append(("J2", str(pin), label, dx, 0, face))
for ref,start,dy in (("J3",0,2.1),("J4",4,-2.1)):
    for i in range(4):
        for side in ("F","B"):
            offset = dy if side == 'F' else (-1.3 if ref == 'J3' else 1.37)
            PIN_LABELS.append((ref,str(i+1),f'G{start+i}',0,offset,side))


def build():
    # NewBoard can rewrite the companion project with KiCad defaults.
    # Preserve the project's declared rules and net classes explicitly.
    from pathlib import Path
    project = Path(pc.PCB).with_suffix('.kicad_pro')
    project_text = project.read_text()
    board = pcbnew.NewBoard(pc.PCB)
    project.write_text(project_text)
    bds = board.GetDesignSettings()
    bds.SetCopperLayerCount(4)
    bds.SetBoardThickness(mm(1.6))
    # sensible manufacturing minimums (JLC 4-layer capable)
    bds.m_TrackMinWidth = mm(0.15)
    bds.m_ViasMinSize = mm(0.45)
    bds.m_MinThroughDrill = mm(0.3)
    bds.m_HoleClearance = mm(0.25)
    bds.m_MinClearance = mm(0.15)
    bds.m_CopperEdgeClearance = mm(0.3)

    # ---- outline: rounded rect ----
    r = CORNER_R
    segs = [
        ((X0 + r, Y0), (X1 - r, Y0)),
        ((X1, Y0 + r), (X1, Y1 - r)),
        ((X1 - r, Y1), (X0 + r, Y1)),
        ((X0, Y1 - r), (X0, Y0 + r)),
    ]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)
    arcs = [  # start, mid, end (clockwise corners)
        ((X0, Y0 + r), (X0 + r * 0.2929, Y0 + r * 0.2929), (X0 + r, Y0)),
        ((X1 - r, Y0), (X1 - r * 0.2929, Y0 + r * 0.2929), (X1, Y0 + r)),
        ((X1, Y1 - r), (X1 - r * 0.2929, Y1 - r * 0.2929), (X1 - r, Y1)),
        ((X0 + r, Y1), (X0 + r * 0.2929, Y1 - r * 0.2929), (X0, Y1 - r)),
    ]
    for a, m_, b in arcs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(pt(*a), pt(*m_), pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)

    # ---- nets ----
    comps, nets = pc.load_netlist()
    place_all(comps)
    netmap = {}
    for name in sorted(nets):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netmap[name] = ni
    pad2net = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            pad2net[(ref, pin)] = name

    # ---- footprints ----
    missing = []
    for ref, meta in sorted(comps.items()):
        if ref not in PLACEMENT:
            missing.append(ref)
            continue
        x, y, rot, side = PLACEMENT[ref]
        fp = pc.load_footprint(meta["footprint"])
        fp.SetFPID(pcbnew.LIB_ID(*meta["footprint"].split(":",1)))
        fp.SetReference(ref)
        fp.SetValue(meta["value"])
        board.Add(fp)
        fp.SetPosition(pt(x, y))
        if side == "B":
            fp.Flip(fp.GetPosition(), False)
        fp.SetOrientationDegrees(rot)
        # bind nets
        for pad in fp.Pads():
            key = (ref, str(pad.GetNumber()))
            if key in pad2net:
                pad.SetNet(netmap[pad2net[key]])
        # tidy reference text
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        fp.Reference().SetTextThickness(mm(0.13))
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        pc.sync_footprint(board, fp, meta)
    if missing:
        print("WARNING: no placement for:", missing)

    # ---- silk texts ----
    for text, x, y, size, side in SILK_TEXTS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(pt(x, y))
        t.SetLayer(pcbnew.F_SilkS if side=="F" else pcbnew.B_SilkS)
        t.SetMirrored(side=="B")
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(max(0.12, size * 0.15)))
        board.Add(t)
    # per-pin labels
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for jref, pad_no, text, dx, dy, side in PIN_LABELS:
        fp = fps.get(jref)
        if not fp:
            continue
        pad = next(p for p in fp.Pads() if str(p.GetNumber()) == pad_no)
        pos = pad.GetPosition()
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(pcbnew.VECTOR2I(pos.x + mm(dx), pos.y + mm(dy)))
        t.SetLayer(pcbnew.F_SilkS if side=="F" else pcbnew.B_SilkS)
        t.SetMirrored(side=="B")
        t.SetTextSize(pcbnew.VECTOR2I(mm(0.7), mm(0.7)))
        t.SetTextThickness(mm(0.13))
        board.Add(t)

    board.BuildListOfNets()
    pcbnew.SaveBoard(pc.PCB, board)
    project.write_text(project_text)
    print(f"saved {pc.PCB}: {len(list(board.GetFootprints()))} footprints, "
          f"{board.GetNetCount()} nets")
    return board


if __name__ == "__main__":
    build()
