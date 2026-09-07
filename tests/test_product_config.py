"""product_config is the single source for protected regions; keep it honest."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pcbnew
import pcb_common as pc
import product_config as cfg
from gen_pcb import PLACEMENT


class RectHelperTests(unittest.TestCase):
    def test_inflate_matches_decimal_literals(self):
        self.assertEqual(cfg.inflate(cfg.USB_REAR_GND_WINDOW, .25), (105.25, 106.35, 113.85, 115.55))
        self.assertEqual(cfg.inflate(cfg.USB_REAR_GND_WINDOW, -.3), (105.8, 106.9, 113.3, 115.0))
        self.assertEqual(cfg.inflate(cfg.HSE_BODY, .075), (125.925, 109.575, 129.275, 112.425))

    def test_contains_is_strict(self):
        x0, y0, x1, y1 = cfg.HSE_BODY
        self.assertTrue(cfg.contains(cfg.HSE_BODY, (x0 + x1) / 2, (y0 + y1) / 2))
        self.assertFalse(cfg.contains(cfg.HSE_BODY, x0, (y0 + y1) / 2))
        self.assertFalse(cfg.contains(cfg.HSE_BODY, (x0 + x1) / 2, y1))

    def test_rect_shape_has_exact_size(self):
        shape = pc.rect_shape(cfg.HSE_BODY)
        self.assertEqual(shape.GetPosition(), pc.pt(126, 109.65))
        self.assertEqual(shape.GetSize(), pc.pt(3.2, 2.7))

    def test_protected_nets_cover_usb_and_clock(self):
        self.assertEqual(set(cfg.PROTECTED_NETS), set(cfg.USB_NETS) | set(cfg.CLOCK_NETS))
        self.assertTrue(set(cfg.PLANE_NETS) <= set(cfg.POWER_WIDTH_NETS))


class BoardConsistencyTests(unittest.TestCase):
    def test_hse_body_centred_on_x1_placement(self):
        self.assertEqual(cfg.rect_center(cfg.HSE_BODY), tuple(PLACEMENT['X1'][:2]))

    def test_rear_usb_window_matches_working_board_zone(self):
        board = pcbnew.LoadBoard(str(Path(__file__).resolve().parents[1] / 'hardware' / 'ailink.kicad_pcb'))
        windows = [z for z in board.Zones() if not z.GetIsRuleArea()
                   and z.GetNetname() == 'GND' and z.IsOnLayer(pcbnew.In2_Cu)]
        self.assertEqual(len(windows), 1)
        bb = windows[0].GetBoundingBox()
        self.assertEqual((pc.to_mm(bb.GetLeft()), pc.to_mm(bb.GetTop()),
                          pc.to_mm(bb.GetRight()), pc.to_mm(bb.GetBottom())),
                         cfg.USB_REAR_GND_WINDOW)


if __name__ == '__main__':
    unittest.main()
