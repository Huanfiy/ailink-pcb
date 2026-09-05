#!/usr/bin/env python3
"""Project-owned v0.4 connector footprints and TPS2553 DBV symbol.

J2 uses two independent rows of surface pads on opposite board faces.
The nominal 0.64 mm square pins need a centring fixture on a 1.6 mm PCB;
mechanical qualification remains a sample-assembly operation.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "hardware/lib/ailink.pretty"


def product_footprint_id(source):
    """Product variants keep the manufacturer's pad/courtyard geometry."""
    if source.startswith('ailink:'):
        return source
    return 'ailink:Product_' + source.split(':', 1)[1]


def product_variants():
    import pcbnew
    from gen_sch import FP
    sources = set(FP.values()) | {'Capacitor_SMD:C_0402_1005Metric'}
    for source in sorted(sources):
        if source.startswith('ailink:'):
            continue
        library, name = source.split(':', 1)
        fp = pcbnew.FootprintLoad('/usr/share/kicad/footprints/' + library + '.pretty', name)
        product_name = product_footprint_id(source).split(':', 1)[1]
        fp.SetFPID(pcbnew.LIB_ID('ailink', product_name))
        fp.SetLibDescription(fp.GetLibDescription() + '; ailink product: assembly outlines on Fab')
        for item in fp.GraphicalItems():
            if item.GetLayer() == pcbnew.F_SilkS:
                item.SetLayer(pcbnew.F_Fab)
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        if name == 'PinHeader_1x04_P2.54mm_Vertical':
            fp.Models().clear()  # User-solderable holes have no installed connector.
        if name == 'USB_C_Receptacle_HRO_TYPE-C-31-M-12':
            fp.Models().clear()
            model=pcbnew.FP_3DMODEL()
            model.m_Filename='${KIPRJMOD}/lib/ailink.3dshapes/USB_C_HRO_envelope.wrl'
            fp.Models().push_back(model)
        pcbnew.FootprintSave(str(LIB), fp)


def usb_envelope():
    """Illustrative envelope, not vendor MCAD or a tolerance-qualified model."""
    dest=ROOT/'hardware/lib/ailink.3dshapes'
    dest.mkdir(exist_ok=True)
    shapes=[]
    def box(x,y,z,sx,sy,sz,color):
        shapes.append(f'Transform {{ translation {x} {y} {z} children [ Shape {{ '
                      f'appearance Appearance {{ material Material {{ diffuseColor {color} '
                      'specularColor 0.5 0.5 0.5 shininess 0.6 }} '
                      f'geometry Box {{ size {sx} {sy} {sz} }} }} ] }}')
    silver='0.65 0.67 0.69'
    box(0,0,3.05,8.94,7.3,.3,silver)
    box(0,0,.15,8.94,7.3,.3,silver)
    box(-4.32,0,1.6,.3,7.3,2.6,silver)
    box(4.32,0,1.6,.3,7.3,2.6,silver)
    box(0,3.5,1.6,8.34,.3,2.6,silver)
    box(0,.4,1.6,6.6,5.5,.7,'0.07 0.07 0.07')
    for i in range(12):box(-2.75+i*.5,-.5,1.99,.25,3.3,.08,'0.75 0.6 0.25')
    (dest/'USB_C_HRO_envelope.wrl').write_text(
        '#VRML V2.0 utf8\n# Illustrative HRO envelope; use vendor drawings for mechanical qualification.\n'
        'Transform { scale 0.3937007874 0.3937007874 0.3937007874 children [\n'+
        '\n'.join(shapes)+'\n] }\n')


def header():
    parts = ['(footprint "Header_2x06_P2.54mm_Straddle" (version 20241229) (generator pcbnew)',
             ' (layer "F.Cu") (attr smd exclude_from_pos_files)',
             ' (descr "2x6 straight square-pin straddle header; 1.6mm PCB; fixture required")',
             ' (property "Reference" "J" (at -5 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             ' (property "Value" "2x6 STRADDLE" (at 1.27 9) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))']
    for side in ('F', 'B'):
        parts += [f' (fp_rect (start -4.2 -8) (end 2.79 8) (stroke (width 0.05) (type solid)) (fill none) (layer "{side}.CrtYd"))',
                  f' (fp_rect (start 0 -7.62) (end 2.54 7.62) (stroke (width 0.1) (type solid)) (fill none) (layer "{side}.Fab"))']
    for col in range(6):
        y = -6.35 + col * 2.54
        for row, side in enumerate(('F', 'B')):
            pin = 1 + col * 2 + row
            # Paste is intentionally absent: SMT first, fixture-solder header last.
            parts.append(f' (pad "{pin}" smd roundrect (at -1.8 {y:.2f}) (size 2.6 1.3) '
                         f'(layers "{side}.Cu" "{side}.Mask") (roundrect_rratio 0.15))')
    parts.append(' (model "${KICAD10_3DMODEL_DIR}/Connector_PinHeader_2.54mm.3dshapes/PinHeader_2x06_P2.54mm_Vertical.step" '
                 '(offset (xyz 0 6.35 0.47)) (scale (xyz 1 1 1)) (rotate (xyz 0 -90 0)))')
    parts.append(')')
    return '\n'.join(parts) + '\n'


def contacts(name, rows, cols):
    parts = [f'(footprint "{name}" (version 20241229) (generator pcbnew)',
             ' (layer "F.Cu") (attr smd exclude_from_pos_files exclude_from_bom)',
             ' (property "Reference" "J" (at 0 -1.3) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             f' (property "Value" "{name}" (at 0 5) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             f' (fp_rect (start -0.7 -0.7) (end {(cols-1)*1.27+0.7:.2f} {(rows-1)*1.27+0.7:.2f}) '
             '(stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))']
    for row in range(rows):
        for col in range(cols):
            pin = 1 + row * cols + col
            shape = 'rect' if pin == 1 else 'circle'
            parts.append(f' (pad "{pin}" smd {shape} (at {col*1.27:.2f} {row*1.27:.2f}) '
                         '(size 0.9 0.9) (layers "F.Cu" "F.Mask"))')
    parts.append(')')
    return '\n'.join(parts) + '\n'


def switch_symbol():
    # TI SLVS841F p5: DBV 1=IN,2=GND,3=EN,4=FAULT,5=ILIM,6=OUT.
    pins = [('IN', 1, 'power_in', -10.16, 5.08, 0),
            ('GND', 2, 'power_in', 0, -10.16, 90),
            ('EN', 3, 'input', -10.16, 0, 0),
            ('~{FAULT}', 4, 'open_collector', 10.16, 0, 180),
            ('ILIM', 5, 'passive', 10.16, -5.08, 180),
            ('OUT', 6, 'power_out', 10.16, 5.08, 180)]
    parts = ['(symbol "TPS2553DBV" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
             ' (property "Reference" "U" (at 0 10.16 0) (effects (font (size 1.27 1.27))))',
             ' (property "Value" "TPS2553DBV" (at 0 7.62 0) (effects (font (size 1.27 1.27))))',
             ' (property "Footprint" "Package_TO_SOT_SMD:SOT-23-6" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
             ' (property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps2553.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
             ' (symbol "TPS2553DBV_0_1" (rectangle (start -7.62 7.62) (end 7.62 -7.62) (stroke (width 0.254) (type default)) (fill (type background))))',
             ' (symbol "TPS2553DBV_1_1"']
    for name, number, kind, x, y, angle in pins:
        parts.append(f'  (pin {kind} line (at {x} {y} {angle}) (length 2.54) '
                     f'(name "{name}" (effects (font (size 1.27 1.27)))) '
                     f'(number "{number}" (effects (font (size 1.27 1.27)))))')
    parts.append(' ))')
    return '\n'.join(parts)


def main():
    LIB.mkdir(parents=True, exist_ok=True)
    (LIB/'Header_2x06_P2.54mm_Straddle.kicad_mod').write_text(header())
    (LIB/'Service_2x03_P1.27mm.kicad_mod').write_text(contacts('Service_2x03_P1.27mm', 3, 2))
    (LIB/'Console_1x03_P1.27mm.kicad_mod').write_text(contacts('Console_1x03_P1.27mm', 1, 3))
    usb_envelope()
    product_variants()
    # Merge into the existing project library without replacing the Flash symbol.
    import sexp
    from sexp import Sym, find_all, dumps
    dest = ROOT/'hardware/lib/ailink.kicad_sym'
    lib = sexp.parse(dest.read_text())
    for sym in list(find_all(lib, 'symbol')):
        if str(sym[1]) == 'TPS2553DBV':
            lib.remove(sym)
    lib.append(sexp.parse(switch_symbol()))
    dest.write_text(dumps(lib)+'\n')
    print('v0.4 project footprints and TPS2553 DBV symbol generated')


if __name__ == '__main__':
    main()
