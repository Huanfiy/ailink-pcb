"""cleanup_routes regression tests; run with the system Python that provides pcbnew."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pcbnew
import pcb_common as pc
from cleanup_routes import clean_pass


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
        return pc.add_track(self.board, self.net, layer, [(start, 110), (end, 110)], .15)[0]

    def via(self, x):
        return pc.add_via(self.board, self.net, (x, 110), .5, .3)

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
