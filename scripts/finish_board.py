#!/usr/bin/env python3
"""Sync sourcing/assembly data, tent vias, set origin and preview stackup."""
from pathlib import Path
import pcbnew
import pcb_common as pc
import sexp

STACKUP='''(stackup
 (layer "F.SilkS" (type "Top Silk Screen") (color "White"))
 (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (color "Black") (thickness 0.01))
 (layer "F.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "FR4") (epsilon_r 4.4) (loss_tangent 0.02))
 (layer "In1.Cu" (type "copper") (thickness 0.0175))
 (layer "dielectric 2" (type "core") (thickness 1.0742) (material "FR4") (epsilon_r 4.4) (loss_tangent 0.02))
 (layer "In2.Cu" (type "copper") (thickness 0.0175))
 (layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "FR4") (epsilon_r 4.4) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0.035))
 (layer "B.Mask" (type "Bottom Solder Mask") (color "Black") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste"))
 (layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
 (copper_finish "ENIG") (dielectric_constraints no))'''


def main():
    board=pcbnew.LoadBoard(pc.PCB)
    comps,_=pc.load_netlist()
    for fp in board.GetFootprints():
        meta=comps[fp.GetReference()]
        library=pc.load_footprint(meta['footprint'])
        fp.SetAttributes(library.GetAttributes())
        fp.Models().clear()
        for model in library.Models():fp.Models().push_back(model)
        pc.sync_footprint(board,fp,meta)
    for via in board.GetTracks():
        if via.GetClass()=='PCB_VIA':
            via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
            via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    # Fabrication/placement origin: lower left of the rectangular board frame.
    board.GetDesignSettings().SetAuxOrigin(pc.pt(100,122))
    board.GetDesignSettings().SetGridOrigin(pc.pt(100,122))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB,board)
    path=Path(pc.PCB)
    root=sexp.parse(path.read_text())
    setup=sexp.find_all(root,'setup')[0]
    for old in list(sexp.find_all(setup,'stackup')):setup.remove(old)
    setup.insert(1,sexp.parse(STACKUP))
    path.write_text(sexp.dumps(root)+'\n')
    # Restore canonical KiCad formatting and verify that the stackup parses.
    board=pcbnew.LoadBoard(str(path))
    pcbnew.SaveBoard(str(path),board)
    print('Assembly flags, schematic identity, via tenting and preview stackup synced')


if __name__=='__main__':main()
