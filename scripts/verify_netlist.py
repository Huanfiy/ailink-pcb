#!/usr/bin/env python3
"""Golden connectivity check: asserts the generated schematic netlist matches
product.md v0.3 (§5.1 pin table + §4 protection topology) exactly."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp

HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hardware")
SCH = os.path.join(HW, "ailink.kicad_sch")
NET = "/tmp/ailink_verify.net"


def load_nets():
    subprocess.run(["kicad-cli", "sch", "export", "netlist",
                    "--format", "kicadsexpr", "-o", NET, SCH],
                   check=True, capture_output=True)
    tree = sexp.parse(open(NET).read())
    nets_node = [x for x in tree if isinstance(x, list) and x and x[0] == "nets"][0]
    nets = {}
    pad2net = {}
    for n in [x for x in nets_node if isinstance(x, list) and x[0] == "net"]:
        name = str([f for f in n if isinstance(f, list) and f[0] == "name"][0][1])
        nodes = set()
        for f in [x for x in n if isinstance(x, list) and x[0] == "node"]:
            ref = str([q for q in f if isinstance(q, list) and q[0] == "ref"][0][1])
            pin = str([q for q in f if isinstance(q, list) and q[0] == "pin"][0][1])
            nodes.add((ref, pin))
            pad2net[(ref, pin)] = name
        nets[name] = nodes
    return nets, pad2net


FAIL = []


def expect(nets, pad2net, netname, *pads):
    """Assert every pad is on net `netname`."""
    for p in pads:
        ref, pin = p.split("-", 1)
        actual = pad2net.get((ref, pin))
        if actual != netname:
            FAIL.append(f"{p}: expected net '{netname}', got '{actual}'")


def expect_nc(pad2net, *pads):
    for p in pads:
        ref, pin = p.split("-", 1)
        actual = pad2net.get((ref, pin), "<absent>")
        if actual != "<absent>" and not actual.startswith("unconnected-"):
            FAIL.append(f"{p}: expected unconnected, got '{actual}'")


def main():
    nets, pad2net = load_nets()

    # ---- product.md §5.1: MCU pin table ----
    pinmap = {
        "14": "TGPIO2", "15": "TGPIO6", "16": "CON_TX", "17": "CON_RX",
        "20": "T_SWCLK", "21": "T_SWDIO", "22": "T_nRESET",
        "41": "TGPIO7", "42": "B_TX", "43": "B_RX",
        "44": "USB_DM", "45": "USB_DP",
        "46": "MCU_SWDIO", "49": "MCU_SWCLK",
        "26": "TGPIO0", "27": "TGPIO1", "28": "BOOT1",
        "61": "TGPIO3", "62": "TGPIO4", "29": "TGPIO5",
        "33": "FLASH_CS", "34": "SPI2_SCK", "35": "SPI2_MISO",
        "36": "SPI2_MOSI",
        "8": "LED1", "9": "LED2", "10": "LED3",
        "37": "A_TX", "38": "A_RX",
        "5": "OSC_IN", "6": "OSC_OUT",
        "60": "BOOT0", "7": "NRST",
    }
    for pad, net in pinmap.items():
        expect(nets, pad2net, net, f"U1-{pad}")

    # ---- power pins ----
    expect(nets, pad2net, "+3V3", "U1-1", "U1-19", "U1-32", "U1-48", "U1-64")
    expect(nets, pad2net, "GND", "U1-18", "U1-31", "U1-47", "U1-63", "U1-12")
    expect(nets, pad2net, "VDDA", "U1-13", "FB1-2", "C8-1", "C9-1")
    expect(nets, pad2net, "VCAP", "U1-30", "C7-1")
    expect(nets, pad2net, "+3V3", "FB1-1", "C3-1", "C4-1", "C5-1", "C6-1")

    # ---- USB path ----
    expect(nets, pad2net, "USB_DM",
           "U1-44", "J1-A7", "J1-B7", "D1-1", "D1-6", "TP7-1")
    expect(nets, pad2net, "USB_DP",
           "U1-45", "J1-A6", "J1-B6", "D1-3", "D1-4", "TP6-1")
    expect(nets, pad2net, "VBUS",
           "J1-A4", "J1-A9", "J1-B4", "J1-B9", "F1-1", "TP1-1")
    expect(nets, pad2net, "VBUS_P",
           "F1-2", "U3-1", "U3-3", "D1-5", "C1-1")
    # TVS polarity is DIRECTIONAL: D_SMA pad1 = cathode band -> VBUS_P,
    # pad2 = anode -> GND. A reversed part would forward-short VBUS.
    expect(nets, pad2net, "VBUS_P", "D7-1")
    expect(nets, pad2net, "GND", "D7-2")
    expect(nets, pad2net, "CC1", "J1-A5", "R1-1")
    expect(nets, pad2net, "CC2", "J1-B5", "R2-1")
    expect(nets, pad2net, "SHIELD", "J1-SH", "R3-1", "C13-1")
    expect(nets, pad2net, "GND",
           "J1-A1", "J1-A12", "J1-B1", "J1-B12",
           "R1-2", "R2-2", "R3-2", "C13-2", "D1-2")
    expect(nets, pad2net, "+3V3", "U3-5", "C2-1", "TP2-1")
    expect(nets, pad2net, "GND", "U3-2", "C1-2", "C2-2", "TP3-1")

    # ---- crystal ----
    expect(nets, pad2net, "OSC_IN", "U1-5", "X1-3", "C10-1")
    expect(nets, pad2net, "OSC_XO", "X1-1", "R6-1", "C11-1")
    expect(nets, pad2net, "OSC_OUT", "U1-6", "R6-2")
    expect(nets, pad2net, "GND", "X1-2", "X1-4", "C10-2", "C11-2")

    # ---- boot / reset ----
    expect(nets, pad2net, "BOOT0", "U1-60", "R4-1", "SW1-1", "TP5-1")
    expect(nets, pad2net, "BOOT1", "U1-28", "R5-1")
    expect(nets, pad2net, "NRST", "U1-7", "C12-1", "SW2-1", "TP4-1")
    expect(nets, pad2net, "GND", "R4-2", "R5-2", "C12-2", "SW2-2")
    expect(nets, pad2net, "+3V3", "SW1-2")

    # ---- SPI NOR ----
    expect(nets, pad2net, "FLASH_CS", "U1-33", "U2-1", "R7-2")
    expect(nets, pad2net, "SPI2_MISO", "U1-35", "U2-2")
    expect(nets, pad2net, "SPI2_MOSI", "U1-36", "U2-5")
    expect(nets, pad2net, "SPI2_SCK", "U1-34", "U2-6")
    expect(nets, pad2net, "FLASH_WP", "U2-3", "R8-2")
    expect(nets, pad2net, "FLASH_HOLD", "U2-7", "R9-2")
    expect(nets, pad2net, "+3V3", "U2-8", "R7-1", "R8-1", "R9-1", "C14-1")
    expect(nets, pad2net, "GND", "U2-4", "C14-2")

    # ---- LEDs ----
    expect(nets, pad2net, "+3V3", "D8-4", "R30-1")
    expect(nets, pad2net, "RGB_RK", "D8-1", "R27-1")
    expect(nets, pad2net, "RGB_GK", "D8-2", "R28-1")
    expect(nets, pad2net, "RGB_BK", "D8-3", "R29-1")
    expect(nets, pad2net, "LED1", "R27-2", "U1-8")
    expect(nets, pad2net, "LED2", "R28-2", "U1-9")
    expect(nets, pad2net, "LED3", "R29-2", "U1-10")
    expect(nets, pad2net, "PWRLED", "R30-2", "D9-2")
    expect(nets, pad2net, "GND", "D9-1")

    # ---- target interfaces: MCU -> 220R -> ESD+connector ----
    series = [
        # (mcu_net, r_ref, j_net, connector_pad, esd_pad)
        ("T_SWCLK", "R10", "T_SWCLK_J", "J2-2", "D2-1"),
        ("T_SWDIO", "R11", "T_SWDIO_J", "J2-3", "D2-3"),
        ("T_nRESET", "R12", "T_nRESET_J", "J2-4", "D2-4"),
        ("A_TX", "R13", "A_TX_J", "J3-1", "D3-1"),
        ("A_RX", "R14", "A_RX_J", "J3-3", "D3-3"),
        ("B_TX", "R15", "B_TX_J", "J3-2", "D3-4"),
        ("B_RX", "R16", "B_RX_J", "J3-4", "D3-6"),
        ("TGPIO0", "R17", "TGPIO0_J", "J4-1", "D4-1"),
        ("TGPIO1", "R18", "TGPIO1_J", "J4-3", "D4-3"),
        ("TGPIO2", "R19", "TGPIO2_J", "J4-5", "D5-1"),
        ("TGPIO3", "R20", "TGPIO3_J", "J4-7", "D5-3"),
        ("TGPIO4", "R21", "TGPIO4_J", "J4-2", "D4-6"),
        ("TGPIO5", "R22", "TGPIO5_J", "J4-4", "D4-4"),
        ("TGPIO6", "R23", "TGPIO6_J", "J4-6", "D5-6"),
        ("TGPIO7", "R24", "TGPIO7_J", "J4-8", "D5-4"),
        ("CON_TX", "R25", "CON_TX_J", "J5-1", "D6-1"),
        ("CON_RX", "R26", "CON_RX_J", "J5-2", "D6-3"),
    ]
    for mcu_net, r, j_net, j_pad, esd_pad in series:
        expect(nets, pad2net, mcu_net, f"{r}-1")
        expect(nets, pad2net, j_net, f"{r}-2", j_pad, esd_pad)
    expect(nets, pad2net, "GND", "J2-1", "J3-5", "J3-6", "J4-9", "J4-10",
           "J5-3", "D2-2", "D3-2", "D4-2", "D5-2", "D6-2")
    expect(nets, pad2net, "+3V3", "D2-5", "D3-5", "D4-5", "D5-5", "D6-5")

    # ---- J6 self-SWD ----
    expect(nets, pad2net, "+3V3", "J6-1")
    expect(nets, pad2net, "MCU_SWDIO", "J6-2", "U1-46")
    expect(nets, pad2net, "MCU_SWCLK", "J6-3", "U1-49")
    expect(nets, pad2net, "GND", "J6-4")

    # ---- NC pins (ER-10) ----
    expect_nc(pad2net,
              "U1-2", "U1-3", "U1-4", "U1-11", "U1-23", "U1-24", "U1-25",
              "U1-39", "U1-40", "U1-50", "U1-51", "U1-52", "U1-53", "U1-54",
              "U1-55", "U1-56", "U1-57", "U1-58", "U1-59",
              "J1-A8", "J1-B8", "U3-4", "D2-6", "D6-4", "D6-6")

    # ---- no unexpected net merges: all these must be distinct ----
    names = ["+3V3", "GND", "VBUS", "VBUS_P", "VDDA", "VCAP",
             "USB_DP", "USB_DM", "OSC_IN", "OSC_XO", "OSC_OUT",
             "BOOT0", "BOOT1", "NRST"]
    for n in names:
        if n not in nets:
            FAIL.append(f"net '{n}' missing")

    if FAIL:
        print(f"VERIFY FAILED: {len(FAIL)} problems")
        for f in FAIL:
            print("  -", f)
        sys.exit(1)
    print(f"VERIFY OK: all §5.1 pin mappings + topology assertions passed "
          f"({len(nets)} nets)")


if __name__ == "__main__":
    main()
