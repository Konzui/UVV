# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import numpy as np
import itertools

from bpy.props import BoolProperty, EnumProperty
from bpy.types import Operator
from math import pi, sqrt
from bl_math import clamp, lerp
from mathutils import Vector, Matrix

from .. import utils
from .. import types
from ..types import AdvIslands, AdvIsland, UnionIslands

class UVV_OT_ResetScale(Operator, utils.OverlapHelper):
    bl_idname = "uv.uvv_reset_scale"
    bl_label = 'Optimize'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Optimize the scale of separate UV islands, based on their area in 3D space\n\nDefault - Optimize islands scale\nShift - Lock Overlaps"

    shear: BoolProperty(name='Shear', default=True, description='Reduce shear within islands')
    axis: EnumProperty(name='Axis', default='XY', items=(('XY', 'Both', ''), ('X', 'X', ''), ('Y', 'Y', '')))
    use_aspect: BoolProperty(name='Correct Aspect', default=True)

    @classmethod
    def poll(cls, context):
        return (obj := context.active_object) and obj.type == 'MESH'

    def invoke(self, context, event):
        if event.value == 'PRESS':
            return self.execute(context)
        self.lock_overlap = event.shift
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        self.draw_overlap()
        layout.row(align=True).prop(self, 'axis', expand=True)
        layout.prop(self, 'shear')
        layout.prop(self, 'use_aspect')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.umeshes = None

    def execute(self, context):
        self.umeshes = types.UMeshes(report=self.report)
        for umesh in self.umeshes:
            umesh.update_tag = False
            umesh.value = umesh.check_uniform_scale(report=self.report)

        if not self.bl_idname.startswith('UV'):
            self.umeshes.set_sync()

        all_islands = []

        islands_calc_type = None
        if self.umeshes.is_edit_mode:
            selected_umeshes, unselected_umeshes = self.umeshes.filtered_by_selected_and_visible_uv_faces()
            self.umeshes = selected_umeshes if selected_umeshes else unselected_umeshes
            islands_calc_type = AdvIslands.calc_extended_with_mark_seam if selected_umeshes else AdvIslands.calc_visible_with_mark_seam
        else:
            islands_calc_type = AdvIslands.calc_with_hidden
            for umesh in self.umeshes:
                umesh.ensure(face=True)

        if self.use_aspect:
            self.umeshes.calc_aspect_ratio(from_mesh=False)

        for umesh in self.umeshes:
            adv_islands = islands_calc_type(umesh)
            assert adv_islands, f'Object "{umesh.obj.name}" not found islands'
            all_islands.extend(adv_islands)
            adv_islands.calc_tris_simple()
            adv_islands.calc_flat_uv_coords(save_triplet=True)
            adv_islands.calc_flat_unique_uv_coords()
            adv_islands.calc_flat_3d_coords(save_triplet=True, scale=umesh.value)
            adv_islands.calc_area_3d(umesh.value, areas_to_weight=True)  # umesh.value == obj scale

        if not all_islands:
            self.report({'WARNING'}, 'Islands not found')
            return {'CANCELLED'}

        if self.lock_overlap:
            all_islands = self.calc_overlapped_island_groups(all_islands)

        for isl in all_islands:
            isl.value = isl.bbox.center  # isl.value == pivot
            # TODO: Find how to calculate the shear for the X axis when aspect != 1 without rotation island
            if self.axis == 'X' and isl.umesh.aspect != 1.0 and self.shear:
                isl.rotate_simple(pi/2, isl.umesh.aspect)
                self.individual_scale(isl, 'Y',  self.shear)
                isl.rotate_simple(-pi/2, isl.umesh.aspect)
                new_center = isl.calc_bbox().center
            else:
                new_center = self.individual_scale(isl, self.axis, self.shear)
            isl.set_position(isl.value, new_center)

        self.umeshes.update(info='All islands were with scaled')

        if not self.umeshes.is_edit_mode:
            self.umeshes.free()
            utils.update_area_by_type('VIEW_3D')

        return {'FINISHED'}

    @staticmethod
    def individual_scale(isl, axis, shear, threshold=1e-8):
        # TODO: The threshold can be made lower if the triangulation (tessellation) is performed using the UV topology.
        from bl_math import clamp, lerp
        aspect = isl.umesh.aspect
        new_center = isl.value.copy()

        transform_acc = Matrix.Identity(2)
        scale_acc = Vector((1.0, 1.0))

        flat_3d_coords = np.array([(pt_a.to_tuple(), pt_b.to_tuple(), pt_c.to_tuple()) for pt_a, pt_b, pt_c in isl.flat_3d_coords], dtype=np.float32)
        vec_ac = flat_3d_coords[:, 0] - flat_3d_coords[:, 2]
        vec_bc = flat_3d_coords[:, 1] - flat_3d_coords[:, 2]

        flat_uv_coords = np.array([(pt_a.to_tuple(), pt_b.to_tuple(), pt_c.to_tuple()) for pt_a, pt_b, pt_c in isl.flat_coords], dtype=np.float32)
        weights = np.array(list(isl.weights) if isinstance(isl.weights, itertools.chain) else isl.weights, dtype=np.float32)

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
            if shear:
                cou_n = cou / utils.np_vec_normalized(cou)
                cov_n = cov / utils.np_vec_normalized(cov)
                scale_cross = np.sum(utils.np_vec_dot(cou_n, cov_n) * w)

            if scale_cou * scale_cov < 1e-10:
                break

            scale_factor_u = sqrt(scale_cou / scale_cov / aspect)
            if axis != 'XY':
                scale_factor_u **= 2

            tolerance = 1e-5  # Trade accuracy for performance.
            if shear:
                t = Matrix.Identity(2)
                t[0][0] = scale_factor_u
                t[1][0] = clamp((scale_cross / isl.area_3d) * aspect, -0.5 * aspect, 0.5 * aspect)
                t[0][1] = 0
                t[1][1] = 1 / scale_factor_u

                if axis == 'X':
                    t[1][1] = 1
                    temp = t[0][1]
                    t[0][1] = t[1][0]
                    t[1][0] = temp

                elif axis == 'Y':
                    t[0][0] = 1

                err = abs(t[0][0] - 1.0) + abs(t[1][0]) + abs(t[0][1]) + abs(t[1][1] - 1.0)
                if err < tolerance:
                    break

                # Transform
                transform_acc @= t
                flat_uv_coords = flat_uv_coords @ np.array(t, dtype=np.float32)
            else:
                if math.isclose(scale_factor_u, 1.0, abs_tol=tolerance):
                    break
                scale = Vector((scale_factor_u, 1.0/scale_factor_u))
                if axis == 'X':
                    scale.y = 1
                elif axis == 'Y':
                    scale.x = 1

                scale_acc *= scale
                flat_uv_coords *= np.array(scale, dtype=np.float32)

        if shear:
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

    def normalize(self, islands, tot_area_uv, tot_area_3d):
        """
        Normalize islands based on total UV and 3D areas.
        Based on UniV's normalize() method.
        """
        if not self.xy_scale and len(islands) <= 1:
            self.report({'WARNING'}, f"Islands should be more than 1, given {len(islands)} islands")
            return
        if tot_area_3d == 0.0 or tot_area_uv == 0.0:
            # Prevent divide by zero.
            self.report({'WARNING'}, f"Cannot normalize islands, total {'UV-area' if tot_area_3d else '3D-area'} of faces is zero")
            return

        tot_fac = tot_area_3d / tot_area_uv

        zero_area_islands = []
        for isl in islands:
            if math.isclose(isl.area_3d, 0.0, abs_tol=1e-6) or math.isclose(isl.area_uv, 0.0, abs_tol=1e-6):
                zero_area_islands.append(isl)
                continue

            fac = isl.area_3d / isl.area_uv
            scale = math.sqrt(fac / tot_fac)

            if self.xy_scale or self.shear:
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

            self.report({'WARNING'}, f"Found {len(zero_area_islands)} islands with zero area")

    def avg_by_frequencies(self, all_islands):
        """
        Calculate average areas by frequency analysis.
        Based on UniV's avg_by_frequencies() method.
        """
        areas_uv = np.empty(len(all_islands), dtype=float)
        areas_3d = np.empty(len(all_islands), dtype=float)

        for idx, isl in enumerate(all_islands):
            areas_uv[idx] = isl.calc_area_uv()
            areas_3d[idx] = isl.area_3d

        areas = areas_uv if self.bl_idname.startswith('UV') else areas_3d
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
            idx = self.np_find_nearest(areas, idx_for_find)
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

class UVV_OT_ResetScale_VIEW3D(UVV_OT_ResetScale):
    bl_idname = "mesh.uvv_reset_scale"

classes = [
    UVV_OT_ResetScale_VIEW3D,  # Child must be registered BEFORE parent
    UVV_OT_ResetScale,
]
