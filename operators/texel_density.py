"""Texel Density operators for UVV addon - UNIV-based implementation"""

import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, EnumProperty, IntProperty
from ..properties import get_uvv_settings
from ..types import UMeshes, AdvIslands, UnionIslands
from .. import utils
from ..utils.uv_face_utils import calc_uv_faces
from math import sqrt, isclose
import bl_math


class UVV_OT_TexelDensityGet(Operator):
    """Get texel density from selected UV faces"""
    bl_idname = "uv.uvv_texel_density_get"
    bl_label = "Get"
    bl_description = "Get texel density from selected faces"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (obj := context.active_object) and obj.type == 'MESH'

    def execute(self, context):
        settings = get_uvv_settings()
        texture_size = (int(settings.texture_size_x) + int(settings.texture_size_y)) / 2.0

        umeshes = UMeshes(report=self.report)

        # Check if in edit mode
        cancel = False
        if umeshes.is_edit_mode:
            selected_umeshes, unselected_umeshes = umeshes.filtered_by_selected_and_visible_uv_faces()
            if selected_umeshes:
                has_selected = True
                umeshes = selected_umeshes
            elif unselected_umeshes:
                has_selected = False
                umeshes = unselected_umeshes
            else:
                cancel = True
        else:
            if not umeshes:
                cancel = True
            else:
                has_selected = False

        if cancel:
            self.report({'WARNING'}, 'Faces not found')
            return {'CANCELLED'}

        total_3d_area = 0.0
        total_uv_area = 0.0

        for umesh in umeshes:
            if umeshes.is_edit_mode:
                faces = calc_uv_faces(umesh, selected=has_selected)
            else:
                faces = umesh.bm.faces
            scale = umesh.check_uniform_scale(self.report)
            total_3d_area += utils.calc_total_area_3d(faces, scale)
            total_uv_area += utils.calc_total_area_uv(faces, umesh.uv)

        umeshes.free()

        area_3d = sqrt(total_3d_area)
        area_uv = sqrt(total_uv_area) * texture_size

        if isclose(area_3d, 0.0, abs_tol=1e-6) or isclose(area_uv, 0.0, abs_tol=1e-6):
            self.report({'WARNING'}, "All faces have zero area")
            return {'CANCELLED'}

        texel = area_uv / area_3d
        settings.texel_density = bl_math.clamp(texel, 1.0, 10000.0)

        self.report({'INFO'}, f"Texel density: {texel:.2f}")
        return {'FINISHED'}


class UVV_OT_TexelDensitySet(Operator):
    """Set texel density for selected UV faces"""
    bl_idname = "uv.uvv_texel_density_set"
    bl_label = "Set"
    bl_description = "Set texel density for selected faces\n\n" \
                     "Default - Set TD\n" \
                     "Shift - Lock Overlaps\n" \
                     "Shift+Alt - Union (scale all islands together)"
    bl_options = {'REGISTER', 'UNDO'}

    grouping_type: EnumProperty(
        name='Grouping Type',
        default='NONE',
        items=(
            ('NONE', 'None', 'Set TD for each island independently'),
            ('OVERLAP', 'Overlap', 'Lock overlapping islands together'),
            ('UNION', 'Union', 'Scale all islands as one group')
        )
    )

    lock_overlap_mode: EnumProperty(
        name='Lock Overlaps Mode',
        default='ANY',
        items=(
            ('ANY', 'Any', 'Any overlap'),
            ('EXACT', 'Exact', 'Exact overlap only')
        )
    )

    threshold: FloatProperty(
        name='Distance',
        default=0.001,
        min=0.0,
        soft_min=0.00005,
        soft_max=0.00999
    )

    custom_density: FloatProperty(
        name="Custom Density",
        description="Custom texel density value (use -1 for settings value)",
        default=-1.0,
        min=-1.0,
        max=10000.0
    )

    @classmethod
    def poll(cls, context):
        return (obj := context.active_object) and obj.type == 'MESH'

    def invoke(self, context, event):
        if event.value == 'PRESS':
            return self.execute(context)
        if event.shift:
            self.grouping_type = 'UNION' if event.alt else 'OVERLAP'
        else:
            self.grouping_type = 'NONE'
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        if self.grouping_type == 'OVERLAP':
            if self.lock_overlap_mode == 'EXACT':
                layout.prop(self, 'threshold', slider=True)
            layout.row().prop(self, 'lock_overlap_mode', expand=True)
        layout.row(align=True).prop(self, 'grouping_type', expand=True)

    def execute(self, context):
        settings = get_uvv_settings()

        # Determine target density
        if self.custom_density > 0:
            target_td = self.custom_density
        else:
            target_td = settings.texel_density

        texture_size = (int(settings.texture_size_x) + int(settings.texture_size_y)) / 2.0

        umeshes = UMeshes(report=self.report)

        cancel = False
        if not umeshes.is_edit_mode:
            if not umeshes:
                cancel = True
            else:
                has_selected = False
                islands_calc_type = AdvIslands.calc_with_hidden_with_mark_seam
                umeshes.ensure(True)
        else:
            selected_umeshes, unselected_umeshes = umeshes.filtered_by_selected_and_visible_uv_faces()
            if selected_umeshes:
                has_selected = True
                umeshes = selected_umeshes
                islands_calc_type = AdvIslands.calc_extended_with_mark_seam
            elif unselected_umeshes:
                has_selected = False
                umeshes = unselected_umeshes
                islands_calc_type = AdvIslands.calc_visible_with_mark_seam
            else:
                cancel = True

        if cancel:
            self.report({'WARNING'}, 'Islands not found')
            return {'CANCELLED'}

        all_islands = []
        selected_islands_of_mesh = []
        zero_area_islands = []
        umeshes.update_tag = False

        for umesh in umeshes:
            if adv_islands := islands_calc_type(umesh):
                umesh.value = umesh.check_uniform_scale(report=self.report)

                if self.grouping_type != 'NONE':
                    adv_islands.calc_tris()
                    adv_islands.calc_flat_uv_coords(save_triplet=True)
                    all_islands.extend(adv_islands)

                # Calculate areas for each island individually
                for isl in adv_islands:
                    isl.calc_area_uv()
                    isl.calc_area_3d(scale=umesh.value)

                if self.grouping_type == 'NONE':
                    for isl in adv_islands:
                        if (status := isl.set_texel(target_td, texture_size)) is None:
                            zero_area_islands.append(isl)
                            continue
                        umesh.update_tag |= status

                if has_selected:
                    selected_islands_of_mesh.append(adv_islands)

        if self.grouping_type != 'NONE':
            if self.grouping_type == 'OVERLAP':
                threshold = None if self.lock_overlap_mode == 'ANY' else self.threshold
                groups_of_islands = UnionIslands.calc_overlapped_island_groups(all_islands, threshold)
                for isl in groups_of_islands:
                    if (status := isl.set_texel(target_td, texture_size)) is None:
                        zero_area_islands.append(isl)
                        continue
                    isl.umesh.update_tag |= status
            else:
                union_islands = UnionIslands(all_islands)
                status = union_islands.set_texel(target_td, texture_size)
                union_islands.umesh.update_tag = status in (True, None)

                for u_isl in union_islands:
                    area_3d = sqrt(u_isl.area_3d)
                    area_uv = sqrt(u_isl.area_uv) * texture_size
                    if isclose(area_3d, 0.0, abs_tol=1e-6) or isclose(area_uv, 0.0, abs_tol=1e-6):
                        zero_area_islands.append(union_islands)

        if zero_area_islands:
            self.report({'WARNING'}, f"Found {len(zero_area_islands)} islands with zero area")
            if umeshes.is_edit_mode:
                for islands in selected_islands_of_mesh:
                    for isl in islands:
                        isl.select = False
                for isl in zero_area_islands:
                    isl.select = True
            umeshes.update_tag = True
            umeshes.silent_update()
            if not umeshes.is_edit_mode:
                umeshes.free()
                utils.update_area_by_type('VIEW_3D')
            return {'FINISHED'}

        if not umeshes.is_edit_mode:
            umeshes.update(info=f'Texel density set to {target_td:.2f}')
            umeshes.free()
            if umeshes.update_tag:
                utils.update_area_by_type('VIEW_3D')
            return {'FINISHED'}

        umeshes.update(info=f'Texel density set to {target_td:.2f}')
        return {'FINISHED'}


class UVV_OT_SetTexelPreset(Operator):
    """Set texel density from preset value"""
    bl_idname = "uv.uvv_set_texel_preset"
    bl_label = "Set Texel Preset"
    bl_description = "Set texel density to preset value"
    bl_options = {'REGISTER', 'UNDO'}

    preset_value: FloatProperty(
        name="Preset Value",
        description="Texel density preset value",
        default=512.0,
        min=1.0,
        max=10000.0
    )

    def execute(self, context):
        settings = get_uvv_settings()
        settings.texel_density = self.preset_value

        self.report({'INFO'}, f"Texel density set to {self.preset_value:.0f}")
        return {'FINISHED'}


class UVV_OT_TexelDensityMultiply(Operator):
    """Multiply current texel density by 2"""
    bl_idname = "uv.uvv_texel_density_multiply"
    bl_label = "Multiply Texel Density"
    bl_description = "Multiply current texel density by 2"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = get_uvv_settings()
        new_value = settings.texel_density * 2.0
        settings.texel_density = min(new_value, 10000.0)  # Cap at max value

        self.report({'INFO'}, f"Texel density multiplied: {settings.texel_density:.0f}")
        return {'FINISHED'}


class UVV_OT_TexelDensityDivide(Operator):
    """Divide current texel density by 2"""
    bl_idname = "uv.uvv_texel_density_divide"
    bl_label = "Divide Texel Density"
    bl_description = "Divide current texel density by 2"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = get_uvv_settings()
        new_value = settings.texel_density / 2.0
        settings.texel_density = max(new_value, 1.0)  # Cap at min value

        self.report({'INFO'}, f"Texel density divided: {settings.texel_density:.0f}")
        return {'FINISHED'}


classes = [
    UVV_OT_TexelDensityGet,
    UVV_OT_TexelDensitySet,
    UVV_OT_SetTexelPreset,
    UVV_OT_TexelDensityMultiply,
    UVV_OT_TexelDensityDivide,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
