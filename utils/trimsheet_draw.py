"""Draw handler for rendering trimsheet rectangles in UV editor"""

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from ..utils import trimsheet_utils
from ..utils.geometry import TextRect


# Get appropriate shader for Blender version
if not bpy.app.background:
    shader_2d_uniform = gpu.shader.from_builtin('UNIFORM_COLOR')
    if bpy.app.version < (3, 5, 0):
        shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    else:
        shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')


_draw_handler_view = None
_draw_handler_pixel = None
_handled_text_rects = set()


def draw_trimsheet_rectangles():
    """Draw trim rectangles in UV space (POST_VIEW)"""
    context = bpy.context

    # Only draw in UV editor
    if not context.space_data or context.space_data.type != 'IMAGE_EDITOR':
        return

    # Check visibility setting
    settings = context.scene.uvv_settings
    if not settings.show_trim_overlays:
        return

    material = trimsheet_utils.get_active_material(context)
    if not material or not hasattr(material, 'uvv_trims'):
        return

    trims = material.uvv_trims
    if len(trims) == 0:
        return

    # Get opacity multiplier
    opacity = settings.trim_overlay_opacity

    try:
        # Enable alpha blending
        gpu.state.blend_set('ALPHA')

        for idx, trim in enumerate(trims):
            # Skip disabled trims
            if not trim.enabled:
                continue

            is_active = (material.uvv_trims_index == idx)
            is_selected = trim.selected

            # Draw filled rectangle
            fill_alpha = (0.2 if is_active else 0.1) * opacity
            fill_color = (*trim.color, fill_alpha)

            fill_verts = [
                (trim.left, trim.bottom),
                (trim.right, trim.bottom),
                (trim.right, trim.top),
                (trim.left, trim.top)
            ]

            fill_batch = batch_for_shader(
                shader_2d_uniform, 'TRI_FAN', {"pos": fill_verts}
            )

            shader_2d_uniform.bind()
            shader_2d_uniform.uniform_float("color", fill_color)
            fill_batch.draw(shader_2d_uniform)

            # Draw border (skip if in edit mode and this is the active trim)
            # In edit mode, the transform handles will draw the border instead
            if is_active and settings.trim_edit_mode:
                # Skip drawing border for active trim in edit mode
                # The transform draw handler will show the blue border with handles
                continue

            border_verts = [
                (trim.left, trim.bottom),
                (trim.right, trim.bottom),
                (trim.right, trim.top),
                (trim.left, trim.top)
            ]

            # Determine border color and width
            if is_active:
                # Active trim: white at 50% opacity
                border_color = (1.0, 1.0, 1.0, 0.5 * opacity)
                line_width = 2.0
            else:
                # All other trims: use trim color
                border_color = (*trim.color, 0.8 * opacity)
                line_width = 1.5

            border_batch = batch_for_shader(
                shader_line, 'LINE_LOOP', {"pos": border_verts}
            )

            shader_line.bind()

            # Set line width for modern Blender versions
            if bpy.app.version >= (3, 4, 0):
                region = context.region
                shader_line.uniform_float('viewportSize', (region.width, region.height))
                shader_line.uniform_float('lineWidth', line_width)

            shader_line.uniform_float('color', border_color)
            border_batch.draw(shader_line)

        gpu.state.blend_set('NONE')

    except Exception as e:
        # Silently fail to avoid console spam during drawing
        pass


def draw_trimsheet_text():
    """Draw trim text labels in screen space (POST_PIXEL)"""
    context = bpy.context

    # Only draw in UV editor
    if not context.space_data or context.space_data.type != 'IMAGE_EDITOR':
        return

    # Check visibility setting
    settings = context.scene.uvv_settings
    if not settings.show_trim_overlays:
        return

    material = trimsheet_utils.get_active_material(context)
    if not material or not hasattr(material, 'uvv_trims'):
        return

    trims = material.uvv_trims
    if len(trims) == 0:
        return

    # Get opacity multiplier
    opacity = settings.trim_overlay_opacity

    try:
        # Draw text labels using TextRect system
        global _handled_text_rects
        _handled_text_rects.clear()

        font_id = 0
        ui_scale = context.preferences.system.ui_scale
        font_size = 12  # Base font size

        # Set font size with proper version-specific parameters
        # ZenUV approach: different blf.size() calls for different Blender versions
        if bpy.app.version < (3, 4, 0):
            # Older Blender versions need DPI parameter
            blf.size(font_id, int(font_size * ui_scale), 72)
        else:
            # Modern Blender versions (3.4+)
            blf.size(font_id, font_size * ui_scale)

        for idx, trim in enumerate(trims):
            # Skip disabled trims
            if not trim.enabled:
                continue

            is_active = (material.uvv_trims_index == idx)
            is_selected = trim.selected

            # Calculate center position in UV space
            center_u = (trim.left + trim.right) / 2.0
            center_v = (trim.bottom + trim.top) / 2.0

            # Convert UV coordinates to region pixel coordinates
            screen_pos = trimsheet_utils.view_to_region(context, center_u, center_v)

            if screen_pos:
                # Get text dimensions for centering
                text = trim.name
                text_width, text_height = blf.dimensions(font_id, text)

                # Create TextRect for this label
                text_rect = TextRect()
                text_rect.name = text

                # Position text centered on trim
                text_rect.left = screen_pos[0] - text_width / 2.0
                text_rect.bottom = screen_pos[1] - text_height / 2.0
                text_rect.right = text_rect.left + text_width
                text_rect.top = text_rect.bottom + text_height

                # Set text color (white with opacity)
                text_rect.color = (1.0, 1.0, 1.0, 0.9 * opacity)

                # Check for collision with other labels
                # Always draw if active or selected, otherwise check for intersections
                should_draw = is_active or is_selected or not any(
                    text_rect.intersects(existing_rect)
                    for existing_rect in _handled_text_rects
                )

                if should_draw:
                    text_rect.draw_text()
                    _handled_text_rects.add(text_rect)

    except Exception as e:
        # Silently fail to avoid console spam during drawing
        pass


def register_draw_handler():
    """Register the draw handlers"""
    global _draw_handler_view, _draw_handler_pixel

    if _draw_handler_view is None:
        # Register rectangles in UV space (POST_VIEW)
        _draw_handler_view = bpy.types.SpaceImageEditor.draw_handler_add(
            draw_trimsheet_rectangles, (), 'WINDOW', 'POST_VIEW'
        )

    if _draw_handler_pixel is None:
        # Register text in screen space (POST_PIXEL)
        _draw_handler_pixel = bpy.types.SpaceImageEditor.draw_handler_add(
            draw_trimsheet_text, (), 'WINDOW', 'POST_PIXEL'
        )


def unregister_draw_handler():
    """Unregister the draw handlers"""
    global _draw_handler_view, _draw_handler_pixel

    if _draw_handler_view is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler_view, 'WINDOW')
        _draw_handler_view = None

    if _draw_handler_pixel is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler_pixel, 'WINDOW')
        _draw_handler_pixel = None
