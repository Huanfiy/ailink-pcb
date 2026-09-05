"""Regression tests; run with the system Python that provides pcbnew."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pcbnew
import astar_router as ar
import pcb_common as pc
from cleanup_routes import clean_pass


class PolylineTests(unittest.TestCase):
    def setUp(self):
        self.settings = ar.STEP, ar.CLR
        ar.set_step(.05, .155)

    def tearDown(self):
        ar.set_step(*self.settings)

    def test_decimal_collinear_points_collapse(self):
        path = [(0, 101 + i, 99 + i) for i in range(50)]
        segments, vias = ar.path_to_geometry(path)
        self.assertEqual(segments, [(0, [ar.coord(path[0][1:]), ar.coord(path[-1][1:])])])
        self.assertEqual(vias, [])

    def test_round_pad_corner_remains_routable(self):
        grid = ar.Grid()
        shape = pcbnew.SHAPE_CIRCLE(pc.pt(115, 110), pc.mm(.9))
        grid.block_shape(ar.F, shape, .23)
        self.assertTrue(grid.is_free(ar.F, ar.cell(115.9, 110.9)))
        self.assertFalse(grid.is_free(ar.F, ar.cell(115.95, 110)))

    def test_corner_and_layer_change_preserved(self):
        path = [(0, 100, 100), (0, 101, 100), (0, 101, 101),
                (1, 101, 101), (1, 102, 101)]
        segments, vias = ar.path_to_geometry(path)
        self.assertEqual([len(points) for _, points in segments], [3, 2])
        self.assertEqual(vias, [ar.coord((101, 101))])


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.board = pcbnew.BOARD()
        self.net = pcbnew.NETINFO_ITEM(self.board, 'TEST')
        self.board.Add(self.net)

    def pad(self, ref, x, layer):
        fp = pcbnew.FOOTPRINT(self.board)
        fp.SetReference(ref)
        self.board.Add(fp)
        pad = pcbnew.PAD(fp)
        pad.SetNumber('1')
        pad.SetPosition(pc.pt(x, 110))
        pad.SetSize(pc.pt(.6, .6))
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        layers = pcbnew.LSET()
        layers.AddLayer(layer)
        pad.SetLayerSet(layers)
        pad.SetNet(self.net)
        fp.Add(pad)
        return pad

    def track(self, start, end, layer):
        track = pcbnew.PCB_TRACK(self.board)
        track.SetStart(pc.pt(start, 110))
        track.SetEnd(pc.pt(end, 110))
        track.SetWidth(pc.mm(.15))
        track.SetLayer(layer)
        track.SetNet(self.net)
        self.board.Add(track)
        return track

    def via(self, x):
        via = pcbnew.PCB_VIA(self.board)
        via.SetPosition(pc.pt(x, 110))
        via.SetWidth(pc.mm(.5))
        via.SetDrill(pc.mm(.3))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(self.net)
        self.board.Add(via)
        return via

    def report(self, item, kind='via_dangling'):
        return {'violations': [{'type': kind, 'items': [{'uuid': item.m_Uuid.AsString()}]}]}

    def test_redundant_single_layer_via_removed(self):
        self.pad('R1', 115, pcbnew.F_Cu)
        self.pad('R2', 117, pcbnew.F_Cu)
        self.track(115, 117, pcbnew.F_Cu)
        via = self.via(116)
        self.assertEqual(len(clean_pass(self.board, self.report(via))), 1)

    def test_layer_bridge_not_removed_even_if_reported(self):
        self.pad('R1', 115, pcbnew.F_Cu)
        self.pad('R2', 117, pcbnew.B_Cu)
        self.track(115, 116, pcbnew.F_Cu)
        self.track(116, 117, pcbnew.B_Cu)
        via = self.via(116)
        self.assertEqual(clean_pass(self.board, self.report(via)), [])

    def test_unfinished_escape_kept(self):
        self.pad('R1', 115, pcbnew.F_Cu)
        self.pad('R2', 117, pcbnew.B_Cu)
        self.track(115, 116, pcbnew.F_Cu)
        via = self.via(116)
        self.assertEqual(clean_pass(self.board, self.report(via)), [])

    def test_dead_track_on_unfinished_net_is_pruned(self):
        self.pad('R1', 115, pcbnew.F_Cu)
        self.pad('R2', 118, pcbnew.B_Cu)
        track = self.track(115, 116, pcbnew.F_Cu)
        self.assertEqual(len(clean_pass(self.board, self.report(track, 'track_dangling'))), 1)

    def test_real_connection_not_deleted_as_stub(self):
        self.pad('R1', 115, pcbnew.F_Cu)
        self.pad('R2', 117, pcbnew.F_Cu)
        track = self.track(115, 117, pcbnew.F_Cu)
        self.assertEqual(clean_pass(self.board, self.report(track, 'track_dangling')), [])


if __name__ == '__main__':
    unittest.main()
