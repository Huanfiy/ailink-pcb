"""Mechanical constants for the approved v0.4 product layout (millimetres)."""

REVISION = "v0.4"
X0, Y0, X1, Y1 = 100.0, 100.0, 142.0, 122.0
CORNER_R = 2.0
MCU_CENTER = (118.5, 111.0)
HEADER_Y = tuple(104.65 + 2.54 * i for i in range(6))

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
