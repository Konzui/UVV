# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

"""
UVV Texel Density Operators (ZenUV compatibility)
"""

import bpy
from mathutils import Color


class UVV_OT_TD_ManualUpdate(bpy.types.Operator):
    """Manually update texel density visualization"""
    bl_idname = "uv.uvv_td_manual_update"
    bl_label = "Update TD Visualization"
    bl_description = "Manually rebuild texel density visualization (use when auto-update is disabled)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Force rebuild by calling update_all_gizmos
        from ..checker.gizmo_draw import update_all_gizmos
        update_all_gizmos(context, force=True)

        # Redraw UV editor
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

        self.report({'INFO'}, "TD visualization updated")
        return {'FINISHED'}


class UVV_OT_TD_AddPreset(bpy.types.Operator):
    """Add current texel density value as a preset"""
    bl_idname = "uv.uvv_td_add_preset"
    bl_label = "Add TD Preset"
    bl_description = "Add current texel density as a preset with custom color"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.uvv_settings
        presets = context.scene.uvv_td_presets

        # Add new preset
        preset = presets.add()
        preset.value = settings.texel_density
        preset.display_color = (0.0, 1.0, 0.0)  # Default green

        # Set as active
        context.scene.uvv_td_presets_index = len(presets) - 1

        self.report({'INFO'}, f"Added TD preset: {preset.value:.1f}")
        return {'FINISHED'}


class UVV_OT_TD_RemovePreset(bpy.types.Operator):
    """Remove selected texel density preset"""
    bl_idname = "uv.uvv_td_remove_preset"
    bl_label = "Remove TD Preset"
    bl_description = "Remove the selected texel density preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        presets = context.scene.uvv_td_presets
        index = context.scene.uvv_td_presets_index

        if 0 <= index < len(presets):
            presets.remove(index)
            # Adjust index
            if index > 0:
                context.scene.uvv_td_presets_index = index - 1
            self.report({'INFO'}, "Removed TD preset")
        else:
            self.report({'WARNING'}, "No preset selected")

        return {'FINISHED'}


class UVV_OT_TD_ApplyPreset(bpy.types.Operator):
    """Apply selected preset TD value to current object"""
    bl_idname = "uv.uvv_td_apply_preset"
    bl_label = "Apply TD Preset"
    bl_description = "Set current texel density to the selected preset value"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.uvv_settings
        presets = context.scene.uvv_td_presets
        index = context.scene.uvv_td_presets_index

        if 0 <= index < len(presets):
            preset = presets[index]
            settings.texel_density = preset.value
            self.report({'INFO'}, f"Applied TD preset: {preset.value:.1f}")
        else:
            self.report({'WARNING'}, "No preset selected")

        return {'FINISHED'}


# Registration
classes = [
    UVV_OT_TD_ManualUpdate,
    UVV_OT_TD_AddPreset,
    UVV_OT_TD_RemovePreset,
    UVV_OT_TD_ApplyPreset,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
