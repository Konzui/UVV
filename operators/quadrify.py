# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

# The code was taken and modified from the UvSquares addon: https://github.com/Radivarig/UvSquares/blob/master/uv_squares.py

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy
import math
import numpy as np
import itertools
from itertools import chain
from math import sqrt
from mathutils import Vector, Matrix
from bmesh.types import BMLoopUV, BMLoop, BMFace
from collections.abc import Callable
from mathutils.geometry import area_tri
from bl_math import clamp, lerp

from .. import utils
from .. import types
from ..types import UMeshes, IslandHit
from ..types.island import AdvIsland, AdvIslands
from ..utils import linked_crn_uv_by_face_tag_unordered_included, set_faces_tag
from ..utils.stitch_utils import get_aspect_ratio


class UVV_OT_Quadrify(bpy.types.Operator):
    bl_idname = "uv.uvv_quadrify"
    bl_label = "Quadrify"
    bl_description = "Align selected UV to rectangular distribution"
    bl_options = {'REGISTER', 'UNDO'}

    shear: bpy.props.BoolProperty(name='Shear', default=False, description='Reduce shear within islands')
    xy_scale: bpy.props.BoolProperty(name='Scale Independently', default=True,
                                     description='Scale U and V independently')
    use_aspect: bpy.props.BoolProperty(name='Correct Aspect', default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and (obj := context.active_object) and obj.type == 'MESH'  # noqa # pylint:disable=used-before-assignment

    def invoke(self, context, event):
        # Use default max pick distance - handle 3D viewport case
        try:
            if hasattr(context.region, 'view2d') and context.region.view2d:
                self.max_distance = utils.get_max_distance_from_px(10.0, context.region.view2d)
            else:
                # Fallback for 3D viewport or when view2d is not available
                self.max_distance = 0.1
        except:
            # Fallback if view2d access fails
            self.max_distance = 0.1
            
        self.mouse_pos = None
        if event.value == 'PRESS':
            if context.area.ui_type == 'UV':
                try:
                    self.mouse_pos = utils.get_mouse_pos(context, event)
                except:
                    # Fallback if mouse position calculation fails
                    self.mouse_pos = None
            return self.execute(context)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        if self.shear or self.xy_scale:
            layout.prop(self, 'use_aspect')
        layout.prop(self, 'shear')
        layout.prop(self, 'xy_scale')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_selected = True
        self.islands_calc_type: Callable = Callable
        self.umeshes: UMeshes | None = None
        self.mouse_pos: Vector | None = None
        self.max_distance: float | None = None

    def execute(self, context):
        # Allow execution from 3D viewport for pie menu usage
        from_3d_viewport = False
        if context.area.ui_type != 'UV':
            # If called from 3D viewport, switch to UV editor or work with current selection
            if context.area.type == 'VIEW_3D':
                # For 3D viewport, we'll work with the current mesh selection
                from_3d_viewport = True
            else:
                self.report({'WARNING'}, 'Active area must be UV or 3D Viewport')
                return {'CANCELLED'}

        self.umeshes = UMeshes(report=self.report)

        # Check UV sync mode
        tool_settings = context.tool_settings
        use_uv_select_sync = tool_settings.use_uv_select_sync if hasattr(tool_settings, 'use_uv_select_sync') else True

        # Use appropriate selection method based on context
        if from_3d_viewport or use_uv_select_sync:
            # 3D viewport or UV sync mode: temporarily force sync mode to use mesh selection
            # Store original sync state
            original_sync_state = {}
            for umesh in self.umeshes:
                original_sync_state[umesh] = umesh.sync
                umesh.sync = True  # Force sync mode to use mesh selection

            try:
                # Now use the standard filtering which will use mesh selection due to sync=True
                selected_umeshes, unselected_umeshes = self.umeshes.filtered_by_selected_and_visible_uv_faces()
                if selected_umeshes:
                    self.umeshes = selected_umeshes
                    return self.quadrify_selected()
                elif unselected_umeshes and self.mouse_pos:
                    self.umeshes = unselected_umeshes
                    return self.quadrify_pick()
                else:
                    self.report({'WARNING'}, 'No faces selected')
                    return {'CANCELLED'}
            finally:
                # Restore original sync state
                for umesh, original_sync in original_sync_state.items():
                    umesh.sync = original_sync
        else:
            # UV editor without sync: use UV selection
            selected_umeshes, unselected_umeshes = self.umeshes.filtered_by_selected_and_visible_uv_faces()
            if selected_umeshes:
                self.umeshes = selected_umeshes
                return self.quadrify_selected()
            elif unselected_umeshes and self.mouse_pos:
                self.umeshes = unselected_umeshes
                return self.quadrify_pick()
            else:
                self.report({'WARNING'}, 'Islands not found')
                return {'CANCELLED'}

    def quadrify_selected(self):
        counter = 0
        selected_non_quads_counter = 0
        for umesh in self.umeshes:
            umesh.update_tag = False
            if dirt_islands := AdvIslands.calc_extended_with_mark_seam(umesh):
                uv = umesh.uv
                umesh.value = umesh.check_uniform_scale(report=self.report)
                umesh.aspect = get_aspect_ratio(umesh) if self.use_aspect else 1.0
                edge_lengths = []
                for d_island in dirt_islands:
                    links_static_with_quads, static_faces, non_quad_selected, quad_islands = self.split_by_static_faces_and_quad_islands(
                        d_island)
                    selected_non_quads_counter += len(non_quad_selected)
                    for isl in quad_islands:
                        utils.set_faces_tag(isl, True)
                        set_corner_tag_by_border_and_by_tag(isl)  # TODO: Preserve flipped 3D

                        if not edge_lengths:
                            edge_lengths = self.init_edge_sequence_from_umesh(umesh)

                        quad(isl, edge_lengths)
                        counter += 1
                        umesh.update_tag = True

                    if self.shear or self.xy_scale:
                        self.quad_normalize(quad_islands, umesh)

                    for static_crn, quad_corners in links_static_with_quads:
                        static_co = static_crn[uv].uv
                        min_dist_quad_crn = min(quad_corners, key=lambda q_crn: (q_crn[uv].uv - static_co).length)
                        static_co[:] = min_dist_quad_crn[uv].uv

        if selected_non_quads_counter:
            self.report({'WARNING'}, f"Ignored {selected_non_quads_counter} non-quad faces")
        elif not counter:
            return self.umeshes.update()

        self.umeshes.silent_update()
        return {'FINISHED'}

    @staticmethod
    def init_edge_sequence_from_umesh(umesh: types.UMesh) -> list[None | float]:
        idx = 0
        for f in umesh.bm.faces:
            for crn in f.loops:
                crn.index = idx
                idx += 1

        return [None] * umesh.total_corners

    @staticmethod
    def init_edge_sequence_from_island(island: types.FaceIsland) -> list[None | float]:
        idx = 0
        for f in island:
            for crn in f.loops:
                crn.index = idx
                idx += 1

        return [None] * idx

    def quad_normalize(self, quad_islands, umesh):
        """Normalize quad islands with shear and scale adjustments"""
        # adjust and normalize
        quad_islands = AdvIslands(quad_islands, umesh)
        quad_islands.calc_tris_simple()
        quad_islands.calc_flat_uv_coords(save_triplet=True)
        quad_islands.calc_flat_unique_uv_coords()
        quad_islands.calc_flat_3d_coords(save_triplet=True, scale=umesh.value)
        quad_islands.calc_area_3d(umesh.value, areas_to_weight=True)  # umesh.value == obj scale
        
        # Use the normalize operator methods like univ does - call static methods with self as first parameter
        for isl in quad_islands:
            old_center = isl.bbox.center
            isl.value = old_center
            new_center = UVV_OT_Quadrify.individual_scale(self, isl)  # Call static method with self as first parameter
            isl.value = new_center
            if len(quad_islands) == 1:
                isl.set_position(old_center, new_center)
        
        if len(quad_islands) > 1:
            tot_area_uv, tot_area_3d = UVV_OT_Quadrify.avg_by_frequencies(self, quad_islands)
            UVV_OT_Quadrify.normalize(self, quad_islands, tot_area_uv, tot_area_3d)

    @staticmethod
    def individual_scale(quadrify_op, isl, threshold=1e-8):
        """
        Individual scale method for quadrify normalization.
        Based on UniV's individual_scale() method.
        """
        if not quadrify_op.shear and not quadrify_op.xy_scale:
            return isl.value

        if isinstance(isl.value, Vector):
            new_center = isl.value.copy()
        else:
            new_center = Vector((1, 1))

        aspect = isl.umesh.aspect
        transform_acc = Matrix.Identity(2)
        scale_acc = Vector((1.0, 1.0))

        flat_3d_coords = np.array([(pt_a.to_tuple(), pt_b.to_tuple(), pt_c.to_tuple())
                                  for pt_a, pt_b, pt_c in isl.flat_3d_coords], dtype=np.float32)
        vec_ac = flat_3d_coords[:, 0] - flat_3d_coords[:, 2]
        vec_bc = flat_3d_coords[:, 1] - flat_3d_coords[:, 2]
        flat_uv_coords = np.array([(pt_a.to_tuple(), pt_b.to_tuple(), pt_c.to_tuple())
                                  for pt_a, pt_b, pt_c in isl.flat_coords], dtype=np.float32)
        weights = np.array(list(isl.weights) if isinstance(
            isl.weights, itertools.chain) else isl.weights, dtype=np.float32)

        for _ in range(10):
            m00 = flat_uv_coords[:, 0, 0] - flat_uv_coords[:, 2, 0]
            m01 = flat_uv_coords[:, 0, 1] - flat_uv_coords[:, 2, 1]
            m10 = flat_uv_coords[:, 1, 0] - flat_uv_coords[:, 2, 0]
            m11 = flat_uv_coords[:, 1, 1] - flat_uv_coords[:, 2, 1]

            det = m00 * m11 - m01 * m10
            mask = np.abs(det) > threshold

            with np.errstate(divide='ignore', invalid='ignore'):
                inv00, inv01 = m11 / det, -m01 / det
                inv10, inv11 = -m10 / det, m00 / det

                cou = inv00[:, None] * vec_ac + inv01[:, None] * vec_bc
                cov = inv10[:, None] * vec_ac + inv11[:, None] * vec_bc

            w = weights
            if not np.all(mask):
                if not np.any(mask):
                    break
                cou = cou[mask]
                cov = cov[mask]
                w = weights[mask]

            scale_cou = np.sum(utils.np_vec_normalized(cou, keepdims=False) * w)
            scale_cov = np.sum(utils.np_vec_normalized(cov, keepdims=False) * w)
            scale_cross = 0.0
            if quadrify_op.shear:
                cou_n = cou / utils.np_vec_normalized(cou)
                cov_n = cov / utils.np_vec_normalized(cov)
                scale_cross = np.sum(utils.np_vec_dot(cou_n, cov_n) * w)

            if scale_cou * scale_cov < 1e-10:
                break

            scale_factor_u = sqrt(scale_cou / scale_cov / aspect)

            tolerance = 1e-5  # Trade accuracy for performance.
            if quadrify_op.shear:
                t = Matrix.Identity(2)
                t[0][0] = scale_factor_u
                t[1][0] = clamp((scale_cross / isl.area_3d) * aspect, -0.5 * aspect, 0.5 * aspect)
                t[0][1] = 0
                t[1][1] = 1 / scale_factor_u

                err = abs(t[0][0] - 1.0) + abs(t[1][0]) + abs(t[0][1]) + abs(t[1][1] - 1.0)
                if err < tolerance:
                    break

                # Transform
                transform_acc @= t
                flat_uv_coords = flat_uv_coords @ np.array(t, dtype=np.float32)
            else:
                if not quadrify_op.xy_scale:
                    # If xy_scale is False, don't apply any scaling
                    break
                if math.isclose(scale_factor_u, 1.0, abs_tol=tolerance):
                    break
                scale = Vector((scale_factor_u, 1.0/scale_factor_u))
                scale_acc *= scale
                flat_uv_coords *= np.array(scale, dtype=np.float32)

        if quadrify_op.shear:
            if transform_acc != Matrix.Identity(2):
                isl.umesh.update_tag = True
                for uv_coord in isl.flat_unique_uv_coords:
                    uv_coord.xy = uv_coord @ transform_acc
                new_center = new_center @ transform_acc
        else:
            if scale_acc != Vector((1.0, 1.0)):
                isl.umesh.update_tag = True
                for uv_coord in isl.flat_unique_uv_coords:
                    uv_coord *= scale_acc
                new_center *= scale_acc
        return new_center

    @staticmethod
    def normalize(quadrify_op, islands, tot_area_uv, tot_area_3d):
        """
        Normalize islands based on total UV and 3D areas.
        Based on UniV's normalize() method.
        """
        if not quadrify_op.xy_scale and len(islands) <= 1:
            quadrify_op.report({'WARNING'}, f"Islands should be more than 1, given {len(islands)} islands")
            return
        if tot_area_3d == 0.0 or tot_area_uv == 0.0:
            # Prevent divide by zero.
            quadrify_op.report({'WARNING'}, f"Cannot normalize islands, total {'UV-area' if tot_area_3d else '3D-area'} of faces is zero")
            return

        tot_fac = tot_area_3d / tot_area_uv

        zero_area_islands = []
        for isl in islands:
            if math.isclose(isl.area_3d, 0.0, abs_tol=1e-6) or math.isclose(isl.area_uv, 0.0, abs_tol=1e-6):
                zero_area_islands.append(isl)
                continue

            fac = isl.area_3d / isl.area_uv
            scale = math.sqrt(fac / tot_fac)

            if quadrify_op.xy_scale or quadrify_op.shear:
                old_pivot = isl.bbox.center
                new_pivot = isl.value
                new_pivot_with_scale = new_pivot * scale

                diff1 = old_pivot - new_pivot
                diff = (new_pivot - new_pivot_with_scale) + diff1

                if utils.vec_isclose(old_pivot, new_pivot) and math.isclose(scale, 1.0, abs_tol=0.00001):
                    continue

                for crn_co in isl.flat_unique_uv_coords:
                    crn_co *= scale
                    crn_co += diff

                isl.umesh.update_tag = True
            else:
                if math.isclose(scale, 1.0, abs_tol=0.00001):
                    continue
                if isl.scale(Vector((scale, scale)), pivot=isl.calc_bbox().center):
                    isl.umesh.update_tag = True

        if zero_area_islands:
            for isl in islands:
                if isl not in zero_area_islands:
                    isl.select = False
                    isl.umesh.update_tag = True
            for isl in zero_area_islands:
                isl.select = True
                isl.umesh.update_tag = True

            quadrify_op.report({'WARNING'}, f"Found {len(zero_area_islands)} islands with zero area")

    @staticmethod
    def avg_by_frequencies(quadrify_op, all_islands):
        """
        Calculate average areas by frequency analysis.
        Based on UniV's avg_by_frequencies() method.
        """
        areas_uv = np.empty(len(all_islands), dtype=float)
        areas_3d = np.empty(len(all_islands), dtype=float)

        for idx, isl in enumerate(all_islands):
            areas_uv[idx] = isl.calc_area_uv()
            areas_3d[idx] = isl.area_3d

        areas = areas_uv if quadrify_op.bl_idname.startswith('UV') else areas_3d
        median: float = np.median(areas)
        min_area = np.amin(areas)
        max_area = np.amax(areas)

        center = (min_area + max_area) / 2
        if center > median:
            diff = lerp(median, max_area, 0.15) - median
        else:
            diff = median - lerp(median, min_area, 0.15)

        min_clamp = median - diff
        max_clamp = median + diff

        indexes = (areas >= min_clamp) & (areas <= max_clamp)
        total_uv_area = np.sum(areas_uv, where=indexes)
        total_3d_area = np.sum(areas_3d, where=indexes)

        # TODO: Averaging by area_3d to area_uv ratio (by frequency of occurrence of the same values)
        if total_uv_area and total_3d_area:
            return total_uv_area, total_3d_area
        else:
            idx_for_find = math.nextafter(median, max_area)
            idx = UVV_OT_Quadrify.np_find_nearest(areas, idx_for_find)
            total_uv_area = areas_uv[idx]
            total_3d_area = areas_3d[idx]
            if total_uv_area and total_3d_area:
                return total_uv_area, total_3d_area
            else:
                return np.sum(areas_uv), np.sum(areas_3d)

    @staticmethod
    def np_find_nearest(array, value):
        """Find nearest value in array."""
        idx = (np.abs(array - value)).argmin()
        return idx

    def quadrify_pick(self):
        hit = IslandHit(self.mouse_pos, self.max_distance)

        for umesh in self.umeshes:
            if dirt_islands := AdvIslands.calc_visible_with_mark_seam(umesh):
                for d_island in dirt_islands:
                    hit.find_nearest_island_by_crn(d_island)
        if not hit:
            self.report({'WARNING'}, "Islands not found")
            return {'CANCELLED'}

        links_static_with_quads, static_faces, quad_islands = self.split_by_static_faces_and_quad_islands_pick(
            hit.island)
        if not quad_islands:
            self.report({'WARNING'}, f"All {len(static_faces)} faces is non-quad")
            return {'CANCELLED'}

        for isl in quad_islands:
            utils.set_faces_tag(isl, True)
            set_corner_tag_by_border_and_by_tag(isl)
            edge_lengths = self.init_edge_sequence_from_island(isl)
            quad(isl, edge_lengths)

        umesh = hit.island.umesh
        uv = umesh.uv
        umesh.value = umesh.check_uniform_scale(report=self.report)
        umesh.aspect = get_aspect_ratio(umesh) if self.use_aspect else 1.0
        if self.shear or self.xy_scale:
            self.quad_normalize(quad_islands, umesh)

        for static_crn, quad_corners in links_static_with_quads:
            static_co = static_crn[uv].uv
            min_dist_quad_crn = min(quad_corners, key=lambda q_crn: (q_crn[uv].uv - static_co).length)
            static_co[:] = min_dist_quad_crn[uv].uv

        hit.island.umesh.update()
        if static_faces:
            self.report({'WARNING'}, f"Ignored {len(static_faces)} non-quad faces")
        return {'FINISHED'}

    def split_by_static_faces_and_quad_islands(self, island):
        umesh = island.umesh
        uv = umesh.uv
        quad_faces = []
        selected_non_quads = []
        static_faces = []
        face_select_get = utils.face_select_get_func(umesh)

        for f in island:
            if face_select_get(f):
                if len(f.loops) == 4:
                    quad_faces.append(f)
                else:
                    selected_non_quads.append(f)
            else:
                static_faces.append(f)

        if not (static_faces or selected_non_quads):  # Full quad case
            return [], static_faces, selected_non_quads, [island]
        elif len(static_faces) + len(selected_non_quads) == len(island):  # Non quad case
            return [], static_faces, selected_non_quads, []

        utils.set_faces_tag(quad_faces)
        links_static_with_quads = self.store_links_static_with_quads(chain(static_faces, selected_non_quads), uv)
        fake_umesh = umesh.fake_umesh(quad_faces)
        # Calc sub-islands
        islands = [AdvIslands.island_type(i, umesh) for i in AdvIslands.calc_iter_ex(fake_umesh)]
        return links_static_with_quads, static_faces, selected_non_quads, islands

    def split_by_static_faces_and_quad_islands_pick(self, island):
        umesh = island.umesh
        uv = umesh.uv
        quad_faces = []
        static_faces = []

        for f in island:
            if len(f.loops) == 4:
                quad_faces.append(f)
            else:
                static_faces.append(f)

        if not static_faces:
            return [], static_faces, [island]
        elif len(static_faces) == len(island):
            return [], static_faces, []

        utils.set_faces_tag(quad_faces)
        links_static_with_quads = self.store_links_static_with_quads(static_faces, uv)
        fake_umesh = umesh.fake_umesh(quad_faces)
        islands = [AdvIslands.island_type(i, umesh) for i in AdvIslands.calc_iter_ex(fake_umesh)]
        return links_static_with_quads, static_faces, islands

    @staticmethod
    def store_links_static_with_quads(faces, uv):
        links_static_with_quads = []
        for f in faces:
            for crn in f.loops:
                if linked_corners := linked_crn_uv_by_face_tag_unordered_included(crn, uv):
                    links_static_with_quads.append((crn, linked_corners))
        return links_static_with_quads


def set_corner_tag_by_border_and_by_tag(island: AdvIsland):
    uv = island.umesh.uv
    for crn in island.corners_iter():
        prev = crn.link_loop_radial_prev
        if crn.edge.seam or crn == prev or not prev.face.tag:
            crn.tag = False
            continue
        crn.tag = utils.is_pair(crn, prev, uv)


def quad(island: AdvIsland, edge_lengths):
    uv = island.umesh.uv

    def max_quad_uv_face_area(f):
        f_loops = f.loops
        l1 = f_loops[0][uv].uv
        l2 = f_loops[1][uv].uv
        l3 = f_loops[2][uv].uv
        l4 = f_loops[3][uv].uv

        return area_tri(l1, l2, l3) + area_tri(l3, l4, l1)

    # TODO: Find most quare and large target face
    target_face = max(island, key=max_quad_uv_face_area)
    co_and_linked_uv_corners = calc_co_and_linked_uv_corners_dict(target_face, island.umesh.uv)
    shape_face(uv, target_face, co_and_linked_uv_corners)
    follow_active_uv(target_face, island, edge_lengths)


def calc_co_and_linked_uv_corners_dict(f, uv) -> dict[Vector, list[BMLoopUV]]:
    co_and_linked_uv_corners = {}
    for crn in f.loops:
        co: Vector = crn[uv].uv.copy().freeze()
        corners = linked_crn_uv_by_face_tag_unordered_included(crn, uv)
        co_and_linked_uv_corners[co] = [crn[uv] for crn in corners]

    return co_and_linked_uv_corners


def shape_face(uv, target_face, co_and_linked_uv_corners):
    corners = []
    for l in target_face.loops:
        corners.append(l[uv])

    first_highest = corners[0]
    for c in corners:
        if c.uv.y > first_highest.uv.y:
            first_highest = c
    corners.remove(first_highest)

    second_highest = corners[0]
    for c in corners:
        if c.uv.y > second_highest.uv.y:
            second_highest = c

    if first_highest.uv.x < second_highest.uv.x:
        left_up = first_highest
        right_up = second_highest
    else:
        left_up = second_highest
        right_up = first_highest
    corners.remove(second_highest)

    first_lowest = corners[0]
    second_lowest = corners[1]

    if first_lowest.uv.x < second_lowest.uv.x:
        left_down = first_lowest
        right_down = second_lowest
    else:
        left_down = second_lowest
        right_down = first_lowest

    make_uv_face_equal_rectangle(co_and_linked_uv_corners, left_up, right_up, right_down, left_down)


def make_uv_face_equal_rectangle(co_and_linked_uv_corners, left_up, right_up, right_down, left_down):
    left_up = left_up.uv.copy().freeze()
    right_up = right_up.uv.copy().freeze()
    right_down = right_down.uv.copy().freeze()
    left_down = left_down.uv.copy().freeze()

    final_scale_x = (left_up - right_up).length
    final_scale_y = (left_up - left_down).length
    curr_row_x = left_up.x
    curr_row_y = left_up.y

    for v in co_and_linked_uv_corners[left_up]:
        v.uv[:] = curr_row_x, curr_row_y

    for v in co_and_linked_uv_corners[right_up]:
        v.uv[:] = curr_row_x + final_scale_x, curr_row_y

    for v in co_and_linked_uv_corners[right_down]:
        v.uv[:] = curr_row_x + final_scale_x, curr_row_y - final_scale_y

    for v in co_and_linked_uv_corners[left_down]:
        v.uv[:] = curr_row_x, curr_row_y - final_scale_y


def follow_active_uv(f_act, island: AdvIsland, edge_lengths):
    uv = island.umesh.uv  # noqa

    def walk_face(f: BMFace):  # noqa
        # all faces in this list must be tagged
        f.tag = False
        faces_a = [f]
        faces_b = []

        while faces_a:
            for f in faces_a:  # noqa
                for l in f.loops:  # noqa
                    if l.tag:
                        l_other = l.link_loop_radial_prev
                        f_other = l_other.face
                        if f_other.tag:
                            yield l
                            f_other.tag = False
                            faces_b.append(f_other)
            # swap
            faces_a, faces_b = faces_b, faces_a
            faces_b.clear()

    def extrapolate_uv(fac,
                       l_a_outer, l_a_inner,
                       l_b_outer, l_b_inner):
        l_b_inner[:] = l_a_inner
        l_b_outer[:] = l_a_inner + ((l_a_inner - l_a_outer) * fac)

    def apply_uv(l_prev: BMLoop):
        l_a: list[BMLoop | None] = [None, None, None, None]  # TODO: Array convert to vars
        l_b: list[BMLoop | None] = [None, None, None, None]

        l_a[0] = l_prev
        l_a[1] = l_a[0].link_loop_next
        l_a[2] = l_a[1].link_loop_next
        l_a[3] = l_a[2].link_loop_next

        #  l_b
        #  +-----------+
        #  |(3)        |(2)
        #  |           |
        #  |l_next(0)  |(1)
        #  +-----------+
        #        ^
        #  l_a   |
        #  +-----------+
        #  |l_prev(0)  |(1)
        #  |    (f)    |
        #  |(3)        |(2)
        #  +-----------+
        #  copy from this face to the one above.

        # get the other loops
        l_next = l_prev.link_loop_radial_prev
        assert l_next != l_prev
        l_b[1] = l_next
        l_b[0] = l_b[1].link_loop_next
        l_b[3] = l_b[0].link_loop_next
        l_b[2] = l_b[3].link_loop_next

        l_a_uv: list[Vector] = [l[uv].uv for l in l_a]  # noqa
        l_b_uv: list[Vector] = [l[uv].uv for l in l_b]  # noqa

        try:
            fac = edge_lengths[l_b[2].index] / edge_lengths[l_a[1].index]
        except ZeroDivisionError:
            fac = 1.0

        extrapolate_uv(fac,
                       l_a_uv[3], l_a_uv[0],
                       l_b_uv[3], l_b_uv[0])

        extrapolate_uv(fac,
                       l_a_uv[2], l_a_uv[1],
                       l_b_uv[2], l_b_uv[1])

    calc_avg_ring_length(edge_lengths, island)

    f_act.tag = False
    for l_prev_ in walk_face(f_act):
        apply_uv(l_prev_)


def calc_avg_ring_length(edge_lengths, island):
    for f in island:
        for ring_crn in f.loops:
            if edge_lengths[ring_crn.index] is None:
                corners = get_ring_corners_from_crn(ring_crn)

                avg_length = sum(crn.edge.calc_length() for crn in corners) / len(corners)
                for crn in corners:
                    edge_lengths[crn.index] = avg_length


# TODO: This algorithm does not always pass through all the edges, so we have to pass all 4 edges through this algorithm
def get_ring_corners_from_crn(first_crn: BMLoop):
    corners = [first_crn]

    # first direction
    iter_crn = first_crn
    while True:
        iter_crn = iter_crn.link_loop_next.link_loop_next
        corners.append(iter_crn)
        if not iter_crn.tag:
            break

        iter_crn = iter_crn.link_loop_radial_prev
        if iter_crn == first_crn:  # is circular
            return corners
        corners.append(iter_crn)

    # other dir
    if first_crn.tag:
        iter_crn = first_crn.link_loop_radial_prev
        if not iter_crn.tag:
            return corners

        while True:
            iter_crn = iter_crn.link_loop_next.link_loop_next
            corners.append(iter_crn)

            if not iter_crn.tag:
                break
            iter_crn = iter_crn.link_loop_radial_prev
            corners.append(iter_crn)
    return corners


# Classes to register
classes = [
    UVV_OT_Quadrify,
]
