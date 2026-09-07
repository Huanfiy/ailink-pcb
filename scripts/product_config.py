"""Mechanical constants for the approved v0.4 product layout (millimetres).

Pure data plus a few rectangle helpers; this module must not import pcbnew so
that netlist-only tools can use it. Rectangles are (x0, y0, x1, y1).
"""

REVISION = "v0.4"
X0, Y0, X1, Y1 = 100.0, 100.0, 142.0, 122.0
CORNER_R = 2.0
MCU_CENTER = (118.5, 111.0)
HEADER_Y = tuple(104.65 + 2.54 * i for i in range(6))

# J2 2x6 straddle header, product.md §5.1: (pin, net, face, silk label).
# Odd pins are the front row (UART), even pins the back row (SWD + power).
J2_PINS = (
    (1, 'A_TX_J', 'F', 'ATX'),      (2, 'GND', 'B', 'GND'),
    (3, 'A_RX_J', 'F', 'ARX'),      (4, 'T_SWCLK_J', 'B', 'CLK'),
    (5, 'GND', 'F', 'GND'),         (6, 'T_SWDIO_J', 'B', 'DIO'),
    (7, 'B_TX_J', 'F', 'BTX'),      (8, 'T_nRESET_J', 'B', 'nRST'),
    (9, 'B_RX_J', 'F', 'BRX'),      (10, '+3V3_OUT', 'B', '3V3'),
    (11, 'GND', 'F', 'GND'),        (12, '+5V_OUT', 'B', '5V'),
)


def j2_row(pin):
    """HEADER_Y index of a J2 pin (pins 1/2 share the first row)."""
    return (pin - 1) // 2

# Protected copper regions. Callers inflate these by their own clearance; the
# base rectangles are the physical objects, not routing margins.
USB_REAR_GND_WINDOW = (105.5, 106.6, 113.6, 115.3)   # L3 GND pour under rear USB (D1 side)
HSE_BODY = (126.0, 109.65, 129.2, 112.35)            # X1 crystal body incl. pad projection

# Nets whose hand-routed copper is locked and restored across autorouting.
USB_NETS = ('USB_DP', 'USB_DM')
CLOCK_NETS = ('OSC_IN', 'OSC_OUT', 'OSC_XO')
PROTECTED_NETS = USB_NETS + CLOCK_NETS
# Inner-plane nets; their copper is fixed for Freerouting and refilled after edits.
PLANE_NETS = ('GND', '+3V3')
# Nets that get the wider 0.2 mm track when the grid router completes them.
POWER_WIDTH_NETS = PLANE_NETS + ('+3V3_OUT', '+5V_OUT', 'VBUS', 'VBUS_P', 'VDDA')


def inflate(rect, margin):
    """Grow (or shrink, for negative margin) a rectangle on all four sides.

    Results are rounded to 1 nm so an inflated edge compares exactly equal to
    the same value written as a decimal literal.
    """
    x0, y0, x1, y1 = rect
    return (round(x0 - margin, 6), round(y0 - margin, 6),
            round(x1 + margin, 6), round(y1 + margin, 6))


def contains(rect, x, y):
    """Strict interior test: points on the edge are outside."""
    x0, y0, x1, y1 = rect
    return x0 < x < x1 and y0 < y < y1


def rect_corners(rect):
    x0, y0, x1, y1 = rect
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def rect_center(rect):
    x0, y0, x1, y1 = rect
    return (round((x0 + x1) / 2, 6), round((y0 + y1) / 2, 6))

# Current-limit bounds include 1% R tolerance, TI SLVS841F, equation (1).
# Rated outputs leave room below the minimum current-limit thresholds.
OUTPUTS = {
    "3V3": {"rated_ma": 100, "rlim_kohm": 226, "ref": "U4"},
    "5V": {"rated_ma": 150, "rlim_kohm": 147, "ref": "U5"},
}


def current_limit_bounds(r_kohm):
    return (25230 / (r_kohm * 1.01) ** 1.016,
            23950 / r_kohm ** 0.977,
            22980 / (r_kohm * 0.99) ** 0.94)
