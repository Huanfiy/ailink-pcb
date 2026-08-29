"""Minimal S-expression parser/serializer for KiCad files."""


class Sym(str):
    """Bare (unquoted) atom."""
    __slots__ = ()


def parse(text: str):
    """Parse an s-expression string into nested lists of Sym/str/int/float."""
    i = 0
    n = len(text)

    def skip_ws(idx):
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        return idx

    def parse_expr(idx):
        idx = skip_ws(idx)
        if idx >= n:
            raise ValueError("unexpected EOF")
        c = text[idx]
        if c == "(":
            idx += 1
            items = []
            while True:
                idx = skip_ws(idx)
                if idx >= n:
                    raise ValueError("unclosed list")
                if text[idx] == ")":
                    return items, idx + 1
                item, idx = parse_expr(idx)
                items.append(item)
        elif c == '"':
            idx += 1
            buf = []
            while idx < n:
                ch = text[idx]
                if ch == "\\" and idx + 1 < n:
                    nxt = text[idx + 1]
                    if nxt == "n":
                        buf.append("\n")
                    elif nxt == "t":
                        buf.append("\t")
                    else:
                        buf.append(nxt)
                    idx += 2
                elif ch == '"':
                    return "".join(buf), idx + 1
                else:
                    buf.append(ch)
                    idx += 1
            raise ValueError("unclosed string")
        else:
            start = idx
            while idx < n and text[idx] not in " \t\r\n()":
                idx += 1
            tok = text[start:idx]
            return Sym(tok), idx

    expr, i = parse_expr(0)
    return expr


def _fmt_atom(a):
    if isinstance(a, Sym):
        return str(a)
    if isinstance(a, bool):
        return "yes" if a else "no"
    if isinstance(a, float):
        # KiCad style: strip trailing zeros, keep up to 6 decimals
        s = f"{a:.6f}".rstrip("0").rstrip(".")
        return s if s != "-0" else "0"
    if isinstance(a, int):
        return str(a)
    # quoted string
    esc = str(a).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{esc}"'


def dumps(expr, indent=0) -> str:
    """Serialize nested lists to KiCad-style s-expression text."""
    if not isinstance(expr, list):
        return _fmt_atom(expr)
    pad = "  " * indent
    # Decide single-line vs multi-line: single-line if no nested list children
    # or short leaf lists like (at 1 2 3)
    has_list = any(isinstance(x, list) for x in expr)
    if not has_list:
        return "(" + " ".join(_fmt_atom(x) for x in expr) + ")"
    parts = []
    head = []
    idx = 0
    # leading atoms stay on the opening line
    while idx < len(expr) and not isinstance(expr[idx], list):
        head.append(_fmt_atom(expr[idx]))
        idx += 1
    opening = "(" + " ".join(head)
    parts.append(opening)
    for x in expr[idx:]:
        if isinstance(x, list):
            parts.append("  " * (indent + 1) + dumps(x, indent + 1))
        else:
            parts.append("  " * (indent + 1) + _fmt_atom(x))
    parts.append(pad + ")")
    return "\n".join(parts)


def find(expr, key):
    """First child list whose head == key."""
    for x in expr:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(expr, key):
    return [x for x in expr if isinstance(x, list) and x and x[0] == key]
