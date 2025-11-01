"""Trimsheet workspace tool with gizmo rendering"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from bpy.types import GizmoGroup, Gizmo, WorkSpaceTool
from ..utils import trimsheet_utils


# Get appropriate shader for Blender version
if not bpy.app.background:
    if bpy.app.version < (3, 4, 0):
        shader_2d_uniform = gpu.shader.from_builtin('UNIFORM_COLOR')
        shader_line = shader_2d_uniform
    else:
        shader_2d_uniform = gpu.shader.from_builtin('UNIFORM_COLOR')
        if bpy.app.version < (3, 5, 0):
            shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        else:
            shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')


class UVV_GT_trim_rect(Gizmo):
    """Gizmo for rendering a single trim rectangle"""
    bl_idname = "UVV_GT_trim_rect"

    __slots__ = (
        'custom_shape',
        'custom_shape_border',
        'custom_shape_handles',
        'trim_index',
        'is_active',
        'is_selected',
    )

    def _update_shape(self, trim):
        """Update shape geometry based on trim bounds"""
        left, right = trim.left, trim.right
        bottom, top = trim.bottom, trim.top

        # Rectangle vertices (two triangles)
        verts = [
            (left, bottom), (right, bottom), (right, top),
            (right, top), (left, top), (left, bottom)
        ]

        self.custom_shape = self.new_custom_shape('TRIS', verts)

        # Border line loop
        border_verts = [(left, bottom), (right, bottom), (right, top), (left, top)]
        self.custom_shape_border = batch_for_shader(
            shader_line, 'LINE_LOOP', {"pos": border_verts}
        )

        # Corner handles (small squares)
        handle_size = 0.01
        handle_verts = []

        # Bottom-left handle
        handle_verts.extend([
            (left - handle_size, bottom - handle_size),
            (left + handle_size, bottom - handle_size),
            (left + handle_size, bottom + handle_size),
            (left + handle_size, bottom + handle_size),
            (left - handle_size, bottom + handle_size),
            (left - handle_size, bottom - handle_size),
        ])

        # Bottom-right handle
        handle_verts.extend([
            (right - handle_size, bottom - handle_size),
            (right + handle_size, bottom - handle_size),
            (right + handle_size, bottom + handle_size),
            (right + handle_size, bottom + handle_size),
            (right - handle_size, bottom + handle_size),
            (right - handle_size, bottom - handle_size),
        ])

        # Top-right handle
        handle_verts.extend([
            (right - handle_size, top - handle_size),
            (right + handle_size, top - handle_size),
            (right + handle_size, top + handle_size),
            (right + handle_size, top + handle_size),
            (right - handle_size, top + handle_size),
            (right - handle_size, top - handle_size),
        ])

        # Top-left handle
        handle_verts.extend([
            (left - handle_size, top - handle_size),
            (left + handle_size, top - handle_size),
            (left + handle_size, top + handle_size),
            (left + handle_size, top + handle_size),
            (left - handle_size, top + handle_size),
            (left - handle_size, top - handle_size),
        ])

        self.custom_shape_handles = batch_for_shader(
            shader_2d_uniform, 'TRIS', {"pos": handle_verts}
        )

    def draw(self, context):
        """Draw the trim rectangle"""
        try:
            material = trimsheet_utils.get_active_material(context)
            if not material or not hasattr(material, 'uvv_trims'):
                return

            if self.trim_index < 0 or self.trim_index >= len(material.uvv_trims):
                return

            trim = material.uvv_trims[self.trim_index]

            # Update shape if needed
            if not hasattr(self, 'custom_shape') or self.custom_shape is None:
                self._update_shape(trim)

            # Determine if active/selected
            self.is_active = (material.uvv_trims_index == self.trim_index)
            self.is_selected = trim.selected

            # Draw filled rectangle
            fill_alpha = 0.15 if not self.is_active else 0.3
            self.color = (*trim.color, fill_alpha)
            self.color_highlight = (*trim.color, fill_alpha * 1.5)

            if hasattr(self, 'custom_shape') and self.custom_shape:
                self.draw_custom_shape(self.custom_shape)

            # Draw border
            gpu.state.blend_set('ALPHA')

            # Determine border color
            if self.is_active:
                border_color = (1.0, 0.5, 0.0, 1.0)  # Orange for active
                line_width = 2.0
            elif self.is_selected:
                border_color = (0.2, 0.5, 1.0, 1.0)  # Blue for selected
                line_width = 1.5
            else:
                border_color = (*trim.color, 0.8)  # Trim color for normal
                line_width = 1.0

            shader_line.bind()

            # Set line width for modern Blender versions
            if bpy.app.version >= (3, 4, 0):
                region = context.region
                shader_line.uniform_float('viewportSize', (region.width, region.height))
                shader_line.uniform_float('lineWidth', line_width)

            shader_line.uniform_float('color', border_color)

            if hasattr(self, 'custom_shape_border') and self.custom_shape_border:
                self.custom_shape_border.draw(shader_line)

            # Draw corner handles ONLY in edit mode
            settings = context.scene.uvv_settings
            if self.is_active and settings.trim_edit_mode and hasattr(self, 'custom_shape_handles') and self.custom_shape_handles:
                shader_2d_uniform.bind()
                shader_2d_uniform.uniform_float('color', (1.0, 1.0, 1.0, 1.0))  # White handles
                self.custom_shape_handles.draw(shader_2d_uniform)

            gpu.state.blend_set('NONE')
        except Exception as e:
            # Silently fail to avoid console spam
            pass

    def draw_select(self, context, select_id):
        """Draw for selection"""
        self.draw(context)

    def test_select(self, context, location):
        """Test if location is inside this trim"""
        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index >= len(material.uvv_trims):
            return -1

        trim = material.uvv_trims[self.trim_index]

        if trimsheet_utils.point_in_rect(location, trim.left, trim.top, trim.right, trim.bottom):
            return 0
        return -1

    def setup(self):
        """Initialize gizmo"""
        self.trim_index = -1
        self.is_active = False
        self.is_selected = False


class UVV_GT_trim_move(Gizmo):
    """Gizmo for moving trim (entire rectangle area)"""
    bl_idname = "UVV_GT_trim_move"
    bl_target_properties = (
        {"id": "offset", "type": 'FLOAT', "array_length": 2},
    )

    __slots__ = (
        'trim_index',
        'init_bounds',
        'init_mouse_uv',
    )

    def draw(self, context):
        """Draw semi-transparent rectangle for moving"""
        self._do_draw(context)

    def draw_select(self, context, select_id):
        """Draw for selection"""
        self._do_draw(context, select_id=select_id)

    def _do_draw(self, context, select_id=None):
        """Internal draw method"""
        import gpu
        from gpu_extras.batch import batch_for_shader

        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index >= len(material.uvv_trims):
            return

        trim = material.uvv_trims[self.trim_index]

        # Get region coordinates
        region = context.region
        rv2d = region.view2d

        # Convert trim bounds to region coordinates
        left_rgn = rv2d.view_to_region(trim.left, trim.bottom, clip=False)
        right_rgn = rv2d.view_to_region(trim.right, trim.top, clip=False)

        # Create rectangle vertices in region space
        verts = [
            (left_rgn[0], left_rgn[1]),
            (right_rgn[0], left_rgn[1]),
            (right_rgn[0], right_rgn[1]),
            (left_rgn[0], left_rgn[1]),
            (right_rgn[0], right_rgn[1]),
            (left_rgn[0], right_rgn[1]),
        ]

        # Create shader
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'TRIS', {"pos": verts})

        # Set color
        if select_id is None:
            # Normal drawing - semi-transparent
            if self.is_highlight:
                color = (0.5, 0.7, 1.0, 0.3)  # Blue when hovering
            else:
                color = (0.3, 0.3, 0.3, 0.1)  # Gray normally
        else:
            # Selection drawing - use select_id
            color = (1.0, 1.0, 1.0, 1.0)

        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')

    def test_select(self, context, location):
        """Test if location is inside the trim"""
        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index >= len(material.uvv_trims):
            return -1

        trim = material.uvv_trims[self.trim_index]

        if trimsheet_utils.point_in_rect(location, trim.left, trim.top, trim.right, trim.bottom):
            return 0
        return -1

    def invoke(self, context, event):
        """Start moving"""
        material = trimsheet_utils.get_active_material(context)
        if material and self.trim_index < len(material.uvv_trims):
            trim = material.uvv_trims[self.trim_index]
            self.init_bounds = (trim.left, trim.right, trim.top, trim.bottom)
            region = context.region
            rv2d = region.view2d
            self.init_mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        """Handle moving"""
        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index >= len(material.uvv_trims):
            return {'CANCELLED'}

        trim = material.uvv_trims[self.trim_index]

        # Get mouse position in UV space
        region = context.region
        rv2d = region.view2d
        mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

        # Calculate delta
        delta = mouse_uv - self.init_mouse_uv

        # Move trim
        width = self.init_bounds[1] - self.init_bounds[0]
        height = self.init_bounds[2] - self.init_bounds[3]

        trim.left = self.init_bounds[0] + delta.x
        trim.right = trim.left + width
        trim.top = self.init_bounds[2] + delta.y
        trim.bottom = trim.top - height

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        """Finish moving"""
        if cancel:
            material = trimsheet_utils.get_active_material(context)
            if material and self.trim_index < len(material.uvv_trims):
                trim = material.uvv_trims[self.trim_index]
                trim.left, trim.right, trim.top, trim.bottom = self.init_bounds
                context.area.tag_redraw()

    def setup(self):
        """Initialize"""
        self.trim_index = -1
        self.init_bounds = None
        self.init_mouse_uv = None


class UVV_GT_trim_handle(Gizmo):
    """Gizmo for a corner handle"""
    bl_idname = "UVV_GT_trim_handle"
    bl_target_properties = (
        {"id": "offset", "type": 'FLOAT', "array_length": 2},
    )

    __slots__ = (
        'custom_shape',
        'trim_index',
        'corner',  # 'bottom_left', 'bottom_right', 'top_right', 'top_left'
    )

    def _update_shape(self, trim):
        """Update handle shape"""
        handle_size = 0.02  # Increased size for better visibility
        left, right = trim.left, trim.right
        bottom, top = trim.bottom, trim.top

        # Determine corner position
        if self.corner == 'bottom_left':
            x, y = left, bottom
        elif self.corner == 'bottom_right':
            x, y = right, bottom
        elif self.corner == 'top_right':
            x, y = right, top
        elif self.corner == 'top_left':
            x, y = left, top
        else:
            x, y = 0, 0

        # Handle vertices
        verts = [
            (x - handle_size, y - handle_size),
            (x + handle_size, y - handle_size),
            (x + handle_size, y + handle_size),
            (x + handle_size, y + handle_size),
            (x - handle_size, y + handle_size),
            (x - handle_size, y - handle_size),
        ]

        self.custom_shape = self.new_custom_shape('TRIS', verts)

    def draw(self, context):
        """Draw the handle"""
        try:
            material = trimsheet_utils.get_active_material(context)
            if not material or self.trim_index >= len(material.uvv_trims):
                return

            trim = material.uvv_trims[self.trim_index]

            # Update shape if needed
            if not hasattr(self, 'custom_shape') or self.custom_shape is None:
                self._update_shape(trim)

            # Draw handle
            self.color = (1.0, 1.0, 1.0, 1.0)  # White
            self.color_highlight = (1.0, 0.5, 0.0, 1.0)  # Orange on hover

            if hasattr(self, 'custom_shape') and self.custom_shape:
                self.draw_custom_shape(self.custom_shape)
        except:
            pass

    def test_select(self, context, location):
        """Test if location is inside this handle"""
        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index >= len(material.uvv_trims):
            return -1

        trim = material.uvv_trims[self.trim_index]

        handle_size = 0.02  # Match the visual size
        left, right = trim.left, trim.right
        bottom, top = trim.bottom, trim.top

        # Determine corner position
        if self.corner == 'bottom_left':
            x, y = left, bottom
        elif self.corner == 'bottom_right':
            x, y = right, bottom
        elif self.corner == 'top_right':
            x, y = right, top
        elif self.corner == 'top_left':
            x, y = left, top
        else:
            return -1

        # Check if location is inside handle
        if (x - handle_size <= location[0] <= x + handle_size and
            y - handle_size <= location[1] <= y + handle_size):
            return 0
        return -1

    def invoke(self, context, event):
        """Start dragging handle"""
        self.init_mouse_x = event.mouse_x
        self.init_mouse_y = event.mouse_y

        material = trimsheet_utils.get_active_material(context)
        if material and self.trim_index < len(material.uvv_trims):
            trim = material.uvv_trims[self.trim_index]
            self.init_bounds = (trim.left, trim.right, trim.top, trim.bottom)

        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        """Handle dragging"""
        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index >= len(material.uvv_trims):
            return {'CANCELLED'}

        trim = material.uvv_trims[self.trim_index]

        # Get mouse position in UV space
        region = context.region
        rv2d = region.view2d
        mouse_uv = Vector(rv2d.region_to_view(event.mouse_region_x, event.mouse_region_y))

        # Update bounds based on corner
        if self.corner == 'bottom_left':
            trim.left = mouse_uv.x
            trim.bottom = mouse_uv.y
        elif self.corner == 'bottom_right':
            trim.right = mouse_uv.x
            trim.bottom = mouse_uv.y
        elif self.corner == 'top_right':
            trim.right = mouse_uv.x
            trim.top = mouse_uv.y
        elif self.corner == 'top_left':
            trim.left = mouse_uv.x
            trim.top = mouse_uv.y

        # Update shape
        self._update_shape(trim)
        context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        """Finish dragging"""
        if cancel:
            material = trimsheet_utils.get_active_material(context)
            if material and self.trim_index < len(material.uvv_trims):
                trim = material.uvv_trims[self.trim_index]
                trim.left, trim.right, trim.top, trim.bottom = self.init_bounds
                context.area.tag_redraw()

    def draw(self, context):
        """Draw the handle"""
        self._do_draw(context)

    def draw_select(self, context, select_id):
        """Draw for selection"""
        self._do_draw(context, select_id=select_id)

    def _do_draw(self, context, select_id=None):
        """Internal draw method"""
        import gpu
        from gpu_extras.batch import batch_for_shader

        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index >= len(material.uvv_trims):
            return

        trim = material.uvv_trims[self.trim_index]

        # Get region coordinates
        region = context.region
        rv2d = region.view2d

        # Determine corner position in UV space
        if self.corner == 'bottom_left':
            uv_pos = (trim.left, trim.bottom)
        elif self.corner == 'bottom_right':
            uv_pos = (trim.right, trim.bottom)
        elif self.corner == 'top_right':
            uv_pos = (trim.right, trim.top)
        elif self.corner == 'top_left':
            uv_pos = (trim.left, trim.top)
        else:
            return

        # Convert to region coordinates
        rgn_pos = rv2d.view_to_region(uv_pos[0], uv_pos[1], clip=False)

        # Handle size in pixels
        handle_size = 8

        # Create square handle vertices in region space
        verts = [
            (rgn_pos[0] - handle_size, rgn_pos[1] - handle_size),
            (rgn_pos[0] + handle_size, rgn_pos[1] - handle_size),
            (rgn_pos[0] + handle_size, rgn_pos[1] + handle_size),
            (rgn_pos[0] - handle_size, rgn_pos[1] - handle_size),
            (rgn_pos[0] + handle_size, rgn_pos[1] + handle_size),
            (rgn_pos[0] - handle_size, rgn_pos[1] + handle_size),
        ]

        # Create shader
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'TRIS', {"pos": verts})

        # Set color
        if select_id is None:
            # Normal drawing
            if self.is_highlight:
                color = (1.0, 0.5, 0.0, 1.0)  # Orange on hover
            else:
                color = (1.0, 1.0, 1.0, 1.0)  # White
        else:
            # Selection drawing
            color = (1.0, 1.0, 1.0, 1.0)

        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')

    def test_select(self, context, location):
        """Test if location is inside this handle"""
        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index >= len(material.uvv_trims):
            return -1

        trim = material.uvv_trims[self.trim_index]

        # Determine corner position
        if self.corner == 'bottom_left':
            x, y = trim.left, trim.bottom
        elif self.corner == 'bottom_right':
            x, y = trim.right, trim.bottom
        elif self.corner == 'top_right':
            x, y = trim.right, trim.top
        elif self.corner == 'top_left':
            x, y = trim.left, trim.top
        else:
            return -1

        # Handle size in UV space (approximate based on view)
        region = context.region
        rv2d = region.view2d

        # Convert 8 pixels to UV space
        rgn_pos = rv2d.view_to_region(x, y, clip=False)
        test_pos1 = rv2d.region_to_view(rgn_pos[0] - 8, rgn_pos[1] - 8)
        test_pos2 = rv2d.region_to_view(rgn_pos[0] + 8, rgn_pos[1] + 8)

        handle_size_x = abs(test_pos2[0] - test_pos1[0]) / 2
        handle_size_y = abs(test_pos2[1] - test_pos1[1]) / 2

        # Check if location is inside handle
        if (x - handle_size_x <= location[0] <= x + handle_size_x and
            y - handle_size_y <= location[1] <= y + handle_size_y):
            return 0
        return -1

    def setup(self):
        """Initialize handle"""
        self.trim_index = -1
        self.corner = 'bottom_left'


class UVV_GGT_trimsheet(GizmoGroup):
    """Gizmo group for managing all trim rectangles"""
    bl_idname = "UVV_GGT_trimsheet"
    bl_label = "Trimsheet Gizmos"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context):
        """Only show in UV editor with material and trims, and NOT in edit mode"""
        if not (context.space_data and context.space_data.type == 'IMAGE_EDITOR'):
            return False

        # Don't show gizmos in edit mode (draw handler takes over)
        settings = context.scene.uvv_settings
        if settings.trim_edit_mode:
            return False

        material = context.active_object.active_material if context.active_object else None
        if not material or not hasattr(material, 'uvv_trims'):
            return False

        # Show if there are any trims
        return len(material.uvv_trims) > 0

    def setup(self, context):
        """Setup gizmos"""
        self.trim_gizmos = []
        self.handle_gizmos = []
        self.move_gizmo = None

    def refresh(self, context):
        """Refresh gizmos based on current trims"""
        try:
            material = trimsheet_utils.get_active_material(context)
            if not material or not hasattr(material, 'uvv_trims'):
                # Clear all gizmos
                if hasattr(self, 'trim_gizmos'):
                    self.trim_gizmos.clear()
                if hasattr(self, 'handle_gizmos'):
                    self.handle_gizmos.clear()
                return

            trims = material.uvv_trims
            trim_count = len(trims)

            # Initialize gizmo lists if needed
            if not hasattr(self, 'trim_gizmos'):
                self.trim_gizmos = []
            if not hasattr(self, 'handle_gizmos'):
                self.handle_gizmos = []

            # Adjust trim gizmo count to match trim count
            while len(self.trim_gizmos) < trim_count:
                gz = self.gizmos.new(UVV_GT_trim_rect.bl_idname)
                gz.use_draw_scale = False
                gz.use_draw_modal = True
                gz.trim_index = len(self.trim_gizmos)
                self.trim_gizmos.append(gz)

            while len(self.trim_gizmos) > trim_count:
                # Remove excess gizmos
                self.trim_gizmos.pop()

            # Update all trim gizmos
            for i, gz in enumerate(self.trim_gizmos):
                if i < len(trims):
                    gz.trim_index = i
                    gz._update_shape(trims[i])

            # Create move and scale gizmos for active trim when edit mode is enabled
            settings = context.scene.uvv_settings
            active_index = material.uvv_trims_index

            if settings.trim_edit_mode and active_index >= 0 and active_index < trim_count:
                # Create move gizmo if needed
                if self.move_gizmo is None:
                    self.move_gizmo = self.gizmos.new(UVV_GT_trim_move.bl_idname)
                    self.move_gizmo.use_draw_scale = False
                    self.move_gizmo.use_draw_modal = True

                # Update move gizmo
                self.move_gizmo.trim_index = active_index
                # Move gizmo doesn't need _update_shape - it doesn't draw custom shapes

                # Need 4 corner handles per active trim
                corner_names = ['bottom_left', 'bottom_right', 'top_right', 'top_left']

                # Create handles if needed
                while len(self.handle_gizmos) < 4:
                    gz = self.gizmos.new(UVV_GT_trim_handle.bl_idname)
                    gz.use_draw_scale = False
                    gz.use_draw_modal = True
                    gz.corner = corner_names[len(self.handle_gizmos)]
                    self.handle_gizmos.append(gz)

                # Update handles for active trim
                for gz in self.handle_gizmos:
                    gz.trim_index = active_index
                    gz._update_shape(trims[active_index])
            else:
                # Clear gizmos if edit mode disabled or no active trim
                self.move_gizmo = None
                self.handle_gizmos.clear()

        except Exception as e:
            import traceback
            traceback.print_exc()

    def draw_prepare(self, context):
        """Prepare drawing - refresh gizmos if needed"""
        self.refresh(context)

    def invoke_prepare(self, context, gizmo):
        """Prepare for interaction"""
        return True


# Workspace tool definition
class UVV_WorkspaceTool_Trimsheet(WorkSpaceTool):
    bl_space_type = 'IMAGE_EDITOR'
    bl_context_mode = 'UV'
    bl_idname = "uvv.trimsheet_tool"
    bl_label = "Trimsheet"
    bl_description = "Create and manage trimsheet rectangles"
    bl_icon = "ops.mesh.primitive_plane_add_gizmo"  # Placeholder icon
    bl_widget = UVV_GGT_trimsheet.bl_idname
    bl_keymap = (
        # Modal operator that handles both create and edit modes
        ("uv.uvv_trimsheet_tool_modal", {"type": 'LEFTMOUSE', "value": 'PRESS'}, {}),
    )


classes = [
    UVV_GT_trim_rect,
    UVV_GT_trim_move,
    UVV_GT_trim_handle,
    UVV_GGT_trimsheet,
]


def register():
    """Register gizmo classes only"""
    for cls in classes:
        bpy.utils.register_class(cls)


def register_tool():
    """Register workspace tool - called separately"""
    try:
        bpy.utils.register_tool(UVV_WorkspaceTool_Trimsheet, after={"builtin.select_box"}, separator=True, group=False)
    except Exception as e:
        pass


def unregister_tool():
    """Unregister workspace tool - called separately"""
    try:
        bpy.utils.unregister_tool(UVV_WorkspaceTool_Trimsheet)
    except Exception as e:
        pass


def unregister():
    """Unregister gizmo classes only"""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
