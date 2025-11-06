"""Pack preset management operators for UVV addon"""

import bpy
from bpy.types import Operator
from ..properties import get_uvv_settings


class UVV_OT_SavePackPreset(Operator):
    """Save current pack settings to the selected preset"""
    bl_idname = "uv.uvv_save_pack_preset"
    bl_label = "Save Pack Preset"
    bl_description = "Save current pack settings to preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = get_uvv_settings()
        presets = context.scene.uvv_pack_presets
        index = context.scene.uvv_pack_presets_index

        if index < 0 or index >= len(presets):
            self.report({'WARNING'}, "No preset selected")
            return {'CANCELLED'}

        preset = presets[index]

        # Copy current settings to preset
        preset.use_uvpm = settings.use_uvpm
        preset.shape_method = settings.shape_method
        preset.scale = settings.scale
        preset.rotate = settings.rotate
        preset.normalize_islands = settings.normalize_islands
        preset.rotate_method = settings.rotate_method
        preset.pin = settings.pin
        preset.pin_method = settings.pin_method
        preset.merge_overlap = settings.merge_overlap
        preset.udim_source = settings.udim_source
        preset.padding = settings.padding
        preset.pack_enable_stacking = settings.pack_enable_stacking
        preset.pack_use_stack_groups = settings.pack_use_stack_groups

        self.report({'INFO'}, f"Preset '{preset.name}' saved")
        return {'FINISHED'}


class UVV_OT_AddPackPreset(Operator):
    """Add a new pack preset"""
    bl_idname = "uv.uvv_add_pack_preset"
    bl_label = "Add Pack Preset"
    bl_description = "Add a new pack preset with default name 'New Preset'"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = get_uvv_settings()
        presets = context.scene.uvv_pack_presets

        # Create new preset with current settings
        preset = presets.add()
        preset.name = "New Preset"

        # Copy current settings
        preset.use_uvpm = settings.use_uvpm
        preset.shape_method = settings.shape_method
        preset.scale = settings.scale
        preset.rotate = settings.rotate
        preset.normalize_islands = settings.normalize_islands
        preset.rotate_method = settings.rotate_method
        preset.pin = settings.pin
        preset.pin_method = settings.pin_method
        preset.merge_overlap = settings.merge_overlap
        preset.udim_source = settings.udim_source
        preset.padding = settings.padding
        preset.pack_enable_stacking = settings.pack_enable_stacking
        preset.pack_use_stack_groups = settings.pack_use_stack_groups

        # Set active index to new preset
        context.scene.uvv_pack_presets_index = len(presets) - 1

        self.report({'INFO'}, f"Preset '{preset.name}' added - rename and save it")
        return {'FINISHED'}


class UVV_OT_DeletePackPreset(Operator):
    """Delete the selected pack preset"""
    bl_idname = "uv.uvv_delete_pack_preset"
    bl_label = "Delete Pack Preset"
    bl_description = "Delete the currently selected preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        presets = context.scene.uvv_pack_presets
        index = context.scene.uvv_pack_presets_index

        if index < 0 or index >= len(presets):
            self.report({'WARNING'}, "No preset selected")
            return {'CANCELLED'}

        preset_name = presets[index].name
        presets.remove(index)

        # Update index
        if index > 0:
            context.scene.uvv_pack_presets_index = index - 1
        elif len(presets) > 0:
            context.scene.uvv_pack_presets_index = 0
        else:
            context.scene.uvv_pack_presets_index = -1

        self.report({'INFO'}, f"Preset '{preset_name}' deleted")
        return {'FINISHED'}


class UVV_OT_ResetPackPresets(Operator):
    """Reset all pack presets to defaults"""
    bl_idname = "uv.uvv_reset_pack_presets"
    bl_label = "Reset Pack Presets"
    bl_description = "Delete all presets and recreate default presets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        presets = context.scene.uvv_pack_presets

        # Clear all existing presets
        presets.clear()

        # Recreate defaults
        # Preset 1: Fast (native Blender)
        preset = presets.add()
        preset.name = "Fast"
        preset.use_uvpm = False
        preset.shape_method = 'AABB'
        preset.scale = True
        preset.rotate = True
        preset.normalize_islands = False
        preset.rotate_method = 'CARDINAL'
        preset.pin = False
        preset.merge_overlap = False
        preset.udim_source = 'CLOSEST_UDIM'
        preset.padding = 4

        # Preset 2: Accurate (native Blender)
        preset = presets.add()
        preset.name = "Accurate"
        preset.use_uvpm = False
        preset.shape_method = 'CONCAVE'
        preset.scale = True
        preset.rotate = True
        preset.normalize_islands = True  # Enable normalize for Accurate
        preset.rotate_method = 'CARDINAL'
        preset.pin = False
        preset.merge_overlap = False
        preset.udim_source = 'CLOSEST_UDIM'
        preset.padding = 4

        # Preset 3: UVPM Fast
        preset = presets.add()
        preset.name = "UVPM Fast"
        preset.use_uvpm = True
        preset.shape_method = 'AABB'
        preset.scale = True
        preset.rotate = True
        preset.normalize_islands = True
        preset.rotate_method = 'CARDINAL'
        preset.pin = False
        preset.merge_overlap = False
        preset.udim_source = 'CLOSEST_UDIM'
        preset.padding = 4
        preset.pack_enable_stacking = True
        preset.pack_use_stack_groups = True

        # Preset 4: UVPM Accurate
        preset = presets.add()
        preset.name = "UVPM Accurate"
        preset.use_uvpm = True
        preset.shape_method = 'CONCAVE'
        preset.scale = True
        preset.rotate = True
        preset.normalize_islands = True
        preset.rotate_method = 'ANY'
        preset.pin = False
        preset.merge_overlap = False
        preset.udim_source = 'CLOSEST_UDIM'
        preset.padding = 4
        preset.pack_enable_stacking = True
        preset.pack_use_stack_groups = True

        # Check if UVPM is installed and auto-select UVPM Fast preset
        if hasattr(context.scene, 'uvpm3_props'):
            # Find UVPM Fast preset index
            for i, p in enumerate(presets):
                if p.name == "UVPM Fast":
                    context.scene.uvv_pack_presets_index = i
                    break
            else:
                # Fallback to first preset if UVPM Fast not found
                context.scene.uvv_pack_presets_index = 0
        else:
            # Set active index to first preset if UVPM not installed
            context.scene.uvv_pack_presets_index = 0

        self.report({'INFO'}, "Pack presets reset to defaults")
        return {'FINISHED'}


class UVV_OT_ApplyPackPreset(Operator):
    """Apply the selected pack preset to current settings"""
    bl_idname = "uv.uvv_apply_pack_preset"
    bl_label = "Apply Pack Preset"
    bl_description = "Apply preset to current pack settings"
    bl_options = {'REGISTER', 'UNDO'}

    preset_index: bpy.props.IntProperty(
        name="Preset Index",
        description="Index of preset to apply",
        default=-1
    )

    def execute(self, context):
        settings = get_uvv_settings()
        presets = context.scene.uvv_pack_presets

        # Use provided index or fall back to scene index
        index = self.preset_index if self.preset_index >= 0 else context.scene.uvv_pack_presets_index

        if index < 0 or index >= len(presets):
            self.report({'WARNING'}, "No preset selected")
            return {'CANCELLED'}

        preset = presets[index]

        # Update active index
        context.scene.uvv_pack_presets_index = index

        # Apply preset to current settings
        settings.use_uvpm = preset.use_uvpm
        settings.shape_method = preset.shape_method
        settings.scale = preset.scale
        settings.rotate = preset.rotate
        settings.normalize_islands = preset.normalize_islands
        settings.rotate_method = preset.rotate_method
        settings.pin = preset.pin
        settings.pin_method = preset.pin_method
        settings.merge_overlap = preset.merge_overlap
        settings.udim_source = preset.udim_source
        settings.padding = preset.padding
        settings.pack_enable_stacking = preset.pack_enable_stacking
        settings.pack_use_stack_groups = preset.pack_use_stack_groups

        # Set heuristic search based on preset name for UVPM presets
        if preset.use_uvpm and hasattr(context.scene, 'uvpm3_props'):
            uvpm_scene_props = context.scene.uvpm3_props
            uvpm_main_props = uvpm_scene_props.default_main_props if hasattr(uvpm_scene_props, 'default_main_props') else uvpm_scene_props
            try:
                # UVPM Fast: heuristic disabled, UVPM Accurate: heuristic enabled
                if preset.name == "UVPM Fast":
                    uvpm_main_props.heuristic_enable = False
                elif preset.name == "UVPM Accurate":
                    uvpm_main_props.heuristic_enable = True
            except Exception:
                pass

        self.report({'INFO'}, f"Applied preset '{preset.name}'")
        return {'FINISHED'}


class UVV_OT_ApplyPackPresetFast(Operator):
    """Apply Fast pack preset"""
    bl_idname = "uv.uvv_apply_pack_preset_fast"
    bl_label = "Fast"
    bl_description = "Apply Fast pack preset (native Blender, AABB, cardinal rotation)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = get_uvv_settings()
        
        # Apply Fast preset settings
        settings.use_uvpm = False
        settings.shape_method = 'AABB'
        settings.scale = True
        settings.rotate = True
        settings.normalize_islands = False
        settings.rotate_method = 'CARDINAL'
        settings.pin = False
        settings.merge_overlap = False
        settings.udim_source = 'CLOSEST_UDIM'
        settings.padding = 4
        
        # Execute pack operation
        bpy.ops.uv.uvv_pack()
        
        self.report({'INFO'}, "Applied Fast pack preset")
        return {'FINISHED'}


class UVV_OT_ApplyPackPresetAccurate(Operator):
    """Apply Accurate pack preset"""
    bl_idname = "uv.uvv_apply_pack_preset_accurate"
    bl_label = "Accurate"
    bl_description = "Apply Accurate pack preset (native Blender, concave, normalize islands)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = get_uvv_settings()
        
        # Apply Accurate preset settings
        settings.use_uvpm = False
        settings.shape_method = 'CONCAVE'
        settings.scale = True
        settings.rotate = True
        settings.normalize_islands = True
        settings.rotate_method = 'CARDINAL'
        settings.pin = False
        settings.merge_overlap = False
        settings.udim_source = 'CLOSEST_UDIM'
        settings.padding = 4
        
        # Execute pack operation
        bpy.ops.uv.uvv_pack()
        
        self.report({'INFO'}, "Applied Accurate pack preset")
        return {'FINISHED'}


class UVV_OT_ApplyPackPresetUVMasterFast(Operator):
    """Apply UVPM Fast pack preset"""
    bl_idname = "uv.uvv_apply_pack_preset_uvmaster_fast"
    bl_label = "UVPM Fast"
    bl_description = "Apply UVPM Fast pack preset (UVPM, AABB, cardinal rotation)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = get_uvv_settings()
        
        # Apply UVPM Fast preset settings
        settings.use_uvpm = True
        settings.shape_method = 'AABB'
        settings.scale = True
        settings.rotate = True
        settings.normalize_islands = True
        settings.rotate_method = 'CARDINAL'
        settings.pin = False
        settings.merge_overlap = False
        settings.udim_source = 'CLOSEST_UDIM'
        settings.padding = 4
        settings.pack_enable_stacking = True
        settings.pack_use_stack_groups = True
        
        # Set heuristic search to disabled for UVPM Fast
        if hasattr(context.scene, 'uvpm3_props'):
            uvpm_scene_props = context.scene.uvpm3_props
            uvpm_main_props = uvpm_scene_props.default_main_props if hasattr(uvpm_scene_props, 'default_main_props') else uvpm_scene_props
            try:
                uvpm_main_props.heuristic_enable = False
            except Exception:
                pass
        
        # Execute pack operation
        bpy.ops.uv.uvv_pack()
        
        self.report({'INFO'}, "Applied UVPM Fast pack preset")
        return {'FINISHED'}


class UVV_OT_ApplyPackPresetUVMasterAccurate(Operator):
    """Apply UVPM Accurate pack preset"""
    bl_idname = "uv.uvv_apply_pack_preset_uvmaster_accurate"
    bl_label = "UVPM Accurate"
    bl_description = "Apply UVPM Accurate pack preset (UVPM, concave, any rotation)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = get_uvv_settings()
        
        # Apply UVPM Accurate preset settings
        settings.use_uvpm = True
        settings.shape_method = 'CONCAVE'
        settings.scale = True
        settings.rotate = True
        settings.normalize_islands = True
        settings.rotate_method = 'ANY'
        settings.pin = False
        settings.merge_overlap = False
        settings.udim_source = 'CLOSEST_UDIM'
        settings.padding = 4
        settings.pack_enable_stacking = True
        settings.pack_use_stack_groups = True
        
        # Set heuristic search to enabled for UVPM Accurate
        if hasattr(context.scene, 'uvpm3_props'):
            uvpm_scene_props = context.scene.uvpm3_props
            uvpm_main_props = uvpm_scene_props.default_main_props if hasattr(uvpm_scene_props, 'default_main_props') else uvpm_scene_props
            try:
                uvpm_main_props.heuristic_enable = True
            except Exception:
                pass
        
        # Execute pack operation
        bpy.ops.uv.uvv_pack()
        
        self.report({'INFO'}, "Applied UVPM Accurate pack preset")
        return {'FINISHED'}


classes = [
    UVV_OT_SavePackPreset,
    UVV_OT_AddPackPreset,
    UVV_OT_DeletePackPreset,
    UVV_OT_ResetPackPresets,
    UVV_OT_ApplyPackPreset,
    UVV_OT_ApplyPackPresetFast,
    UVV_OT_ApplyPackPresetAccurate,
    UVV_OT_ApplyPackPresetUVMasterFast,
    UVV_OT_ApplyPackPresetUVMasterAccurate,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
