"""Export and parse a KiCad s-expression netlist. No pcbnew dependency.

Shared by pcb_common (board generation) and verify_netlist (golden check) so
both read the schematic through one code path.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp


def _value(node, key, default=''):
    found = sexp.find_all(node, key)
    return str(found[0][1]) if found and len(found[0]) > 1 else default


def export(sch_path):
    """Run kicad-cli and return the parsed netlist tree."""
    with tempfile.TemporaryDirectory(prefix='ailink-netlist-') as directory:
        net_path = os.path.join(directory, 'ailink.net')
        subprocess.run(["kicad-cli", "sch", "export", "netlist",
                        "--format", "kicadsexpr", "-o", net_path, sch_path],
                       check=True, capture_output=True)
        with open(net_path) as handle:
            return sexp.parse(handle.read())


def nets(tree):
    """netname -> [(ref, pin), ...] in netlist order."""
    out = {}
    for net in sexp.find_all(sexp.find(tree, "nets"), "net"):
        out[_value(net, "name")] = [(_value(node, "ref"), _value(node, "pin"))
                                    for node in sexp.find_all(net, "node")]
    return out


def components(tree, root_uuid):
    """ref -> {footprint, value, dnp, exclude_bom, properties, path}."""
    comps = {}
    for comp in sexp.find_all(sexp.find(tree, "components"), "comp"):
        properties = {_value(p, 'name'): _value(p, 'value')
                      for p in sexp.find_all(comp, "property")}
        stamps = sexp.find_all(comp, 'tstamps')
        comps[_value(comp, "ref")] = {
            "footprint": _value(comp, "footprint"),
            "value": _value(comp, "value"),
            "dnp": 'dnp' in properties,
            "exclude_bom": 'exclude_from_bom' in properties,
            "properties": {k: v for k, v in properties.items() if k in ('MPN', 'Spec')},
            "path": '/' + root_uuid + '/' + str(stamps[0][1]) if stamps else '',
        }
    return comps


def schematic_uuid(sch_path):
    with open(sch_path) as handle:
        return str(sexp.find_all(sexp.parse(handle.read()), 'uuid')[0][1])


def load(sch_path):
    """Return (components, nets) for a schematic; see components() and nets()."""
    tree = export(sch_path)
    return components(tree, schematic_uuid(sch_path)), nets(tree)
