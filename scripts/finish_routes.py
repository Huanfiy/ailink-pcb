#!/usr/bin/env python3
"""Join actual disconnected copper groups, preserving completed routes.

The grid search proposes paths; native copper-shape checks validate every
segment/via before insertion. Existing isolated groups are never presumed
connected merely because they have the same net name.
"""
import sys
import os
import math
import pcbnew
import pcb_common as pc
import astar_router as ar
from fanout_product import Geometry,connected_groups
from product_config import PLANE_NETS,POWER_WIDTH_NETS,PROTECTED_NETS


def seeds(group,grid):
    out={}
    for item in group:
        if item.GetClass()=='PAD':
            layers=[i for i,l in ar.LAYER_ID.items() if item.IsOnLayer(l)]
            points=[item.GetPosition()]
        elif item.GetClass()=='PCB_VIA':
            layers=list(ar.LAYER_ID);points=[item.GetPosition()]
        else:
            layers=[i for i,l in ar.LAYER_ID.items() if item.GetLayer()==l]
            points=[item.GetStart(),item.GetEnd()]
        for layer in layers:
            for point in points:
                node=(layer,*ar.cell(pc.to_mm(point.x),pc.to_mm(point.y)))
                if 0<=node[1]<ar.NX and 0<=node[2]<ar.NY and grid.track_allowed(layer,node[1],node[2]):
                    out[node]=(pc.to_mm(point.x),pc.to_mm(point.y))
    return out


def join_net(board,net,step):
    power=net in PLANE_NETS
    ar.TRACK_W=.2 if net in POWER_WIDTH_NETS else .15
    ar.set_step(step,.155)
    geometry=Geometry(board)
    groups=connected_groups(geometry,net,with_zones=power)
    if len(groups)<=1:return True
    grid=ar.build_grid(board,{net})
    groups.sort(key=lambda g:-len(g))
    merged=groups.pop(0)
    while groups:
        target=seeds(merged,grid)
        candidate_groups=sorted(groups,key=lambda group:min(
            (abs(node[1]-goal[1])+abs(node[2]-goal[2]) for node in seeds(group,grid) for goal in target),
            default=1e9))
        for group in candidate_groups:
            source=seeds(group,grid)
            if not source or not target:continue
            accepted=False
            for attempt in range(24):
                path=ar.astar(grid,set(source),set(target))
                if not path:break
                segs,vias=ar.path_to_geometry(path)
                first,last=path[0],path[-1]
                segs=[(first[0],[source[first],ar.coord(first[1:])])]+segs+[
                    (last[0],[ar.coord(last[1:]),target[last]])]
                bad_vias=[point for point in vias if not geometry.free_via(net,pc.pt(*point))]
                if bad_vias:
                    for point in bad_vias:grid.block_via_disc(*point,.08)
                    continue
                bad_tracks=[(layer,a,b) for layer,points in segs for a,b in zip(points,points[1:])
                            if not geometry.free_track(net,ar.LAYER_ID[layer],pc.pt(*a),pc.pt(*b),ar.TRACK_W)]
                if bad_tracks:
                    # A diagonal grid edge can clip a clearance capsule even
                    # when its end cells are free. Block that crossing and
                    # let the search propose another native-checked path.
                    for layer,a,b in bad_tracks:
                        n=max(1,math.ceil(math.dist(a,b)/(step/3)))
                        for k in range(n+1):
                            p=(a[0]+(b[0]-a[0])*k/n,a[1]+(b[1]-a[1])*k/n)
                            if geometry.free_track(net,ar.LAYER_ID[layer],pc.pt(*p),pc.pt(*p),ar.TRACK_W):continue
                            ar.Grid.block_disc(grid,layer,*p,step*.8)
                    source={node:p for node,p in source.items() if grid.track_allowed(*node)}
                    target={node:p for node,p in target.items() if grid.track_allowed(*node)}
                    if not source or not target:break
                    continue
                accepted=True
                break
            if not accepted:continue
            ar.add_route(board,net,segs,vias)
            if power:pcbnew.ZONE_FILLER(board).Fill(board.Zones())
            merged+=group;groups.remove(group)
            # Refresh connectivity after a route: touching another same-net
            # group can complete more than one requested connection.
            geometry=Geometry(board)
            fresh=connected_groups(geometry,net,with_zones=power)
            if len(fresh)<=1:return True
            fresh.sort(key=lambda g:-len(g));merged=fresh[0];groups=fresh[1:]
            break
        else:
            print(f'{net}: {len(groups)} gaps remain at {step} mm grid',flush=True)
            return False
    return True


def main():
    if os.environ.get('AILINK_INNER_SIGNALS')=='1':ar.enable_inner_signals()
    board=pcbnew.LoadBoard(pc.PCB)
    selected=sys.argv[1:] or sorted(n.GetNetname() for n in board.GetNetsByName().values()
                                  if n.GetNetname() not in ('',)+PLANE_NETS+PROTECTED_NETS
                                  and not n.GetNetname().startswith('unconnected'))
    pending=selected
    for step in (.1,.05,.025):
        failed=[]
        for net in pending:
            if join_net(board,net,step):print(f'{net}: connected',flush=True)
            else:failed.append(net)
            pcbnew.SaveBoard(pc.PCB,board)
        pending=failed
        if not pending:break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    # New L3 signal escapes can split an otherwise connected 3.3 V pour.
    # Repair actual filled-plane groups, not merely nets that contain vias.
    for net in PLANE_NETS:
        if net in selected:
            continue
        for step in (.1,.05,.025):
            if join_net(board,net,step):
                print(f'{net}: filled-plane connectivity preserved',flush=True)
                break
        else:
            pending.append(net)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pc.PCB,board)
    print('Remaining:',pending,flush=True)
    return bool(pending)


if __name__=='__main__':sys.exit(main())
