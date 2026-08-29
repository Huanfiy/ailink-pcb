#!/bin/bash
# Full deterministic PCB build: placement -> USB pair -> planes -> power
# fanout -> A* signal routing -> outer pours.
set -e
cd "$(dirname "$0")/.."
PY="python3"
FILTER='rg -v "assert|leak|Debug"'

echo "=== 1. board + placement ==="
$PY scripts/gen_pcb.py 2>&1 | rg -v "assert|leak|Debug" | tail -1
echo "=== 2. USB differential pair ==="
$PY scripts/route_usb.py 2>&1 | rg -v "assert|leak|Debug" | tail -2
echo "=== 3. inner planes ==="
$PY scripts/post_route.py zones-inner 2>&1 | rg -v "assert|leak|Debug" | tail -1
echo "=== 4. power fanout (auto) ==="
$PY scripts/fanout_power.py 2>&1 | rg -v "assert|leak|Debug" | tail -3
echo "=== 5. power fanout (MCU pairs) ==="
$PY scripts/fanout_mcu.py 2>&1 | rg -v "assert|leak|Debug" | tail -1

echo "=== 6. A* signal routing ==="
NETS=(
  TGPIO5 FLASH_CS TGPIO1 TGPIO0 SPI2_SCK SPI2_MOSI SPI2_MISO
  FLASH_HOLD FLASH_WP MCU_SWCLK MCU_SWDIO OSC_IN OSC_XO OSC_OUT
  TGPIO7 TGPIO2 TGPIO6 TGPIO3 TGPIO4
  T_SWDIO T_SWCLK T_nRESET B_TX B_RX A_TX A_RX CON_TX CON_RX
  VCAP BOOT1 BOOT0 NRST LED1 LED2 LED3 RGB_RK RGB_GK RGB_BK PWRLED
  CC1 CC2 SHIELD VBUS_P VBUS VDDA
  T_SWCLK_J T_SWDIO_J T_nRESET_J A_TX_J A_RX_J B_TX_J B_RX_J
  CON_TX_J CON_RX_J
  TGPIO0_J TGPIO1_J TGPIO2_J TGPIO3_J TGPIO4_J TGPIO5_J TGPIO6_J TGPIO7_J
)
FAILED=()
for n in "${NETS[@]}"; do
  if ! $PY scripts/astar_router.py --route "$n" 2>/dev/null | rg -q "OK"; then
    FAILED+=("$n")
    echo "  pass1 FAILED: $n"
  fi
done
echo "pass1 failed: ${FAILED[*]:-none}"

# pass 2: retry stragglers (later nets may have freed space is not the case,
# but ordering effects sometimes resolve after neighbors exist)
STILL=()
for n in "${FAILED[@]}"; do
  $PY scripts/astar_router.py --rip "$n" >/dev/null 2>&1
  if ! $PY scripts/astar_router.py --route "$n" 2>/dev/null | rg -q "OK"; then
    STILL+=("$n")
    echo "  pass2 FAILED: $n"
  fi
done
echo "pass2 failed: ${STILL[*]:-none}"

echo "=== 7. outer pours ==="
$PY scripts/post_route.py zones-outer 2>&1 | rg -v "assert|leak|Debug" | tail -1
echo "=== pipeline done ==="
