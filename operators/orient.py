"""
Orient Operator - Rotates UV islands to minimal rectangle
Ported from UniV addon
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty
from math import atan2, pi
from mathutils import Vector

from .. import types
from .. import utils
from ..utils.overlap_helper import OverlapHelper


def find_min_rotate_angle(angle):
    """Calculate minimal rotation angle to nearest 90-degree increment"""
    return -(round(angle / (pi / 2)) * (pi / 2) - angle)


def get_mouse_pos(context, event):
    """Get mouse position in UV space"""
    region = context.region
    rv2d = region.view2d
    return rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y)


def get_max_distance_from_px(pixel_distance, view2d):
    """Convert pixel distance to UV space distance"""
    # Simple approximation - convert pixels to view space
    return pixel_distance * (view2d.view_to_region(1.0, 1.0, clip=False)[0] - view2d.view_to_region(0.0, 0.0, clip=False)[0]) / view2d.region.width


def is_boundary_sync(crn, uv):
    """Check if corner is on boundary in sync mode"""
    return crn.edge.seam or not crn.edge.is_manifold


def is_boundary_non_sync(crn, uv):
    """Check if corner is on boundary in non-sync mode"""
    return crn.edge.seam or not utils.is_manifold_uv(crn, uv)


class Islands:
    """Island calculation helper - simplified version"""

    @staticmethod
    def calc_extended_with_mark_seam(umesh):
        """Calculate islands from selected faces"""
        from ..types import AdvIsland

        # Get selected faces
        selected_faces = [f for f in umesh.bm.faces if f.select]
        if not selected_faces:
            return None

        # Use existing island detection
        island_groups = utils.get_island(bpy.context, umesh.bm, umesh.uv)

        # Filter to only selected islands
        islands = []
        for island in island_groups:
            # Check if any face in island is selected
            if any(f.select for f in island):
                isl = AdvIsland(umesh, list(island))
                isl.calc_bbox()
                islands.append(isl)

        return islands if islands else None

    @staticmethod
    def calc_visible_with_mark_seam(umesh):
        """Calculate all visible islands"""
        from ..types import AdvIsland

        # Get all islands
        island_groups = utils.get_island(bpy.context, umesh.bm, umesh.uv)

        islands = []
        for island in island_groups:
            isl = AdvIsland(umesh, list(island))
            isl.calc_bbox()
            islands.append(isl)

        return islands if islands else None

    @staticmethod
    def calc_extended_any_edge_with_markseam(umesh):
        """Calculate islands from selected edges"""
        from ..types import AdvIsland

        # Get islands where at least one edge is selected
        island_groups = utils.get_island(bpy.context, umesh.bm, umesh.uv)

        islands = []
        for island in island_groups:
            # Check if any edge in island is selected
            has_selected_edge = False
            for f in island:
                for edge in f.edges:
                    if edge.select:
                        has_selected_edge = True
                        break
                if has_selected_edge:
                    break

            if has_selected_edge:
                isl = AdvIsland(umesh, list(island))
                isl.calc_bbox()
                islands.append(isl)

        return islands if islands else None


class AdvIslands:
    """Advanced islands helper"""

    @staticmethod
    def calc_extended_or_visible_with_mark_seam(umesh, extended=True):
        """Calculate islands based on selection mode"""
        if extended:
            return Islands.calc_extended_with_mark_seam(umesh)
        else:
            return Islands.calc_visible_with_mark_seam(umesh)

    @staticmethod
    def calc_extended_any_edge_with_markseam(umesh):
        """Calculate islands from selected edges"""
        return Islands.calc_extended_any_edge_with_markseam(umesh)


class UVV_OT_Orient(Operator, OverlapHelper):
    bl_idname = 'uv.uvv_orient'
    bl_label = 'Orient'
    bl_description = "Rotated to a minimal rectangle, either vertical or horizontal\n\n" \
                     "Default - Fit by Islands\n" \
                     "Alt - Orient by Edge"
    bl_options = {'REGISTER', 'UNDO'}

    edge_dir: EnumProperty(name='Direction', default='BOTH', items=(
        ('BOTH', 'Both', ''),
        ('HORIZONTAL', 'Horizontal', ''),
        ('VERTICAL', 'Vertical', ''),
    ))
    use_correct_aspect: BoolProperty(name='Correct Aspect', default=True)

    def draw(self, context):
        layout = self.layout
        layout.row().prop(self, 'edge_dir', expand=True)
        layout.prop(self, 'use_correct_aspect')
        self.draw_overlap()

    def invoke(self, context, event):
        self.max_distance = 0.01  # Fixed distance for now
        self.mouse_pos = None
        if event.value == 'PRESS':
            if context.area.ui_type == 'UV':
                self.mouse_pos = get_mouse_pos(context, event)
            return self.execute(context)

        self.lock_overlap = event.shift
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and (obj := context.active_object) and obj.type == 'MESH'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aspect: float = 1.0
        self.mouse_pos: Vector | None = None
        self.max_distance: float | None = None
        self.umeshes: list = []

    def execute(self, context):
        self.aspect = utils.get_aspect_ratio() if self.use_correct_aspect else 1.0

        # Get all selected objects in edit mode
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.mode == 'EDIT']
        if not selected_objects:
            return {'CANCELLED'}

        self.umeshes = []
        for obj in selected_objects:
            import bmesh
            bm = bmesh.from_edit_mesh(obj.data)
            umesh = types.UMesh(bm, obj)
            self.umeshes.append(umesh)

        # Check if we have face selection
        selected_faces_umeshes = []
        selected_edges_umeshes = []

        for umesh in self.umeshes:
            has_selected_faces = any(f.select for f in umesh.bm.faces)
            has_selected_edges = any(e.select for e in umesh.bm.edges if not any(f.select for f in e.link_faces))

            if has_selected_faces:
                selected_faces_umeshes.append(umesh)
            elif has_selected_edges:
                selected_edges_umeshes.append(umesh)

        if not selected_faces_umeshes and not selected_edges_umeshes:
            # No selection - orient all visible islands
            return self.orient_pick_or_visible()

        if self.lock_overlap:
            if selected_faces_umeshes:
                self.orient_islands_with_selected_faces_overlap(selected_faces_umeshes, extended=True)
            elif selected_edges_umeshes:
                self.orient_islands_with_selected_edges_overlap(selected_edges_umeshes)
        else:
            if selected_faces_umeshes:
                self.orient_islands_with_selected_faces(selected_faces_umeshes)
            elif selected_edges_umeshes:
                self.orient_islands_with_selected_edges(selected_edges_umeshes)
            else:
                return self.orient_pick_or_visible()

        # Update all meshes
        for umesh in self.umeshes:
            umesh.update()

        return {'FINISHED'}

    def orient_islands_with_selected_faces(self, umeshes):
        for umesh in umeshes:
            islands = Islands.calc_extended_with_mark_seam(umesh)
            if islands:
                for island in islands:
                    self.orient_island(island)

    def orient_islands_with_selected_edges(self, umeshes):
        for umesh in umeshes:
            islands = Islands.calc_extended_any_edge_with_markseam(umesh)
            if islands:
                for island in islands:
                    self.orient_edge(island)

    def orient_pick_or_visible(self):
        for umesh in self.umeshes:
            islands = Islands.calc_visible_with_mark_seam(umesh)
            if islands:
                for isl in islands:
                    self.orient_island(isl)

        # Update all meshes
        for umesh in self.umeshes:
            umesh.update()

        return {'FINISHED'}

    def orient_islands_with_selected_faces_overlap(self, umeshes, extended):
        islands_of_mesh = []
        for umesh in umeshes:
            islands = AdvIslands.calc_extended_or_visible_with_mark_seam(umesh, extended=extended)
            if islands:
                for isl in islands:
                    isl.calc_tris()
                    isl.calc_flat_coords(save_triplet=True)
                islands_of_mesh.extend(islands)

        for overlapped_isl in self.calc_overlapped_island_groups(islands_of_mesh):
            self.orient_island(overlapped_isl)

    def orient_islands_with_selected_edges_overlap(self, umeshes):
        islands_of_mesh = []
        for umesh in umeshes:
            islands = AdvIslands.calc_extended_any_edge_with_markseam(umesh)
            if islands:
                for isl in islands:
                    isl.calc_tris()
                    isl.calc_flat_coords(save_triplet=True)
                islands_of_mesh.extend(islands)

        for overlapped_isl in self.calc_overlapped_island_groups(islands_of_mesh):
            self.orient_edge(overlapped_isl)

    def orient_edge(self, island):
        iter_isl = island if isinstance(island, types.UnionIslands) else (island,)
        max_length = -1.0
        v1 = Vector()
        v2 = Vector()
        for isl in iter_isl:
            uv = isl.umesh.uv
            for f in isl:
                for crn in f.loops:
                    if crn.edge.select:
                        v1_ = crn[uv].uv
                        v2_ = crn.link_loop_next[uv].uv
                        if (new_length := (v1_ - v2_).length) > max_length:
                            v1 = v1_
                            v2 = v2_
                            max_length = new_length

        if max_length != -1.0:
            self.orient_edge_ex(island, v1, v2)

    def orient_edge_ex(self, island, v1: Vector, v2: Vector):
        edge_vec: Vector = (v2 - v1) * Vector((self.aspect, 1.0))
        edge_vec.normalize()

        if not any(edge_vec):
            return

        if self.edge_dir == 'BOTH':
            current_angle = atan2(*edge_vec)
            angle_to_rotate = -find_min_rotate_angle(current_angle)

        elif self.edge_dir == 'HORIZONTAL':
            left_dir = Vector((-1, 0))
            right_dir = Vector((1, 0))
            a = edge_vec.angle_signed(left_dir)
            b = edge_vec.angle_signed(right_dir)
            angle_to_rotate = a if abs(a) < abs(b) else b

        else:  # VERTICAL
            bottom_dir = Vector((0, -1))
            upper_dir = Vector((0, 1))
            a = edge_vec.angle_signed(bottom_dir)
            b = edge_vec.angle_signed(upper_dir)
            angle_to_rotate = a if abs(a) < abs(b) else b

        pivot: Vector = (v1 + v2) / 2
        island.umesh.update_tag |= island.rotate(angle_to_rotate, pivot, self.aspect)

    def orient_island(self, island):
        from collections import Counter
        angles: Counter[float | float] = Counter()
        boundary_coords = []
        is_boundary = is_boundary_sync if island.umesh.sync else is_boundary_non_sync

        iter_isl = island if isinstance(island, types.UnionIslands) else (island, )
        for isl_ in iter_isl:
            uv = isl_.umesh.uv
            vec_aspect = Vector((self.aspect, 1.0))

            boundary_corners = (crn for f in isl_ for crn in f.loops if crn.edge.seam or is_boundary(crn, uv))
            for crn in boundary_corners:
                v1 = crn[uv].uv
                v2 = crn.link_loop_next[uv].uv
                boundary_coords.append(v1)

                edge_vec: Vector = (v2 - v1) * vec_aspect
                if any(edge_vec):
                    current_angle = atan2(*edge_vec)
                    angle_to_rotate = -find_min_rotate_angle(round(current_angle, 4))
                    angles[round(angle_to_rotate, 4)] += edge_vec.length

        if not angles:
            return

        angle = max(angles, key=angles.get)

        bbox = types.BBox.calc_bbox(boundary_coords)
        island.umesh.update_tag |= island.rotate(angle, bbox.center, self.aspect)

        bbox = types.BBox.calc_bbox(boundary_coords)
        if self.edge_dir == 'HORIZONTAL':
            if bbox.width*self.aspect < bbox.height:
                final_angle = pi/2 if angle < 0 else -pi/2
                island.umesh.update_tag |= island.rotate(final_angle, bbox.center, self.aspect)

        elif self.edge_dir == 'VERTICAL':
            if bbox.width*self.aspect > bbox.height:
                final_angle = pi/2 if angle < 0 else -pi/2
                island.umesh.update_tag |= island.rotate(final_angle, bbox.center, self.aspect)


classes = (
    UVV_OT_Orient,
)
