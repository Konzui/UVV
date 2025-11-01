# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later
# Copied from UniV addon for weld functionality

"""
Core weld utility functions from UniV addon.
These functions are copied directly from UniV to ensure weld works exactly the same.
"""

import bmesh
from mathutils import Vector
from bmesh.types import BMLoop, BMLayerItem


def shared_crn(crn: BMLoop) -> BMLoop | None:
    """Get the shared corner (other side of edge). UniV ubm.py:21"""
    shared = crn.link_loop_radial_prev
    if shared != crn:
        return shared
    return None


def linked_crn_uv_by_island_index_unordered_included(crn: BMLoop, uv: BMLayerItem, idx: int):
    """
    Linked to arg corner by island index with arg corner.
    UniV ubm.py:691-694
    """
    first_co = crn[uv].uv
    return [l_crn for l_crn in crn.vert.link_loops if l_crn.face.index == idx and l_crn[uv].uv == first_co]


def copy_pos_to_target_with_select(crn, uv, idx):
    """
    Weld and Selects a common edge.
    This is Phase 2 of UniV's weld - handles non-sync mode.
    UniV ubm.py:842-859
    """
    next_crn_co = crn.link_loop_next[uv].uv
    shared = shared_crn(crn)
    if not shared:
        return

    shared[uv].select_edge = True

    for _crn in linked_crn_uv_by_island_index_unordered_included(shared, uv, idx):
        _crn_uv = _crn[uv]
        _crn_uv.uv = next_crn_co
        _crn_uv.select = True

    crn_co = crn[uv].uv
    shared_next = shared_crn(crn).link_loop_next

    for _crn in linked_crn_uv_by_island_index_unordered_included(shared_next, uv, idx):
        _crn_uv = _crn[uv]
        _crn_uv.uv = crn_co
        _crn_uv.select = True


def weld_crn_edge_by_idx(crn: BMLoop, crn_pair, idx, uv: BMLayerItem):
    """
    For Weld OT - welds two corners by averaging their UV coordinates.
    This is the EXACT implementation from UniV (ubm.py:862-890).

    Args:
        crn: First corner to weld
        crn_pair: Second corner to weld
        idx: Island index (face.index) to identify which corners belong to same island
        uv: UV layer
    """
    print(f"WELD FUNCTION: Called with crn={crn.index}, crn_pair={crn_pair.index}, idx={idx}")
    
    coords_sum_a = Vector((0.0, 0.0))

    corners = []
    corners_append = corners.append

    # Collect all corners at first vertex that share the same UV coordinate AND same island
    # UNIV BEHAVIOR: Only weld corners within the same island
    first_co = crn[uv].uv
    print(f"WELD FUNCTION: First corner UV = {first_co}")
    for crn_a in crn.vert.link_loops:
        if crn_a.face.index == idx:  # Only same island
            crn_a_uv = crn_a[uv]
            crn_a_co = crn_a_uv.uv
            if crn_a_co == first_co:  # ← Match UV coordinates exactly
                coords_sum_a += crn_a_co
                corners_append(crn_a_uv)
                print(f"WELD FUNCTION: Added corner from first vertex: {crn_a_co} (face.index={crn_a.face.index})")

    # Collect all corners at second vertex that share the same UV coordinate AND same island
    second_co = crn_pair[uv].uv
    print(f"WELD FUNCTION: Second corner UV = {second_co}")
    for crn_b in crn_pair.vert.link_loops:
        if crn_b.face.index == idx:  # Only same island
            crn_b_uv = crn_b[uv]
            crn_b_co = crn_b_uv.uv
            if crn_b_co == second_co:  # ← Match UV coordinates exactly
                coords_sum_a += crn_b_co
                corners_append(crn_b_uv)
                print(f"WELD FUNCTION: Added corner from second vertex: {crn_b_co} (face.index={crn_b.face.index})")

    # Calculate average and apply to all corners (UniV lines 887-890)
    if corners:
        avg_co_a = coords_sum_a / len(corners)
        print(f"WELD FUNCTION: Calculated average UV = {avg_co_a} for {len(corners)} corners")
        for crn_ in corners:
            crn_.uv = avg_co_a
        print(f"WELD FUNCTION: Applied average UV to all corners")
    else:
        print(f"WELD FUNCTION: No corners found to weld!")


def weld_crn_edge_by_dict(crn: BMLoop, crn_pair, face_to_island_idx: dict, idx: int, uv: BMLayerItem):
    """
    For Weld OT - welds two corners by averaging their UV coordinates.
    Uses a dictionary mapping instead of face.index.
    This is the exact implementation from uniV's weld_crn_edge_by_idx.

    Args:
        crn: First corner to weld
        crn_pair: Second corner to weld
        face_to_island_idx: Dictionary mapping face -> island index
        idx: Island index to identify which corners belong to same island
        uv: UV layer
    """
    coords_sum_a = Vector((0.0, 0.0))

    corners = []
    corners_append = corners.append

    # Collect all corners at first vertex that share the same UV coordinate AND same island
    # UNIV BEHAVIOR: Only weld corners within the same island
    first_co = crn[uv].uv
    for crn_a in crn.vert.link_loops:
        if crn_a.face.index == idx:  # Only same island
            crn_a_uv = crn_a[uv]
            crn_a_co = crn_a_uv.uv
            if (crn_a_co - first_co).length < 1e-6:
                coords_sum_a += crn_a_co
                corners_append(crn_a_uv)

    # Collect all corners at second vertex that share the same UV coordinate AND same island
    second_co = crn_pair[uv].uv
    for crn_b in crn_pair.vert.link_loops:
        if crn_b.face.index == idx:  # Only same island
            crn_b_uv = crn_b[uv]
            crn_b_co = crn_b_uv.uv
            if (crn_b_co - second_co).length < 1e-6:
                coords_sum_a += crn_b_co
                corners_append(crn_b_uv)

    # Calculate average and apply to all corners
    if corners:
        avg_co_a = coords_sum_a / len(corners)
        for crn_ in corners:
            crn_.uv = avg_co_a

