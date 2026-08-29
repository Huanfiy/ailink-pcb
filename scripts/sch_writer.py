"""KiCad 10 schematic (.kicad_sch) document builder."""
import uuid as _uuid

import symlib
from sexp import Sym, dumps, find

SCH_VERSION = 20250610
GENERATOR = "eeschema"
GENERATOR_VERSION = "9.99"


def new_uuid():
    return str(_uuid.uuid4())


def _effects(size=1.27, hide=False, justify=None, bold=False):
    font = [Sym("font"), [Sym("size"), size, size]]
    if bold:
        font.append([Sym("bold"), Sym("yes")])
    eff = [Sym("effects"), font]
    if justify:
        eff.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        eff.append([Sym("hide"), Sym("yes")])
    return eff


class Instance:
    """A placed symbol instance."""

    def __init__(self, doc, ref, embed_name, x, y, rot, mirror):
        self.doc = doc
        self.ref = ref
        self.embed_name = embed_name
        self.x, self.y, self.rot, self.mirror = x, y, rot, mirror
        self.pins = {p["number"]: p for p in symlib.get_pins(doc.lib[embed_name])}

    def pin(self, number):
        p = self.pins[str(number)]
        return symlib.pin_pos(self.x, self.y, self.rot, self.mirror, p)

    def pin_out_dir(self, number):
        p = self.pins[str(number)]
        return symlib.pin_dir(self.rot, self.mirror, p)

    def stub(self, number, length=2.54):
        """Draw a wire outward from the pin; return the far endpoint."""
        x0, y0 = self.pin(number)
        dx, dy = self.pin_out_dir(number)
        x1, y1 = round(x0 + dx * length, 4), round(y0 + dy * length, 4)
        self.doc.wire((x0, y0), (x1, y1))
        return (x1, y1)


class SchDoc:
    def __init__(self, title, paper="A2", rev="v0.3", company="", date=""):
        self.uuid = new_uuid()
        self.title, self.paper, self.rev = title, paper, rev
        self.company, self.date = company, date
        self.lib = {}          # embed_name -> symbol expr
        self.items = []        # placed graphics/symbols/wires...
        self.project_name = "ailink"
        self._pwr_count = 0
        self._flg_count = 0

    # ---------- library ----------
    def use_symbol(self, lib_nickname, name, embed_name=None, **kw):
        embed_name = embed_name or f"{lib_nickname}:{name}"
        if embed_name not in self.lib:
            self.lib[embed_name] = symlib.get_symbol(
                lib_nickname, name, embed_name=embed_name, **kw)
        return embed_name

    def add_external_symbol(self, embed_name, sym_expr):
        self.lib[embed_name] = sym_expr

    # ---------- placement ----------
    def place(self, ref, embed_name, x, y, rot=0, mirror=None, value=None,
              footprint="", dnp=False, in_bom=True, ref_hide=False,
              value_hide=False, value_at=None, props=None):
        inst = Instance(self, ref, embed_name, x, y, rot, mirror)
        at = [Sym("at"), x, y, rot]
        node = [Sym("symbol"),
                [Sym("lib_id"), embed_name],
                at,
                [Sym("unit"), 1],
                [Sym("exclude_from_sim"), Sym("no")],
                [Sym("in_bom"), Sym("yes") if in_bom else Sym("no")],
                [Sym("on_board"), Sym("yes")],
                [Sym("dnp"), Sym("yes") if dnp else Sym("no")],
                [Sym("uuid"), new_uuid()]]
        if mirror:
            at_idx = node.index(at)
            node.insert(at_idx + 1, [Sym("mirror"), Sym(mirror)])
        libsym = self.lib[embed_name]
        # default value: library Value property
        lib_value = ""
        for p in [q for q in libsym if isinstance(q, list) and q and q[0] == "property"]:
            if str(p[1]) == "Value":
                lib_value = str(p[2])
        val = value if value is not None else lib_value
        # property positions: reference above, value below symbol origin
        props_out = [
            ("Reference", ref, (x, y - 2.54), ref_hide),
            ("Value", val, value_at or (x, y + 2.54), value_hide),
            ("Footprint", footprint, (x, y), True),
            ("Datasheet", "", (x, y), True),
            ("Description", "", (x, y), True),
        ]
        if props:
            for k, v in props.items():
                props_out.append((k, v, (x, y), True))
        for pname, pval, (px, py), hide in props_out:
            pnode = [Sym("property"), pname, pval,
                     [Sym("at"), px, py, 0]]
            if hide:
                pnode.append([Sym("hide"), Sym("yes")])
            pnode.append(_effects(1.27))
            node.append(pnode)
        for pnum in inst.pins:
            node.append([Sym("pin"), pnum, [Sym("uuid"), new_uuid()]])
        node.append([Sym("instances"),
                     [Sym("project"), self.project_name,
                      [Sym("path"), "/" + self.uuid,
                       [Sym("reference"), ref],
                       [Sym("unit"), 1]]]])
        self.items.append(node)
        return inst

    def power(self, net, x, y, rot=0):
        """Place a power symbol (net: GND, +3V3, VBUS...)."""
        self._pwr_count += 1
        ref = f"#PWR{self._pwr_count:03d}"
        embed = self.use_symbol("power", net)
        return self.place(ref, embed, x, y, rot=rot, ref_hide=True)

    def pwr_flag(self, x, y, rot=0):
        self._flg_count += 1
        ref = f"#FLG{self._flg_count:03d}"
        embed = self.use_symbol("power", "PWR_FLAG")
        return self.place(ref, embed, x, y, rot=rot, ref_hide=True,
                          value_hide=True)

    # ---------- graphics / connectivity ----------
    def wire(self, p1, p2):
        if p1 == p2:
            return
        self.items.append(
            [Sym("wire"),
             [Sym("pts"), [Sym("xy"), p1[0], p1[1]], [Sym("xy"), p2[0], p2[1]]],
             [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("solid")]],
             [Sym("uuid"), new_uuid()]])

    def chain(self, points, junction_interior=True):
        """Wire consecutive points; junctions at interior points."""
        for a, b in zip(points, points[1:]):
            self.wire(a, b)
        if junction_interior:
            for p in points[1:-1]:
                self.junction(p)

    def junction(self, p):
        self.items.append(
            [Sym("junction"), [Sym("at"), p[0], p[1]],
             [Sym("diameter"), 0], [Sym("color"), 0, 0, 0, 0],
             [Sym("uuid"), new_uuid()]])

    def no_connect(self, p):
        self.items.append(
            [Sym("no_connect"), [Sym("at"), p[0], p[1]],
             [Sym("uuid"), new_uuid()]])

    def glabel(self, net, p, angle=0, shape="bidirectional", justify=None):
        if justify is None:
            justify = "left" if angle == 0 else "right"
        node = [Sym("global_label"), net,
                [Sym("shape"), Sym(shape)],
                [Sym("at"), p[0], p[1], angle],
                [Sym("fields_autoplaced"), Sym("yes")],
                _effects(1.27, justify=justify),
                [Sym("uuid"), new_uuid()],
                [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}",
                 [Sym("at"), p[0], p[1], 0],
                 _effects(1.27, hide=True)]]
        self.items.append(node)

    def label_right(self, net, p, shape="bidirectional"):
        """Label extending rightward from point (attach on its left)."""
        self.glabel(net, p, angle=0, shape=shape, justify="left")

    def label_left(self, net, p, shape="bidirectional"):
        self.glabel(net, p, angle=180, shape=shape, justify="right")

    def text(self, s, x, y, size=2.5, bold=True):
        self.items.append(
            [Sym("text"), s,
             [Sym("exclude_from_sim"), Sym("no")],
             [Sym("at"), x, y, 0],
             _effects(size, bold=bold, justify="left bottom"),
             [Sym("uuid"), new_uuid()]])

    # ---------- output ----------
    def dumps(self):
        root = [Sym("kicad_sch"),
                [Sym("version"), SCH_VERSION],
                [Sym("generator"), GENERATOR],
                [Sym("generator_version"), GENERATOR_VERSION],
                [Sym("uuid"), self.uuid],
                [Sym("paper"), self.paper],
                [Sym("title_block"),
                 [Sym("title"), self.title],
                 [Sym("date"), self.date],
                 [Sym("rev"), self.rev],
                 [Sym("company"), self.company]]]
        libs = [Sym("lib_symbols")]
        for name in sorted(self.lib):
            libs.append(self.lib[name])
        root.append(libs)
        root.extend(self.items)
        root.append([Sym("sheet_instances"),
                     [Sym("path"), "/", [Sym("page"), "1"]]])
        root.append([Sym("embedded_fonts"), Sym("no")])
        return dumps(root) + "\n"

    def save(self, path):
        with open(path, "w") as f:
            f.write(self.dumps())
