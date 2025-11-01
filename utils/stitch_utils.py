# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later
# Ported from UniV addon for stitch functionality

"""
Stitch-specific utility functions.
Based on UniV's utils/ubm.py and utils/__init__.py implementations.
"""

import bmesh
import bpy
import copy
from mathutils import Vector
from bmesh.types import BMLoop, BMLayerItem, BMFace
from typing import List, Callable, Any, Iterator
from itertools import chain


def closest_pt_to_line(pt: Vector, l_a: Vector, l_b: Vector):
    """
    Calculate closest point on line to given point.
    Exact UniV implementation from utils.umath.closest_pt_to_line().
    """
    near_pt, percent = intersect_point_line(pt, l_a, l_b)
    if percent < 0.0:
        return l_a
    elif percent > 1.0:
        return l_b
    return near_pt


def shared_crn(crn: BMLoop) -> BMLoop | None:
    """
    Get the shared corner across an edge.
    Based on UniV's shared_crn() function.
    
    Args:
        crn: Corner to get shared corner for
        
    Returns:
        BMLoop: Shared corner, or None if boundary edge
    """
    shared = crn.link_loop_radial_prev
    if shared != crn:
        return shared
    return None


def is_flipped_3d(crn: BMLoop) -> bool:
    """
    Check if a corner has a flipped 3D face.
    Based on UniV's is_flipped_3d() function.
    
    Args:
        crn: Corner to check
        
    Returns:
        bool: True if flipped 3D face
    """
    pair = crn.link_loop_radial_prev
    if pair == crn:
        return False
    return pair.vert == crn.vert


def is_pair(crn: BMLoop, rad_prev: BMLoop, uv: BMLayerItem) -> bool:
    """
    Check if two corners form a proper pair.
    Based on UniV's is_pair() function.
    
    Args:
        crn: First corner
        rad_prev: Second corner
        uv: UV layer
        
    Returns:
        bool: True if corners form a proper pair
    """
    return (crn.link_loop_next[uv].uv == rad_prev[uv].uv and 
            crn[uv].uv == rad_prev.link_loop_next[uv].uv)


def is_pair_with_flip(crn: BMLoop, rad_prev: BMLoop, uv: BMLayerItem) -> bool:
    """
    Check if two corners form a proper pair, accounting for flipped faces.
    Based on UniV's is_pair_with_flip() function.

    Args:
        crn: First corner
        rad_prev: Second corner
        uv: UV layer

    Returns:
        bool: True if corners form a proper pair
    """
    if crn.vert == rad_prev.vert:  # is flipped
        return (crn[uv].uv == rad_prev[uv].uv and
                crn.link_loop_next[uv].uv == rad_prev.link_loop_next[uv].uv)
    return (crn.link_loop_next[uv].uv == rad_prev[uv].uv and
            crn[uv].uv == rad_prev.link_loop_next[uv].uv)


def is_pair_by_idx(crn: BMLoop, rad_prev: BMLoop, uv: BMLayerItem) -> bool:
    """
    Check if two corners form a proper pair using face index.
    Used for non-manifold geometry where face.index is set.
    Based on UniV's is_pair_by_idx() function.

    Args:
        crn: First corner
        rad_prev: Second corner
        uv: UV layer

    Returns:
        bool: True if corners form a proper pair
    """
    return (crn.face.index == rad_prev.face.index and
            crn.link_loop_next[uv].uv == rad_prev[uv].uv and
            crn[uv].uv == rad_prev.link_loop_next[uv].uv)


def is_boundary_sync(crn: BMLoop, uv: BMLayerItem) -> bool:
    """
    Check if corner is on boundary in sync mode.
    Based on UniV's is_boundary_sync() function.
    
    Args:
        crn: Corner to check
        uv: UV layer
        
    Returns:
        bool: True if boundary corner
    """
    shared_crn = crn.link_loop_radial_prev
    if shared_crn == crn:
        return True
    if shared_crn.face.hide:
        return True
    return not (crn[uv].uv == shared_crn.link_loop_next[uv].uv and
                crn.link_loop_next[uv].uv == shared_crn[uv].uv)


def is_boundary_non_sync(crn: BMLoop, uv: BMLayerItem) -> bool:
    """
    Check if corner is on boundary in non-sync mode.
    Based on UniV's is_boundary_non_sync() function.
    
    Args:
        crn: Corner to check
        uv: UV layer
        
    Returns:
        bool: True if boundary corner
    """
    next_linked_disc = crn.link_loop_radial_prev
    if next_linked_disc == crn:
        return True
    if not next_linked_disc.face.select:
        return True
    return not (crn[uv].uv == next_linked_disc.link_loop_next[uv].uv and
                crn.link_loop_next[uv].uv == next_linked_disc[uv].uv)


def all_equal(iterable: Iterator[Any], key: Callable = None) -> bool:
    """
    Check if all elements in iterable are equal.
    Based on UniV's all_equal() function.
    
    Args:
        iterable: Iterable to check
        key: Optional key function
        
    Returns:
        bool: True if all elements are equal
    """
    if key is None:
        key = lambda x: x
    
    iterator = iter(iterable)
    try:
        first = next(iterator)
    except StopIteration:
        return True
    
    return all(key(item) == key(first) for item in iterator)


def split_by_similarity(lst, key=None):
    """
    Split list by similar values with key function.
    Based on UniV's split_by_similarity() function (other.py:214-221).
    
    Args:
        lst: List to split
        key: Key function for similarity (optional)
        
    Returns:
        List[List[Any]]: List of groups with similar values
    """
    from itertools import groupby
    
    if key:
        return [list(group) for _, group in groupby(lst, key=key)]
    else:
        return [list(group) for _, group in groupby(lst)]


# REMOVED: Duplicate get_aspect_ratio() function - use the full version below at line 797


def get_max_distance_from_px(max_px: float, view2d) -> float:
    """
    Convert pixel distance to UV space distance.
    Based on UniV's get_max_distance_from_px() function.
    
    Args:
        max_px: Maximum distance in pixels
        view2d: View2D object
        
    Returns:
        float: Distance in UV space
    """
    # Convert pixel distance to UV space
    # This is a simplified implementation
    # In practice, you'd need to account for zoom level and viewport size
    return max_px * 0.001  # Rough conversion


def linked_crn_uv(first: BMLoop, uv: BMLayerItem) -> List[BMLoop]:
    """
    Get all corners linked to this corner at the same UV position.
    Based on UniV's linked_crn_uv() function (ubm.py:267-286).

    Args:
        first: Corner to start from
        uv: UV layer

    Returns:
        List[BMLoop]: Linked corners (excluding input corner)
    """
    first_vert = first.vert
    first_co = first[uv].uv
    linked = []
    bm_iter = first

    while True:
        bm_iter = bm_iter.link_loop_prev.link_loop_radial_prev  # get ccw corner
        if first_vert != bm_iter.vert:  # Skip boundary or flipped
            bm_iter = first
            linked_cw = []
            while True:
                bm_iter = bm_iter.link_loop_radial_next.link_loop_next  # get cw corner
                if first_vert != bm_iter.vert:  # Skip boundary or flipped
                    break

                if bm_iter == first:
                    break
                if first_co == bm_iter[uv].uv:
                    linked_cw.append(bm_iter)
                else:
                    break
            linked.extend(linked_cw[::-1])
            break
        if bm_iter == first:
            break
        if first_co == bm_iter[uv].uv:
            linked.append(bm_iter)
        else:
            break

    return linked


def linked_crn_uv_by_idx_unordered(crn: BMLoop, uv: BMLayerItem) -> List[BMLoop]:
    """
    Get linked corners by face index and UV position (unordered).
    Based on UniV's linked_crn_uv_by_idx_unordered() function.

    Args:
        crn: Corner to start from
        uv: UV layer

    Returns:
        List[BMLoop]: Linked corners (excluding input corner)
    """
    uv_co = crn[uv].uv
    face_idx = crn.face.index
    linked = []
    for loop in crn.vert.link_loops:
        if loop != crn and loop.face.index == face_idx and loop[uv].uv == uv_co:
            linked.append(loop)
    return linked


def linked_crn_uv_by_idx_unordered_included(crn: BMLoop, uv: BMLayerItem) -> List[BMLoop]:
    """
    Get linked corners by face index and UV position (unordered, including input).
    Based on UniV's linked_crn_uv_by_idx_unordered_included() function.

    Args:
        crn: Corner to start from
        uv: UV layer

    Returns:
        List[BMLoop]: Linked corners (including input corner)
    """
    uv_co = crn[uv].uv
    face_idx = crn.face.index
    linked = [crn]
    for loop in crn.vert.link_loops:
        if loop != crn and loop.face.index == face_idx and loop[uv].uv == uv_co:
            linked.append(loop)
    return linked


def linked_crn_uv_by_face_index(crn: BMLoop, uv: BMLayerItem) -> List[BMLoop]:
    """
    Get linked corners by face index (includes input corner).
    Based on UniV's linked_crn_uv_by_face_index() function.

    Args:
        crn: Corner to start from
        uv: UV layer

    Returns:
        List[BMLoop]: Linked corners
    """
    face_index = crn.face.index
    linked = [crn]
    bm_iter = crn

    while True:
        bm_iter = bm_iter.link_loop_prev.link_loop_radial_prev
        if bm_iter == crn:
            break
        if bm_iter.face.index == face_index and crn[uv].uv == bm_iter[uv].uv:
            linked.append(bm_iter)

    return linked


def linked_crn_to_vert_pair_with_seam(crn: BMLoop, uv: BMLayerItem, sync: bool) -> List[BMLoop]:
    """
    Get linked corners to vertex pair with seam consideration.
    Based on UniV's linked_crn_to_vert_pair_with_seam() function.
    
    Args:
        crn: Corner to start from
        uv: UV layer
        sync: Whether in sync mode
        
    Returns:
        List[BMLoop]: Linked corners
    """
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


def is_invisible_func(sync: bool) -> Callable[[BMFace], bool]:
    """
    Get function to check if face is invisible.
    Based on UniV's is_invisible_func() function.
    
    Args:
        sync: Whether in sync mode
        
    Returns:
        Callable: Function to check face visibility
    """
    if sync:
        return lambda f: f.hide
    else:
        return lambda f: not f.select


def copy_pos_to_target_with_select(crn: BMLoop, uv: BMLayerItem, idx: int):
    """
    Copy position to target with selection.
    Based on UniV's copy_pos_to_target_with_select() function.
    
    Args:
        crn: Corner to copy from
        uv: UV layer
        idx: Island index
    """
    next_crn_co = crn.link_loop_next[uv].uv
    shared = shared_crn(crn)
    
    if shared:
        shared[uv].select_edge = True
        
        for _crn in linked_crn_uv_by_face_index(shared, uv):
            _crn_uv = _crn[uv]
            _crn_uv.uv = next_crn_co
            _crn_uv.select = True
    
    crn_co = crn[uv].uv
    if shared:
        shared_next = shared.link_loop_next
        
        for _crn in linked_crn_uv_by_face_index(shared_next, uv):
            _crn_uv = _crn[uv]
            _crn_uv.uv = crn_co
            _crn_uv.select = True


class UMesh:
    """Single UMesh for stitch operations - UNIV implementation."""

    def __init__(self, bm, obj, is_edit_bm=True, verify_uv=True):
        self.bm = bm
        self.obj = obj
        self.elem_mode = None  # Will be set by UMeshes
        self.uv = bm.loops.layers.uv.verify() if verify_uv else None
        self.is_edit_bm = is_edit_bm
        self.update_tag = True
        self.sync = True  # Will be set by UMeshes
        self.aspect = 1.0
        self.sequence = []

    def update(self, force=False):
        """Update mesh - UNIV implementation."""
        if not self.update_tag:
            return False
        if self.is_edit_bm:
            bmesh.update_edit_mesh(self.obj.data, loop_triangles=force, destructive=force)
        else:
            self.bm.to_mesh(self.obj.data)
        return True

    @property
    def is_full_face_selected(self) -> bool:
        """Check if all faces are selected - UNIV implementation (umesh.py:92-93)."""
        if not self.bm.faces:
            return False
        return all(face.select for face in self.bm.faces if not face.hide)

    @property
    def is_full_face_deselected(self) -> bool:
        """Check if no faces are selected - UNIV implementation (umesh.py:96-97)."""
        return not any(face.select for face in self.bm.faces if not face.hide)

    def set_corners_tag(self, value):
        """Set corner tags."""
        for face in self.bm.faces:
            if not face.hide:
                for loop in face.loops:
                    loop.tag = value

    @property
    def total_edge_sel(self):
        """Total selected edges - UniV implementation."""
        return sum(1 for e in self.bm.edges if e.select)

    @property
    def total_face_sel(self):
        """Total selected faces - UniV implementation."""
        return sum(1 for f in self.bm.faces if f.select)

    def has_selected_uv_edges(self) -> bool:
        """
        Check if mesh has selected UV edges.
        EXACT UniV implementation from UMesh.has_selected_uv_edges() (umesh.py:187-205).
        """
        if self.sync:
            if not self.total_edge_sel:
                return False
            elif self.total_face_sel:
                return True
            else:
                for f in self.bm.faces:
                    if not f.hide:
                        for e in f.edges:
                            if e.select:
                                return True
                return False
        if not self.total_face_sel:
            return False
        uv = self.uv
        if self.is_full_face_selected:
            return any(any(crn[uv].select_edge for crn in f.loops) for f in self.bm.faces)
        return any(f.select and any(crn[uv].select_edge for crn in f.loops) for f in self.bm.faces)

    def has_selected_uv_faces(self) -> bool:
        """
        Check if mesh has selected UV faces.
        Based on UniV's UMesh.has_selected_uv_faces() (umesh.py:153-166).

        CRITICAL: Same pattern as has_selected_uv_edges() - checks if all faces
        are selected first to avoid mixing 3D and UV selection.
        """
        if self.sync:
            return any(face.select for face in self.bm.faces if not face.hide)

        if not self.bm.faces:
            return False

        # Check if any faces are selected at all
        has_selected_faces = any(face.select for face in self.bm.faces)
        if not has_selected_faces:
            return False

        uv = self.uv

        # Check UV select mode for proper selection checking
        uv_select_mode = bpy.context.tool_settings.uv_select_mode

        # CRITICAL: Check if ALL faces are selected
        if self.is_full_face_selected:
            # If all faces selected, check ALL faces for UV face selection
            if uv_select_mode == 'EDGE':
                return any(all(crn[uv].select_edge for crn in f.loops) for f in self.bm.faces)
            return any(all(crn[uv].select for crn in f.loops) for f in self.bm.faces)
        else:
            # If partial face selection, filter by face.select
            if uv_select_mode == 'EDGE':
                return any(all(crn[uv].select_edge for crn in f.loops) and f.select for f in self.bm.faces)
            return any(all(crn[uv].select for crn in f.loops) and f.select for f in self.bm.faces)

    def has_visible_uv_faces(self) -> bool:
        """Check if mesh has visible UV faces - UNIV implementation."""
        if self.sync:
            return any(not face.hide for face in self.bm.faces)
        else:
            return any(face.select for face in self.bm.faces)

    def verify_uv(self):
        """
        Verify and set UV layer for this mesh.
        Based on UniV's UMesh.verify_uv() implementation.

        Ensures the mesh has a UV layer, creating one if necessary.
        """
        if self.bm.loops.layers.uv:
            self.uv = self.bm.loops.layers.uv.verify()
        else:
            self.uv = self.bm.loops.layers.uv.new()


class UMeshes:
    """UMeshes collection for stitch operations - UNIV implementation."""
    
    def __init__(self, umeshes=None, *, report=None):
        if umeshes is None:
            self._sel_ob_with_uv()
        else:
            self.umeshes = umeshes
        self.report_obj = report
        self._cancel = False
        # Set sync mode based on Blender's UV sync setting - UNIV implementation
        self.sync = bpy.context.scene.tool_settings.use_uv_select_sync
        self.is_edit_mode = bpy.context.mode == 'EDIT_MESH'
    
    def report(self, info_type={'INFO'}, info="No uv for manipulate"):
        """Report info - UNIV implementation."""
        if self.report_obj is None:
            print(info_type, info)
            return
        self.report_obj(info_type, info)
    
    def update(self, force=False, info_type={'INFO'}, info="No uv for manipulate"):
        """Update mesh - UNIV implementation."""
        if self._cancel is True:
            return {'CANCELLED'}
        if sum(umesh.update(force=force) for umesh in self.umeshes):
            return {'FINISHED'}
        if info:
            self.report(info_type, info)
        return {'CANCELLED'}
    
    @property
    def update_tag(self):
        return any(umesh.update_tag for umesh in self)
    
    @update_tag.setter
    def update_tag(self, value):
        for umesh in self:
            umesh.update_tag = value
    
    def _sel_ob_with_uv(self):
        """Select objects with UV - UNIV implementation."""
        import bmesh
        from collections import defaultdict
        
        bmeshes = []
        if bpy.context.mode == 'EDIT_MESH':
            for obj in bpy.context.objects_in_mode_unique_data:
                if obj.type == 'MESH' and obj.data.uv_layers:
                    bm = bmesh.from_edit_mesh(obj.data)
                    if bm.faces:
                        bmeshes.append(UMesh(bm, obj))
        else:
            data_and_objects = defaultdict(list)
            
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH' and obj.data.uv_layers and obj.data.polygons:
                    data_and_objects[obj.data].append(obj)
            
            for data, objs in data_and_objects.items():
                bm = bmesh.new()
                bm.from_mesh(data)
                bmeshes.append(UMesh(bm, objs[0], False))
        self.umeshes = bmeshes
    
    def filtered_by_selected_and_visible_uv_edges(self):
        """Filter by selected and visible UV edges - UNIV implementation."""
        selected = []
        visible = []
        for umesh in self:
            if umesh.has_selected_uv_edges():
                selected.append(umesh)
            else:
                visible.append(umesh)
        
        # Remove umeshes without visible faces if no selected edges found
        if not selected:
            for umesh2 in reversed(visible):
                if not umesh2.has_visible_uv_faces():
                    visible.remove(umesh2)
        
        u1 = copy.copy(self)
        u2 = copy.copy(self)
        u1.umeshes = selected
        u2.umeshes = visible
        return u1, u2
    
    def filtered_by_selected_uv_faces(self):
        """Filter by selected UV faces - UNIV implementation."""
        selected = []
        unselect_or_invisible = []
        for umesh in self:
            if umesh.has_selected_uv_faces():
                selected.append(umesh)
            else:
                unselect_or_invisible.append(umesh)
        self.umeshes = selected
        other = copy.copy(self)
        other.umeshes = unselect_or_invisible
        return other

    @classmethod
    def calc(cls, report=None, verify_uv=True):
        """
        Get umeshes without requiring UV layers (but with faces).
        Based on UniV's UMeshes.calc() (umesh.py:853-874).

        This is used by 3D viewport operators to initialize UMeshes
        without requiring UV layers to exist first.
        """
        import bmesh
        from collections import defaultdict

        bmeshes = []
        if bpy.context.mode == 'EDIT_MESH':
            for obj in bpy.context.objects_in_mode_unique_data:
                if obj.type == 'MESH':
                    bm = bmesh.from_edit_mesh(obj.data)
                    if bm.faces:
                        bmeshes.append(UMesh(bm, obj, is_edit_bm=True, verify_uv=verify_uv))
        else:
            data_and_objects = defaultdict(list)

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH' and obj.data.polygons:
                    data_and_objects[obj.data].append(obj)

            for data, objs in data_and_objects.items():
                bm = bmesh.new()
                bm.from_mesh(data)
                objs.sort(key=lambda a: a.name)
                bmeshes.append(UMesh(bm, objs[0], is_edit_bm=False, verify_uv=verify_uv))

        return cls(bmeshes, report=report)

    def set_sync(self, state=True):
        """
        Explicitly set sync mode for all umeshes.
        Based on UniV's UMeshes.set_sync() (umesh.py:732-736).

        This is critical for 3D viewport operators to ensure they
        use 3D selection regardless of UV editor state.
        """
        for umesh in self:
            umesh.sync = state
        self.sync = state

    def filtered_by_uv_exist(self):
        """
        Filter out umeshes that don't have UV layers.
        Based on UniV's implementation for handling meshes without UVs.

        Returns UMeshes containing meshes WITHOUT UV layers.
        Updates self to contain only meshes WITH UV layers.
        """
        with_uv = []
        without_uv = []

        for umesh in self:
            if umesh.bm.loops.layers.uv:
                with_uv.append(umesh)
            else:
                without_uv.append(umesh)

        self.umeshes = with_uv
        other = copy.copy(self)
        other.umeshes = without_uv
        return other

    def verify_uv(self):
        """
        Verify and set UV layer for all umeshes.
        Based on UniV's verify_uv() implementation.
        """
        for umesh in self:
            umesh.verify_uv()

    def __iter__(self):
        return iter(self.umeshes)
    
    def __len__(self):
        return len(self.umeshes)
    
    def __bool__(self):
        return bool(self.umeshes)


def get_aspect_ratio(umesh=None):
    """Get aspect ratio - UniV implementation."""
    import bpy
    
    if umesh:
        # Aspect from checker
        if hasattr(umesh, 'obj') and umesh.obj:
            if modifiers := [m for m in umesh.obj.modifiers if m.name.startswith('UniV Checker')]:
                socket = 'Socket_1' if 'Socket_1' in modifiers[0] else 'Input_1'
                if mtl := modifiers[0][socket]:
                    for node in mtl.node_tree.nodes:
                        if node.bl_idname == 'ShaderNodeTexImage' and (image := node.image):
                            image_width, image_height = image.size
                            if image_height:
                                return image_width / image_height
            # Aspect from material
            elif mtl := umesh.obj.active_material:
                if mtl.use_nodes and (active_node := mtl.node_tree.nodes.active):
                    if active_node.bl_idname == 'ShaderNodeTexImage' and (image := active_node.image):
                        image_width, image_height = image.size
                        if image_height:
                            return image_width / image_height
        return 1.0
    
    # Aspect from active area
    if (area := bpy.context.area) and area.type == 'IMAGE_EDITOR':
        space_data = area.spaces.active
        if space_data and space_data.image:
            image_width, image_height = space_data.image.size
            if image_height:
                return image_width / image_height
    else:
        # Aspect from VIEW3D
        for area in bpy.context.screen.areas:
            if not area.type == 'IMAGE_EDITOR':
                continue
            space_data = area.spaces.active
            if space_data and space_data.image:
                image_width, image_height = space_data.image.size
                if image_height:
                    return image_width / image_height
    return 1.0


def get_max_distance_from_px(px_distance, view2d):
    """Convert pixel distance to UV space distance - UniV implementation."""
    if not view2d:
        return 0.1
    
    # Get the scale factor from view2d
    scale = view2d.view_to_region(1, 1)[0] - view2d.view_to_region(0, 0)[0]
    if scale <= 0:
        return 0.1
    
    # Convert pixel distance to UV space
    uv_distance = px_distance / scale
    return max(0.001, uv_distance)


def get_active_image_size():
    """Get active image size - UniV implementation."""
    import bpy
    
    # Check active area
    if (area := bpy.context.area) and area.type == 'IMAGE_EDITOR':
        space_data = area.spaces.active
        if space_data and space_data.image:
            return space_data.image.size
    
    # Check all areas for image editor
    for area in bpy.context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            space_data = area.spaces.active
            if space_data and space_data.image:
                return space_data.image.size
    
    return None


def get_prefs():
    """Get preferences - UniV implementation."""
    try:
        from ..properties import get_uvv_settings
        return get_uvv_settings()
    except ImportError:
        # Fallback to default preferences
        class DefaultPrefs:
            max_pick_distance = 10.0
        return DefaultPrefs()


def is_visible_func(sync):
    """Get visibility function based on sync mode."""
    if sync:
        return lambda face: not face.hide
    else:
        return lambda face: face.select


def is_invisible_func(sync):
    """Get invisibility function based on sync mode."""
    if sync:
        return lambda face: face.hide
    else:
        return lambda face: not face.select


def calc_signed_face_area_uv(face: BMFace, uv: BMLayerItem) -> float:
    """
    Calculate signed 2D area of face in UV space.
    Based on UniV's calc_signed_face_area_uv() function.

    Args:
        face: Face to calculate area for
        uv: UV layer

    Returns:
        float: Signed area (positive if CCW, negative if CW)
    """
    loops = face.loops
    area = 0.0
    v1 = loops[0][uv].uv

    for i in range(1, len(loops) - 1):
        v2 = loops[i][uv].uv
        v3 = loops[i + 1][uv].uv
        area += (v2.x - v1.x) * (v3.y - v1.y) - (v3.x - v1.x) * (v2.y - v1.y)

    return area * 0.5


def prev_disc(crn: BMLoop) -> BMLoop:
    """
    Get previous corner in disc (radial) order.
    Based on UniV's prev_disc() function.
    """
    return crn.link_loop_radial_prev


def linked_crn_uv_unordered_included(crn: BMLoop, uv) -> List[BMLoop]:
    """
    Get linked UV corners unordered included.
    Based on UniV's linked_crn_uv_unordered_included() function.
    """
    linked = []
    vert = crn.vert
    for face in vert.link_faces:
        for loop in face.loops:
            if loop.vert == vert and loop[uv].uv == crn[uv].uv:
                linked.append(loop)
    return linked


def linked_crn_uv_by_crn_tag_unordered_included(crn: BMLoop, uv) -> List[BMLoop]:
    """
    Get linked UV corners by corner tag unordered included.
    Based on UniV's linked_crn_uv_by_crn_tag_unordered_included() function.
    """
    linked = []
    vert = crn.vert
    for face in vert.link_faces:
        for loop in face.loops:
            if loop.vert == vert and loop[uv].uv == crn[uv].uv and loop.tag:
                linked.append(loop)
    return linked


def linked_crn_vert_uv_for_transform(crn: BMLoop, uv) -> List[BMLoop]:
    """
    Get linked corners for vertex UV transform.
    Based on UniV's linked_crn_vert_uv_for_transform() function.
    """
    linked = []
    vert = crn.vert
    for face in vert.link_faces:
        for loop in face.loops:
            if loop.vert == vert and loop[uv].uv == crn[uv].uv:
                linked.append(loop)
    return linked


def weighted_linear_space(start: Vector, end: Vector, weights: List[float]) -> List[Vector]:
    """
    Create weighted linear space between start and end.
    Based on UniV's weighted_linear_space() function.
    """
    if not weights:
        return [start, end]
    
    total_weight = sum(weights)
    if total_weight == 0:
        return [start, end]
    
    points = []
    current_pos = start.copy()
    direction = end - start
    
    for i, weight in enumerate(weights):
        if i == 0:
            points.append(current_pos.copy())
        
        if i < len(weights) - 1:
            step = direction * (weight / total_weight)
            current_pos += step
            points.append(current_pos.copy())
    
    points.append(end.copy())
    return points


def vec_to_cardinal(vec: Vector) -> Vector:
    """
    Convert vector to cardinal direction.
    Based on UniV's vec_to_cardinal() function.
    """
    abs_x = abs(vec.x)
    abs_y = abs(vec.y)
    
    if abs_x > abs_y:
        return Vector((1, 0)) if vec.x > 0 else Vector((-1, 0))
    else:
        return Vector((0, 1)) if vec.y > 0 else Vector((0, -1))


def vec_isclose_to_zero(vec: Vector, epsilon: float = 1e-6) -> bool:
    """
    Check if vector is close to zero.
    Based on UniV's vec_isclose_to_zero() function.
    """
    return abs(vec.x) < epsilon and abs(vec.y) < epsilon


def sync() -> bool:
    """
    Check if UV sync mode is enabled.
    Based on UniV's sync() function.
    """
    return bpy.context.scene.tool_settings.use_uv_select_sync


class PaddingHelper:
    """
    Helper class for padding calculations and UI display.
    Based on UniV's PaddingHelper class.
    """
    
    padding_multiplayer: bpy.props.FloatProperty(
        name='Padding Multiplayer', default=0, min=-32, soft_min=0, soft_max=4, max=32)

    def __init__(self):
        self.padding = 0.0

    def draw_padding(self):
        """Draw padding UI elements."""
        layout = self.layout
        if self.padding_multiplayer:
            # Try to get UVV settings for padding info
            try:
                from ..properties import get_uvv_settings
                settings = get_uvv_settings()
                if settings:
                    layout.separator(factor=0.35)
                    layout.label(text=f"Global Texture Size = {min(1024, 1024)}")  # Default fallback
                    layout.label(text=f"Padding = {getattr(settings, 'padding', 0)}({int(getattr(settings, 'padding', 0) * self.padding_multiplayer)})px")
            except ImportError:
                pass

        layout.prop(self, "padding_multiplayer", slider=True)

    def calc_padding(self):
        """Calculate padding from settings."""
        try:
            from ..properties import get_uvv_settings
            settings = get_uvv_settings()
            if settings:
                padding_value = getattr(settings, 'padding', 0)
                size_x = getattr(settings, 'size_x', 1024)
                size_y = getattr(settings, 'size_y', 1024)
                self.padding = int(padding_value * self.padding_multiplayer) / min(int(size_x), int(size_y))
            else:
                self.padding = 0.0
        except ImportError:
            self.padding = 0.0

    def report_padding(self):
        """Report padding warnings if needed."""
        if self.padding:
            try:
                # Check if active image size differs from settings
                import bpy
                for area in bpy.context.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        space = area.spaces.active
                        if space and space.image:
                            img_size = space.image.size
                            if img_size and min(img_size) != 1024:  # Default fallback
                                self.report({'WARNING'}, 'Global and Active texture sizes have different values, '
                                                         'which will result in incorrect padding.')
                            break
            except Exception:
                pass
