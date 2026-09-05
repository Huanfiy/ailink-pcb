#!/usr/bin/env python3
"""Remove DRC-reported dead copper without changing pad connectivity.

Work in an isolated project and accept changes only after native, refilled DRC
shows no regression. Zone-connected nets are left alone. Dangling vias on
unfinished nets are kept as routing access points; dead tracks may be pruned.
"""
from collections import Counter
from copy import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pcbnew
import pcb_common as pc
from fanout_product import Geometry, connected_groups


def pad_partition(geometry, net, skip=()):
    geometry = copy(geometry)
    geometry.items = [entry for entry in geometry.items
                      if entry[0].m_Uuid.AsString() not in skip]
    return frozenset(
        frozenset(item.m_Uuid.AsString() for item in group
                  if item.GetClass() == 'PAD')
        for group in connected_groups(geometry, net)
        if any(item.GetClass() == 'PAD' for item in group)
    )


def drc(path, report):
    subprocess.run([
        'kicad-cli', 'pcb', 'drc', '--severity-all', '--schematic-parity',
        '--refill-zones', '--save-board', '--format', 'json',
        '-o', str(report), str(path),
    ], check=True)
    return json.loads(report.read_text())


def issue_counts(report):
    return Counter((section, item['type'], item['severity'])
                   for section in ('violations', 'unconnected_items', 'schematic_parity')
                   for item in report[section])


def clean_pass(board, report):
    zone_nets = {zone.GetNetname() for zone in board.Zones()
                 if not zone.GetIsRuleArea()}
    geometry = Geometry(board)
    by_id = {item.m_Uuid.AsString(): item for item in board.GetTracks()}
    removed = []
    for violation in report['violations']:
        if violation['type'] not in ('via_dangling', 'track_dangling'):
            continue
        for entry in violation['items']:
            uuid = entry['uuid']
            item = by_id.get(uuid)
            if item is None or item.GetNetname() in zone_nets:
                continue
            net = item.GetNetname()
            before = pad_partition(geometry, net)
            # Keep unfinished vias as layer access, but prune dead track ends
            # on any net when all existing terminal connections are preserved.
            if violation['type'] == 'via_dangling' and len(before) != 1:
                continue
            if pad_partition(geometry, net, (uuid,)) != before:
                continue
            kind = item.GetClass()
            board.Remove(item)
            del by_id[uuid]
            geometry.items = [entry for entry in geometry.items
                              if entry[0].m_Uuid.AsString() != uuid]
            removed.append((net, kind, uuid))
    return removed


def main():
    source = Path(pc.PCB).resolve()
    original_bytes = source.read_bytes()
    all_removed = []
    with tempfile.TemporaryDirectory(prefix='ailink-cleanup-') as directory:
        project = Path(directory) / 'hardware'
        shutil.copytree(pc.HW, project)
        candidate = project / 'ailink.kicad_pcb'
        shutil.copy2(source, candidate)
        report_path = project / 'cleanup-drc.json'
        baseline = drc(candidate, report_path)
        report = baseline
        removed_path = project / 'removed.json'
        for _ in range(32):
            # KiCad 10's SWIG wrappers can decay after repeated LoadBoard calls
            # in one interpreter. Each mutation pass gets a fresh process.
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--pass',
                            str(candidate), str(report_path), str(removed_path)], check=True)
            removed = json.loads(removed_path.read_text())
            if not removed:
                break
            report = drc(candidate, report_path)
            if issue_counts(report)['unconnected_items', 'unconnected_items', 'error'] > \
                    issue_counts(baseline)['unconnected_items', 'unconnected_items', 'error']:
                raise RuntimeError('Cleanup would increase unconnected items; source unchanged')
            unexpected = issue_counts(report) - issue_counts(baseline)
            # Removing a dead via can expose its dead track; the next pass removes it.
            unexpected = {key: count for key, count in unexpected.items()
                          if key[1] not in ('via_dangling', 'track_dangling')}
            if unexpected:
                raise RuntimeError(f'Cleanup DRC regression: {unexpected}; source unchanged')
            all_removed.extend(removed)
        else:
            raise RuntimeError('Cleanup did not converge; source unchanged')
        if all_removed:
            if source.read_bytes() != original_bytes:
                raise RuntimeError('Source changed during cleanup; refusing to overwrite it')
            with tempfile.NamedTemporaryFile(prefix=f'.{source.name}.cleanup-',
                                             dir=source.parent, delete=False) as handle:
                replacement = Path(handle.name)
            try:
                shutil.copy2(candidate, replacement)
                os.replace(replacement, source)
            finally:
                replacement.unlink(missing_ok=True)
    for net, kind, uuid in all_removed:
        print(f'Removed {kind} {net} {uuid}')
    print(f'Cleanup: {len(all_removed)} redundant copper items removed; pad connectivity preserved')


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--pass':
        board = pcbnew.LoadBoard(sys.argv[2])
        removed = clean_pass(board, json.loads(Path(sys.argv[3]).read_text()))
        if removed:
            pcbnew.SaveBoard(sys.argv[2], board)
        Path(sys.argv[4]).write_text(json.dumps(removed))
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit('Usage: cleanup_routes.py (board selected by AILINK_HW/AILINK_PCB)')
