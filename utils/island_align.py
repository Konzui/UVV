"""
Island Alignment for Weld Operations
Based on UniV's reorient_to_target method (stitch_and_weld.py lines 137-223)

This module implements the sophisticated island alignment logic that makes
UV islands snap together properly during weld operations.
"""

import math
from mathutils import Vector
from .transform import (
    move_island,
    rotate_island_with_aspect,
    scale_island_with_pivot,
    calc_island_bbox_center,
    BoundingBox2d
)


def calc_edge_endpoints(edge_corners, uv_layer):
    """
    Calculate the start and end points of an edge.
    Based on UniV's calc_begin_end_pt() for LoopGroup

    Args:
        edge_corners: List of 2 BMLoop objects representing the edge
        uv_layer: UV layer

    Returns:
        tuple: (pt1, pt2) - Start and end UV coordinates
    """
    if len(edge_corners) != 2:
        print(f"[ALIGN] ERROR: Expected 2 corners for edge, got {len(edge_corners)}")
        return None, None

    pt1 = edge_corners[0][uv_layer].uv
    pt2 = edge_corners[1][uv_layer].uv

    print(f"[ALIGN] Edge endpoints: pt1={pt1}, pt2={pt2}")
    return pt1, pt2


def calc_signed_face_area(face, uv_layer):
    """
    Calculate the signed area of a face in UV space.
    Used to detect if a face is flipped (negative area).
    Based on UniV's calc_signed_face_area()

    Args:
        face: BMFace
        uv_layer: UV layer

    Returns:
        float: Signed area (negative if flipped)
    """
    area = 0.0
    uvs = [loop[uv_layer].uv for loop in face.loops]

    for i in range(len(uvs)):
        area += uvs[i - 1].cross(uvs[i])

    return area


def reorient_island_to_target(ref_island, trans_island, ref_pt1, ref_pt2, trans_pt1, trans_pt2, uv_layer, aspect=1.0):
    """
    Align trans_island to ref_island by rotating, scaling, and moving it.
    Based on UniV's reorient_to_target() method (stitch_and_weld.py lines 137-223)

    This is the core algorithm that makes weld work properly!

    Args:
        ref_island: Reference island (list of BMFaces) - stays in place
        trans_island: Transform island (list of BMFaces) - will be moved
        ref_pt1: Start point of reference edge (Vector) - BEFORE welding
        ref_pt2: End point of reference edge (Vector) - BEFORE welding
        trans_pt1: Start point of transform edge (Vector) - BEFORE welding
        trans_pt2: End point of transform edge (Vector) - BEFORE welding
        uv_layer: UV layer
        aspect: Aspect ratio for rotation correction

    Returns:
        bool: True if transformation was successful
    """
    # Use the pre-weld edge endpoints
    pt_a1 = ref_pt1
    pt_a2 = ref_pt2
    pt_b1 = trans_pt1
    pt_b2 = trans_pt2

    # Step 3: Calculate rotation angle (UniV lines 202-206)
    # Get edge vectors - these are the ORIGINAL vectors, not transformed
    normal_a = pt_a1 - pt_a2
    normal_b = pt_b1 - pt_b2

    # Apply aspect ratio for angle calculation
    normal_a_with_aspect = normal_a * Vector((aspect, 1.0))
    normal_b_with_aspect = normal_b * Vector((aspect, 1.0))

    # Calculate signed angle between edges
    rotate_angle = normal_a_with_aspect.angle_signed(normal_b_with_aspect, 0)

    # Step 4: Rotate island (UniV line 206)
    if abs(rotate_angle) > 0.0001:
        # Rotate around the first point of the edge
        pivot = pt_b1
        rotate_island_with_aspect(trans_island, uv_layer, rotate_angle, pivot, aspect)

    # Step 5: Calculate scale factor (UniV lines 209-218)
    # IMPORTANT: Use ORIGINAL vectors, not re-read from corners!
    length_a = normal_a.length
    length_b = normal_b.length  # Use original vector length, NOT re-read from corners!

    if length_a < 1e-06 or length_b < 1e-06:
        scale_factor = 1.0
    else:
        scale_factor = length_a / length_b

    # Step 6: Scale island (UniV line 218)
    if abs(scale_factor - 1.0) > 0.0001:
        scale_vec = Vector((scale_factor, scale_factor))
        # Scale from the first point of the edge
        pivot = pt_b1
        scale_island_with_pivot(trans_island, uv_layer, scale_vec, pivot)

    # Step 7: Move island to align edges (UniV line 221)
    # Calculate delta based on ORIGINAL pt_b1 (before welding)
    delta = pt_a1 - pt_b1
    move_island(trans_island, uv_layer, delta)

    return True


def find_welded_edge_pairs(all_islands, face_to_island_idx, uv_layer, tolerance=1e-5):
    """
    Find pairs of edges that were welded together.

    This scans all edges in all islands to find edges where:
    1. Both vertices have the same UV coordinates (were welded)
    2. The edges belong to different islands

    Args:
        all_islands: List of islands (each island is a list of BMFaces)
        face_to_island_idx: Dictionary mapping face -> island index
        uv_layer: UV layer
        tolerance: UV coordinate matching tolerance

    Returns:
        list: List of dicts with keys:
            - 'ref_island_idx': Index of reference island
            - 'trans_island_idx': Index of transform island
            - 'ref_edge_corners': [corner1, corner2] of reference edge
            - 'trans_edge_corners': [corner1, corner2] of transform edge
    """
    print(f"\n[ALIGN] ========== find_welded_edge_pairs START ==========")
    print(f"[ALIGN] Searching for welded edges across {len(all_islands)} islands...")

    welded_pairs = []
    processed_edges = set()

    for island_idx, island in enumerate(all_islands):
        for face in island:
            for loop in face.loops:
                edge = loop.edge

                # Skip if we've already processed this edge
                if edge.index in processed_edges:
                    continue

                # Get the two corners of this edge
                corner1 = loop
                corner2 = loop.link_loop_next

                uv1 = corner1[uv_layer].uv
                uv2 = corner2[uv_layer].uv

                # Check the radial neighbor (other side of the edge)
                shared_loop = loop.link_loop_radial_prev
                if shared_loop == loop:
                    # Boundary edge, skip
                    continue

                shared_face = shared_loop.face
                shared_island_idx = face_to_island_idx.get(shared_face, -1)

                # Skip if same island or no island
                if shared_island_idx == island_idx or shared_island_idx == -1:
                    continue

                # Get UV coordinates of shared edge
                shared_corner1 = shared_loop.link_loop_next  # Reversed order
                shared_corner2 = shared_loop

                shared_uv1 = shared_corner1[uv_layer].uv
                shared_uv2 = shared_corner2[uv_layer].uv

                # Check if UVs match (indicating weld happened)
                uv1_matches = (uv1 - shared_uv1).length < tolerance
                uv2_matches = (uv2 - shared_uv2).length < tolerance

                if uv1_matches and uv2_matches:
                    print(f"[ALIGN] Found welded edge between islands {island_idx} and {shared_island_idx}")
                    print(f"[ALIGN]   Edge UVs: {uv1} - {uv2}")
                    print(f"[ALIGN]   Shared UVs: {shared_uv1} - {shared_uv2}")

                    welded_pairs.append({
                        'ref_island_idx': island_idx,
                        'trans_island_idx': shared_island_idx,
                        'ref_edge_corners': [corner1, corner2],
                        'trans_edge_corners': [shared_corner1, shared_corner2]
                    })

                    processed_edges.add(edge.index)

    print(f"[ALIGN] Found {len(welded_pairs)} welded edge pair(s)")
    print(f"[ALIGN] ========== find_welded_edge_pairs END ==========\n")

    return welded_pairs
