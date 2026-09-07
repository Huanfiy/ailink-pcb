"""grid_router and fanout_product.Geometry tests on synthetic boards."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pcbnew
import pcb_common as pc
import grid_router as gr
import product_config as cfg_mod
from fanout_product import Geometry, connected_groups, on_plane

FINE = gr.RouterConfig(step=.05, clearance=.155)


def add_pad(board, net, ref, x, y, layer=pcbnew.F_Cu, size=.6):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(ref)
    board.Add(fp)
    pad = pcbnew.PAD(fp)
    pad.SetNumber('1')
    pad.SetPosition(pc.pt(x, y))
    pad.SetSize(pc.pt(size, size))
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    layers = pcbnew.LSET()
    layers.AddLayer(layer)
    pad.SetLayerSet(layers)
    pad.SetNet(net)
    fp.Add(pad)
    return pad


class PolylineTests(unittest.TestCase):
    def test_decimal_collinear_points_collapse(self):
        path = [(0, 101 + i, 99 + i) for i in range(50)]
        segments, vias = gr.path_to_geometry(FINE, path)
        self.assertEqual(segments, [(0, [FINE.coord(path[0][1:]), FINE.coord(path[-1][1:])])])
        self.assertEqual(vias, [])

    def test_round_pad_corner_remains_routable(self):
        grid = gr.Grid(FINE)
        shape = pcbnew.SHAPE_CIRCLE(pc.pt(115, 110), pc.mm(.9))
        grid.block_shape(gr.F, shape, .23)
        self.assertTrue(grid.is_free(gr.F, FINE.cell(115.9, 110.9)))
        self.assertFalse(grid.is_free(gr.F, FINE.cell(115.95, 110)))

    def test_corner_and_layer_change_preserved(self):
        path = [(0, 100, 100), (0, 101, 100), (0, 101, 101),
                (1, 101, 101), (1, 102, 101)]
        segments, vias = gr.path_to_geometry(FINE, path)
        self.assertEqual([len(points) for _, points in segments], [3, 2])
        self.assertEqual(vias, [FINE.coord((101, 101))])


class ConfigTests(unittest.TestCase):
    def test_configs_are_independent(self):
        coarse = gr.RouterConfig(step=.25)
        self.assertEqual((coarse.nx, coarse.ny), (169, 89))
        self.assertEqual((FINE.nx, FINE.ny), (841, 441))
        self.assertEqual(coarse.cell(*coarse.coord((10, 20))), (10, 20))
        self.assertEqual(FINE.cell(*FINE.coord((10, 20))), (10, 20))

    def test_inner_layer_only_when_requested(self):
        outer = gr.Grid(gr.RouterConfig(step=.1))
        inner = gr.Grid(gr.RouterConfig(step=.1, layers=gr.WITH_INNER))
        self.assertNotIn(gr.IN2, outer.blocked)
        self.assertIn(gr.IN2, inner.blocked)
        self.assertIsNone(outer.config.layer_index(pcbnew.In2_Cu))
        self.assertEqual(inner.config.layer_index(pcbnew.In2_Cu), gr.IN2)

    def test_protected_regions_block_grid_cells(self):
        grid = gr.Grid(gr.RouterConfig(step=.1, layers=gr.WITH_INNER))
        hse = cfg_mod.rect_center(cfg_mod.HSE_BODY)
        usb = cfg_mod.rect_center(cfg_mod.USB_REAR_GND_WINDOW)
        self.assertFalse(grid.track_allowed(gr.F, *grid.cell(*hse)))
        self.assertTrue(grid.track_allowed(gr.B, *grid.cell(*hse)))
        self.assertFalse(grid.track_allowed(gr.IN2, *grid.cell(*usb)))
        self.assertTrue(grid.track_allowed(gr.F, *grid.cell(*usb)))
        self.assertTrue(grid.track_allowed(gr.IN2, *grid.cell(120, 111)))


class GeometryBoundaryTests(unittest.TestCase):
    """fanout_product.Geometry honours the product_config regions on an empty board."""

    def setUp(self):
        self.geometry = Geometry(pcbnew.BOARD())

    def test_via_keepout_around_crystal(self):
        x0, y0, x1, y1 = cfg_mod.inflate(cfg_mod.HSE_BODY, .25)
        inside, outside = pc.pt(x0 + .05, (y0 + y1) / 2), pc.pt(x0 - .05, (y0 + y1) / 2)
        self.assertFalse(self.geometry.free_via('TGPIO0_J', inside))
        self.assertTrue(self.geometry.free_via('TGPIO0_J', outside))
        self.assertTrue(self.geometry.free_via('GND', inside))

    def test_front_tracks_stay_off_crystal_body(self):
        cx, cy = cfg_mod.rect_center(cfg_mod.HSE_BODY)
        a, b = pc.pt(cx - .5, cy), pc.pt(cx + .5, cy)
        self.assertFalse(self.geometry.free_track('TGPIO0_J', pcbnew.F_Cu, a, b))
        self.assertTrue(self.geometry.free_track('OSC_IN', pcbnew.F_Cu, a, b))
        self.assertTrue(self.geometry.free_track('GND', pcbnew.F_Cu, a, b))
        self.assertTrue(self.geometry.free_track('TGPIO0_J', pcbnew.B_Cu, a, b))

    def test_inner_tracks_stay_off_rear_usb_window(self):
        x0, y0, x1, y1 = cfg_mod.USB_REAR_GND_WINDOW
        cy = (y0 + y1) / 2
        crossing = (pc.pt(x0 - 1, cy), pc.pt(x0 + 1, cy))
        grazing = (pc.pt(x1 + .3, cy - 1), pc.pt(x1 + .3, cy + 1))
        self.assertFalse(self.geometry.free_track('TGPIO0_J', pcbnew.In2_Cu, *crossing))
        self.assertTrue(self.geometry.free_track('GND', pcbnew.In2_Cu, *crossing))
        self.assertTrue(self.geometry.free_track('TGPIO0_J', pcbnew.In2_Cu, *grazing))
        self.assertTrue(self.geometry.free_track('TGPIO0_J', pcbnew.F_Cu, *crossing))

    def test_plane_holes_avoid_window_neighbourhood(self):
        x0, y0, x1, y1 = cfg_mod.inflate(cfg_mod.USB_REAR_GND_WINDOW, .4)
        self.assertFalse(on_plane('+3V3', pc.pt(x0 + .05, y0 + .05)))
        self.assertTrue(on_plane('+3V3', pc.pt(x0 - .05, y0 - .05)))
        self.assertTrue(on_plane('GND', pc.pt(x0 + .05, y0 + .05)))


class SyntheticRouteTests(unittest.TestCase):
    """Two pads with a foreign track in between: the route must connect and clear it."""

    def setUp(self):
        self.board = pcbnew.BOARD()
        self.board.GetDesignSettings().SetCopperLayerCount(4)
        self.net = pcbnew.NETINFO_ITEM(self.board, 'TEST')
        self.other = pcbnew.NETINFO_ITEM(self.board, 'OTHER')
        self.board.Add(self.net)
        self.board.Add(self.other)
        add_pad(self.board, self.net, 'R1', 115, 110)
        add_pad(self.board, self.net, 'R2', 118, 110)
        pc.add_track(self.board, self.other, pcbnew.F_Cu, [(116.5, 108), (116.5, 112)], .15)

    def test_route_connects_pads_and_clears_obstacle(self):
        before = Geometry(self.board)
        config = gr.RouterConfig(step=.1, clearance=.155, track_w=.15)
        grid = gr.build_grid(self.board, config, {'TEST'})
        self.assertTrue(gr.route_net(self.board, grid, 'TEST'))
        new = [t for t in self.board.GetTracks() if t.GetNetname() == 'TEST']
        self.assertTrue(new)
        for item in new:
            if item.GetClass() == 'PCB_VIA':
                self.assertTrue(before.free_via('TEST', item.GetPosition()), 'via clearance')
            else:
                self.assertTrue(before.free_track('TEST', item.GetLayer(), item.GetStart(),
                                                  item.GetEnd(), config.track_w), 'track clearance')
        self.assertEqual(len(connected_groups(Geometry(self.board), 'TEST')), 1)
        self.assertEqual(len(connected_groups(Geometry(self.board), 'OTHER')), 1)


if __name__ == '__main__':
    unittest.main()
