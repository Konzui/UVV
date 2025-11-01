"""Modal operators for trimsheet transform in edit mode"""

import bpy
from bpy.types import Operator
from mathutils import Vector
from ..utils import trimsheet_utils
from ..utils import trim_snapping


class UVV_OT_trim_edit_move(Operator):
    """Move trim by dragging (Figma-style)"""
    bl_idname = "uv.uvv_trim_edit_move"
    bl_label = "Move Trim"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    @classmethod
    def poll(cls, context):
        if context.space_data.type != 'IMAGE_EDITOR':
            return False
        settings = context.scene.uvv_settings
        if not settings.trim_edit_mode:
            return False
        material = trimsheet_utils.get_active_material(context)
        if not material or not hasattr(material, 'uvv_trims'):
            return False
        return material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims)

    def invoke(self, context, event):
        material = trimsheet_utils.get_active_material(context)
        if not material or material.uvv_trims_index < 0:
            return {'CANCELLED'}

        self.trim = material.uvv_trims[material.uvv_trims_index]
        self.material = material

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

            # Calculate new positions
            new_left = self.original_left + delta.x
            new_right = self.original_right + delta.x
            new_top = self.original_top + delta.y
            new_bottom = self.original_bottom + delta.y

            # Apply snapping unless CTRL is pressed
            if not event.ctrl:
                # Snap left edge
                snapped_left = trim_snapping.find_snap_target_vertical(
                    self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                )
                # Snap bottom edge
                snapped_bottom = trim_snapping.find_snap_target_horizontal(
                    self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                )

                # Calculate snap offset
                snap_offset_x = snapped_left - new_left
                snap_offset_y = snapped_bottom - new_bottom

                # Apply snap offset to all edges
                self.trim.left = new_left + snap_offset_x
                self.trim.right = new_right + snap_offset_x
                self.trim.top = new_top + snap_offset_y
                self.trim.bottom = new_bottom + snap_offset_y
            else:
                # No snapping - apply delta directly
                self.trim.left = new_left
                self.trim.right = new_right
                self.trim.top = new_top
                self.trim.bottom = new_bottom

            # Redraw
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
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


class UVV_OT_trim_edit_scale_corner(Operator):
    """Scale trim from a corner (Figma-style). Hold Alt to scale from center"""
    bl_idname = "uv.uvv_trim_edit_scale_corner"
    bl_label = "Scale Trim Corner"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    corner: bpy.props.StringProperty(default='bottom_left')

    @classmethod
    def poll(cls, context):
        if context.space_data.type != 'IMAGE_EDITOR':
            return False
        settings = context.scene.uvv_settings
        if not settings.trim_edit_mode:
            return False
        material = trimsheet_utils.get_active_material(context)
        if not material or not hasattr(material, 'uvv_trims'):
            return False
        return material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims)

    def invoke(self, context, event):
        material = trimsheet_utils.get_active_material(context)
        if not material or material.uvv_trims_index < 0:
            return {'CANCELLED'}

        self.trim = material.uvv_trims[material.uvv_trims_index]
        self.material = material

        # Store original bounds and center
        self.original_left = self.trim.left
        self.original_right = self.trim.right
        self.original_top = self.trim.top
        self.original_bottom = self.trim.bottom
        self.original_center_x = (self.original_left + self.original_right) / 2
        self.original_center_y = (self.original_bottom + self.original_top) / 2

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Get mouse position in UV space
            region = context.region
            rv2d = region.view2d
            mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

            # Check if Alt is pressed for symmetric scaling from center
            is_symmetric = event.alt
            # Check if Ctrl is pressed to disable snapping
            snap_enabled = not event.ctrl

            if is_symmetric:
                # Scale from center - mirror all changes to opposite corner
                if self.corner == 'bottom_left':
                    # Dragging bottom-left, mirror to top-right
                    new_left = min(mouse_uv.x, self.original_center_x - 0.001)
                    new_bottom = min(mouse_uv.y, self.original_center_y - 0.001)
                    if snap_enabled:
                        new_left = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_bottom = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )
                        new_left = min(new_left, self.original_center_x - 0.001)
                        new_bottom = min(new_bottom, self.original_center_y - 0.001)
                    offset_x = self.original_center_x - new_left
                    offset_y = self.original_center_y - new_bottom
                    self.trim.left = new_left
                    self.trim.bottom = new_bottom
                    self.trim.right = self.original_center_x + offset_x
                    self.trim.top = self.original_center_y + offset_y

                elif self.corner == 'bottom_right':
                    # Dragging bottom-right, mirror to top-left
                    new_right = max(mouse_uv.x, self.original_center_x + 0.001)
                    new_bottom = min(mouse_uv.y, self.original_center_y - 0.001)
                    if snap_enabled:
                        new_right = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_bottom = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )
                        new_right = max(new_right, self.original_center_x + 0.001)
                        new_bottom = min(new_bottom, self.original_center_y - 0.001)
                    offset_x = new_right - self.original_center_x
                    offset_y = self.original_center_y - new_bottom
                    self.trim.right = new_right
                    self.trim.bottom = new_bottom
                    self.trim.left = self.original_center_x - offset_x
                    self.trim.top = self.original_center_y + offset_y

                elif self.corner == 'top_right':
                    # Dragging top-right, mirror to bottom-left
                    new_right = max(mouse_uv.x, self.original_center_x + 0.001)
                    new_top = max(mouse_uv.y, self.original_center_y + 0.001)
                    if snap_enabled:
                        new_right = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_top = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )
                        new_right = max(new_right, self.original_center_x + 0.001)
                        new_top = max(new_top, self.original_center_y + 0.001)
                    offset_x = new_right - self.original_center_x
                    offset_y = new_top - self.original_center_y
                    self.trim.right = new_right
                    self.trim.top = new_top
                    self.trim.left = self.original_center_x - offset_x
                    self.trim.bottom = self.original_center_y - offset_y

                elif self.corner == 'top_left':
                    # Dragging top-left, mirror to bottom-right
                    new_left = min(mouse_uv.x, self.original_center_x - 0.001)
                    new_top = max(mouse_uv.y, self.original_center_y + 0.001)
                    if snap_enabled:
                        new_left = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_top = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )
                        new_left = min(new_left, self.original_center_x - 0.001)
                        new_top = max(new_top, self.original_center_y + 0.001)
                    offset_x = self.original_center_x - new_left
                    offset_y = new_top - self.original_center_y
                    self.trim.left = new_left
                    self.trim.top = new_top
                    self.trim.right = self.original_center_x + offset_x
                    self.trim.bottom = self.original_center_y - offset_y
            else:
                # Normal corner scaling - drag one corner
                if self.corner == 'bottom_left':
                    new_left = min(mouse_uv.x, self.original_right - 0.001)
                    new_bottom = min(mouse_uv.y, self.original_top - 0.001)
                    if snap_enabled:
                        new_left = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_bottom = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )
                    self.trim.left = min(new_left, self.original_right - 0.001)
                    self.trim.bottom = min(new_bottom, self.original_top - 0.001)
                elif self.corner == 'bottom_right':
                    new_right = max(mouse_uv.x, self.original_left + 0.001)
                    new_bottom = min(mouse_uv.y, self.original_top - 0.001)
                    if snap_enabled:
                        new_right = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_bottom = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )
                    self.trim.right = max(new_right, self.original_left + 0.001)
                    self.trim.bottom = min(new_bottom, self.original_top - 0.001)
                elif self.corner == 'top_right':
                    new_right = max(mouse_uv.x, self.original_left + 0.001)
                    new_top = max(mouse_uv.y, self.original_bottom + 0.001)
                    if snap_enabled:
                        new_right = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_top = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )
                    self.trim.right = max(new_right, self.original_left + 0.001)
                    self.trim.top = max(new_top, self.original_bottom + 0.001)
                elif self.corner == 'top_left':
                    new_left = min(mouse_uv.x, self.original_right - 0.001)
                    new_top = max(mouse_uv.y, self.original_bottom + 0.001)
                    if snap_enabled:
                        new_left = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_top = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )
                    self.trim.left = min(new_left, self.original_right - 0.001)
                    self.trim.top = max(new_top, self.original_bottom + 0.001)

            # Redraw
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
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


class UVV_OT_trim_edit_scale_edge(Operator):
    """Scale trim from an edge (Figma-style). Hold Alt for symmetric scaling"""
    bl_idname = "uv.uvv_trim_edit_scale_edge"
    bl_label = "Scale Trim Edge"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    edge: bpy.props.StringProperty(default='left')

    @classmethod
    def poll(cls, context):
        if context.space_data.type != 'IMAGE_EDITOR':
            return False
        settings = context.scene.uvv_settings
        if not settings.trim_edit_mode:
            return False
        material = trimsheet_utils.get_active_material(context)
        if not material or not hasattr(material, 'uvv_trims'):
            return False
        return material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims)

    def invoke(self, context, event):
        material = trimsheet_utils.get_active_material(context)
        if not material or material.uvv_trims_index < 0:
            return {'CANCELLED'}

        self.trim = material.uvv_trims[material.uvv_trims_index]
        self.material = material

        # Store original bounds and center
        self.original_left = self.trim.left
        self.original_right = self.trim.right
        self.original_top = self.trim.top
        self.original_bottom = self.trim.bottom
        self.original_center_x = (self.original_left + self.original_right) / 2
        self.original_center_y = (self.original_bottom + self.original_top) / 2

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Get mouse position in UV space
            region = context.region
            rv2d = region.view2d
            mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

            # Check if Alt is pressed for symmetric scaling
            is_symmetric = event.alt
            # Check if Ctrl is pressed to disable snapping
            snap_enabled = not event.ctrl

            if is_symmetric:
                # Symmetric scaling: scale both sides from center
                if self.edge == 'left':
                    # Scale left, mirror to right
                    new_left = min(mouse_uv.x, self.original_center_x - 0.001)
                    if snap_enabled:
                        new_left = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_left = min(new_left, self.original_center_x - 0.001)
                    offset = self.original_center_x - new_left
                    self.trim.left = new_left
                    self.trim.right = self.original_center_x + offset
                elif self.edge == 'right':
                    # Scale right, mirror to left
                    new_right = max(mouse_uv.x, self.original_center_x + 0.001)
                    if snap_enabled:
                        new_right = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_right = max(new_right, self.original_center_x + 0.001)
                    offset = new_right - self.original_center_x
                    self.trim.right = new_right
                    self.trim.left = self.original_center_x - offset
                elif self.edge == 'top':
                    # Scale top, mirror to bottom
                    new_top = max(mouse_uv.y, self.original_center_y + 0.001)
                    if snap_enabled:
                        new_top = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )
                        new_top = max(new_top, self.original_center_y + 0.001)
                    offset = new_top - self.original_center_y
                    self.trim.top = new_top
                    self.trim.bottom = self.original_center_y - offset
                elif self.edge == 'bottom':
                    # Scale bottom, mirror to top
                    new_bottom = min(mouse_uv.y, self.original_center_y - 0.001)
                    if snap_enabled:
                        new_bottom = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )
                        new_bottom = min(new_bottom, self.original_center_y - 0.001)
                    offset = self.original_center_y - new_bottom
                    self.trim.bottom = new_bottom
                    self.trim.top = self.original_center_y + offset
            else:
                # Normal single-edge scaling
                if self.edge == 'left':
                    new_left = min(mouse_uv.x, self.original_right - 0.001)
                    if snap_enabled:
                        new_left = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                    self.trim.left = min(new_left, self.original_right - 0.001)
                elif self.edge == 'right':
                    new_right = max(mouse_uv.x, self.original_left + 0.001)
                    if snap_enabled:
                        new_right = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                    self.trim.right = max(new_right, self.original_left + 0.001)
                elif self.edge == 'top':
                    new_top = max(mouse_uv.y, self.original_bottom + 0.001)
                    if snap_enabled:
                        new_top = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )
                    self.trim.top = max(new_top, self.original_bottom + 0.001)
                elif self.edge == 'bottom':
                    new_bottom = min(mouse_uv.y, self.original_top - 0.001)
                    if snap_enabled:
                        new_bottom = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )
                    self.trim.bottom = min(new_bottom, self.original_top - 0.001)

            # Redraw
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
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


class UVV_OT_trim_edit_transform(Operator):
    """Main transform tool that routes to specific modal operators based on click position"""
    bl_idname = "uv.uvv_trim_edit_transform"
    bl_label = "Transform Trim"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.space_data.type != 'IMAGE_EDITOR':
            return False
        settings = context.scene.uvv_settings
        if not settings.trim_edit_mode:
            return False
        material = trimsheet_utils.get_active_material(context)
        if not material or not hasattr(material, 'uvv_trims'):
            return False
        return material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims)

    def invoke(self, context, event):
        from ..utils.trimsheet_transform_draw import get_handle_type_at_position

        material = trimsheet_utils.get_active_material(context)
        if not material or material.uvv_trims_index < 0:
            return {'CANCELLED'}

        trim = material.uvv_trims[material.uvv_trims_index]

        # Determine what was clicked
        handle_type, handle_id = get_handle_type_at_position(
            context, trim, event.mouse_region_x, event.mouse_region_y
        )

        if not handle_type:
            return {'CANCELLED'}

        # Route to appropriate operator
        if handle_type == 'corner':
            bpy.ops.uv.uvv_trim_edit_scale_corner('INVOKE_DEFAULT', corner=handle_id)
        elif handle_type == 'edge':
            bpy.ops.uv.uvv_trim_edit_scale_edge('INVOKE_DEFAULT', edge=handle_id)
        elif handle_type == 'center':
            bpy.ops.uv.uvv_trim_edit_move('INVOKE_DEFAULT')

        return {'FINISHED'}


classes = [
    UVV_OT_trim_edit_move,
    UVV_OT_trim_edit_scale_corner,
    UVV_OT_trim_edit_scale_edge,
    UVV_OT_trim_edit_transform,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
