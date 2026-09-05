"""Shared helpers for PCB generation scripts (pcbnew API)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp

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


def load_netlist():
    """Return (components, nets):
    components: ref -> {footprint, value, dnp}
    nets: netname -> [(ref, pad), ...]
    """
    net_path = "/tmp/ailink_pcb.net"
    subprocess.run(["kicad-cli", "sch", "export", "netlist",
                    "--format", "kicadsexpr", "-o", net_path, SCH],
                   check=True, capture_output=True)
    tree = sexp.parse(open(net_path).read())
    root_uuid = str(sexp.find_all(sexp.parse(open(SCH).read()), 'uuid')[0][1])
    comps = {}
    comp_node = [x for x in tree if isinstance(x, list) and x and x[0] == "components"][0]
    for c in [x for x in comp_node if isinstance(x, list) and x[0] == "comp"]:
        ref = str([f for f in c if isinstance(f, list) and f[0] == "ref"][0][1])
        fp_node = [f for f in c if isinstance(f, list) and f[0] == "footprint"]
        val_node = [f for f in c if isinstance(f, list) and f[0] == "value"]
        props = [f for f in c if isinstance(f, list) and f[0] == "property"]
        def prop_value(prop, key):
            nodes = sexp.find_all(prop, key)
            return str(nodes[0][1]) if nodes and len(nodes[0])>1 else ''
        properties = {prop_value(p,'name'):prop_value(p,'value') for p in props}
        dnp = 'dnp' in properties
        stamps = sexp.find_all(c,'tstamps')
        comps[ref] = {
            "footprint": str(fp_node[0][1]) if fp_node else "",
            "value": str(val_node[0][1]) if val_node else "",
            "dnp": dnp,
            "exclude_bom": 'exclude_from_bom' in properties,
            "properties": {k:v for k,v in properties.items() if k in ('MPN','Spec')},
            "path": '/' + root_uuid + '/' + str(stamps[0][1]) if stamps else '',
        }
    nets = {}
    nets_node = [x for x in tree if isinstance(x, list) and x and x[0] == "nets"][0]
    for n in [x for x in nets_node if isinstance(x, list) and x[0] == "net"]:
        name = str([f for f in n if isinstance(f, list) and f[0] == "name"][0][1])
        nodes = []
        for f in [x for x in n if isinstance(x, list) and x[0] == "node"]:
            ref = str([q for q in f if isinstance(q, list) and q[0] == "ref"][0][1])
            pin = str([q for q in f if isinstance(q, list) and q[0] == "pin"][0][1])
            nodes.append((ref, pin))
        nets[name] = nodes
    return comps, nets


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
