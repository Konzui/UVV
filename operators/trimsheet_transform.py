"""Trimsheet transform operators for moving trims with modal interaction"""

import bpy
from bpy.types import Operator
from mathutils import Vector
from ..utils import trimsheet_utils


class UVV_OT_trim_move_modal(Operator):
    """Move selected trim with mouse (G key)"""
    bl_idname = "uv.uvv_trim_move_modal"
    bl_label = "Move Trim"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    @classmethod
    def poll(cls, context):
        if context.space_data.type != 'IMAGE_EDITOR':
            return False
        material = context.active_object.active_material if context.active_object else None
        if not material or len(material.uvv_trims) == 0:
            return False
        return material.uvv_trims_index >= 0

    def invoke(self, context, event):
        material = trimsheet_utils.get_active_material(context)
        if not material or material.uvv_trims_index < 0:
            return {'CANCELLED'}

        self.trim = material.uvv_trims[material.uvv_trims_index]

        # Store original bounds
        self.original_left = self.trim.left
        self.original_right = self.trim.right
        self.original_top = self.trim.top
        self.original_bottom = self.trim.bottom

        # Get initial mouse position in UV space
        region = context.region
        rv2d = region.view2d
        self.init_mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Calculate mouse delta in UV space
            region = context.region
            rv2d = region.view2d
            current_mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))
            delta = current_mouse_uv - self.init_mouse_uv

            # Apply delta to trim bounds
            self.trim.left = self.original_left + delta.x
            self.trim.right = self.original_right + delta.x
            self.trim.top = self.original_top + delta.y
            self.trim.bottom = self.original_bottom + delta.y

            # Redraw
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # Confirm
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Cancel - restore original bounds
            self.trim.left = self.original_left
            self.trim.right = self.original_right
            self.trim.top = self.original_top
            self.trim.bottom = self.original_bottom
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


class UVV_OT_trim_scale_modal(Operator):
    """Scale selected trim with mouse (S key)"""
    bl_idname = "uv.uvv_trim_scale_modal"
    bl_label = "Scale Trim"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    @classmethod
    def poll(cls, context):
        if context.space_data.type != 'IMAGE_EDITOR':
            return False
        material = context.active_object.active_material if context.active_object else None
        if not material or len(material.uvv_trims) == 0:
            return False
        return material.uvv_trims_index >= 0

    def invoke(self, context, event):
        material = trimsheet_utils.get_active_material(context)
        if not material or material.uvv_trims_index < 0:
            return {'CANCELLED'}

        self.trim = material.uvv_trims[material.uvv_trims_index]

        # Store original bounds and center
        self.original_left = self.trim.left
        self.original_right = self.trim.right
        self.original_top = self.trim.top
        self.original_bottom = self.trim.bottom

        self.center_x = (self.trim.left + self.trim.right) / 2.0
        self.center_y = (self.trim.top + self.trim.bottom) / 2.0

        # Get initial mouse position
        self.init_mouse_x = event.mouse_region_x

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Calculate scale factor based on mouse movement
            delta_x = event.mouse_region_x - self.init_mouse_x
            scale = 1.0 + (delta_x * 0.01)  # 0.01 = sensitivity
            scale = max(0.01, scale)  # Minimum scale

            # Calculate original size from center
            orig_width = (self.original_right - self.original_left) / 2.0
            orig_height = (self.original_top - self.original_bottom) / 2.0

            # Apply scale from center
            self.trim.left = self.center_x - (orig_width * scale)
            self.trim.right = self.center_x + (orig_width * scale)
            self.trim.top = self.center_y + (orig_height * scale)
            self.trim.bottom = self.center_y - (orig_height * scale)

            # Redraw
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # Confirm
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Cancel - restore original bounds
            self.trim.left = self.original_left
            self.trim.right = self.original_right
            self.trim.top = self.original_top
            self.trim.bottom = self.original_bottom
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


classes = [
    UVV_OT_trim_move_modal,
    UVV_OT_trim_scale_modal,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
