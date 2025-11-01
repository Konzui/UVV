"""Operator for creating trimsheet rectangles"""

import bpy
from bpy.types import Operator
from ..utils import trimsheet_utils


class UVV_OT_trim_create(Operator):
    """Create a new trim rectangle in the center of UV space"""
    bl_idname = "uv.uvv_trim_create"
    bl_label = "Create Trim"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Only available in UV editor with an active material"""
        if not (context.area and context.area.type == 'IMAGE_EDITOR'):
            return False
        if not (context.active_object and context.active_object.active_material):
            return False
        return True

    def execute(self, context):
        """Create a trim in the center of UV space"""
        material = trimsheet_utils.get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material")
            return {'CANCELLED'}

        # Create a new trim
        material.uvv_trims.add()
        new_trim = material.uvv_trims[-1]

        # Initialize trim properties
        trim_count = len([t for t in material.uvv_trims if t.name.startswith("Trim")])
        new_trim.name = f"Trim.{trim_count:03d}"
        new_trim.color = trimsheet_utils.generate_trim_color(material.uvv_trims)

        # Create trim in center with default size (0.25 x 0.25)
        center_x = 0.5
        center_y = 0.5
        half_width = 0.125
        half_height = 0.125

        new_trim.set_rect(
            center_x - half_width,  # left
            center_y + half_height,  # top
            center_x + half_width,   # right
            center_y - half_height   # bottom
        )

        # Deselect all other trims and select the new one
        trimsheet_utils.deselect_all_trims(material)
        new_trim.selected = True

        # Make it the active trim
        material.uvv_trims_index = len(material.uvv_trims) - 1

        # Automatically enable edit mode if not already enabled
        settings = context.scene.uvv_settings
        if not settings.trim_edit_mode:
            settings.trim_edit_mode = True
            # Start the tool modal
            from .trimsheet_tool_modal import UVV_OT_trimsheet_tool_modal
            if not UVV_OT_trimsheet_tool_modal._is_running:
                bpy.ops.uv.uvv_trimsheet_tool_modal('INVOKE_DEFAULT')

        # Redraw
        context.area.tag_redraw()

        self.report({'INFO'}, f"Created trim '{new_trim.name}'")
        return {'FINISHED'}


classes = [
    UVV_OT_trim_create,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
