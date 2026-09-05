#!/usr/bin/env python3
"""Export Specctra DSN for freerouting."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc

import pcbnew

DSN = os.environ.get("AILINK_DSN", "/tmp/ailink.dsn")

board = pcbnew.LoadBoard(pc.PCB)
ok = pcbnew.ExportSpecctraDSN(board, DSN)
if not ok:
    raise RuntimeError("Specctra export failed")

# L2 is always ground-only. L3 may carry internal signals outside the rear
# USB reference window; KiCad refills the remaining 3.3 V pour on import.
inner_signals = os.environ.get("AILINK_INNER_SIGNALS") == "1"
txt = open(DSN).read()
# Specctra's bare quote declaration is not a KiCad string literal. Temporarily
# normalize it before passing the rest of the document through our parser.
txt = txt.replace('(string_quote ")', '(string_quote SPECCTRA_QUOTE)')
for lay in (("In1.Cu",) if inner_signals else ("In1.Cu", "In2.Cu")):
    txt = txt.replace(f"(layer {lay}\n      (type signal)",
                      f"(layer {lay}\n      (type power)")
    txt = txt.replace(f"(layer {lay} (type signal)",
                      f"(layer {lay} (type power)")
# Single-pin NC nets must remain copper obstacles, without pointless fanout.
import sexp
tree = sexp.parse(txt)
structure = sexp.find(tree, 'structure')
if inner_signals:
    structure.append([sexp.Sym('keepout'), 'USB_REAR_REFERENCE',
                      [sexp.Sym('rect'), sexp.Sym('In2.Cu'),
                       105500, -115300, 113600, -106600]])
# Reserve the crystal body projection for the already locked oscillator
# circuit and its ground pads. Unrelated front traces must go around it.
structure.append([sexp.Sym('keepout'), 'HSE_BODY',
                  [sexp.Sym('rect'), sexp.Sym('F.Cu'),
                   126000, -112350, 129200, -109650]])
network = sexp.find_all(tree, 'network')[0]
unused = set()
for net in list(sexp.find_all(network, 'net')):
    pins = sexp.find_all(net, 'pins')
    if not pins or len(pins[0]) <= 2:
        unused.add(str(net[1]))
        network.remove(net)
for group in sexp.find_all(network, 'class'):
    group[:] = [item for item in group if isinstance(item,list) or str(item) not in unused]
    # KiCad netclass widths are preferred widths, not DRC minima. Freerouting
    # treats them as width rules; allow the valid fine-pitch escapes explicitly.
    width = {'POWER':200,'USB_DIFF':250}.get(str(group[1]),150)
    for rule in sexp.find_all(group,'rule'):
        for entry in sexp.find_all(rule,'width'):entry[1]=width
# Preserve the native plane polygons so the router recognizes power fanouts.
# Raw polygons are intentional: KiCad regenerates clearance cutouts on import.
# Through-hole sizes are absent from DSN; final hole checks belong to KiCad.
for item in sexp.find_all(tree, 'wiring')[0][1:]:
    net = sexp.find(item, 'net')
    if net and net[1] in ('GND', '+3V3'):
        kind = sexp.find(item, 'type')
        if kind:
            kind[1] = sexp.Sym('fix')
txt = sexp.dumps(tree)
txt = txt.replace('(string_quote SPECCTRA_QUOTE)', '(string_quote ")')
open(DSN, "w").write(txt)
n_power = txt.count("(type power)")
print("DSN export:", ok, DSN, os.path.getsize(DSN), "power layers:", n_power)
