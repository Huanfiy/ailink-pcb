#!/bin/bash
# Generate every deliverable into outputs/
set -e
cd "$(dirname "$0")/.."
SCH=hardware/ailink.kicad_sch
PCB=hardware/ailink.kicad_pcb
OUT=outputs

mkdir -p "$OUT/renders" "$OUT/gerbers" "$OUT/pcb-pdf"

echo "== schematic PDF =="
kicad-cli sch export pdf -o "$OUT/ailink-schematic.pdf" "$SCH"
pdftoppm -png -r 150 "$OUT/ailink-schematic.pdf" "$OUT/ailink-schematic"

echo "== ERC / DRC reports =="
kicad-cli sch erc --severity-all --format report -o "$OUT/erc-report.txt" "$SCH" || true
kicad-cli pcb drc --severity-all --format report -o "$OUT/drc-report.txt" "$PCB" || true
kicad-cli pcb drc --severity-all --format json -o "$OUT/drc-report.json" "$PCB" || true

echo "== netlist =="
kicad-cli sch export netlist --format kicadsexpr -o "$OUT/ailink.net" "$SCH"

echo "== BOM =="
kicad-cli sch export bom \
  --fields 'Reference,Value,Footprint,${QUANTITY},${DNP}' \
  --labels 'Refs,Value,Footprint,Qty,DNP' \
  --group-by Value,Footprint \
  -o "$OUT/ailink-bom.csv" "$SCH"

echo "== PCB layer PDFs =="
kicad-cli pcb export pdf --layers "F.Cu,Edge.Cuts"      -o "$OUT/pcb-pdf/01-F_Cu.pdf"   "$PCB"
kicad-cli pcb export pdf --layers "In1.Cu,Edge.Cuts"    -o "$OUT/pcb-pdf/02-In1_GND.pdf" "$PCB"
kicad-cli pcb export pdf --layers "In2.Cu,Edge.Cuts"    -o "$OUT/pcb-pdf/03-In2_PWR.pdf" "$PCB"
kicad-cli pcb export pdf --layers "B.Cu,Edge.Cuts"      -o "$OUT/pcb-pdf/04-B_Cu.pdf"   "$PCB"
kicad-cli pcb export pdf --layers "F.SilkS,F.Mask,Edge.Cuts" -o "$OUT/pcb-pdf/05-F_Silk.pdf" "$PCB"
kicad-cli pcb export pdf --layers "B.SilkS,B.Mask,Edge.Cuts" -o "$OUT/pcb-pdf/06-B_Silk.pdf" "$PCB"

echo "== 3D renders =="
kicad-cli pcb render --side top    --quality high -w 2000 -h 1400 --background opaque -o "$OUT/renders/render-top.png"    "$PCB"
kicad-cli pcb render --side bottom --quality high -w 2000 -h 1400 --background opaque -o "$OUT/renders/render-bottom.png" "$PCB"
kicad-cli pcb render --rotate '-35,0,25'  --zoom 0.85 --perspective --quality high -w 2000 -h 1400 --background opaque -o "$OUT/renders/render-iso-front.png" "$PCB"
kicad-cli pcb render --rotate '145,0,205' --zoom 0.85 --perspective --quality high -w 2000 -h 1400 --background opaque -o "$OUT/renders/render-iso-back.png" "$PCB"

echo "== gerbers + drill =="
kicad-cli pcb export gerbers -o "$OUT/gerbers/" "$PCB"
kicad-cli pcb export drill   -o "$OUT/gerbers/" "$PCB"
(cd "$OUT" && zip -qr ailink-gerbers.zip gerbers/)

echo "== done: $(ls $OUT | wc -l) items in $OUT =="
