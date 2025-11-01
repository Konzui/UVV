

""" UVV Checker Cleanup Operators """

import bpy
from .checker_labels import UVVCheckerLabels as label


class UVV_OT_CleanupAllCheckers(bpy.types.Operator):
    """Clean up all UV checker artifacts from the entire scene"""
    bl_idname = "uv.uvv_cleanup_all_checkers"
    bl_label = "Clean All Checkers"
    bl_description = "Remove all UV checker artifacts from the entire scene (modifiers, materials, node groups)"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Remove all UV checker artifacts from scene?")
        layout.label(text="This will clean up:")
        layout.label(text="  • All checker modifiers")
        layout.label(text="  • All checker node overrides in materials")
        layout.label(text="  • Checker node groups and materials")

    def execute(self, context):
        removed_modifiers = 0
        removed_overrides = 0
        removed_node_groups = 0
        removed_materials = 0

        # 0. Disable auto mode handler if active
        from .checker_mode_handler import is_checker_auto_mode_active, disable_checker_auto_mode
        if is_checker_auto_mode_active():
            disable_checker_auto_mode(context)

        # 1. Remove all UV Flow style checkers from all objects
        from .uvflow_style_checker import disable_checker_material

        uvflow_checked_objects = [obj for obj in bpy.data.objects
                                  if obj.get('uvv_checker_enabled')]
        if uvflow_checked_objects:
            disable_checker_material(context, uvflow_checked_objects)
            removed_modifiers = len(uvflow_checked_objects)

        # 2. Remove all material-based checker overrides
        from .checker import (
            UVV_GLOBAL_OVERRIDER_NAME,
            UVV_GLOBAL_OVERRIDER_NAME_OLD,
            UVV_OVERRIDER_NAME,
            disable_overrider,
            get_materials_with_overrider
        )

        # Get all materials with overriders
        all_materials = list(bpy.data.materials)
        materials_with_overrider = get_materials_with_overrider(all_materials)

        if materials_with_overrider:
            disable_overrider(context, materials_with_overrider)
            removed_overrides = len(materials_with_overrider)

        # 3. Remove checker node groups
        from .modifier_checker import UVV_CHECKER_GEONODES_NAME
        node_groups_to_remove = [
            UVV_GLOBAL_OVERRIDER_NAME,
            UVV_GLOBAL_OVERRIDER_NAME_OLD,
            UVV_CHECKER_GEONODES_NAME
        ]

        for ng_name in node_groups_to_remove:
            ng = bpy.data.node_groups.get(ng_name)
            if ng:
                bpy.data.node_groups.remove(ng)
                removed_node_groups += 1

        # 4. Remove checker materials
        from .checker import UVV_GENERIC_MAT_NAME, remove_uvv_generic_mats
        from .modifier_checker import UVV_CHECKER_MATERIAL_NAME

        # Remove generic materials
        remove_uvv_generic_mats()

        # Remove modifier checker material
        checker_mat = bpy.data.materials.get(UVV_CHECKER_MATERIAL_NAME)
        if checker_mat:
            bpy.data.materials.remove(checker_mat)
            removed_materials += 1

        # Build report message
        messages = []
        if removed_modifiers > 0:
            messages.append(f"{removed_modifiers} modifier(s)")
        if removed_overrides > 0:
            messages.append(f"{removed_overrides} material override(s)")
        if removed_node_groups > 0:
            messages.append(f"{removed_node_groups} node group(s)")
        if removed_materials > 0:
            messages.append(f"{removed_materials} material(s)")

        if messages:
            self.report({'INFO'}, f"Cleaned up: {', '.join(messages)}")
        else:
            self.report({'INFO'}, "No checker artifacts found")

        # Redraw viewports
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'VIEW_3D', 'IMAGE_EDITOR'}:
                    area.tag_redraw()

        return {'FINISHED'}


class UVV_OT_CleanupModifierCheckers(bpy.types.Operator):
    """Remove all UV Flow style checkers from selected objects"""
    bl_idname = "uv.uvv_cleanup_modifier_checkers"
    bl_label = "Remove UV Flow Checkers"
    bl_description = "Remove UV checker materials from selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects and any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        from .uvflow_style_checker import disable_checker_material

        # Get selected objects with checkers
        checked_objects = [obj for obj in context.selected_objects
                          if obj.get('uvv_checker_enabled')]

        if checked_objects:
            disable_checker_material(context, checked_objects)
            self.report({'INFO'}, f"Removed checker from {len(checked_objects)} object(s)")
        else:
            self.report({'INFO'}, "No checkers found on selected objects")

        # Redraw viewports
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'VIEW_3D', 'IMAGE_EDITOR'}:
                    area.tag_redraw()

        return {'FINISHED'}


class UVV_OT_CleanupMaterialCheckers(bpy.types.Operator):
    """Remove all material-based checker overrides from selected objects"""
    bl_idname = "uv.uvv_cleanup_material_checkers"
    bl_label = "Remove Material Overrides"
    bl_description = "Remove UV checker material overrides from selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects and any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        from .checker import (
            disable_overrider,
            get_materials_with_overrider,
            get_materials_from_objects,
            enshure_material_slots
        )

        # Get materials from selected objects
        materials = []
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                for slot in enshure_material_slots(context, obj):
                    if slot.material:
                        materials.append(slot.material)

        # Get materials with overrider
        materials_with_overrider = get_materials_with_overrider(materials)

        if materials_with_overrider:
            disable_overrider(context, materials_with_overrider)
            self.report({'INFO'}, f"Removed material overrides from {len(materials_with_overrider)} material(s)")
        else:
            self.report({'INFO'}, "No material overrides found on selected objects")

        # Redraw viewports
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'VIEW_3D', 'IMAGE_EDITOR'}:
                    area.tag_redraw()

        return {'FINISHED'}


classes = [
    UVV_OT_CleanupAllCheckers,
    UVV_OT_CleanupModifierCheckers,
    UVV_OT_CleanupMaterialCheckers,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
