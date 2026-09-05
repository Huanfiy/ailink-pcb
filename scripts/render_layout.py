#!/usr/bin/env python3
"""Render the product layout from actual PCB positions, without routing copper."""
from pathlib import Path
import xml.etree.ElementTree as ET

import pcbnew
import pcb_common as pc
from product_config import X0, Y0, X1, Y1, HEADER_Y

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
SCALE = 12


def element(parent, tag, **attrs):
    return ET.SubElement(parent, '{'+NS+'}'+tag,
                         {key.replace('_', '-'): str(value) for key, value in attrs.items()})


def label(parent, x, y, value, size=15, color='#42566b', anchor='start', **attrs):
    e = element(parent, 'text', x=x, y=y, fill=color, font_size=size,
                text_anchor=anchor, **attrs)
    e.text = value
    return e


def main():
    board = pcbnew.LoadBoard(pc.PCB)
    root = ET.Element('{'+NS+'}svg', width='1600', height='780', viewBox='0 0 1600 780',
                      role='img', attrib={'aria-labelledby': 'title desc'})
    element(root, 'title', id='title').text = 'ailink v0.4 A 方案 · 实际 PCB 正反面布局'
    element(root, 'desc', id='desc').text = (
        '同一块 42×22 mm 四层产品板。USB 在左，2×6 夹板针在右。'
        '正面为双 UART 和逐针对齐的四颗通信灯；PWR、STATUS 在 USB 座两侧。'
        '背面沿长轴翻面显示 SWD、电源、D1 USB ESD、Flash 及维护触点。'
        '长边各四个可选焊接 GPIO 孔，无 BOOT 或 RST 按键。元件中心和焊盘来自 PCB，器件本体为示意。')
    element(root, 'style').text = 'text{font-family:"Noto Sans CJK SC","DejaVu Sans",sans-serif}'
    element(root, 'rect', width=1600, height=780, fill='#f5f7fa')
    label(root, 60, 45, 'ailink · 产品版布局', 29, '#172838', font_weight=700)
    label(root, 1530, 44, 'v0.4 / 42 × 22 mm / 无用户按键', 17, anchor='end')
    copper = '#cfb574'
    bodies = {'U1': (10,10), 'U2': (5.3,5.2), 'U3': (1.7,2.9),
              'D7': (4.5,2.6), 'D8': (3.2,2.7), 'F1': (3.2,1.6), 'X1': (3.2,2.5)}
    names = {'U1': 'STM32F446', 'U2': 'FLASH', 'U3': 'LDO', 'U4': 'U4', 'U5': 'U5',
             'D1': 'D1', 'D2': 'D2', 'D3': 'D3', 'D4': 'D4', 'D5': 'D5',
             'D6': 'D6', 'D7': 'TVS', 'F1': 'F1', 'X1': 'HSE'}
    for side, ox in [('F',60), ('B',830)]:
        oy=185
        front=side=='F'
        layer=pcbnew.F_Cu if front else pcbnew.B_Cu
        def project(x,y):
            return ox+(x-X0)*SCALE, oy+((y-Y0) if front else (Y1-y))*SCALE
        def rect(x,y,w,h,fill,**attrs):
            px,py=project(x,y)
            return element(root,'rect',x=px-w*SCALE/2,y=py-h*SCALE/2,
                           width=w*SCALE,height=h*SCALE,fill=fill,**attrs)
        label(root,ox,104,'A 方案 · '+('正面' if front else '背面'),23,'#172838',font_weight=700)
        label(root,ox,136,'双 UART · TX/RX 指示灯正对针位' if front else 'SWD / 电源 · 沿长轴翻面，USB 保持在左',16)
        element(root,'path',d=f'M {ox} 177 V 157 H {ox+42*SCALE} V 177',
                fill='none',stroke='#8191a3')
        label(root,ox+21*SCALE,151,'42 mm',14,anchor='middle')
        element(root,'rect',x=ox,y=oy,width=42*SCALE,height=22*SCALE,
                rx=2*SCALE,fill='#1c2b30',stroke='#53656b',stroke_width=2,
                id=side+'-board',data_width_mm=42,data_height_mm=22)
        if not front:
            rect(103.6,111,8.6,9.0,'none',stroke='#6c8188',stroke_dasharray='5 5')
            rect(118.5,111,10,10,'none',stroke='#577078',stroke_dasharray='5 5')
        # Header plastic and outward mating pins are illustrative; PCB pads are exact.
        rect(143.27,111,2.54,15.24,'#182029',rx=2)
        for y in HEADER_Y:
            px,py=project(142,y); qx,_=project(150.5,y)
            element(root,'path',d=f'M {px-2.8*SCALE} {py} H {qx}',
                    stroke='#d5bf85',stroke_width=.64*SCALE)
        for fp in board.GetFootprints():
            ref=fp.GetReference()
            for pad in fp.Pads():
                if not pad.IsOnLayer(layer):continue
                pos=pad.GetPosition();x,y=pc.to_mm(pos.x),pc.to_mm(pos.y)
                bb=pad.GetBoundingBox();w,h=pc.to_mm(bb.GetWidth()),pc.to_mm(bb.GetHeight())
                px,py=project(x,y)
                if pad.GetShape()==pcbnew.PAD_SHAPE_CIRCLE:
                    element(root,'circle',cx=px,cy=py,r=w*SCALE/2,fill=copper)
                else:
                    rect(x,y,w,h,copper,rx=min(w,h)*SCALE*.15)
                if pad.GetDrillSize().x:
                    ds=pad.GetDrillSize();dw,dh=pc.to_mm(ds.x),pc.to_mm(ds.y)
                    if abs(dw-dh)<.01:
                        element(root,'circle',cx=px,cy=py,r=dw*SCALE/2,fill='#f5f7fa')
                    else:rect(x,y,dw,dh,'#f5f7fa',rx=min(dw,dh)*SCALE/2)
            if fp.GetLayer()!=layer or ref.startswith(('J','TP')):continue
            pos=fp.GetPosition();x,y=pc.to_mm(pos.x),pc.to_mm(pos.y)
            if ref in bodies:w,h=bodies[ref]
            elif ref.startswith(('D','U')):
                w,h=(1.6,.8) if ref in ('D9','D10','D11','D12','D13') else (1.7,2.9)
            elif ref.startswith('R') or '0402' in str(fp.GetFPID()):w,h=1,.5
            else:w,h=1.6,.8
            if round(fp.GetOrientationDegrees())%180==90:w,h=h,w
            fill='#0b131b'
            if ref.startswith(('C','FB')):fill='#8c7657'
            if ref=='X1':fill='#a4b1b8'
            if ref in ('D9','D11','D13'):fill='#75c799'
            if ref in ('D10','D12'):fill='#e5ad5f'
            if ref=='D8':fill='#a9d4d3'
            item=rect(x,y,w,h,fill,rx=1.5,stroke='#96a3aa',stroke_width=.5,
                      id=side+'-'+ref,data_ref=ref,
                      data_center_x_mm=x-X0,data_center_y_mm=y-Y0)
            element(item,'title').text=ref+' '+fp.GetValue()
            if ref in names:
                px,py=project(x,y)
                label(root,px,py+3,names[ref],10 if ref!='U1' else 15,
                      '#e2eaf0' if ref!='X1' else '#172838',anchor='middle')
        if front:
            # Connector body in physical front projection, opening at the left edge.
            rect(103.6,111,7.3,8.94,'#c5ced4',rx=5,stroke='#788b99',stroke_width=1)
            rect(100.45,111,.7,7.5,'#25333d',rx=2)
            px,py=project(103.6,111)
            label(root,px,py+5,'USB-C',13,'#344a5a',anchor='middle')
        for item in board.GetDrawings():
            if item.GetClass()!='PCB_TEXT':continue
            if item.GetLayer()!=(pcbnew.F_SilkS if front else pcbnew.B_SilkS):continue
            pos=item.GetPosition();px,py=project(pc.to_mm(pos.x),pc.to_mm(pos.y))
            label(root,px,py+3,item.GetText(),max(9,pc.to_mm(item.GetTextHeight())*SCALE),
                  '#e3edf0',anchor='middle')
        labels=('ATX','ARX','GND','BTX','BRX','GND') if front else ('GND','CLK','DIO','nRST','3V3','5V')
        for i,(y,name) in enumerate(zip(HEADER_Y,labels)):
            px,py=project(151,y)
            label(root,px,py+4,f'{i*2+(1 if front else 2):2}  {name}',12,'#334b60')
    label(root,60,483,'器件中心与焊盘来自当前 PCB；省略走线。本体、USB 外壳和夹板针为外观示意。',16)
    cards=[(60,'正面：使用与识别',[
        'USB 座上侧 PWR，下侧 RGB STATUS',
        'ATX / ARX / BTX / BRX 四灯与针脚对齐',
        '两条长边各 4 个 GPIO 孔，出厂不装排针']),
        (560,'背面：电源与保护',[
        'D1：USB ESD；U2：独立 Flash',
        'U4：3.3 V / 100 mA；U5：5 V / 150 mA（目标值）',
        'SWD、维护触点、固定启动与复位电路']),
        (1060,'结构与电气边界',[
        '42 × 22 mm · 四层 · 1.6 mm · R2',
        '全部信号 3.3 V，5 V 针仅提供电源',
        '夹板针装配、输出额定值及阻抗需验证'])]
    for x,title,lines in cards:
        element(root,'rect',x=x,y=524,width=470,height=166,rx=12,fill='#e8eef3')
        label(root,x+20,557,title,19,'#20384a',font_weight=700)
        for i,line in enumerate(lines):label(root,x+20,591+i*29,line,14)
    label(root,60,739,'前后面表示同一块板。背面上长边为 G4～G7；尾针从上到下为 12、10、8、6、4、2。',16)
    dest=Path(__file__).resolve().parents[1]/'docs/design/layout-options.svg'
    dest.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(root)
    ET.ElementTree(root).write(dest,encoding='unicode')
    print(dest)


if __name__=='__main__':main()
