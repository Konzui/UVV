"""Modal operators for trimsheet transform in edit mode"""

import bpy
from bpy.types import Operator
from mathutils import Vector
from ..utils import trimsheet_utils
from ..utils import trim_snapping
from ..utils.trimsheet_transform_draw import set_snap_state


def apply_trim_bounds_with_clamping(context, trim, left, right, top, bottom):
    """Apply trim bounds with optional clamping to 0-1 UV space

    Args:
        context: Blender context
        trim: The trim object to update
        left, right, top, bottom: The new bounds values
    """
    settings = context.scene.uvv_settings

    # If unrestricted placement is disabled, clamp to 0-1
    if not settings.trim_unrestricted_placement:
        left = max(0.0, min(1.0, left))
        right = max(0.0, min(1.0, right))
        top = max(0.0, min(1.0, top))
        bottom = max(0.0, min(1.0, bottom))

    # Apply the bounds
    trim.left = left
    trim.right = right
    trim.top = top
    trim.bottom = bottom


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

        # Check if circular
        self.is_circle = hasattr(self.trim, 'shape_type') and self.trim.shape_type == 'CIRCLE'

        # Always store bounding box bounds (used for both circles and rectangles)
        self.original_left = self.trim.left
        self.original_right = self.trim.right
        self.original_top = self.trim.top
        self.original_bottom = self.trim.bottom

        if self.is_circle:
            # Also store original ellipse data for restoration on cancel
            circle_data = self.trim.get_circle_data()
            if circle_data:
                self.original_center_x, self.original_center_y, self.original_radius_x, self.original_radius_y = circle_data

        # Get initial mouse position in UV space
        region = context.region
        if not region:
            return {'CANCELLED'}
        rv2d = region.view2d
        if not rv2d:
            return {'CANCELLED'}
        self.init_mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Calculate mouse delta in UV space
            region = context.region
            if not region:
                return {'RUNNING_MODAL'}
            rv2d = region.view2d
            if not rv2d:
                return {'RUNNING_MODAL'}
            current_mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))
            delta = current_mouse_uv - self.init_mouse_uv

            # Both circles and rectangles use the SAME movement logic (bounding box)
            # This ensures consistent behavior across all trim shapes

            # Calculate new positions
            new_left = self.original_left + delta.x
            new_right = self.original_right + delta.x
            new_top = self.original_top + delta.y
            new_bottom = self.original_bottom + delta.y

            # Apply snapping unless CTRL is pressed
            if not event.ctrl:
                # Check all four edges for snapping and use the closest one
                # This allows snapping to work when any edge of the trim gets close to another trim

                # Check left edge
                snapped_left, snap_x_left = trim_snapping.find_snap_target_vertical(
                    self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                )
                # Check right edge
                snapped_right, snap_x_right = trim_snapping.find_snap_target_vertical(
                    self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                )
                # Check bottom edge
                snapped_bottom, snap_y_bottom = trim_snapping.find_snap_target_horizontal(
                    self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                )
                # Check top edge
                snapped_top, snap_y_top = trim_snapping.find_snap_target_horizontal(
                    self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                )

                # Choose the snap that's closest (smallest delta)
                snap_offset_x = 0.0
                snap_x = None
                if snap_x_left is not None:
                    left_delta = abs(snapped_left - new_left)
                    right_delta = abs(snapped_right - new_right) if snap_x_right is not None else float('inf')
                    if left_delta <= right_delta:
                        snap_offset_x = snapped_left - new_left
                        snap_x = snap_x_left
                    else:
                        snap_offset_x = snapped_right - new_right
                        snap_x = snap_x_right
                elif snap_x_right is not None:
                    snap_offset_x = snapped_right - new_right
                    snap_x = snap_x_right

                snap_offset_y = 0.0
                snap_y = None
                if snap_y_bottom is not None:
                    bottom_delta = abs(snapped_bottom - new_bottom)
                    top_delta = abs(snapped_top - new_top) if snap_y_top is not None else float('inf')
                    if bottom_delta <= top_delta:
                        snap_offset_y = snapped_bottom - new_bottom
                        snap_y = snap_y_bottom
                    else:
                        snap_offset_y = snapped_top - new_top
                        snap_y = snap_y_top
                elif snap_y_top is not None:
                    snap_offset_y = snapped_top - new_top
                    snap_y = snap_y_top

                # Apply snap offset to all edges (with clamping if needed)
                apply_trim_bounds_with_clamping(
                    context,
                    self.trim,
                    new_left + snap_offset_x,
                    new_right + snap_offset_x,
                    new_top + snap_offset_y,
                    new_bottom + snap_offset_y
                )

                # Set snap state for visual feedback
                set_snap_state(snap_x=snap_x, snap_y=snap_y)
            else:
                # No snapping - apply delta directly (with clamping if needed)
                apply_trim_bounds_with_clamping(
                    context,
                    self.trim,
                    new_left,
                    new_right,
                    new_top,
                    new_bottom
                )
                # Clear snap state
                set_snap_state(snap_x=None, snap_y=None)

            # For circles, the bounding box update will automatically trigger
            # the update callback which syncs center_x, center_y from the bbox
            # (This happens via the property system we set up earlier)

            # Redraw
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # Clear snap state
            set_snap_state(snap_x=None, snap_y=None)
            # Confirm and restart trimsheet modal
            try:
                from .trimsheet_tool_modal import start_trimsheet_modal_if_needed
                start_trimsheet_modal_if_needed(context)
            except:
                pass
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Clear snap state
            set_snap_state(snap_x=None, snap_y=None)
            # Cancel - restore original (no clamping on restore)
            if self.is_circle:
                self.trim.set_circle(self.original_center_x, self.original_center_y, self.original_radius_x, self.original_radius_y)
            else:
                self.trim.left = self.original_left
                self.trim.right = self.original_right
                self.trim.top = self.original_top
                self.trim.bottom = self.original_bottom
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


class UVV_OT_trim_edit_scale_corner(Operator):
    """Scale trim from a corner (Figma-style). Hold Alt to scale from center, Shift to maintain proportions"""
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

        # Store original aspect ratio for proportional scaling (Shift)
        self.original_width = self.original_right - self.original_left
        self.original_height = self.original_top - self.original_bottom
        self.original_aspect = self.original_width / self.original_height if self.original_height > 0 else 1.0

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Get mouse position in UV space
            region = context.region
            if not region:
                return {'RUNNING_MODAL'}
            rv2d = region.view2d
            if not rv2d:
                return {'RUNNING_MODAL'}
            mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

            # Check if Alt is pressed for symmetric scaling from center
            is_symmetric = event.alt
            # Check if Shift is pressed for proportional scaling (maintain aspect ratio)
            is_proportional = event.shift
            # Check if Ctrl is pressed to disable snapping
            snap_enabled = not event.ctrl

            # Track snap state
            current_snap_x = None
            current_snap_y = None

            if is_symmetric:
                # Scale from center - mirror all changes to opposite corner
                if self.corner == 'bottom_left':
                    # Dragging bottom-left, mirror to top-right
                    new_left = min(mouse_uv.x, self.original_center_x - 0.001)
                    new_bottom = min(mouse_uv.y, self.original_center_y - 0.001)
                    if snap_enabled:
                        new_left, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_bottom, current_snap_y = trim_snapping.find_snap_target_horizontal(
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
                        new_right, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_bottom, current_snap_y = trim_snapping.find_snap_target_horizontal(
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
                        new_right, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_top, current_snap_y = trim_snapping.find_snap_target_horizontal(
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
                        new_left, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_top, current_snap_y = trim_snapping.find_snap_target_horizontal(
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
                        new_left, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_bottom, current_snap_y = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )

                    # Apply proportional scaling if Shift is pressed
                    if is_proportional:
                        # Calculate new width and height
                        new_width = self.original_right - new_left
                        new_height = self.original_top - new_bottom
                        # Adjust to maintain aspect ratio (use smaller dimension)
                        if new_width / self.original_aspect < new_height:
                            # Width is limiting factor
                            new_bottom = self.original_top - (new_width / self.original_aspect)
                        else:
                            # Height is limiting factor
                            new_left = self.original_right - (new_height * self.original_aspect)

                    apply_trim_bounds_with_clamping(
                        context,
                        self.trim,
                        min(new_left, self.original_right - 0.001),
                        self.trim.right,
                        self.trim.top,
                        min(new_bottom, self.original_top - 0.001)
                    )
                elif self.corner == 'bottom_right':
                    new_right = max(mouse_uv.x, self.original_left + 0.001)
                    new_bottom = min(mouse_uv.y, self.original_top - 0.001)
                    if snap_enabled:
                        new_right, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_bottom, current_snap_y = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )

                    # Apply proportional scaling if Shift is pressed
                    if is_proportional:
                        # Calculate new width and height
                        new_width = new_right - self.original_left
                        new_height = self.original_top - new_bottom
                        # Adjust to maintain aspect ratio (use smaller dimension)
                        if new_width / self.original_aspect < new_height:
                            # Width is limiting factor
                            new_bottom = self.original_top - (new_width / self.original_aspect)
                        else:
                            # Height is limiting factor
                            new_right = self.original_left + (new_height * self.original_aspect)

                    self.trim.right = max(new_right, self.original_left + 0.001)
                    self.trim.bottom = min(new_bottom, self.original_top - 0.001)
                elif self.corner == 'top_right':
                    new_right = max(mouse_uv.x, self.original_left + 0.001)
                    new_top = max(mouse_uv.y, self.original_bottom + 0.001)
                    if snap_enabled:
                        new_right, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )
                        new_top, current_snap_y = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )

                    # Apply proportional scaling if Shift is pressed
                    if is_proportional:
                        # Calculate new width and height
                        new_width = new_right - self.original_left
                        new_height = new_top - self.original_bottom
                        # Adjust to maintain aspect ratio (use smaller dimension)
                        if new_width / self.original_aspect < new_height:
                            # Width is limiting factor
                            new_top = self.original_bottom + (new_width / self.original_aspect)
                        else:
                            # Height is limiting factor
                            new_right = self.original_left + (new_height * self.original_aspect)

                    self.trim.right = max(new_right, self.original_left + 0.001)
                    self.trim.top = max(new_top, self.original_bottom + 0.001)
                elif self.corner == 'top_left':
                    new_left = min(mouse_uv.x, self.original_right - 0.001)
                    new_top = max(mouse_uv.y, self.original_bottom + 0.001)
                    if snap_enabled:
                        new_left, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )
                        new_top, current_snap_y = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )

                    # Apply proportional scaling if Shift is pressed
                    if is_proportional:
                        # Calculate new width and height
                        new_width = self.original_right - new_left
                        new_height = new_top - self.original_bottom
                        # Adjust to maintain aspect ratio (use smaller dimension)
                        if new_width / self.original_aspect < new_height:
                            # Width is limiting factor
                            new_top = self.original_bottom + (new_width / self.original_aspect)
                        else:
                            # Height is limiting factor
                            new_left = self.original_right - (new_height * self.original_aspect)

                    self.trim.left = min(new_left, self.original_right - 0.001)
                    self.trim.top = max(new_top, self.original_bottom + 0.001)
            
            # Set snap state for visual feedback
            if snap_enabled:
                set_snap_state(snap_x=current_snap_x, snap_y=current_snap_y)
            else:
                set_snap_state(snap_x=None, snap_y=None)

            # Redraw
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # Clear snap state
            set_snap_state(snap_x=None, snap_y=None)
            # Confirm and restart trimsheet modal
            try:
                from .trimsheet_tool_modal import start_trimsheet_modal_if_needed
                start_trimsheet_modal_if_needed(context)
            except:
                pass
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Clear snap state
            set_snap_state(snap_x=None, snap_y=None)
            # Cancel - restore original bounds
            self.trim.left = self.original_left
            self.trim.right = self.original_right
            self.trim.top = self.original_top
            self.trim.bottom = self.original_bottom
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


class UVV_OT_trim_edit_scale_edge(Operator):
    """Scale trim from an edge (Figma-style). Hold Alt for symmetric scaling, Shift to maintain proportions"""
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

        # Store original aspect ratio for proportional scaling (Shift)
        self.original_width = self.original_right - self.original_left
        self.original_height = self.original_top - self.original_bottom
        self.original_aspect = self.original_width / self.original_height if self.original_height > 0 else 1.0

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            # Get mouse position in UV space
            region = context.region
            if not region:
                return {'RUNNING_MODAL'}
            rv2d = region.view2d
            if not rv2d:
                return {'RUNNING_MODAL'}
            mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

            # Check if Alt is pressed for symmetric scaling
            is_symmetric = event.alt
            # Check if Shift is pressed for proportional scaling (maintain aspect ratio)
            is_proportional = event.shift
            # Check if Ctrl is pressed to disable snapping
            snap_enabled = not event.ctrl
            
            # Track snap state
            current_snap_x = None
            current_snap_y = None

            if is_symmetric:
                # Symmetric scaling: scale both sides from center
                if self.edge == 'left':
                    # Scale left, mirror to right
                    new_left = min(mouse_uv.x, self.original_center_x - 0.001)
                    if snap_enabled:
                        new_left, current_snap_x = trim_snapping.find_snap_target_vertical(
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
                        new_right, current_snap_x = trim_snapping.find_snap_target_vertical(
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
                        new_top, current_snap_y = trim_snapping.find_snap_target_horizontal(
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
                        new_bottom, current_snap_y = trim_snapping.find_snap_target_horizontal(
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
                        new_left, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_left, 'left'
                        )

                    # Apply proportional scaling if Shift is pressed
                    if is_proportional:
                        # Calculate new width
                        new_width = self.original_right - new_left
                        # Calculate new height maintaining aspect ratio
                        new_height = new_width / self.original_aspect
                        # Center the height change
                        height_change = new_height - self.original_height
                        self.trim.top = self.original_top + (height_change / 2)
                        self.trim.bottom = self.original_bottom - (height_change / 2)

                    self.trim.left = min(new_left, self.original_right - 0.001)
                elif self.edge == 'right':
                    new_right = max(mouse_uv.x, self.original_left + 0.001)
                    if snap_enabled:
                        new_right, current_snap_x = trim_snapping.find_snap_target_vertical(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_right, 'right'
                        )

                    # Apply proportional scaling if Shift is pressed
                    if is_proportional:
                        # Calculate new width
                        new_width = new_right - self.original_left
                        # Calculate new height maintaining aspect ratio
                        new_height = new_width / self.original_aspect
                        # Center the height change
                        height_change = new_height - self.original_height
                        self.trim.top = self.original_top + (height_change / 2)
                        self.trim.bottom = self.original_bottom - (height_change / 2)

                    self.trim.right = max(new_right, self.original_left + 0.001)
                elif self.edge == 'top':
                    new_top = max(mouse_uv.y, self.original_bottom + 0.001)
                    if snap_enabled:
                        new_top, current_snap_y = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_top, 'top'
                        )

                    # Apply proportional scaling if Shift is pressed
                    if is_proportional:
                        # Calculate new height
                        new_height = new_top - self.original_bottom
                        # Calculate new width maintaining aspect ratio
                        new_width = new_height * self.original_aspect
                        # Center the width change
                        width_change = new_width - self.original_width
                        self.trim.left = self.original_left - (width_change / 2)
                        self.trim.right = self.original_right + (width_change / 2)

                    self.trim.top = max(new_top, self.original_bottom + 0.001)
                elif self.edge == 'bottom':
                    new_bottom = min(mouse_uv.y, self.original_top - 0.001)
                    if snap_enabled:
                        new_bottom, current_snap_y = trim_snapping.find_snap_target_horizontal(
                            self.material.uvv_trims, self.material.uvv_trims_index, new_bottom, 'bottom'
                        )

                    # Apply proportional scaling if Shift is pressed
                    if is_proportional:
                        # Calculate new height
                        new_height = self.original_top - new_bottom
                        # Calculate new width maintaining aspect ratio
                        new_width = new_height * self.original_aspect
                        # Center the width change
                        width_change = new_width - self.original_width
                        self.trim.left = self.original_left - (width_change / 2)
                        self.trim.right = self.original_right + (width_change / 2)

                    self.trim.bottom = min(new_bottom, self.original_top - 0.001)
            
            # Set snap state for visual feedback
            if snap_enabled:
                set_snap_state(snap_x=current_snap_x, snap_y=current_snap_y)
            else:
                set_snap_state(snap_x=None, snap_y=None)

            # Redraw
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # Clear snap state
            set_snap_state(snap_x=None, snap_y=None)
            # Confirm and restart trimsheet modal
            try:
                from .trimsheet_tool_modal import start_trimsheet_modal_if_needed
                start_trimsheet_modal_if_needed(context)
            except:
                pass
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Clear snap state
            set_snap_state(snap_x=None, snap_y=None)
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
        # NOTE: Circles now use the same square handles as rectangles
        # This provides consistent UX across all trim shapes
        if handle_type == 'corner':
            bpy.ops.uv.uvv_trim_edit_scale_corner('INVOKE_DEFAULT', corner=handle_id)
        elif handle_type == 'edge':
            bpy.ops.uv.uvv_trim_edit_scale_edge('INVOKE_DEFAULT', edge=handle_id)
        elif handle_type == 'center':
            bpy.ops.uv.uvv_trim_edit_move('INVOKE_DEFAULT')

        return {'FINISHED'}


class UVV_OT_trim_edit_scale_radius(Operator):
    """Scale circle trim radius by dragging (Figma-style)"""
    bl_idname = "uv.uvv_trim_edit_scale_radius"
    bl_label = "Scale Circle Radius"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    direction: bpy.props.StringProperty(
        name="Direction",
        description="Which radius handle to scale (north, south, east, west)",
        default="east"
    )

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
        if material.uvv_trims_index < 0 or material.uvv_trims_index >= len(material.uvv_trims):
            return False
        # Check if trim is circular
        trim = material.uvv_trims[material.uvv_trims_index]
        return hasattr(trim, 'shape_type') and trim.shape_type == 'CIRCLE'

    def invoke(self, context, event):
        material = trimsheet_utils.get_active_material(context)
        if not material or material.uvv_trims_index < 0:
            return {'CANCELLED'}

        self.trim = material.uvv_trims[material.uvv_trims_index]
        self.material = material

        circle_data = self.trim.get_circle_data()
        if not circle_data:
            return {'CANCELLED'}

        # Store original ellipse data
        self.original_center_x, self.original_center_y, self.original_radius_x, self.original_radius_y = circle_data

        # Get initial mouse position in UV space
        region = context.region
        if not region:
            return {'CANCELLED'}
        rv2d = region.view2d
        if not rv2d:
            return {'CANCELLED'}
        self.init_mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        import math

        if event.type == 'MOUSEMOVE':
            # Calculate mouse position in UV space
            region = context.region
            if not region:
                return {'RUNNING_MODAL'}
            rv2d = region.view2d
            if not rv2d:
                return {'RUNNING_MODAL'}
            current_mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

            # Calculate distance from center to mouse
            dx = current_mouse_uv.x - self.original_center_x
            dy = current_mouse_uv.y - self.original_center_y
            new_radius = math.sqrt(dx * dx + dy * dy)

            # Constrain minimum radius
            new_radius = max(0.001, new_radius)

            # Constrain maximum radius to fit in UV space
            max_radius_x = min(self.original_center_x, 1.0 - self.original_center_x)
            max_radius_y = min(self.original_center_y, 1.0 - self.original_center_y)
            max_radius = min(max_radius_x, max_radius_y)
            new_radius = min(new_radius, max_radius)

            # Update ellipse (set both radii to same value for uniform scaling)
            self.trim.set_circle(self.original_center_x, self.original_center_y, new_radius, new_radius)

            # Redraw
            context.area.tag_redraw()

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # Clear snap state
            set_snap_state(snap_x=None, snap_y=None)
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Cancel - restore original
            self.trim.set_circle(self.original_center_x, self.original_center_y, self.original_radius_x, self.original_radius_y)
            set_snap_state(snap_x=None, snap_y=None)
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


classes = [
    UVV_OT_trim_edit_move,
    UVV_OT_trim_edit_scale_corner,
    UVV_OT_trim_edit_scale_edge,
    UVV_OT_trim_edit_scale_radius,
    UVV_OT_trim_edit_transform,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
