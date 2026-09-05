"""Extract, flatten and rename symbols from KiCad system libraries."""
import copy
import math
import os

import sexp
from sexp import Sym, find, find_all

KICAD_SYMBOL_DIR = "/usr/share/kicad/symbols"

_lib_cache = {}


def load_library(lib_nickname):
    if lib_nickname in _lib_cache:
        return _lib_cache[lib_nickname]
    if lib_nickname == "ailink":
        path = os.path.join(os.path.dirname(__file__), "..", "hardware", "lib", "ailink.kicad_sym")
    else:
        path = os.path.join(KICAD_SYMBOL_DIR, lib_nickname + ".kicad_sym")
    with open(path) as f:
        tree = sexp.parse(f.read())
    symbols = {}
    for node in find_all(tree, "symbol"):
        symbols[str(node[1])] = node
    _lib_cache[lib_nickname] = symbols
    return symbols


def _set_symbol_name(sym_expr, old_name, new_name):
    """Rename outer symbol and its unit sub-symbols."""
    sym_expr[1] = new_name
    short_new = new_name.split(":", 1)[-1]
    for sub in find_all(sym_expr, "symbol"):
        sub_name = str(sub[1])
        if sub_name.startswith(old_name + "_"):
            suffix = sub_name[len(old_name):]
            sub[1] = short_new + suffix
    return sym_expr


def get_symbol(lib_nickname, name, embed_name=None, value=None, extra_props=None):
    """Return a flattened copy of the symbol renamed to embed_name
    (default '<lib>:<name>'), ready to be embedded in lib_symbols."""
    lib = load_library(lib_nickname)
    if name not in lib:
        raise KeyError(f"{lib_nickname}:{name} not found")
    node = copy.deepcopy(lib[name])
    ext = find(node, "extends")
    if ext is not None:
        parent_name = str(ext[1])
        parent = copy.deepcopy(lib[parent_name])
        # merge: parent body, child property overrides
        child_props = {str(p[1]): p for p in find_all(node, "property")}
        merged = parent
        for i, item in enumerate(merged):
            if isinstance(item, list) and item and item[0] == "property":
                pname = str(item[1])
                if pname in child_props:
                    merged[i] = child_props.pop(pname)
        # append remaining child-only properties after last property
        if child_props:
            last_prop_idx = max(
                i for i, it in enumerate(merged)
                if isinstance(it, list) and it and it[0] == "property")
            for extra in child_props.values():
                last_prop_idx += 1
                merged.insert(last_prop_idx, extra)
        _set_symbol_name(merged, parent_name, name)
        node = merged
    final_name = embed_name or f"{lib_nickname}:{name}"
    _set_symbol_name(node, name, final_name)
    if value is not None:
        for p in find_all(node, "property"):
            if str(p[1]) == "Value":
                p[2] = value
    if extra_props:
        for k, v in extra_props.items():
            for p in find_all(node, "property"):
                if str(p[1]) == k:
                    p[2] = v
    return node


def get_pins(sym_expr):
    """All pins across units: list of dicts."""
    pins = []
    for sub in find_all(sym_expr, "symbol"):
        for pin in find_all(sub, "pin"):
            at = find(pin, "at")
            length = find(pin, "length")
            name = find(pin, "name")
            number = find(pin, "number")
            pins.append({
                "etype": str(pin[1]),
                "shape": str(pin[2]) if len(pin) > 2 and not isinstance(pin[2], list) else "line",
                "x": float(at[1]),
                "y": float(at[2]),
                "angle": float(at[3]) if len(at) > 3 else 0.0,
                "length": float(length[1]) if length else 2.54,
                "name": str(name[1]) if name else "",
                "number": str(number[1]) if number else "",
                "hidden": bool(find(pin, "hide")),
            })
    return pins


def pin_pos(sym_at_x, sym_at_y, sym_rot, mirror, pin):
    """Schematic-space electrical point of a pin for a placed instance.

    Symbol-space Y is up; schematic-space Y is down. KiCad applies mirror
    first, then rotation (counterclockwise in symbol space).
    """
    px, py = pin["x"], pin["y"]
    if mirror == "x":      # mirror about x-axis (vertical flip)
        py = -py
    elif mirror == "y":    # mirror about y-axis (horizontal flip)
        px = -px
    a = math.radians(sym_rot)
    rx = px * math.cos(a) - py * math.sin(a)
    ry = px * math.sin(a) + py * math.cos(a)
    return (round(sym_at_x + rx, 4), round(sym_at_y - ry, 4))


def pin_dir(sym_rot, mirror, pin):
    """Outward direction (away from body) unit vector in schematic space."""
    ang = pin["angle"]
    if mirror == "x":
        if ang in (90, 270):
            ang = (ang + 180) % 360
    elif mirror == "y":
        if ang in (0, 180):
            ang = (ang + 180) % 360
    # pin angle points from electrical point toward the body;
    # outward is the opposite
    out = (ang + 180.0) % 360.0
    total = math.radians(out + sym_rot)
    dx = math.cos(total)
    dy = -math.sin(total)
    return (round(dx), round(dy))
