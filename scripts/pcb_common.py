"""Shared helpers for PCB generation scripts (pcbnew API)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp

import pcbnew

HW = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "hardware"))
SCH = os.path.join(HW, "ailink.kicad_sch")
PCB = os.path.join(HW, "ailink.kicad_pcb")
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
    comps = {}
    comp_node = [x for x in tree if isinstance(x, list) and x and x[0] == "components"][0]
    for c in [x for x in comp_node if isinstance(x, list) and x[0] == "comp"]:
        ref = str([f for f in c if isinstance(f, list) and f[0] == "ref"][0][1])
        fp_node = [f for f in c if isinstance(f, list) and f[0] == "footprint"]
        val_node = [f for f in c if isinstance(f, list) and f[0] == "value"]
        props = [f for f in c if isinstance(f, list) and f[0] == "property"]
        dnp = any(str(p[1]) == "dnp" for p in props)
        comps[ref] = {
            "footprint": str(fp_node[0][1]) if fp_node else "",
            "value": str(val_node[0][1]) if val_node else "",
            "dnp": dnp,
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
    fp = pcbnew.FootprintLoad(os.path.join(FP_DIR, lib + ".pretty"), name)
    if fp is None:
        raise RuntimeError(f"footprint not found: {fpid}")
    return fp
