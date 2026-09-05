#!/usr/bin/env bash
# Review exports are available even on failure. Fabrication exports require clean checks.
set -euo pipefail
cd "$(dirname "$0")/.."
SCH=hardware/ailink.kicad_sch
PCB=hardware/ailink.kicad_pcb
OUT=outputs
MODE="${1:-review}"
if [[ "$MODE" != review && "$MODE" != fabrication ]]; then
    echo 'Usage: scripts/export_all.sh [review|fabrication]' >&2
    exit 2
fi
mkdir -p "$OUT/renders" "$OUT/pcb-pdf"
# Remove stale fabrication archives before evaluating the current revision.
rm -f "$OUT/ailink-fab.zip" "$OUT/ailink-gerbers.zip"
rm -rf "$OUT/gerbers" "$OUT/assembly"
status=0
python3 scripts/verify_netlist.py > "$OUT/netlist-check.txt" || status=1
kicad-cli sch erc --severity-all --exit-code-violations --format report \
    -o "$OUT/erc-report.txt" "$SCH" || status=1
kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --save-board \
    --exit-code-violations --format json -o "$OUT/drc-report.json" "$PCB" || status=1
kicad-cli pcb drc --severity-all --schematic-parity --format report \
    -o "$OUT/drc-report.txt" "$PCB"
python3 scripts/si_check.py "$PCB" > "$OUT/si-report.txt" || status=1
python3 scripts/check_product.py > "$OUT/product-check.txt" || status=1

kicad-cli sch export pdf -o "$OUT/ailink-schematic.pdf" "$SCH"
pdftoppm -png -r 150 "$OUT/ailink-schematic.pdf" "$OUT/ailink-schematic"
kicad-cli sch export netlist --format kicadsexpr -o "$OUT/ailink.net" "$SCH"
kicad-cli sch export bom --fields 'Reference,Value,Footprint,MPN,Spec,${QUANTITY},${DNP}' \
    --labels 'Refs,Value,Footprint,MPN,Spec,Qty,DNP' --group-by Value,Footprint,MPN,Spec \
    -o "$OUT/ailink-bom.csv" "$SCH"
kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp \
    --use-drill-file-origin -o "$OUT/ailink-positions.csv" "$PCB"
layers=('F.Cu' 'In1.Cu' 'In2.Cu' 'B.Cu' 'F.SilkS,F.Mask' 'B.SilkS,B.Mask')
files=('01-F_Cu' '02-In1_GND' '03-In2_PWR' '04-B_Cu' '05-F_Silk' '06-B_Silk')
for i in "${!layers[@]}"; do
    kicad-cli pcb export pdf --layers "${layers[i]},Edge.Cuts" \
        -o "$OUT/pcb-pdf/${files[i]}.pdf" "$PCB"
done
kicad-cli pcb render --side top --quality high --use-board-stackup-colors \
    -w 2000 -h 1200 --background opaque -o "$OUT/renders/render-top.png" "$PCB"
kicad-cli pcb render --side bottom --quality high --use-board-stackup-colors \
    -w 2000 -h 1200 --background opaque -o "$OUT/renders/render-bottom.png" "$PCB"
kicad-cli pcb render --rotate '-35,0,25' --zoom .85 --perspective --quality high \
    --use-board-stackup-colors -w 2000 -h 1400 --background opaque \
    -o "$OUT/renders/render-iso-front.png" "$PCB"
kicad-cli pcb render --rotate '145,0,205' --zoom .85 --perspective --quality high \
    --use-board-stackup-colors -w 2000 -h 1400 --background opaque \
    -o "$OUT/renders/render-iso-back.png" "$PCB"
python3 scripts/render_layout.py
python3 - "$status" <<'PY'
import hashlib,json,pathlib,sys
files=['hardware/ailink.kicad_sch','hardware/ailink.kicad_pcb','hardware/ailink.kicad_pro']
pathlib.Path('outputs/verification.json').write_text(json.dumps({
    'revision':'v0.4', 'digital_checks_passed':sys.argv[1]=='0',
    'production_qualified':False,
    'sha256':{p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in files}
},indent=2)+'\n')
PY
if (( status != 0 )); then
    echo 'Review exports written; digital checks failed. Fabrication outputs withheld.' >&2
    exit 1
fi
if [[ "$MODE" == fabrication ]]; then
    mkdir -p "$OUT/gerbers" "$OUT/assembly"
    kicad-cli pcb export gerbers --use-drill-file-origin --check-zones \
        --layers 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,F.Paste,B.Paste,Edge.Cuts' \
        -o "$OUT/gerbers/" "$PCB"
    kicad-cli pcb export drill --drill-origin plot --excellon-separate-th \
        --generate-map --map-format pdf --generate-report \
        --report-path "$OUT/gerbers/ailink-drill-report.txt" -o "$OUT/gerbers/" "$PCB"
    cp "$OUT/ailink-bom.csv" "$OUT/ailink-positions.csv" "$OUT/assembly/"
    (cd "$OUT" && zip -qr ailink-fab.zip gerbers assembly FAB-NOTES.md verification.json)
fi
echo "Current review exports written to $OUT/; see FAB-NOTES.md for physical qualification."
