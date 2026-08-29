#!/usr/bin/env python3
"""USB DP/DM main-path length / intra-pair skew.

Reads USB_DP / USB_DM copper, builds an endpoint graph (0.01 mm snap,
including T-junctions), then reports the U1→J1 A6/A7 main path.
Vias add 0.5 mm equivalent length. TP6/TP7 and J1 B6/B7 stubs are
excluded from the main path and listed separately.

Default board: pcb_common.PCB. Pass a path (e.g. /tmp/si_dev.kicad_pcb)
to analyze a copy. pcbnew import may emit PROPERTY_ENUM asserts on
stderr; that is expected.
"""
from __future__ import annotations

import hashlib
import heapq
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc

import pcbnew

TOL_MM = 0.01
VIA_EQ_MM = 0.5
MATCH_REQ_MM = 2.0

# Main path endpoints and stubs excluded from the main length.
MAIN_PADS = {
    "USB_DP": (("U1", "45"), ("J1", "A6")),
    "USB_DM": (("U1", "44"), ("J1", "A7")),
}
STUB_PADS = {
    "USB_DP": (("J1", "B6"), ("TP6", "1")),
    "USB_DM": (("J1", "B7"), ("TP7", "1")),
}


def _mm(pt):
    return (pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y))


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _on_segment(p, a, b, tol=TOL_MM):
    """True if p lies on segment ab within tol (including near-endpoint)."""
    ax, ay = a
    bx, by = b
    px, py = p
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    l2 = vx * vx + vy * vy
    if l2 < 1e-18:
        return _dist(p, a) <= tol
    t = (wx * vx + wy * vy) / l2
    if t < -1e-9 or t > 1.0 + 1e-9:
        return False
    t = max(0.0, min(1.0, t))
    return _dist(p, (ax + t * vx, ay + t * vy)) <= tol


def _param_on_segment(p, a, b):
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    l2 = vx * vx + vy * vy
    if l2 < 1e-18:
        return 0.0
    return ((p[0] - ax) * vx + (p[1] - ay) * vy) / l2


class PointSnap:
    """Union nearby XY points within TOL_MM onto a canonical coordinate."""

    def __init__(self, tol=TOL_MM):
        self.tol = tol
        self.canon = []  # list of (x, y)

    def add(self, p):
        for c in self.canon:
            if _dist(p, c) <= self.tol:
                return c
        self.canon.append(p)
        return p

    def nearest(self, p, max_d=0.05):
        best, bd = None, max_d
        for c in self.canon:
            d = _dist(p, c)
            if d <= bd:
                best, bd = c, d
        return best


def _collect_net(board, netname):
    segs = []  # (start, end, layer, length)
    vias = []  # (x, y)
    for t in board.GetTracks():
        if t.GetNetname() != netname:
            continue
        if t.GetClass() == "PCB_VIA":
            vias.append(_mm(t.GetStart()))
            continue
        s, e = _mm(t.GetStart()), _mm(t.GetEnd())
        segs.append((s, e, t.GetLayerName(), _dist(s, e)))
    return segs, vias


def _pad_xy(board, ref, pin):
    for fp in board.GetFootprints():
        if fp.GetReference() != ref:
            continue
        for pad in fp.Pads():
            if str(pad.GetNumber()) == str(pin):
                return _mm(pad.GetPosition())
    return None


def _split_segments(segs, extra_pts):
    """Split each segment at T-junctions / vias / pads that land on it."""
    out = []
    for a, b, layer, _length in segs:
        hits = [a, b]
        for p in extra_pts:
            if _on_segment(p, a, b):
                hits.append(p)
        # unique by rounded coord
        uniq = []
        for p in hits:
            if not any(_dist(p, q) <= TOL_MM * 0.5 for q in uniq):
                uniq.append(p)
        uniq.sort(key=lambda p: _param_on_segment(p, a, b))
        for p, q in zip(uniq, uniq[1:]):
            ln = _dist(p, q)
            if ln < 1e-6:
                continue
            out.append((p, q, layer, ln))
    return out


def _build_graph(segs, vias, snap: PointSnap):
    """Adjacency: node -> list of (nbr, copper_len, layer).

    Via nodes also get a VIA_EQ_MM edge between the same XY if multiple
    layers meet; layer-change cost is applied during the walk instead.
    """
    graph = {}
    via_nodes = set()

    def add_edge(a, b, length, layer):
        graph.setdefault(a, []).append((b, length, layer))
        graph.setdefault(b, []).append((a, length, layer))

    for a, b, layer, length in segs:
        sa, sb = snap.add(a), snap.add(b)
        add_edge(sa, sb, length, layer)

    for v in vias:
        via_nodes.add(snap.add(v))

    return graph, via_nodes


def _dijkstra(graph, via_nodes, start, goals):
    """Shortest path. Layer change at a via node costs VIA_EQ_MM.

    `goals` is a set of nodes. Returns (total_mm, n_vias, path_nodes) or None.
    State is (node, last_layer).
    """
    if start is None or not goals:
        return None
    # (cost, seq, node, last_layer, n_vias)
    pq = [(0.0, 0, start, None, 0)]
    best = {}
    prev = {}
    seq = 0
    found = None
    while pq:
        cost, _, node, last_layer, n_vias = heapq.heappop(pq)
        key = (node, last_layer)
        if key in best and best[key] <= cost + 1e-12:
            continue
        best[key] = cost
        if node in goals and last_layer is not None:
            found = (cost, n_vias, node, last_layer)
            break
        if node in goals and last_layer is None and node == start:
            # degenerate: start==goal
            found = (cost, n_vias, node, last_layer)
            break
        for nbr, length, layer in graph.get(node, ()):
            extra = 0.0
            nv = n_vias
            if last_layer is not None and layer != last_layer:
                extra = VIA_EQ_MM
                nv += 1
            elif last_layer is not None and layer == last_layer:
                extra = 0.0
            ncost = cost + length + extra
            nkey = (nbr, layer)
            if nkey in best and best[nkey] <= ncost + 1e-12:
                continue
            seq += 1
            prev[nkey] = (node, last_layer)
            heapq.heappush(pq, (ncost, seq, nbr, layer, nv))

    if found is None:
        # start is already a goal and isolated
        if start in goals:
            return 0.0, 0, [start]
        return None

    cost, n_vias, node, last_layer = found
    path = [node]
    key = (node, last_layer)
    while key in prev:
        pnode, player = prev[key]
        path.append(pnode)
        key = (pnode, player)
        if pnode == start and player is None:
            break
    path.reverse()
    return cost, n_vias, path


def _nearest_node(snap, p):
    if p is None:
        return None
    n = snap.nearest(p)
    if n is None:
        n = snap.add(p)
    return n


def _analyze_net(board, netname, snap_seed=None):
    segs, vias = _collect_net(board, netname)
    (u_ref, u_pin), (j_ref, j_pin) = MAIN_PADS[netname]
    u_xy = _pad_xy(board, u_ref, u_pin)
    j_xy = _pad_xy(board, j_ref, j_pin)
    stub_xys = []
    stub_meta = []
    for ref, pin in STUB_PADS[netname]:
        xy = _pad_xy(board, ref, pin)
        stub_xys.append(xy)
        stub_meta.append((f"{ref}.{pin}", xy))

    extra = [p for p in [u_xy, j_xy, *stub_xys, *vias] if p is not None]
    for a, b, _layer, _ln in segs:
        extra.append(a)
        extra.append(b)
    split = _split_segments(segs, extra)
    snap = PointSnap()
    graph, via_nodes = _build_graph(split, vias, snap)

    u_node = _nearest_node(snap, u_xy)
    j_node = _nearest_node(snap, j_xy)
    main = _dijkstra(graph, via_nodes, u_node, {j_node} if j_node else set())
    if main is None:
        return {
            "ok": False,
            "error": f"{netname}: no path {u_ref}.{u_pin} -> {j_ref}.{j_pin}",
            "segs": len(segs),
            "vias_on_net": len(vias),
        }

    length, n_vias, path = main
    main_nodes = set(path)

    stubs = []
    for name, xy in stub_meta:
        if xy is None:
            stubs.append((name, None, "pad not found"))
            continue
        sn = _nearest_node(snap, xy)
        res = _dijkstra(graph, via_nodes, sn, main_nodes)
        if res is None:
            stubs.append((name, None, "not connected to main path"))
        else:
            slen, sv, _sp = res
            stubs.append((name, slen, f"{sv} vias" if sv else "no via"))

    return {
        "ok": True,
        "length": length,
        "n_vias": n_vias,
        "path_nodes": len(path),
        "stubs": stubs,
        "segs": len(segs),
        "vias_on_net": len(vias),
        "u_pad": f"{u_ref}.{u_pin}",
        "j_pad": f"{j_ref}.{j_pin}",
    }


def _file_meta(path):
    st = os.stat(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return st.st_mtime, h.hexdigest()[:16]


def report(board_path):
    mtime, digest = _file_meta(board_path)
    board = pcbnew.LoadBoard(board_path)
    lines = []
    lines.append("USB differential pair — main-path length (U1 → J1 A6/A7)")
    lines.append(f"board: {os.path.abspath(board_path)}")
    lines.append(f"mtime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))}  sha256[:16]={digest}")
    lines.append(f"method: endpoint graph tol={TOL_MM} mm; via equivalent={VIA_EQ_MM} mm; "
                 "T-junctions split; stubs TP6/TP7 and J1 B6/B7 excluded")
    lines.append("")

    results = {}
    for net in ("USB_DP", "USB_DM"):
        results[net] = _analyze_net(board, net)

    for net in ("USB_DP", "USB_DM"):
        r = results[net]
        if not r["ok"]:
            lines.append(f"{net}: ERROR {r['error']}")
            continue
        lines.append(
            f"{net} main path {r['u_pad']} -> {r['j_pad']}: "
            f"{r['length']:.2f} mm ({r['n_vias']} vias)"
        )

    if all(results[n]["ok"] for n in ("USB_DP", "USB_DM")):
        dp = results["USB_DP"]["length"]
        dm = results["USB_DM"]["length"]
        skew = abs(dp - dm)
        ok = skew <= MATCH_REQ_MM
        lines.append(f"intra-pair mismatch: {skew:.2f} mm "
                     f"(requirement <= {MATCH_REQ_MM:.0f} mm)")
        lines.append(f"conclusion: {'PASS' if ok else 'FAIL'} "
                     f"({'within' if ok else 'exceeds'} {MATCH_REQ_MM:.0f} mm)")
    else:
        lines.append("conclusion: FAIL (path missing)")

    lines.append("")
    lines.append("stubs (excluded from main path):")
    any_stub = False
    for net in ("USB_DP", "USB_DM"):
        r = results[net]
        if not r["ok"]:
            continue
        for name, slen, note in r["stubs"]:
            any_stub = True
            if slen is None:
                lines.append(f"  {net} {name}: {note}")
            else:
                lines.append(f"  {net} {name}: {slen:.2f} mm ({note})")
    if not any_stub:
        lines.append("  (none)")

    lines.append("")
    lines.append("coupled section: 0.35 mm width / 0.15 mm gap on F.Cu "
                 "over the In1 GND plane (target 90 ohm differential, "
                 "JLC7628 stackup; tune width to fab coupon)")
    return "\n".join(lines) + "\n", results


def main():
    board_path = sys.argv[1] if len(sys.argv) > 1 else pc.PCB
    text, _results = report(board_path)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
