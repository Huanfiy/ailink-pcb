#!/usr/bin/env bash
# Build an isolated candidate. Never replace a reviewed/routed board implicitly.
set -euo pipefail
cd "$(dirname "$0")/.."
BUILD_DIR="${1:-$(mktemp -d /tmp/ailink-v04-build.XXXXXX)}"
mkdir -p "$BUILD_DIR"
BUILD_DIR="$(realpath "$BUILD_DIR")"
if [[ "$BUILD_DIR" == "$(realpath hardware)" ]]; then
    echo 'Choose an isolated output directory; hardware/ contains the working design.' >&2
    exit 2
fi
cp -a hardware/lib hardware/fp-lib-table hardware/sym-lib-table "$BUILD_DIR/"
cp hardware/ailink.kicad_pro "$BUILD_DIR/"
export AILINK_HW="$BUILD_DIR"
export AILINK_PCB="$BUILD_DIR/ailink.kicad_pcb"
export AILINK_DSN="$BUILD_DIR/ailink.dsn"

python3 scripts/gen_sch.py
python3 scripts/verify_netlist.py
kicad-cli sch erc --severity-all --exit-code-violations \
    -o "$BUILD_DIR/erc-report.txt" "$BUILD_DIR/ailink.kicad_sch"
python3 scripts/gen_pcb.py
python3 scripts/route_usb.py
python3 scripts/route_clock.py
python3 scripts/post_route.py zones-inner
python3 scripts/fanout_mcu_product.py
python3 scripts/fanout_product.py
python3 scripts/stitch_usb.py
python3 scripts/escape_trapped_pads.py
AILINK_INNER_SIGNALS=1 python3 scripts/export_dsn.py
./tools/run-freerouting.sh -de "$AILINK_DSN" -do "$BUILD_DIR/ailink.ses" \
    -mp 35 -mt 2 --gui.enabled=false --router.fanout.enabled=false \
    --router.optimizer.enabled=false > "$BUILD_DIR/router.log" 2>&1
python3 scripts/import_ses.py "$BUILD_DIR/ailink.ses"
python3 scripts/cleanup_routes.py
# L3 may carry internal escapes outside the protected rear USB reference.
route_status=0
AILINK_INNER_SIGNALS=1 python3 scripts/finish_routes.py || route_status=$?
python3 scripts/finish_board.py
python3 scripts/cleanup_routes.py
python3 scripts/si_check.py "$AILINK_PCB" > "$BUILD_DIR/si-report.txt"
kicad-cli pcb drc --severity-all --schematic-parity --exit-code-violations \
    --format json -o "$BUILD_DIR/drc-report.json" "$AILINK_PCB"
if (( route_status != 0 )); then
    echo "Candidate needs routing review: $BUILD_DIR" >&2
    exit "$route_status"
fi
echo "Candidate passed digital checks: $BUILD_DIR. Review before replacing hardware/."
