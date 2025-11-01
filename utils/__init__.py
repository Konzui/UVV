# Utils module

import bmesh

from .umath_numpy import *
from .overlap_helper import OverlapHelper
from .relax_utils import (
    calc_selected_verts,
    calc_selected_edges,
    calc_selected_uv_faces,
    linked_crn_uv_unordered,
    shared_is_linked,
    is_boundary_sync,
    is_boundary_non_sync,
    linked_crn_to_vert_pair_with_seam,
    is_invisible_func,
    is_pair,
)

# Import stitch utility functions
from .stitch_utils import (
    shared_crn,
    is_flipped_3d,
    is_pair_with_flip,
    is_pair_by_idx,
    all_equal,
    split_by_similarity,
    linked_crn_uv_by_face_index,
    copy_pos_to_target_with_select,
    is_visible_func,
    is_invisible_func as is_invisible_func_stitch,
    get_max_distance_from_px,
    get_aspect_ratio,
    get_active_image_size,
    get_prefs,
)

# Import new modules for World Orient
from . import constants
from . import transform
from . import projection
from . import generic_helpers
from . import island_utils
from . import base_clusters
from . import quadrify_utils
from .quadrify_utils import (
    linked_crn_uv_by_face_tag_unordered_included,
    set_faces_tag
)
from . import uv_face_utils
from . import math_utils
from .math_utils import calc_total_area_3d, calc_total_area_uv


# Additional utility functions needed by types module
def sync():
    """Check if UV sync is enabled"""
    import bpy
    return bpy.context.scene.tool_settings.use_uv_select_sync


def get_select_mode_mesh():
    """Get mesh selection mode"""
    import bpy
    if bpy.context.tool_settings.mesh_select_mode[0]:
        return 'VERT'
    elif bpy.context.tool_settings.mesh_select_mode[1]:
        return 'EDGE'
    else:
        return 'FACE'


def get_select_mode_uv():
    """Get UV selection mode"""
    import bpy
    mode = bpy.context.scene.tool_settings.uv_select_mode
    if mode == 'VERTEX':
        return 'VERT'
    return mode


def set_select_mode_mesh(mode):
    """Set mesh selection mode"""
    import bpy
    if get_select_mode_mesh() == mode:
        return
    if mode == 'VERT':
        bpy.context.tool_settings.mesh_select_mode[:] = True, False, False
    elif mode == 'EDGE':
        bpy.context.tool_settings.mesh_select_mode[:] = False, True, False
    elif mode == 'FACE':
        bpy.context.tool_settings.mesh_select_mode[:] = False, False, True
    else:
        raise TypeError(f"Mode: '{mode}' not found in ('VERT', 'EDGE', 'FACE')")


def set_select_mode_uv(mode):
    """Set UV selection mode"""
    import bpy
    if get_select_mode_uv() == mode:
        return
    if mode == 'VERT':
        mode = 'VERTEX'
    bpy.context.scene.tool_settings.uv_select_mode = mode


# Import get_aspect_ratio from stitch_utils
from .stitch_utils import get_aspect_ratio


def find_min_rotate_angle(angle):
    """Calculate minimal rotation angle to nearest 90-degree increment"""
    from math import pi
    return -(round(angle / (pi / 2)) * (pi / 2) - angle)


# Removed duplicate get_mouse_pos function - using the more complete one below


def get_active_image_size():
    """Get active image size or return None"""
    import bpy
    
    # Check current area first
    if (area := bpy.context.area) and area.type == 'IMAGE_EDITOR':
        space_data = area.spaces.active
        if space_data and space_data.image:
            return space_data.image.size
    
    # Search all areas for IMAGE_EDITOR
    for area in bpy.context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            space_data = area.spaces.active
            if space_data and space_data.image:
                return space_data.image.size
    
    return None


def update_area_by_type(area_type: str):
    """Update/redraw areas of specific type"""
    import bpy
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == area_type:
                area.tag_redraw()


class NoInit:
    """Placeholder for uninitialized attributes"""
    def __getattribute__(self, item):
        raise AttributeError(f'Object not initialized')

    def __bool__(self):
        raise AttributeError(f'Object not initialized')

    def __len__(self):
        raise AttributeError(f'Object not initialized')


def face_indexes_by_sel_mode(context, bm):
    """Return face indexes converted from selected elements - matches ZenUV"""
    uv_layer = bm.loops.layers.uv.verify()
    selection = []
    sync_uv = context.scene.tool_settings.use_uv_select_sync

    if hasattr(context, 'space_data') and context.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
        sel_faces = set()
        # In non-sync mode, check both mesh-level face selection AND UV loop selection
        # A face must be selected at mesh level AND have selected UV loops
        for f in bm.faces:
            if not f.hide and f.select:
                # Check if any loop in this face has selected UV
                if any(loop[uv_layer].select for loop in f.loops):
                    sel_faces.add(f.index)
        selection.extend(list(sel_faces))
    else:
        mode = context.tool_settings.mesh_select_mode
        if mode[1]:  # Edge mode
            selection = [face.index for edge in [e for e in bm.edges if e.select] for face in edge.link_faces if not face.hide]
        elif mode[2]:  # Face mode
            selection = [face.index for face in bm.faces if face.select and not face.hide]
        elif mode[0]:  # Vertex mode
            selection = [face.index for vert in [v for v in bm.verts if v.select] for face in vert.link_faces if not face.hide]
    return selection


def collect_selected_objects_data(context):
    """Collect Mesh data from every selected object - matches ZenUV"""
    bms = {}
    for obj in context.objects_in_mode_unique_data:
        bm_data = bmesh.from_edit_mesh(obj.data)
        bms[obj] = {
            'data': bm_data,
            'pre_selected_verts': [v for v in bm_data.verts if v.select],
            'pre_selected_faces': [f for f in bm_data.faces if f.select],
            'pre_selected_edges': [e for e in bm_data.edges if e.select],
        }
    return bms


def check_selection_mode(context):
    """Detect current Blender Selection mode - matches ZenUV"""
    work_mode = 'VERTEX'
    if context.tool_settings.mesh_select_mode[:] == (False, True, False):
        work_mode = 'EDGE'
    elif context.tool_settings.mesh_select_mode[:] == (False, False, True):
        work_mode = 'FACE'
    return work_mode


def get_uv_boundary_edges(faces, uv_layer):
    """Get indices of UV boundary edges (edges on island borders)

    Args:
        faces: List of BMesh faces to check
        uv_layer: UV layer to use

    Returns:
        List of edge indices that are on UV boundaries
    """
    # Build dictionary of UV edges
    uv_edges = {}

    for face in faces:
        loops = face.loops
        num_loops = len(loops)

        for i in range(num_loops):
            loop = loops[i]
            next_loop = loops[(i + 1) % num_loops]

            # Get UV coordinates
            uv1 = loop[uv_layer].uv.copy().freeze()
            uv2 = next_loop[uv_layer].uv.copy().freeze()

            # Create sorted edge key
            edge_key = tuple(sorted([uv1, uv2]))

            if edge_key in uv_edges:
                uv_edges[edge_key].append(loop.edge.index)
            else:
                uv_edges[edge_key] = [loop.edge.index]

    # Boundary edges appear only once
    boundary_indices = []
    for edge_key, edge_indices in uv_edges.items():
        if len(edge_indices) == 1:
            boundary_indices.append(edge_indices[0])

    return boundary_indices


def zen_get_islands(bm, _selection, has_selected_faces=False):
    """Get UV islands using edge tagging - matches ZenUV's zen_get_islands"""
    uv_layer = bm.loops.layers.uv.verify()

    # Get UV boundary edges
    _bounds = get_uv_boundary_edges(bm.faces, uv_layer)

    bm.edges.ensure_lookup_table()
    for edge in bm.edges:
        edge.tag = False

    # Tag all edges in uv borders
    for index in _bounds:
        bm.edges[index].tag = True

    _islands = []
    if has_selected_faces:
        faces = set(_selection)
    else:
        faces = set(bm.faces)

    while len(faces) != 0:
        init_face = faces.pop()
        island = {init_face}
        stack = [init_face]
        while len(stack) != 0:
            face = stack.pop()
            for e in face.edges:
                if not e.tag:
                    for f in e.link_faces:
                        if f not in island:
                            stack.append(f)
                            island.add(f)
        for f in island:
            faces.discard(f)
        if True in [f.hide for f in island]:
            continue
        _islands.append(island)

    for index in _bounds:
        bm.edges[index].tag = False

    return _islands


def get_island(context, bm, uv_layer):
    """Return island(s) by selected faces, edges or vertices - matches ZenUV"""
    bm.faces.ensure_lookup_table()
    selection = [bm.faces[index] for index in face_indexes_by_sel_mode(context, bm)]
    return zen_get_islands(bm, selection, has_selected_faces=True)


def is_manifold_uv(crn, uv):
    """Check if UV corner is manifold (has only 2 adjacent faces at this UV position)"""
    # Get UV position
    uv_pos = crn[uv].uv

    # Count how many faces share this UV vertex at this position
    count = 0
    for loop in crn.vert.link_loops:
        if loop[uv].uv == uv_pos:
            count += 1

    return count == 2


# ========================================
# Welding Utility Functions (from UniV)
# ========================================

def shared_crn(crn):
    """Get the radial pair corner (loop on the other side of the edge)"""
    shared = crn.link_loop_radial_prev
    if shared != crn:
        return shared
    return None


# is_boundary_sync and is_boundary_non_sync are imported from relax_utils above


# weld_crn_edge_by_idx is imported from univ_weld_utils - don't duplicate here


def calc_extended_any_edge_non_manifold_islands(context, bm, uv_layer):
    """
    Calculate islands considering non-manifold edges and selected edges.
    More robust than standard island detection for welding operations.

    Returns:
        List of island face sets
    """
    # Get all visible faces
    visible_faces = [f for f in bm.faces if not f.hide]

    if not visible_faces:
        return []

    # Build edge connectivity for island detection
    # An edge is a boundary if:
    # 1. It's a seam
    # 2. It has UV split (different UV coords on each side)
    # 3. It's a mesh boundary (only one face)

    boundary_edges = set()

    for edge in bm.edges:
        if edge.seam:
            boundary_edges.add(edge)
            continue

        # Check if it's a mesh boundary
        if len(edge.link_faces) < 2:
            boundary_edges.add(edge)
            continue

        # Check for UV split
        loops = list(edge.link_loops)
        if len(loops) >= 2:
            loop_a = loops[0]
            loop_b = loops[1]

            # Check if UVs match on both sides
            # For a welded edge: loop_a's UVs should match loop_b's UVs in opposite order
            uv_a1 = loop_a[uv_layer].uv
            uv_a2 = loop_a.link_loop_next[uv_layer].uv
            uv_b1 = loop_b[uv_layer].uv
            uv_b2 = loop_b.link_loop_next[uv_layer].uv

            # If UVs don't match, it's a boundary
            if not (uv_a1 == uv_b2 and uv_a2 == uv_b1):
                boundary_edges.add(edge)

    # Flood fill to find islands
    islands = []
    remaining_faces = set(visible_faces)

    while remaining_faces:
        # Start new island
        start_face = remaining_faces.pop()
        island = [start_face]
        stack = [start_face]
        visited = {start_face}

        while stack:
            face = stack.pop()

            # Check all edges of this face
            for edge in face.edges:
                if edge in boundary_edges:
                    continue

                # Add adjacent faces that aren't separated by boundary
                for adj_face in edge.link_faces:
                    if adj_face not in visited and adj_face in remaining_faces:
                        visited.add(adj_face)
                        stack.append(adj_face)
                        island.append(adj_face)
                        remaining_faces.discard(adj_face)

        islands.append(island)

    return islands


# ========================================
# Additional Welding Utilities from UniV
# ========================================

def is_flipped_3d(crn):
    """Check if corner/loop has flipped 3D face (vertices in wrong order)"""
    pair = crn.link_loop_radial_prev
    if pair == crn:
        return False
    return pair.vert == crn.vert


def is_pair_with_flip(crn, rad_prev, uv):
    """Check if two corners form a UV pair, considering flipped faces"""
    if crn.vert == rad_prev.vert:  # is flipped
        return crn[uv].uv == rad_prev[uv].uv and \
            crn.link_loop_next[uv].uv == rad_prev.link_loop_next[uv].uv
    return crn.link_loop_next[uv].uv == rad_prev[uv].uv and \
        crn[uv].uv == rad_prev.link_loop_next[uv].uv


def linked_crn_uv_by_island_index_unordered_included(crn, uv, idx):
    """Get all corners at same vertex with same UV coordinate and island index (including input corner)"""
    first_co = crn[uv].uv
    return [l_crn for l_crn in crn.vert.link_loops if l_crn.face.index == idx and l_crn[uv].uv == first_co]


def linked_crn_to_vert_pair_with_seam(crn, uv, sync):
    """
    Get linked corners connected by UV pairs (welded edges), respecting seams.
    Used for walking along welded edges.
    """
    from . import sync as sync_check

    def is_invisible(face):
        if sync:
            return face.hide
        return not face.select

    def is_pair(crn1, crn2, uv):
        return crn1.link_loop_next[uv].uv == crn2[uv].uv and \
            crn1[uv].uv == crn2.link_loop_next[uv].uv

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
            prev_crn.edge.seam or
            is_invisible(pair_ccw.face) or
            not is_pair(prev_crn, pair_ccw, uv)):

            bm_iter = crn
            linked_cw = []
            while True:
                if bm_iter.edge.seam:
                    break
                pair_cw = bm_iter.link_loop_radial_next
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
        linked.append(bm_iter)

    return linked


def copy_pos_to_target_with_select(crn, uv, idx):
    """
    Copy UV position to target edge and select it.
    Used for unpaired selections in non-sync mode.
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
    shared_next = shared.link_loop_next

    for _crn in linked_crn_uv_by_island_index_unordered_included(shared_next, uv, idx):
        _crn_uv = _crn[uv]
        _crn_uv.uv = crn_co
        _crn_uv.select = True


def all_equal(iterable, key=None):
    """Check if all elements in iterable are equal"""
    if key:
        iterator = iter(iterable)
        try:
            first = key(next(iterator))
        except StopIteration:
            return True
        return all(key(x) == first for x in iterator)
    else:
        iterator = iter(iterable)
        try:
            first = next(iterator)
        except StopIteration:
            return True
        return all(x == first for x in iterator)


def split_by_similarity(items, key):
    """
    Split a list into groups of consecutive items with the same key value.
    Based on UniV's implementation.

    Args:
        items: List of items to split
        key: Function to extract comparison value from item

    Returns:
        List of lists, where each sublist contains consecutive items with same key
    """
    if not items:
        return []

    groups = []
    current_group = [items[0]]
    current_key = key(items[0])

    for item in items[1:]:
        item_key = key(item)
        if item_key == current_key:
            current_group.append(item)
        else:
            groups.append(current_group)
            current_group = [item]
            current_key = item_key

    # Add final group
    if current_group:
        groups.append(current_group)

    return groups


def linked_crn_uv_by_face_index(crn, uv):
    """
    Get all corners at same vertex with same UV coordinate and same face.index.
    Based on UniV's implementation.

    Args:
        crn: Corner/loop to start from
        uv: UV layer

    Returns:
        List of corners with matching UV position in same island
    """
    first_co = crn[uv].uv
    idx = crn.face.index
    return [l_crn for l_crn in crn.vert.link_loops if l_crn.face.index == idx and l_crn[uv].uv == first_co]


# ========================================
# LoopGroup and LoopGroups Classes
# ========================================
# NOTE: LoopGroup and LoopGroups classes have been moved to types/loop_group.py
# to avoid conflicts with the main implementation. The classes in utils/__init__.py
# were duplicate implementations that were causing method override issues.


# ========================================
# UniV Island Detection Algorithms
# ========================================

def univ_calc_iter_ex(bm, uv_layer, tag_faces=None):
    """
    Calculate UV islands using UniV's exact algorithm.
    Requires faces to be tagged first (face.tag = True for faces to process).

    This is the STANDARD island detection - requires BOTH vertices of edge to match.

    Args:
        bm: BMesh
        uv_layer: UV layer
        tag_faces: Optional list of faces to tag (if None, assumes already tagged)

    Yields:
        Lists of faces forming islands

    Based on UniV's calc_iter_ex (island.py:1350-1378)
    """
    island = []

    # Tag faces if provided
    if tag_faces is not None:
        for face in bm.faces:
            face.tag = False
        for face in tag_faces:
            face.tag = True

    for face in bm.faces:
        if not face.tag:  # Skip untagged and already-processed faces
            continue
        face.tag = False  # Mark as processed

        parts_of_island = [face]  # Container for island elements
        temp = []  # Temp container for next iteration

        while parts_of_island:  # Continue until all connected faces found
            for f in parts_of_island:
                for l in f.loops:  # Check all edges of the face
                    shared_crn = l.link_loop_radial_prev
                    ff = shared_crn.face
                    if not ff.tag:
                        continue

                    # CRITICAL: Both vertices must have matching UV coords (AND logic)
                    if (l[uv_layer].uv == shared_crn.link_loop_next[uv_layer].uv and
                        l.link_loop_next[uv_layer].uv == shared_crn[uv_layer].uv):
                        temp.append(ff)
                        ff.tag = False

            island.extend(parts_of_island)
            parts_of_island = temp
            temp = []

        yield island
        island = []


def univ_calc_iter_non_manifold_ex(bm, uv_layer, tag_faces=None):
    """
    Calculate UV islands using UniV's NON-MANIFOLD algorithm.
    Requires faces to be tagged first (face.tag = True for faces to process).

    This is the KEY algorithm - requires EITHER vertex of edge to match (OR logic).
    Handles partially-welded edges correctly!

    Args:
        bm: BMesh
        uv_layer: UV layer
        tag_faces: Optional list of faces to tag (if None, assumes already tagged)

    Yields:
        Lists of faces forming islands

    Based on UniV's calc_iter_non_manifold_ex (island.py:1381-1409)
    """
    island = []

    # Tag faces if provided
    if tag_faces is not None:
        for face in bm.faces:
            face.tag = False
        for face in tag_faces:
            face.tag = True

    for face in bm.faces:
        if not face.tag:  # Skip untagged and already-processed faces
            continue
        face.tag = False  # Mark as processed

        parts_of_island = [face]  # Container for island elements
        temp = []  # Temp container for next iteration

        while parts_of_island:  # Continue until all connected faces found
            for f in parts_of_island:
                for l in f.loops:  # Check all edges of the face
                    shared_crn = l.link_loop_radial_prev
                    ff = shared_crn.face
                    if not ff.tag:
                        continue

                    # CRITICAL: EITHER vertex can have matching UV coords (OR logic)
                    # This handles partially-welded edges!
                    if (l[uv_layer].uv == shared_crn.link_loop_next[uv_layer].uv or
                        l.link_loop_next[uv_layer].uv == shared_crn[uv_layer].uv):
                        temp.append(ff)
                        ff.tag = False

            island.extend(parts_of_island)
            parts_of_island = temp
            temp = []

        yield island
        island = []


def univ_calc_with_markseam_iter_ex(bm, uv_layer, tag_faces=None):
    """
    Calculate UV islands considering seams using UniV's algorithm.
    Seams are treated as island boundaries.

    Args:
        bm: BMesh
        uv_layer: UV layer
        tag_faces: Optional list of faces to tag (if None, assumes already tagged)

    Yields:
        Lists of faces forming islands

    Based on UniV's calc_with_markseam_iter_ex (island.py:1412-1442)
    """
    island = []

    # Tag faces if provided
    if tag_faces is not None:
        for face in bm.faces:
            face.tag = False
        for face in tag_faces:
            face.tag = True

    for face in bm.faces:
        if not face.tag:
            continue
        face.tag = False

        parts_of_island = [face]
        temp = []

        while parts_of_island:
            for f in parts_of_island:
                for l in f.loops:
                    shared_crn = l.link_loop_radial_prev
                    ff = shared_crn.face
                    if not ff.tag:
                        continue

                    # Skip if edge is marked as seam
                    if l.edge.seam:
                        continue

                    # Both vertices must have matching UV coords
                    if (l[uv_layer].uv == shared_crn.link_loop_next[uv_layer].uv and
                        l.link_loop_next[uv_layer].uv == shared_crn[uv_layer].uv):
                        temp.append(ff)
                        ff.tag = False

            island.extend(parts_of_island)
            parts_of_island = temp
            temp = []

        yield island
        island = []


# ========================================
# AdvIsland and AdvIslands Classes
# ========================================

class AdvIsland:
    """
    Advanced island representation with transform capabilities.
    Simplified version of UniV's AdvIsland for weld/stitch operations.
    """

    def __init__(self, faces, bm, uv_layer, aspect=1.0):
        self.faces = list(faces)  # List of BMFace objects
        self.bm = bm
        self.uv_layer = uv_layer
        self.aspect = aspect
        self.tag = True
        self.select_state = False
        self.area_3d = 0.0
        self.sequence = []  # For balancing filter

    def __len__(self):
        return len(self.faces)

    def __getitem__(self, index):
        return self.faces[index]

    def __iter__(self):
        return iter(self.faces)

    def rotate_simple(self, angle, aspect=1.0):
        """Rotate island around its center"""
        from mathutils import Matrix, Vector

        # Calculate center
        center = self.calc_center()

        # Create rotation matrix with aspect correction
        if aspect > 1:
            normalization_matrix = Matrix.Diagonal(Vector((1, 1 / aspect)))
            rescale_matrix = Matrix.Diagonal(Vector((1, aspect)))
        elif aspect < 1:
            normalization_matrix = Matrix.Diagonal(Vector((aspect, 1)))
            rescale_matrix = Matrix.Diagonal(Vector((1 / aspect, 1)))
        else:
            normalization_matrix = Matrix.Identity(2)
            rescale_matrix = Matrix.Identity(2)

        rotation_matrix = Matrix.Rotation(angle, 2, 'Z')
        transform = rescale_matrix @ rotation_matrix @ normalization_matrix

        # Apply to all UVs
        uv = self.uv_layer
        for face in self.faces:
            for loop in face.loops:
                uv_co = loop[uv].uv
                loop[uv].uv = (transform @ (uv_co - center)) + center

    def scale_simple(self, scale_vec):
        """Scale island around its center"""
        from mathutils import Matrix

        center = self.calc_center()
        scale_matrix = Matrix.Diagonal(scale_vec.to_3d()).to_2d()

        uv = self.uv_layer
        for face in self.faces:
            for loop in face.loops:
                uv_co = loop[uv].uv
                loop[uv].uv = (scale_matrix @ (uv_co - center)) + center

    def scale(self, scale_vec, pivot):
        """Scale island around a pivot point"""
        from mathutils import Matrix

        scale_matrix = Matrix.Diagonal(scale_vec.to_3d()).to_2d()

        uv = self.uv_layer
        for face in self.faces:
            for loop in face.loops:
                uv_co = loop[uv].uv
                loop[uv].uv = (scale_matrix @ (uv_co - pivot)) + pivot

    def set_position(self, target_pos, current_pos):
        """Move island so current_pos moves to target_pos"""
        delta = target_pos - current_pos
        self.move(delta)

    def move(self, delta):
        """Move island by delta vector"""
        uv = self.uv_layer
        for face in self.faces:
            for loop in face.loops:
                loop[uv].uv += delta

    def calc_center(self):
        """Calculate UV center of island"""
        from mathutils import Vector

        uv = self.uv_layer
        total = Vector((0, 0))
        count = 0

        for face in self.faces:
            for loop in face.loops:
                total += loop[uv].uv
                count += 1

        if count == 0:
            return Vector((0, 0))

        return total / count

    def set_boundary_tag(self, match_idx=True):
        """Tag boundary edges in this island"""
        uv = self.uv_layer
        is_sync = sync()

        idx = self.faces[0].index if match_idx else -1

        for face in self.faces:
            for crn in face.loops:
                shared = crn.link_loop_radial_prev

                # Check if boundary
                if shared == crn:
                    crn.tag = True
                elif match_idx and shared.face.index != idx:
                    crn.tag = True
                elif is_sync:
                    crn.tag = is_boundary_sync(crn, uv)
                else:
                    crn.tag = is_boundary_non_sync(crn, uv)


class AdvIslands:
    """
    Collection of AdvIsland objects.
    Simplified version of UniV's AdvIslands.
    """

    def __init__(self, bm, uv_layer, aspect=1.0):
        self.bm = bm
        self.uv_layer = uv_layer
        self.aspect = aspect
        self.islands = []

    def __len__(self):
        return len(self.islands)

    def __getitem__(self, index):
        return self.islands[index]

    def __iter__(self):
        return iter(self.islands)

    def indexing(self):
        """Set face.index to island index for all faces"""
        for idx, island in enumerate(self.islands):
            for face in island.faces:
                face.index = idx

        self.bm.faces.index_update()

    @staticmethod
    def calc_visible_with_mark_seam(bm, uv_layer, aspect=1.0):
        """
        Calculate islands from visible faces, considering seams and UV splits.
        Based on UniV's AdvIslands.calc_visible_with_mark_seam.

        CRITICAL: Now uses UniV's univ_calc_with_markseam_iter_ex instead of zen_get_islands
        for correct handling of partially-welded edges!

        Args:
            bm: BMesh
            uv_layer: UV layer
            aspect: Aspect ratio

        Returns:
            AdvIslands object
        """
        adv_islands = AdvIslands(bm, uv_layer, aspect)

        # Get all visible faces
        is_sync = sync()
        if is_sync:
            visible_faces = [f for f in bm.faces if not f.hide]
        else:
            # In non-sync mode, only process selected faces in 3D viewport
            visible_faces = [f for f in bm.faces if f.select]

        if not visible_faces:
            return adv_islands

        # CRITICAL: Use UniV's algorithm instead of zen_get_islands
        # This correctly handles partially-welded edges using OR logic per-loop
        islands = list(univ_calc_with_markseam_iter_ex(bm, uv_layer, tag_faces=visible_faces))

        # Convert to AdvIsland objects
        for island_faces in islands:
            adv_island = AdvIsland(island_faces, bm, uv_layer, aspect)
            adv_islands.islands.append(adv_island)

        return adv_islands


def get_max_distance_from_px(px_size, view2d):
    """Get maximum distance from pixel size - from UniV other.py line 147"""
    return (Vector(view2d.region_to_view(0, 0)) - Vector(view2d.region_to_view(0, px_size))).length


def get_mouse_pos(context, event):
    """Get mouse position in UV space"""
    import bpy
    from mathutils import Vector
    
    if context.area.type == 'IMAGE_EDITOR':
        space_data = context.area.spaces.active
        if space_data and space_data.image:
            # Convert screen coordinates to UV coordinates
            region = context.region
            view2d = region.view2d
            
            # Get mouse position in region coordinates
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y
            
            # Convert to UV coordinates
            uv_co = view2d.region_to_view(mouse_x, mouse_y)
            return Vector(uv_co)
    
    return Vector((0, 0))


def get_prefs():
    """Get addon preferences"""
    import bpy
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except:
        # Fallback if preferences not found
        class DefaultPrefs:
            max_pick_distance = 10.0
        return DefaultPrefs()


def face_select_get_func(umesh):
    """Get face selection function for umesh"""
    def face_select_get(face):
        return face.select
    return face_select_get


def vert_select_get_func(umesh):
    """Get vertex selection function for umesh"""
    def vert_select_get(crn):
        return crn.vert.select
    return vert_select_get


def closest_pt_to_line(pt, line_start, line_end):
    """Find closest point on line to given point"""
    from mathutils import Vector
    
    line_vec = line_end - line_start
    pt_vec = pt - line_start
    
    if line_vec.length_squared == 0:
        return line_start
    
    t = pt_vec.dot(line_vec) / line_vec.length_squared
    t = max(0, min(1, t))  # Clamp to line segment
    
    return line_start + t * line_vec


def point_inside_face(pt, face, uv):
    """Check if point is inside face in UV space"""
    from mathutils.geometry import intersect_point_tri
    
    # Get UV coordinates of face corners
    corners = [loop[uv].uv for loop in face.loops]
    
    if len(corners) < 3:
        return False
    
    # For triangles, use direct point-in-triangle test
    if len(corners) == 3:
        return intersect_point_tri(pt, corners[0], corners[1], corners[2])[0]
    
    # For quads and higher, triangulate and test each triangle
    for i in range(1, len(corners) - 1):
        if intersect_point_tri(pt, corners[0], corners[i], corners[i + 1])[0]:
            return True
    
    return False


def isclose(a, b, abs_tol=1e-09):
    """Check if two floats are close to each other"""
    return abs(a - b) <= abs_tol


def calc_face_area_uv(face, uv):
    """Calculate UV area of a face"""
    from mathutils.geometry import area_tri
    
    if len(face.loops) < 3:
        return 0.0
    
    # Get UV coordinates
    uvs = [loop[uv].uv for loop in face.loops]
    
    if len(uvs) == 3:
        # Triangle - direct calculation
        return area_tri(uvs[0], uvs[1], uvs[2])
    else:
        # Polygon - triangulate and sum areas
        total_area = 0.0
        for i in range(1, len(uvs) - 1):
            total_area += area_tri(uvs[0], uvs[i], uvs[i + 1])
        return total_area


def calc_max_length_uv_crn(loops, uv):
    """Find the loop with maximum UV edge length"""
    max_length = -1.0
    max_loop = None
    
    for loop in loops:
        # Calculate length of edge from this loop to next
        current_uv = loop[uv].uv
        next_uv = loop.link_loop_next[uv].uv
        length = (current_uv - next_uv).length_squared
        
        if length > max_length:
            max_length = length
            max_loop = loop
    
    return max_loop


def is_pair(crn1, crn2, uv):
    """Check if two corners form a UV pair (welded edge)"""
    return (crn1.link_loop_next[uv].uv == crn2[uv].uv and 
            crn1[uv].uv == crn2.link_loop_next[uv].uv)


def copy_pos_to_target(crn, uv, idx):
    """Copy UV position to target corner"""
    # This is a placeholder - the actual implementation depends on the specific use case
    pass


def vec_isclose(vec1, vec2, abs_tol=1e-09):
    """Check if two vectors are close to each other"""
    if len(vec1) != len(vec2):
        return False
    return all(abs(a - b) <= abs_tol for a, b in zip(vec1, vec2))


def get_max_distance_from_px(px_size, view2d):
    """Get maximum distance from pixel size - from UniV other.py line 147"""
    return (Vector(view2d.region_to_view(0, 0)) - Vector(view2d.region_to_view(0, px_size))).length


def get_mouse_pos(context, event):
    """Get mouse position in UV space"""
    import bpy
    from mathutils import Vector
    
    if context.area.type == 'IMAGE_EDITOR':
        space_data = context.area.spaces.active
        if space_data and space_data.image:
            # Convert screen coordinates to UV coordinates
            region = context.region
            view2d = region.view2d
            
            # Get mouse position in region coordinates
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y
            
            # Convert to UV coordinates
            uv_co = view2d.region_to_view(mouse_x, mouse_y)
            return Vector(uv_co)
    
    return Vector((0, 0))


def get_prefs():
    """Get addon preferences"""
    import bpy
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except:
        # Fallback if preferences not found
        class DefaultPrefs:
            max_pick_distance = 10.0
        return DefaultPrefs()


def face_select_get_func(umesh):
    """Get face selection function for umesh"""
    def face_select_get(face):
        return face.select
    return face_select_get


def vert_select_get_func(umesh):
    """Get vertex selection function for umesh"""
    def vert_select_get(crn):
        return crn.vert.select
    return vert_select_get


def closest_pt_to_line(pt, line_start, line_end):
    """Find closest point on line to given point"""
    from mathutils import Vector
    
    line_vec = line_end - line_start
    pt_vec = pt - line_start
    
    if line_vec.length_squared == 0:
        return line_start
    
    t = pt_vec.dot(line_vec) / line_vec.length_squared
    t = max(0, min(1, t))  # Clamp to line segment
    
    return line_start + t * line_vec


def point_inside_face(pt, face, uv):
    """Check if point is inside face in UV space"""
    from mathutils.geometry import intersect_point_tri
    
    # Get UV coordinates of face corners
    corners = [loop[uv].uv for loop in face.loops]
    
    if len(corners) < 3:
        return False
    
    # For triangles, use direct point-in-triangle test
    if len(corners) == 3:
        return intersect_point_tri(pt, corners[0], corners[1], corners[2])[0]
    
    # For quads and higher, triangulate and test each triangle
    for i in range(1, len(corners) - 1):
        if intersect_point_tri(pt, corners[0], corners[i], corners[i + 1])[0]:
            return True
    
    return False


def isclose(a, b, abs_tol=1e-09):
    """Check if two floats are close to each other"""
    return abs(a - b) <= abs_tol


def calc_face_area_uv(face, uv):
    """Calculate UV area of a face"""
    from mathutils.geometry import area_tri
    
    if len(face.loops) < 3:
        return 0.0
    
    # Get UV coordinates
    uvs = [loop[uv].uv for loop in face.loops]
    
    if len(uvs) == 3:
        # Triangle - direct calculation
        return area_tri(uvs[0], uvs[1], uvs[2])
    else:
        # Polygon - triangulate and sum areas
        total_area = 0.0
        for i in range(1, len(uvs) - 1):
            total_area += area_tri(uvs[0], uvs[i], uvs[i + 1])
        return total_area


def calc_max_length_uv_crn(loops, uv):
    """Find the loop with maximum UV edge length"""
    max_length = -1.0
    max_loop = None
    
    for loop in loops:
        # Calculate length of edge from this loop to next
        current_uv = loop[uv].uv
        next_uv = loop.link_loop_next[uv].uv
        length = (current_uv - next_uv).length_squared
        
        if length > max_length:
            max_length = length
            max_loop = loop
    
    return max_loop


def is_pair(crn1, crn2, uv):
    """Check if two corners form a UV pair (welded edge)"""
    return (crn1.link_loop_next[uv].uv == crn2[uv].uv and 
            crn1[uv].uv == crn2.link_loop_next[uv].uv)


def copy_pos_to_target(crn, uv, idx):
    """Copy UV position to target corner"""
    # This is a placeholder - the actual implementation depends on the specific use case
    pass


def vec_isclose(vec1, vec2, abs_tol=1e-09):
    """Check if two vectors are close to each other"""
    if len(vec1) != len(vec2):
        return False
    return all(abs(a - b) <= abs_tol for a, b in zip(vec1, vec2))
