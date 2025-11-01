# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Utility functions for Relax operator.
Based on UniV's utils/ubm.py implementation.
"""

import bmesh
from bmesh.types import BMLoop, BMLayerItem, BMFace, BMEdge, BMVert
from typing import List, Any
from mathutils import Vector


def calc_selected_verts(umesh) -> List[BMVert]:
    """Calculate selected vertices from umesh - UniV exact implementation"""
    if umesh.is_full_vert_deselected:
        return []
    if umesh.is_full_vert_selected:
        return umesh.bm.verts
    return [v for v in umesh.bm.verts if v.select]


def calc_selected_edges(umesh) -> List[BMEdge]:
    """Calculate selected edges from umesh - UniV exact implementation"""
    if umesh.is_full_edge_deselected:
        return []
    if umesh.is_full_edge_selected:
        return umesh.bm.edges
    return [e for e in umesh.bm.edges if e.select]


def calc_selected_uv_faces(umesh) -> List[BMFace]:
    """Calculate selected UV faces from umesh - UniV exact implementation"""
    if umesh.is_full_face_deselected:
        return []

    if umesh.sync:
        if umesh.is_full_face_selected:
            return umesh.bm.faces
        return [f for f in umesh.bm.faces if f.select]

    uv = umesh.uv
    if umesh.is_full_face_selected:
        if umesh.elem_mode == 'VERT':
            return [f for f in umesh.bm.faces if all(crn[uv].select for crn in f.loops)]
        else:
            return [f for f in umesh.bm.faces if all(crn[uv].select_edge for crn in f.loops)]
    if umesh.elem_mode == 'VERT':
        return [f for f in umesh.bm.faces if all(crn[uv].select for crn in f.loops) and f.select]
    else:
        return [f for f in umesh.bm.faces if all(crn[uv].select_edge for crn in f.loops) and f.select]


def linked_crn_uv_unordered(crn: BMLoop, uv: BMLayerItem) -> List[BMLoop]:
    """Get linked corners at same UV position (unordered)"""
    first_co = crn[uv].uv
    linked = [l_crn for l_crn in crn.vert.link_loops if l_crn[uv].uv == first_co]
    linked.remove(crn)
    return linked


def linked_crn_uv_unordered_included(crn: BMLoop, uv: BMLayerItem) -> List[BMLoop]:
    """Get linked corners at same UV position (unordered, including input)"""
    first_co = crn[uv].uv
    linked = [l_crn for l_crn in crn.vert.link_loops if l_crn[uv].uv == first_co]
    return linked


def is_boundary_sync(crn: BMLoop, uv: BMLayerItem) -> bool:
    """Check if corner is on boundary in sync mode"""
    if (_shared_crn := crn.link_loop_radial_prev) == crn:
        return True
    if _shared_crn.face.hide:
        return True
    return not (crn[uv].uv == _shared_crn.link_loop_next[uv].uv and
                crn.link_loop_next[uv].uv == _shared_crn[uv].uv)


def is_boundary_non_sync(crn: BMLoop, uv: BMLayerItem) -> bool:
    """Check if corner is on boundary in non-sync mode"""
    if (next_linked_disc := crn.link_loop_radial_prev) == crn:
        return True
    if not next_linked_disc.face.select:
        return True
    return not (crn[uv].uv == next_linked_disc.link_loop_next[uv].uv and
                crn.link_loop_next[uv].uv == next_linked_disc[uv].uv)


def shared_is_linked(crn: BMLoop, _shared_crn: BMLoop, uv: BMLayerItem) -> bool:
    """Check if corners share UV edge"""
    return (crn.link_loop_next[uv].uv == _shared_crn[uv].uv and
            crn[uv].uv == _shared_crn.link_loop_next[uv].uv)


def linked_crn_to_vert_pair_with_seam(crn: BMLoop, uv: BMLayerItem, sync: bool) -> List[BMLoop]:
    """Get linked corners to vertex pair with seam consideration"""
    is_invisible = is_invisible_func(sync)
    first_vert = crn.vert
    linked = []
    bm_iter = crn
    iterated = False
    
    while True:
        prev_crn = bm_iter.link_loop_prev
        pair_ccw = prev_crn.link_loop_radial_prev
        
        if pair_ccw == crn and iterated:
            break
        iterated = True
        
        # Finish CCW
        if (pair_ccw in (prev_crn, crn) or
            (first_vert != pair_ccw.vert) or
            pair_ccw.edge.seam or
            is_invisible(pair_ccw.face) or
            not is_pair(prev_crn, pair_ccw, uv)):
            
            bm_iter = crn
            linked_cw = []
            while True:
                pair_cw = bm_iter.link_loop_radial_prev
                if pair_cw == bm_iter:
                    break
                
                next_crn = pair_cw.link_loop_next
                if next_crn == crn:
                    break
                
                if ((first_vert != next_crn.vert) or
                    pair_cw.edge.seam or
                    is_invisible(next_crn.face) or
                    not is_pair(bm_iter, pair_cw, uv)):
                    break
                
                bm_iter = next_crn
                linked_cw.append(next_crn)
            
            linked.extend(linked_cw[::-1])
            break
        
        bm_iter = pair_ccw
        linked.append(pair_ccw)
    
    return linked


def is_invisible_func(sync: bool):
    """Get function to check if face is invisible"""
    if sync:
        return lambda f: f.hide
    else:
        return lambda f: f.hide or not f.select


def is_pair(crn: BMLoop, _rad_prev: BMLoop, uv: BMLayerItem) -> bool:
    """Check if corners form a UV pair"""
    return (crn.link_loop_next[uv].uv == _rad_prev[uv].uv and
            crn[uv].uv == _rad_prev.link_loop_next[uv].uv)


def linked_crn_uv_by_island_index_unordered_included(crn: BMLoop, uv: BMLayerItem, idx: int) -> List[BMLoop]:
    """Get linked corners by island index (unordered, including input)"""
    first_co = crn[uv].uv
    return [l_crn for l_crn in crn.vert.link_loops if l_crn.face.index == idx and l_crn[uv].uv == first_co]


