#!/usr/bin/env python3
"""Import routing while restoring exact locked critical-net geometry."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_common as pc
from product_config import PLANE_NETS, PROTECTED_NETS

import pcbnew

SES = sys.argv[1] if len(sys.argv)>1 else "/tmp/ailink.ses"

board = pcbnew.LoadBoard(pc.PCB)
protected = set(PROTECTED_NETS)
# Specctra sessions omit pre-existing fixed objects. Power fanouts are marked
# fixed by export_dsn.py and therefore must be restored from the source board.
fixed_nets = protected | set(PLANE_NETS)
saved = []
for t in board.GetTracks():
    if t.GetNetname() not in fixed_nets and not t.IsLocked():
        continue
    saved.append(dict(net=t.GetNetname(),start=(t.GetStart().x,t.GetStart().y),
                      end=(t.GetEnd().x,t.GetEnd().y),layer=t.GetLayer(),
                      via=t.GetClass()=='PCB_VIA',
                      width=t.GetFrontWidth() if t.GetClass()=='PCB_VIA' else t.GetWidth(),
                      drill=t.GetDrillValue() if t.GetClass()=='PCB_VIA' else 0))
ok = pcbnew.ImportSpecctraSES(board, SES)
if not ok:
    raise RuntimeError('SES import failed; board not saved')
old = list(board.GetTracks())
for t in old:
    if t.GetNetname() in protected:
        board.Remove(t)
nets = board.GetNetsByName()
def key(t):
    if t.GetClass()=='PCB_VIA':
        return (t.GetNetname(),'via',t.GetPosition().x,t.GetPosition().y)
    return (t.GetNetname(),t.GetLayer(),tuple(sorted(((t.GetStart().x,t.GetStart().y),
                                                   (t.GetEnd().x,t.GetEnd().y)))))
existing={key(t):t for t in board.GetTracks()}
for rec in saved:
    identity = ((rec['net'],'via',*rec['start']) if rec['via'] else
                (rec['net'],rec['layer'],tuple(sorted((rec['start'],rec['end'])))))
    if identity in existing:
        existing[identity].SetLocked(True)
        continue
    t = pcbnew.PCB_VIA(board) if rec['via'] else pcbnew.PCB_TRACK(board)
    if rec['via']:
        t.SetPosition(pcbnew.VECTOR2I(*rec['start']))
        t.SetDrill(rec['drill'])
        t.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
    else:
        t.SetStart(pcbnew.VECTOR2I(*rec['start']))
        t.SetEnd(pcbnew.VECTOR2I(*rec['end']))
        t.SetLayer(rec['layer'])
    t.SetWidth(rec['width'])
    t.SetNet(nets[rec['net']])
    t.SetLocked(True)
    board.Add(t)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
print(f"SES imported; restored {len(saved)} locked objects on {sorted(protected)}")
pcbnew.SaveBoard(pc.PCB, board)
