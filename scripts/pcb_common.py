"""Shared helpers for PCB generation scripts (pcbnew API)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlist

import pcbnew

HW = os.path.abspath(os.environ.get('AILINK_HW', os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "hardware")))
SCH = os.path.join(HW, "ailink.kicad_sch")
PCB = os.environ.get('AILINK_PCB', os.path.join(HW, "ailink.kicad_pcb"))
FP_DIR = "/usr/share/kicad/footprints"


def mm(v):
    return pcbnew.FromMM(v)


def to_mm(v):
    return pcbnew.ToMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def rect_shape(rect):
    """pcbnew.SHAPE_RECT for a product_config (x0, y0, x1, y1) rectangle."""
    x0, y0, x1, y1 = rect
    return pcbnew.SHAPE_RECT(mm(x0), mm(y0), mm(round(x1 - x0, 6)), mm(round(y1 - y0, 6)))


def _vec(p):
    """Accept a VECTOR2I or an (x, y) millimetre tuple."""
    return p if isinstance(p, pcbnew.VECTOR2I) else pt(*p)


def _net(board, net):
    return board.GetNetsByName()[net] if isinstance(net, str) else net


def footprint_by_ref(board, ref):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        raise KeyError(ref)
    return fp


def pad_pos(board, ref, number, digits=3):
    """Pad centre in millimetres; digits=None returns the unrounded value."""
    for pad in footprint_by_ref(board, ref).Pads():
        if str(pad.GetNumber()) == str(number):
            pos = pad.GetPosition()
            x, y = to_mm(pos.x), to_mm(pos.y)
            return (x, y) if digits is None else (round(x, digits), round(y, digits))
    raise KeyError(f"{ref}-{number}")


def add_track(board, net, layer, points, width, locked=False):
    """Add a polyline of tracks; zero-length legs are skipped. Returns the tracks."""
    net = _net(board, net)
    out = []
    for a, b in zip(points, points[1:]):
        a, b = _vec(a), _vec(b)
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(a)
        t.SetEnd(b)
        t.SetWidth(mm(width))
        t.SetLayer(layer)
        t.SetNet(net)
        if locked:
            t.SetLocked(True)
        board.Add(t)
        out.append(t)
    return out


def add_via(board, net, pos, dia, drill, locked=False):
    """Add a through via (F.Cu-B.Cu). Returns the via."""
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(_vec(pos))
    v.SetWidth(mm(dia))
    v.SetDrill(mm(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(_net(board, net))
    if locked:
        v.SetLocked(True)
    board.Add(v)
    return v


def load_netlist():
    """Return (components, nets) of the project schematic; see netlist.load."""
    return netlist.load(SCH)


def load_footprint(fpid):
    lib, name = fpid.split(":", 1)
    path = os.path.join(HW, "lib", "ailink.pretty") if lib == "ailink" else os.path.join(FP_DIR, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f"footprint not found: {fpid}")
    return fp


def sync_footprint(board, fp, meta):
    """Carry schematic identity, sourcing fields and assembly flags to PCB."""
    fp.SetPath(pcbnew.KIID_PATH(meta['path']))
    fp.SetSheetfile('ailink.kicad_sch')
    fp.SetSheetname('ailink')
    for key,value in meta['properties'].items():
        fp.SetField(key,value)
        fp.GetField(key).SetVisible(False)
        fp.GetField(key).SetLayer(pcbnew.B_Fab if fp.GetLayer()==pcbnew.B_Cu else pcbnew.F_Fab)
        fp.GetField(key).SetPosition(fp.GetPosition())
    flags = fp.GetAttributes() & ~(pcbnew.FP_DNP | pcbnew.FP_EXCLUDE_FROM_BOM)
    if meta['dnp']: flags |= pcbnew.FP_DNP
    if meta['exclude_bom']: flags |= pcbnew.FP_EXCLUDE_FROM_BOM
    fp.SetAttributes(flags)
