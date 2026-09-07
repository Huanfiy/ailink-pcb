#!/usr/bin/env python3
"""Generate hardware/ailink.kicad_sch for the ailink board (product.md v0.4)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sch_writer
import symlib
from product_config import J2_PINS
from sch_writer import SchDoc

HW = os.environ.get('AILINK_HW', os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hardware"))
G = 1.27


def g(n):
    """Grid units -> mm."""
    return round(n * G, 4)


# ---------------------------------------------------------------- footprints
FP = {
    "R": "Resistor_SMD:R_0402_1005Metric",
    "C": "Capacitor_SMD:C_0603_1608Metric",
    "MCU": "Package_QFP:LQFP-64_10x10mm_P0.5mm",
    "FLASH": "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
    "LDO": "Package_TO_SOT_SMD:SOT-23-5",
    "SOT236": "Package_TO_SOT_SMD:SOT-23-6",
    "TVS": "Diode_SMD:D_SMA",
    "FUSE": "Fuse:Fuse_1206_3216Metric",
    "FB": "Inductor_SMD:L_0603_1608Metric",
    "XTAL": "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    "USBC": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
    "H1X4": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
    "RGB": "LED_SMD:LED_RGB_1210",
    "LED": "LED_SMD:LED_0603_1608Metric",
    "TP": "TestPoint:TestPoint_Pad_D1.0mm",
    "STRADDLE": "ailink:Header_2x06_P2.54mm_Straddle",
    "SERVICE": "ailink:Service_2x03_P1.27mm",
    "CONSOLE": "ailink:Console_1x03_P1.27mm",
}


def _ps(mpn, spec):
    return {"MPN": mpn, "Spec": spec}


# Production BOM attributes (hidden symbol properties via place(props=...)).
_R220 = _ps("RC0402FR-07220RL", "0402 ±1%")
_R51K = _ps("RC0402FR-075K1L", "0402 ±1%")
_R10K = _ps("RC0402JR-0710KL", "0402 ±5%")
_R620 = _ps("RC0402JR-07620RL", "0402 ±5%")
_R150 = _ps("RC0402JR-07150RL", "0402 ±5%")
_R1K = _ps("RC0402JR-071KL", "0402 ±5%")
_R1M = _ps("RC0402JR-071ML", "0402 ±5%")
_R0 = _ps("RC0402JR-070RL", "0402 0Ω")
_C100N = _ps("CC0402KRX7R7BB104", "0402 X7R 16V")
_C1U = _ps("CL10A105KA8NNNC", "0603 X7R/X5R 25V")
_C22U = _ps("CL10A225KA8NNNC", "0603 X7R/X5R 25V")
_C22U_VCAP = _ps("CL10A225KA8NNNC", "0603 X7R/X5R 25V 低ESR（VCAP）")
_C18P = _ps("C1608C0G1H180J", "0603 C0G/NP0 50V")
_C10N = _ps("CC0603KRX7R9BB103", "0603 X7R 50V")
_SRV = _ps("SRV05-4.TCT", "SOT-23-6 4ch ESD, C~3pF/线")
_HDR14 = _ps("PinHeader 1x4 2.54 直针", "PinHeader 1x4 2.54 直针")

PARTS = {
    "U1": _ps("STM32F446RET6", "LQFP64"),
    "U2": _ps("W25Q64JVSSIQ", "SOIC-8 208mil"),
    "U3": _ps("AP2112K-3.3TRG1", "SOT-23-5 600mA"),
    "D1": _ps("USBLC6-2SC6", "SOT-23-6 超低容USB ESD"),
    "D2": _SRV, "D3": _SRV, "D4": _SRV, "D5": _SRV, "D6": _SRV,
    "D7": _ps("SMAJ5.0A", "SMA 单向TVS 5V/400W"),
    "D8": _ps("FM-B3227RGBA-HG", "国星1210(3227)共阳RGB,装配前按规格书核对1-4脚序"),
    "D9": _ps("KT-0603G", "0603绿色,VF~3V@2mA"),
    "F1": _ps("0ZCJ0075FF2E", "1206 PTC 750mA/6V; temperature derating required"),
    "FB1": _ps("BLM18AG601SN1D", "0603 600R@100MHz"),
    "X1": _ps("YSX321SL-16MHz或TXC 7V等效", "3225 16MHz ±10ppm CL=12pF"),
    "J1": _ps("HRO TYPE-C-31-M-12", "USB-C 16P USB2.0"),
    "J2": _ps("TSW-106-07-L-D", "2x6 2.54mm straight header, straddle fixture; qualify sample"),
    "J6": _ps("PCB contacts", "2x3 1.27mm pogo pads; no component"),
    "J3": _HDR14,
    "J4": _HDR14,
    "J5": _ps("PCB contacts", "3x 1.27mm console pads; no component"),

    "R1": _R51K, "R2": _R51K, "R3": _R1M,
    "R4": _R10K, "R5": _R10K, "R6": _R0,
    "R7": _R10K, "R8": _R10K, "R9": _R10K,
    "R27": _R620, "R28": _R150, "R29": _R150, "R30": _R1K,
    "C1": _C1U, "C2": _C22U,
    "C3": _C100N, "C4": _C100N, "C5": _C100N, "C6": _C100N,
    "C7": _C22U_VCAP, "C8": _C1U, "C9": _C100N,
    "C10": _C18P, "C11": _C18P, "C12": _C100N, "C13": _C10N, "C14": _C100N,
}
PARTS.update({f"R{i}": _R220 for i in range(10, 27)})
PARTS.update({
    "U4": _ps("TPS2553DBVR", "Active-high, auto-retry current limiter with reverse-voltage protection"),
    "U5": _ps("TPS2553DBVR", "Active-high, auto-retry current limiter with reverse-voltage protection"),
    "R31": _R10K,
    "R36": _ps("RC0402FR-07226KL", "226k 1%; 3V3 limit 101..142mA incl resistor tolerance"),
    "R37": _ps("RC0402FR-07147KL", "147k 1%; 5V limit 157..213mA incl resistor tolerance"),
    "R38": _R10K,
})
for i in range(32, 36):
    PARTS[f"R{i}"] = _ps("RC0402FR-071K3L", "1.3k 1%; activity LED approx 1mA")
for i in range(15, 19):
    PARTS[f"C{i}"] = _C100N
for i in range(10, 14):
    PARTS[f"D{i}"] = _ps("LTST-C190KFKT" if i % 2 == 0 else "LTST-C190KGKT",
                           "0603 amber TX" if i % 2 == 0 else "0603 green RX")


def build():
    d = SchDoc("ailink - USB debug bridge (2x CDC + CMSIS-DAP + 8x GPIO + DFU)",
               paper="A2", rev="v0.4", company="ailink project",
               date="2026-09-05")

    _place = d.place

    def place(ref, *args, props=None, **kwargs):
        """Inject MPN/Spec from PARTS when the caller does not pass props."""
        if props is None:
            props = PARTS.get(ref)
        from gen_product_lib import product_footprint_id
        if kwargs.get('footprint'):
            kwargs['footprint'] = product_footprint_id(kwargs['footprint'])
        return _place(ref, *args, props=props, **kwargs)

    d.place = place

    # ---- symbols
    S_R = d.use_symbol("Device", "R")
    S_C = d.use_symbol("Device", "C")
    S_MCU = d.use_symbol("MCU_ST_STM32F4", "STM32F446RETx")
    S_LDO = d.use_symbol("Regulator_Linear", "AP2112K-3.3")
    S_USBC = d.use_symbol("Connector", "USB_C_Receptacle_USB2.0_16P")
    S_USBLC = d.use_symbol("Power_Protection", "USBLC6-2SC6")
    S_SRV = d.use_symbol("Power_Protection", "SRV05-4")
    S_TVS = d.use_symbol("Diode", "SMAJ5.0A")
    S_FUSE = d.use_symbol("Device", "Polyfuse")
    S_FBEAD = d.use_symbol("Device", "FerriteBead")
    S_XTAL = d.use_symbol("Device", "Crystal_GND24")
    S_RGB = d.use_symbol("Device", "LED_RGBA")
    S_LED = d.use_symbol("Device", "LED")
    S_PSW = d.use_symbol("ailink", "TPS2553DBV")
    S_TP = d.use_symbol("Connector", "TestPoint")
    S_C1X3 = d.use_symbol("Connector_Generic", "Conn_01x03")
    S_C1X4 = d.use_symbol("Connector_Generic", "Conn_01x04")
    S_C2X3 = d.use_symbol("Connector_Generic", "Conn_02x03_Odd_Even")
    S_C2X6 = d.use_symbol("Connector_Generic", "Conn_02x06_Odd_Even")
    S_W25 = d.use_symbol(
        "Memory_Flash", "W25Q32JVSS",
        embed_name="ailink:W25Q64JVSSIQ", value="W25Q64JVSSIQ",
        extra_props={
            "Datasheet": "https://www.winbond.com/resource-files/"
                         "w25q64jv%20revj%2003272018%20plus.pdf",
            "Description": "64Mbit SPI NOR Flash, SOIC-8 208mil "
                           "(derived from W25Q32JVSS, same pinout)",
        })

    # ---------------- generic helpers ----------------
    def auto_label(inst, pin, net, shape="bidirectional", stub=2):
        """Stub outward from pin and attach a global label, direction-aware."""
        p0 = inst.pin(pin)
        dx, dy = inst.pin_out_dir(pin)
        p1 = (round(p0[0] + dx * g(stub), 4), round(p0[1] + dy * g(stub), 4))
        d.wire(p0, p1)
        if dx > 0 or (dx == 0 and dy != 0):
            d.label_right(net, p1, shape=shape)
        else:
            d.label_left(net, p1, shape=shape)

    def auto_gnd(inst, pin, stub=2, bend="down"):
        """Stub outward, bend down/up if horizontal, place GND."""
        p0 = inst.pin(pin)
        dx, dy = inst.pin_out_dir(pin)
        p1 = (round(p0[0] + dx * g(stub), 4), round(p0[1] + dy * g(stub), 4))
        d.wire(p0, p1)
        if dy == 1:                      # pointing down already
            d.power("GND", p1[0], p1[1])
        elif dy == -1:                   # pointing up: upside-down GND
            d.power("GND", p1[0], p1[1], rot=180)
        elif bend == "down":
            p2 = (p1[0], round(p1[1] + g(2), 4))
            d.wire(p1, p2)
            d.power("GND", p2[0], p2[1])
        else:                            # bend up: upside-down GND on top
            p2 = (p1[0], round(p1[1] - g(2), 4))
            d.wire(p1, p2)
            d.power("GND", p2[0], p2[1], rot=180)

    def auto_pwr(inst, pin, net="+3V3", stub=2):
        """Stub outward, bend up if horizontal, place power symbol."""
        p0 = inst.pin(pin)
        dx, dy = inst.pin_out_dir(pin)
        p1 = (round(p0[0] + dx * g(stub), 4), round(p0[1] + dy * g(stub), 4))
        d.wire(p0, p1)
        if dy == -1:                     # pointing up
            d.power(net, p1[0], p1[1])
        elif dy == 1:                    # pointing down: rotated power
            d.power(net, p1[0], p1[1], rot=180)
        else:
            p2 = (p1[0], round(p1[1] - g(2), 4))
            d.wire(p1, p2)
            d.power(net, p2[0], p2[1])

    def nc(inst, pin):
        d.no_connect(inst.pin(pin))

    def vert_rc(ref, sym, x, y, value, fp, top, bottom="GND",
                top_shape="passive"):
        """Vertical R/C at (x,y): pin1 up -> top net, pin2 down -> bottom."""
        inst = d.place(ref, sym, x, y, rot=0, value=value, footprint=fp,
                       props=PARTS.get(ref))
        if top in ("+3V3", "VBUS"):
            auto_pwr(inst, "1", net=top)
        else:
            auto_label(inst, "1", top, shape=top_shape)
        if bottom == "GND":
            auto_gnd(inst, "2")
        else:
            auto_label(inst, "2", bottom, shape="passive")
        return inst

    def series_r(ref, x, y, mcu_net, j_net, value="220"):
        """Horizontal 220R: pin1 left(MCU side), pin2 right(connector side)."""
        inst = d.place(ref, S_R, x, y, rot=90, value=value, footprint=FP["R"],
                       props=PARTS.get(ref))
        auto_label(inst, "1", mcu_net, shape="bidirectional")
        auto_label(inst, "2", j_net, shape="passive")
        return inst

    # ================= USB-C connector =================
    d.text("USB TYPE-C & PROTECTION", g(24), g(34))
    j1 = d.place("J1", S_USBC, g(36), g(59), value="USB_C_16P",
                 footprint=FP["USBC"], value_at=(g(36), g(39)),
                 props=PARTS["J1"])
    # VBUS pins (stacked): stub right, power VBUS + PWR_FLAG
    pv = j1.pin("A4")
    pv1 = (round(pv[0] + g(2), 4), pv[1])
    d.wire(pv, pv1)
    d.wire(pv1, (pv1[0], round(pv1[1] - g(2), 4)))
    d.power("VBUS", pv1[0], round(pv1[1] - g(2), 4))
    d.wire(pv1, (round(pv1[0] + g(4), 4), pv1[1]))
    d.pwr_flag(round(pv1[0] + g(4), 4), pv1[1])
    d.junction(pv1)
    # CC pulldowns
    auto_label(j1, "A5", "CC1", shape="passive")
    auto_label(j1, "B5", "CC2", shape="passive")
    # D+/D- (per-pin labels; single net through USBLC6)
    auto_label(j1, "A7", "USB_DM", shape="bidirectional")
    auto_label(j1, "B7", "USB_DM", shape="bidirectional")
    auto_label(j1, "A6", "USB_DP", shape="bidirectional")
    auto_label(j1, "B6", "USB_DP", shape="bidirectional")
    nc(j1, "A8")
    nc(j1, "B8")
    # GND (stacked) + PWR_FLAG
    pg = j1.pin("A1")
    pg1 = (pg[0], round(pg[1] + g(2), 4))
    d.wire(pg, pg1)
    d.power("GND", pg1[0], pg1[1])
    d.wire(pg1, (round(pg1[0] + g(4), 4), pg1[1]))
    d.pwr_flag(round(pg1[0] + g(4), 4), pg1[1])
    d.junction(pg1)
    # shield
    auto_label(j1, "SH", "SHIELD", shape="passive")

    r1 = vert_rc("R1", S_R, g(64), g(88), "5.1k", FP["R"], "CC1")
    r2 = vert_rc("R2", S_R, g(72), g(88), "5.1k", FP["R"], "CC2")
    r3 = vert_rc("R3", S_R, g(24), g(96), "1M", FP["R"], "SHIELD")
    c13 = vert_rc("C13", S_C, g(32), g(96), "10nF", FP["C"], "SHIELD")

    # USB ESD array
    d1 = d.place("D1", S_USBLC, g(83), g(52), value="USBLC6-2SC6",
                 footprint=FP["SOT236"], value_at=(g(95), g(61)),
                 props=PARTS["D1"])
    auto_label(d1, "1", "USB_DM", shape="bidirectional")
    auto_label(d1, "6", "USB_DM", shape="bidirectional")
    auto_label(d1, "3", "USB_DP", shape="bidirectional")
    auto_label(d1, "4", "USB_DP", shape="bidirectional")
    auto_label(d1, "5", "VBUS_P", shape="passive")
    auto_gnd(d1, "2")

    # ================= power =================
    d.text("POWER: VBUS -> 3V3 + protected target outputs", g(24), g(20))
    y_pw = 24  # chain rail y (grid units)
    d.power("VBUS", g(76), g(y_pw - 2))
    d.wire((g(76), g(y_pw - 2)), (g(76), g(y_pw)))
    f1 = d.place("F1", S_FUSE, g(83), g(y_pw), rot=90, value="750mA PTC",
                 footprint=FP["FUSE"], props=PARTS["F1"])
    d.wire((g(76), g(y_pw)), f1.pin("1"))
    # node VBUS_P
    node = (g(92), g(y_pw))
    d.wire(f1.pin("2"), node)
    d.label_right("VBUS_P", (g(92), g(y_pw - 4)), shape="passive")
    d.wire(node, (g(92), g(y_pw - 4)))
    d.pwr_flag(g(96), g(y_pw - 2))
    d.wire(node, (g(96), g(y_pw)))
    d.wire((g(96), g(y_pw)), (g(96), g(y_pw - 2)))
    d.junction(node)
    d.junction((g(96), g(y_pw)))
    # TVS down from node
    tvs = d.place("D7", S_TVS, g(92), g(y_pw + 6), rot=90, value="SMAJ5.0A",
                  footprint=FP["TVS"], props=PARTS["D7"])
    # Unidirectional TVS: pad 1 of D_SMA = cathode (band) -> must face VBUS_P.
    # (The library symbol names its pins A1/A2, so map by NUMBER explicitly.)
    d.wire(node, tvs.pin("1"))
    auto_gnd(tvs, "2")
    # LDO
    u3 = d.place("U3", S_LDO, g(110), g(y_pw + 2), value="AP2112K-3.3",
                 footprint=FP["LDO"], value_at=(g(110), g(y_pw + 12)),
                 props=PARTS["U3"])
    d.wire((g(96), g(y_pw)), u3.pin("1"))
    # EN tied to VIN
    pen = u3.pin("3")
    pin_v = u3.pin("1")
    d.wire(pen, (round(pen[0] - g(2), 4), pen[1]))
    d.wire((round(pen[0] - g(2), 4), pen[1]),
           (round(pen[0] - g(2), 4), pin_v[1]))
    d.junction((round(pen[0] - g(2), 4), pin_v[1]))
    nc(u3, "4")
    auto_gnd(u3, "2")
    # VOUT -> +3V3
    pvo = u3.pin("5")
    pvo1 = (round(pvo[0] + g(4), 4), pvo[1])
    d.wire(pvo, pvo1)
    d.wire(pvo1, (pvo1[0], round(pvo1[1] - g(2), 4)))
    d.power("+3V3", pvo1[0], round(pvo1[1] - g(2), 4))
    c1 = vert_rc("C1", S_C, g(102), g(y_pw + 8), "1uF", FP["C"], "VBUS_P")
    c2 = vert_rc("C2", S_C, g(122), g(y_pw + 8), "2.2uF", FP["C"], "+3V3")

    # ================= MCU =================
    d.text("MCU STM32F446RET6  (HSE 16MHz, LQFP64)", g(160), g(46))
    u1 = d.place("U1", S_MCU, g(208), g(91), value="STM32F446RET6",
                 footprint=FP["MCU"], props=PARTS["U1"])
    # top power rail: VBAT + 4x VDD
    top_y = u1.pin("1")[1]
    xs = [u1.pin(p)[0] for p in ("1", "19", "32", "48", "64")]
    d.chain([(x, top_y) for x in xs])  # rail through the pin points
    rail_l = (xs[0], top_y)
    d.wire(rail_l, (rail_l[0], round(top_y - g(2), 4)))
    d.power("+3V3", rail_l[0], round(top_y - g(2), 4))
    d.junction(rail_l)
    # VDDA via ferrite from 3V3
    auto_label(u1, "13", "VDDA", shape="passive")
    # bottom grounds
    pvss = u1.pin("18")
    d.wire(pvss, (pvss[0], round(pvss[1] + g(2), 4)))
    d.power("GND", pvss[0], round(pvss[1] + g(2), 4))
    pvssa = u1.pin("12")
    d.wire(pvssa, (pvssa[0], round(pvssa[1] + g(4), 4)))
    d.power("GND", pvssa[0], round(pvssa[1] + g(4), 4))
    # VCAP
    auto_label(u1, "30", "VCAP", shape="passive")
    # left-side signals
    auto_label(u1, "7", "NRST")          # NRST
    auto_label(u1, "60", "BOOT0")        # BOOT0
    auto_label(u1, "5", "OSC_IN", shape="passive")
    auto_label(u1, "6", "OSC_OUT", shape="passive")
    auto_label(u1, "8", "LED1")
    auto_label(u1, "9", "LED2")
    auto_label(u1, "10", "LED3")
    auto_label(u1, "37", "A_TX")
    auto_label(u1, "38", "A_RX")
    for pin, net in (("11", "LED_A_TX"), ("24", "LED_A_RX"),
                     ("25", "LED_B_TX"), ("39", "LED_B_RX"), ("40", "PWR_OUT_EN")):
        auto_label(u1, pin, net)
    # right-side signals
    right = {
        "14": "TGPIO2", "15": "TGPIO6", "16": "CON_TX", "17": "CON_RX",
        "20": "T_SWCLK", "21": "T_SWDIO", "22": "T_nRESET",
        "41": "TGPIO7", "42": "B_TX", "43": "B_RX",
        "44": "USB_DM", "45": "USB_DP",
        "46": "MCU_SWDIO", "49": "MCU_SWCLK",
        "26": "TGPIO0", "27": "TGPIO1", "28": "BOOT1",
        "61": "TGPIO3", "62": "TGPIO4", "29": "TGPIO5",
        "33": "FLASH_CS", "34": "SPI2_SCK", "35": "SPI2_MISO",
        "36": "SPI2_MOSI",
    }
    for pin, net in right.items():
        auto_label(u1, pin, net)
    # unused pins -> no-connect (ER-10)
    for pin in ("2", "3", "4", "51", "52",
                "53", "54", "23", "50", "55", "56", "57", "58", "59"):
        nc(u1, pin)

    # decoupling bank
    d.text("DECOUPLING", g(252), g(52), size=1.5)
    for i, ref in enumerate(("C3", "C4", "C5", "C6")):
        vert_rc(ref, S_C, g(252 + i * 8), g(60), "100nF", "Capacitor_SMD:C_0402_1005Metric", "+3V3")
    c7 = vert_rc("C7", S_C, g(252), g(74), "2.2uF", FP["C"], "VCAP")
    # VDDA filter
    fb1 = d.place("FB1", S_FBEAD, g(262), g(74), rot=90, value="FB 600R@100MHz",
                  footprint=FP["FB"], props=PARTS["FB1"])
    auto_pwr(fb1, "1", net="+3V3")
    pfb = fb1.pin("2")
    pfb1 = (round(pfb[0] + g(2), 4), pfb[1])
    d.wire(pfb, pfb1)
    d.label_right("VDDA", pfb1, shape="passive")
    d.wire(pfb1, (pfb1[0], round(pfb1[1] - g(2), 4)))
    d.pwr_flag(pfb1[0], round(pfb1[1] - g(2), 4))
    d.junction(pfb1)
    c8 = vert_rc("C8", S_C, g(274), g(74), "1uF", FP["C"], "VDDA")
    c9 = vert_rc("C9", S_C, g(282), g(74), "100nF", "Capacitor_SMD:C_0402_1005Metric", "VDDA")

    # ================= crystal =================
    d.text("HSE 16MHz", g(150), g(60), size=1.5)
    x1 = d.place("X1", S_XTAL, g(158), g(67), value="16MHz 3225 CL=12pF",
                 footprint=FP["XTAL"], value_at=(g(158), g(72)),
                 props=PARTS["X1"])
    auto_label(x1, "1", "OSC_XO", shape="passive")
    auto_label(x1, "3", "OSC_IN", shape="passive")
    auto_gnd(x1, "2")
    auto_gnd(x1, "4")
    r6 = series_r("R6", g(158), g(77), "OSC_XO", "OSC_OUT", value="0")
    c10 = vert_rc("C10", S_C, g(166), g(86), "18pF", FP["C"], "OSC_IN")
    c11 = vert_rc("C11", S_C, g(150), g(86), "18pF", FP["C"], "OSC_XO")

    # ================= boot / reset =================
    d.text("BOOT & RESET", g(150), g(96), size=1.5)
    r4 = vert_rc("R4", S_R, g(152), g(104), "10k", FP["R"], "BOOT0")
    r5 = vert_rc("R5", S_R, g(180), g(104), "10k", FP["R"], "BOOT1")
    c12 = vert_rc("C12", S_C, g(152), g(120), "100nF", "Capacitor_SMD:C_0402_1005Metric", "NRST")
    vert_rc("R31", S_R, g(170), g(120), "10k", FP["R"], "+3V3", bottom="NRST")

    # ================= SPI NOR =================
    d.text("SPI NOR FLASH (norflash0)", g(108), g(150), size=2.0)
    u2 = d.place("U2", S_W25, g(120), g(166), value="W25Q64JVSSIQ",
                 footprint=FP["FLASH"], props=PARTS["U2"])
    auto_label(u2, "1", "FLASH_CS")
    auto_label(u2, "2", "SPI2_MISO")
    auto_label(u2, "5", "SPI2_MOSI")
    auto_label(u2, "6", "SPI2_SCK")
    auto_label(u2, "3", "FLASH_WP", shape="passive")
    auto_label(u2, "7", "FLASH_HOLD", shape="passive")
    auto_pwr(u2, "8", net="+3V3")
    auto_gnd(u2, "4")
    r7 = vert_rc("R7", S_R, g(146), g(160), "10k", FP["R"], "+3V3",
                 bottom="FLASH_CS")
    r8 = vert_rc("R8", S_R, g(158), g(160), "10k", FP["R"], "+3V3",
                 bottom="FLASH_WP")
    r9 = vert_rc("R9", S_R, g(170), g(160), "10k", FP["R"], "+3V3",
                 bottom="FLASH_HOLD")
    c14 = vert_rc("C14", S_C, g(146), g(174), "100nF", "Capacitor_SMD:C_0402_1005Metric", "+3V3")

    # ================= LEDs =================
    d.text("STATUS RGB (PC0/1/2 active-low) + POWER LED", g(24), g(150),
           size=2.0)
    d8 = d.place("D8", S_RGB, g(32), g(166), value="RGB_CA",
                 footprint=FP["RGB"], props=PARTS["D8"])
    auto_pwr(d8, "4", net="+3V3")
    auto_label(d8, "1", "RGB_RK", shape="passive")
    auto_label(d8, "2", "RGB_GK", shape="passive")
    auto_label(d8, "3", "RGB_BK", shape="passive")
    r27 = series_r("R27", g(64), g(162), "RGB_RK", "LED1", value="620")
    r28 = series_r("R28", g(64), g(166), "RGB_GK", "LED2", value="150")
    r29 = series_r("R29", g(64), g(170), "RGB_BK", "LED3", value="150")
    r30 = vert_rc("R30", S_R, g(88), g(162), "1k", FP["R"], "+3V3",
                  bottom="PWRLED")
    d9 = d.place("D9", S_LED, g(88), g(174), rot=90, value="PWR_LED_GREEN",
                 footprint=FP["LED"], props=PARTS["D9"])
    # LED: pin1=K, pin2=A ; rot90 -> A up, K down
    auto_label(d9, "2", "PWRLED", shape="passive")
    auto_gnd(d9, "1")

    # ================= target interfaces =================
    d.text("TARGET: SIGNALS 3V3 / PROTECTED 3V3 + 5V OUTPUTS", g(324), g(20))

    # ---- J2 SWD
    d.text("TARGET SWD -> J2 BACK", g(330), g(30), size=1.5)
    series_r("R10", g(336), g(36), "T_SWCLK", "T_SWCLK_J")
    series_r("R11", g(336), g(40), "T_SWDIO", "T_SWDIO_J")
    series_r("R12", g(336), g(44), "T_nRESET", "T_nRESET_J")
    j2 = d.place("J2", S_C2X6, g(410), g(44), value="TARGET_2x6_STRADDLE",
                 footprint=FP["STRADDLE"], value_at=(g(410), g(60)))
    for pin, net, _face, _label in J2_PINS:
        auto_label(j2, str(pin), net, shape="passive")
    d2 = d.place("D2", S_SRV, g(340), g(58), value="SRV05-4",
                 footprint=FP["SOT236"], value_at=(g(352), g(67)),
                 props=PARTS["D2"])
    auto_label(d2, "1", "T_SWCLK_J", shape="passive")
    auto_label(d2, "3", "T_SWDIO_J", shape="passive")
    auto_label(d2, "4", "T_nRESET_J", shape="passive")
    nc(d2, "6")
    auto_pwr(d2, "5", net="+3V3")
    auto_gnd(d2, "2")

    # ---- J3 dual UART
    d.text("DUAL UART -> J2 FRONT", g(330), g(74), size=1.5)
    series_r("R13", g(336), g(80), "A_TX", "A_TX_J")
    series_r("R14", g(336), g(84), "A_RX", "A_RX_J")
    series_r("R15", g(336), g(88), "B_TX", "B_TX_J")
    series_r("R16", g(336), g(92), "B_RX", "B_RX_J")
    d3 = d.place("D3", S_SRV, g(340), g(104), value="SRV05-4",
                 footprint=FP["SOT236"], value_at=(g(352), g(113)),
                 props=PARTS["D3"])
    auto_label(d3, "1", "A_TX_J", shape="passive")
    auto_label(d3, "3", "A_RX_J", shape="passive")
    auto_label(d3, "4", "B_TX_J", shape="passive")
    auto_label(d3, "6", "B_RX_J", shape="passive")
    auto_pwr(d3, "5", net="+3V3")
    auto_gnd(d3, "2")

    # ---- J4 GPIO
    d.text("J3 / J4 OPTIONAL GPIO HEADERS", g(330), g(120), size=1.5)
    for i in range(8):
        series_r(f"R{17 + i}", g(336), g(126 + 4 * i),
                 f"TGPIO{i}", f"TGPIO{i}_J")
    for ref, start, y in (("J3", 0, 128), ("J4", 4, 146)):
        j = d.place(ref, S_C1X4, g(405), g(y), value=f"GPIO_{start}_{start+3}",
                    footprint=FP["H1X4"], dnp=True, value_at=(g(405), g(y+9)))
        for i in range(4):
            auto_label(j, str(i+1), f"TGPIO{start+i}_J", shape="passive")
    d4 = d.place("D4", S_SRV, g(340), g(162), value="SRV05-4",
                 footprint=FP["SOT236"], value_at=(g(352), g(171)),
                 props=PARTS["D4"])
    # Each GPIO ESD array protects the four holes on one long edge.
    for k, i in (("1", 0), ("3", 1), ("4", 2), ("6", 3)):
        auto_label(d4, k, f"TGPIO{i}_J", shape="passive")
    auto_pwr(d4, "5", net="+3V3")
    auto_gnd(d4, "2")
    d5 = d.place("D5", S_SRV, g(388), g(162), value="SRV05-4",
                 footprint=FP["SOT236"], value_at=(g(400), g(171)),
                 props=PARTS["D5"])
    for k, i in (("1", 4), ("3", 5), ("4", 6), ("6", 7)):
        auto_label(d5, k, f"TGPIO{i}_J", shape="passive")
    auto_pwr(d5, "5", net="+3V3")
    auto_gnd(d5, "2")

    # ---- J5 console
    d.text("J5 FW CONSOLE (USART2 115200)", g(330), g(180), size=1.5)
    series_r("R25", g(336), g(186), "CON_TX", "CON_TX_J")
    series_r("R26", g(336), g(190), "CON_RX", "CON_RX_J")
    j5 = d.place("J5", S_C1X3, g(368), g(188), value="CONSOLE",
                 footprint=FP["CONSOLE"], dnp=True, in_bom=False, value_at=(g(368), g(195)),
                 props=PARTS["J5"])
    auto_label(j5, "1", "CON_TX_J", shape="passive")
    auto_label(j5, "2", "CON_RX_J", shape="passive")
    auto_gnd(j5, "3")
    d6 = d.place("D6", S_SRV, g(340), g(204), value="SRV05-4",
                 footprint=FP["SOT236"], value_at=(g(352), g(213)),
                 props=PARTS["D6"])
    auto_label(d6, "1", "CON_TX_J", shape="passive")
    auto_label(d6, "3", "CON_RX_J", shape="passive")
    nc(d6, "4")
    nc(d6, "6")
    auto_pwr(d6, "5", net="+3V3")
    auto_gnd(d6, "2")

    # ---- J6 factory SWD + ROM boot and reset contacts
    d.text("J6 FACTORY SWD / ROM RECOVERY (pogo contacts)", g(330), g(222), size=1.5)
    j6 = d.place("J6", S_C2X3, g(365), g(236), value="FACTORY",
                 footprint=FP["SERVICE"], dnp=True, in_bom=False,
                 value_at=(g(365), g(246)))
    auto_pwr(j6, "1", net="+3V3")
    auto_label(j6, "2", "GND", shape="passive")
    for pin, net in (("3", "MCU_SWDIO"), ("4", "MCU_SWCLK"), ("5", "NRST"), ("6", "BOOT0")):
        auto_label(j6, pin, net)

    # ================= test points =================
    d.text("TEST POINTS", g(24), g(196), size=1.5)
    tps = [("TP1", "VBUS"), ("TP6", "USB_DP"), ("TP7", "USB_DM")]
    for i, (ref, net) in enumerate(tps):
        tp = d.place(ref, S_TP, g(24 + i * 10), g(202), value=net,
                     footprint=FP["TP"], value_hide=True, in_bom=False)
        p0 = tp.pin("1")
        dx, dy = tp.pin_out_dir("1")
        p1 = (round(p0[0] + dx * g(2), 4), round(p0[1] + dy * g(2), 4))
        d.wire(p0, p1)
        if net in ("VBUS", "+3V3"):
            d.power(net, p1[0], p1[1], rot=180 if dy == 1 else 0)
        elif net == "GND":
            d.power("GND", p1[0], p1[1], rot=0 if dy == 1 else 180)
        else:
            d.label_right(net, p1, shape="passive")

    # ================= activity indicators =================
    d.text("UART ACTIVITY: independent GPIO, active low", g(24), g(222), size=1.5)
    for i, name in enumerate(("A_TX", "A_RX", "B_TX", "B_RX")):
        x = g(30 + i*24)
        net = f"ACT_{name}_A"
        vert_rc(f"R{32+i}", S_R, x, g(232), "1.3k", FP["R"], "+3V3", bottom=net)
        led = d.place(f"D{10+i}", S_LED, x, g(246), rot=90, value=f"LED_{name}", footprint=FP["LED"])
        auto_label(led, "2", net, shape="passive")
        auto_label(led, "1", f"LED_{name}")

    # ================= protected target supplies =================
    d.text("TARGET POWER: independent limiting / reverse protection", g(142), g(200), size=1.5)
    for ref, supply, output, x, rref, rval, cstart in (
        ("U4", "+3V3", "+3V3_OUT", 166, "R36", "226k", 15),
        ("U5", "VBUS_P", "+5V_OUT", 250, "R37", "147k", 17),
    ):
        sw = d.place(ref, S_PSW, g(x), g(222), value="TPS2553DBVR", footprint=FP["SOT236"],
                     value_at=(g(x), g(212)))
        auto_label(sw, "1", supply, shape="passive")
        auto_gnd(sw, "2")
        auto_label(sw, "3", "PWR_OUT_EN")
        nc(sw, "4")  # Autonomous current limiting and thermal auto-retry.
        auto_label(sw, "5", f"{ref}_ILIM", shape="passive")
        auto_label(sw, "6", output, shape="passive")
        vert_rc(rref, S_R, g(x+22), g(241), rval, FP["R"], f"{ref}_ILIM")
        vert_rc(f"C{cstart}", S_C, g(x-14), g(243), "100nF", "Capacitor_SMD:C_0402_1005Metric", supply)
        vert_rc(f"C{cstart+1}", S_C, g(x+4), g(243), "100nF", "Capacitor_SMD:C_0402_1005Metric", output)
    vert_rc("R38", S_R, g(210), g(222), "10k", FP["R"], "PWR_OUT_EN")
    d.text("J6 carries 3V3 reference, GND, own SWD, NRST and BOOT0. No buttons.", g(24), g(278), size=1.5)
    d.text("Output targets: 3V3 100mA / 5V 150mA; USB configured only. Prototype validation required.", g(24), g(284), size=1.5)

    return d


if __name__ == "__main__":
    doc = build()
    out = os.path.join(HW, "ailink.kicad_sch")
    doc.save(out)
    print("wrote", os.path.abspath(out))
    print("symbols:", len([i for i in doc.items if i[0] == "symbol"]))
