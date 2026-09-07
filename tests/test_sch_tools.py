"""sexp round trip and symlib pin placement (no pcbnew needed)."""
import itertools
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sexp
import symlib

SAMPLE = '''(kicad_sch (version 20250114) (generator "eeschema")
  (uuid "0b7b6a8e-1111-4c1d-9f4a-000000000001")
  (lib_symbols
    (symbol "Device:R" (pin_numbers (hide yes)) (in_bom yes)
      (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
      (property "Value" "10k \\"pull\\"" (at 0 0 90))
      (symbol "R_1_1" (rectangle (start -1.016 -2.54) (end 1.016 2.54))
        (pin passive line (at 0 3.81 270) (length 1.27) (name "~") (number "1")))))
  (text "line one\\nline two" (at 10 20 0))
  (wire (pts (xy 1 2) (xy 3.5 -4)) (stroke (width 0) (type default)))
)'''


class SexpTests(unittest.TestCase):
    def test_parse_dumps_round_trip_is_stable(self):
        tree = sexp.parse(SAMPLE)
        text = sexp.dumps(tree)
        self.assertEqual(sexp.parse(text), tree)
        self.assertEqual(sexp.dumps(sexp.parse(text)), text)

    def test_strings_and_symbols_keep_identity(self):
        tree = sexp.parse(SAMPLE)
        value = [p for p in sexp.find_all(sexp.find(sexp.find(tree, 'lib_symbols'), 'symbol'), 'property')
                 if p[1] == 'Value'][0]
        self.assertEqual(value[2], '10k "pull"')
        self.assertNotIsInstance(value[2], sexp.Sym)
        self.assertIsInstance(sexp.find(tree, 'wire')[0], sexp.Sym)
        self.assertEqual(sexp.find(tree, 'text')[1], 'line one\nline two')

    def test_numbers_format_kicad_style(self):
        self.assertEqual(sexp.dumps([sexp.Sym('at'), 1, 2.5, -0.0, 1.23456789, True]),
                         '(at 1 2.5 0 1.234568 yes)')


def expected_pin(sym_at, rot, mirror, pin):
    """Independent matrix formulation: mirror, then rotate, then flip Y."""
    px, py = pin['x'], pin['y']
    out = math.radians(pin['angle'] + 180)
    dx, dy = math.cos(out), math.sin(out)
    if mirror == 'x':
        py, dy = -py, -dy
    elif mirror == 'y':
        px, dx = -px, -dx
    a = math.radians(rot)
    rx, ry = px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)
    rdx, rdy = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    return (round(sym_at[0] + rx, 4), round(sym_at[1] - ry, 4)), (round(rdx), round(-rdy))


class SymlibPinTests(unittest.TestCase):
    PINS = ({'x': 2.54, 'y': 1.27, 'angle': 180.0}, {'x': 0.0, 'y': -3.81, 'angle': 90.0})

    def test_all_rotations_and_mirrors_match_matrix_model(self):
        for rot, mirror, pin in itertools.product((0, 90, 180, 270), (None, 'x', 'y'), self.PINS):
            with self.subTest(rot=rot, mirror=mirror, pin=pin):
                pos, direction = expected_pin((100, 50), rot, mirror, pin)
                self.assertEqual(symlib.pin_pos(100, 50, rot, mirror, pin), pos)
                self.assertEqual(symlib.pin_dir(rot, mirror, pin), direction)

    def test_known_anchor_cases(self):
        pin = {'x': 2.54, 'y': 0.0, 'angle': 180.0}   # right-hand pin, body to the left
        self.assertEqual(symlib.pin_pos(100, 50, 0, None, pin), (102.54, 50.0))
        self.assertEqual(symlib.pin_dir(0, None, pin), (1, 0))
        self.assertEqual(symlib.pin_pos(100, 50, 90, None, pin), (100.0, 47.46))
        self.assertEqual(symlib.pin_dir(90, None, pin), (0, -1))
        self.assertEqual(symlib.pin_pos(100, 50, 0, 'y', pin), (97.46, 50.0))
        self.assertEqual(symlib.pin_dir(0, 'y', pin), (-1, 0))


if __name__ == '__main__':
    unittest.main()
