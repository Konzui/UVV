"""Draw handler for trimsheet transform handles in edit mode"""

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

# Get appropriate shader for Blender version
if not bpy.app.background:
    shader_2d_uniform = gpu.shader.from_builtin('UNIFORM_COLOR')
    if bpy.app.version < (3, 5, 0):
        shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    else:
        shader_line = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')


# Edit mode transform colors
EDIT_BORDER_COLOR = (0.047, 0.549, 0.914, 1.0)  # #0c8ce9 blue
EDIT_BORDER_COLOR_HOVER = (0.047, 0.549, 0.914, 1.0)  # Same blue, just thicker border on hover
EDIT_HANDLE_FILL_COLOR = (1.0, 1.0, 1.0, 1.0)  # White
EDIT_HANDLE_BORDER_COLOR = (0.047, 0.549, 0.914, 1.0)  # Blue
EDIT_DIMENSION_BG_COLOR = (0.047, 0.549, 0.914, 1.0)  # Blue background
EDIT_DIMENSION_TEXT_COLOR = (1.0, 1.0, 1.0, 1.0)  # White text

# Handle sizes in pixels
CORNER_HANDLE_SIZE = 4  # 4px squares at corners
DIMENSION_TEXT_OFFSET = 8  # 8px below rectangle

# Action button settings
BUTTON_SIZE = 32  # 32px buttons
BUTTON_OFFSET = 8  # 8px offset from trim edge


_draw_handler = None
_hover_handle = None  # Track which handle is being hovered
_hover_text_idx = None  # Track which trim text label is being hovered (when not in edit mode)
_hover_text_start_time = None  # Timestamp when hovering over text started (for tooltip delay)


def get_handle_type_at_position(context, trim, mouse_region_x, mouse_region_y):
    """Determine which handle type is at the given mouse position

    Returns: tuple (handle_type, handle_id)
        handle_type: 'corner', 'edge', 'center', or None
        handle_id: specific identifier like 'bottom_left', 'left', etc.
    """
    region = context.region
    if not region:
        return None, None
    rv2d = region.view2d
    if not rv2d:
        return None, None

    # Convert trim bounds to region coordinates
    bl_region = rv2d.view_to_region(trim.left, trim.bottom, clip=False)
    br_region = rv2d.view_to_region(trim.right, trim.bottom, clip=False)
    tr_region = rv2d.view_to_region(trim.right, trim.top, clip=False)
    tl_region = rv2d.view_to_region(trim.left, trim.top, clip=False)

    if not bl_region or not tr_region:
        return None, None

    mx, my = mouse_region_x, mouse_region_y

    # Check corner handles first (highest priority)
    corners = {
        'bottom_left': bl_region,
        'bottom_right': br_region,
        'top_right': tr_region,
        'top_left': tl_region,
    }

    for corner_id, (cx, cy) in corners.items():
        if (cx - CORNER_HANDLE_SIZE <= mx <= cx + CORNER_HANDLE_SIZE and
            cy - CORNER_HANDLE_SIZE <= my <= cy + CORNER_HANDLE_SIZE):
            return 'corner', corner_id

    # Check edge handles (full length, 8px thick hitbox)
    left_x, right_x = bl_region[0], br_region[0]
    bottom_y, top_y = bl_region[1], tl_region[1]
    edge_hitbox_thickness = 8  # 8px thick hitbox on each edge

    # Left edge (full height)
    if (left_x - edge_hitbox_thickness <= mx <= left_x + edge_hitbox_thickness and
        bottom_y <= my <= top_y):
        return 'edge', 'left'

    # Right edge (full height)
    if (right_x - edge_hitbox_thickness <= mx <= right_x + edge_hitbox_thickness and
        bottom_y <= my <= top_y):
        return 'edge', 'right'

    # Top edge (full width)
    if (left_x <= mx <= right_x and
        top_y - edge_hitbox_thickness <= my <= top_y + edge_hitbox_thickness):
        return 'edge', 'top'

    # Bottom edge (full width)
    if (left_x <= mx <= right_x and
        bottom_y - edge_hitbox_thickness <= my <= bottom_y + edge_hitbox_thickness):
        return 'edge', 'bottom'

    # Check if inside rectangle (for move)
    if (left_x <= mx <= right_x and bottom_y <= my <= top_y):
        return 'center', 'move'

    return None, None


def draw_corner_handle(region_pos):
    """Draw a corner handle at the given region position"""
    x, y = region_pos

    # Draw filled square (always white, no hover color)
    verts = [
        (x - CORNER_HANDLE_SIZE, y - CORNER_HANDLE_SIZE),
        (x + CORNER_HANDLE_SIZE, y - CORNER_HANDLE_SIZE),
        (x + CORNER_HANDLE_SIZE, y + CORNER_HANDLE_SIZE),
        (x - CORNER_HANDLE_SIZE, y - CORNER_HANDLE_SIZE),
        (x + CORNER_HANDLE_SIZE, y + CORNER_HANDLE_SIZE),
        (x - CORNER_HANDLE_SIZE, y + CORNER_HANDLE_SIZE),
    ]

    batch = batch_for_shader(shader_2d_uniform, 'TRIS', {"pos": verts})

    shader_2d_uniform.bind()
    shader_2d_uniform.uniform_float("color", EDIT_HANDLE_FILL_COLOR)
    batch.draw(shader_2d_uniform)

    # Draw border
    border_verts = [
        (x - CORNER_HANDLE_SIZE, y - CORNER_HANDLE_SIZE),
        (x + CORNER_HANDLE_SIZE, y - CORNER_HANDLE_SIZE),
        (x + CORNER_HANDLE_SIZE, y + CORNER_HANDLE_SIZE),
        (x - CORNER_HANDLE_SIZE, y + CORNER_HANDLE_SIZE),
    ]

    border_batch = batch_for_shader(shader_line, 'LINE_LOOP', {"pos": border_verts})

    shader_line.bind()

    if bpy.app.version >= (3, 4, 0):
        region = bpy.context.region
        shader_line.uniform_float('viewportSize', (region.width, region.height))
        shader_line.uniform_float('lineWidth', 2.0)

    shader_line.uniform_float('color', EDIT_HANDLE_BORDER_COLOR)
    border_batch.draw(shader_line)


# Edge handles are now invisible - they only serve as hitboxes
# No visual drawing needed, just hit detection in get_handle_type_at_position()


def draw_dimension_text(context, trim):
    """Draw dimension text below the trim rectangle"""
    region = context.region
    rv2d = region.view2d

    # Calculate dimensions
    width = abs(trim.right - trim.left)
    height = abs(trim.top - trim.bottom)

    # Format text
    text = f"{width:.3f} × {height:.3f}"

    # Get center bottom position in region coordinates
    center_x = (trim.left + trim.right) / 2
    text_pos_uv = (center_x, trim.bottom)
    text_pos_region = rv2d.view_to_region(text_pos_uv[0], text_pos_uv[1], clip=False)

    if not text_pos_region:
        return

    # Setup font
    font_id = 0
    ui_scale = context.preferences.system.ui_scale
    font_size = 11

    if bpy.app.version < (3, 4, 0):
        blf.size(font_id, int(font_size * ui_scale), 72)
    else:
        blf.size(font_id, font_size * ui_scale)

    # Get text dimensions
    text_width, text_height = blf.dimensions(font_id, text)

    # Calculate background rectangle position (8px below trim + padding)
    padding = 4
    bg_x = text_pos_region[0] - text_width / 2 - padding
    bg_y = text_pos_region[1] - DIMENSION_TEXT_OFFSET - text_height - padding * 2
    bg_width = text_width + padding * 2
    bg_height = text_height + padding * 2

    # Draw background rectangle
    bg_verts = [
        (bg_x, bg_y),
        (bg_x + bg_width, bg_y),
        (bg_x + bg_width, bg_y + bg_height),
        (bg_x, bg_y),
        (bg_x + bg_width, bg_y + bg_height),
        (bg_x, bg_y + bg_height),
    ]

    bg_batch = batch_for_shader(shader_2d_uniform, 'TRIS', {"pos": bg_verts})
    shader_2d_uniform.bind()
    shader_2d_uniform.uniform_float("color", EDIT_DIMENSION_BG_COLOR)
    bg_batch.draw(shader_2d_uniform)

    # Draw text
    blf.position(font_id, bg_x + padding, bg_y + padding, 0)
    blf.color(font_id, *EDIT_DIMENSION_TEXT_COLOR)
    blf.draw(font_id, text)


# Removed draw_trim_action_buttons - no longer using overlay buttons


def draw_transform_handles():
    """Draw transform handles for the active trim in edit mode"""
    context = bpy.context

    # Only draw in UV editor
    if not context.space_data or context.space_data.type != 'IMAGE_EDITOR':
        return

    # Check if edit mode is enabled
    settings = context.scene.uvv_settings
    if not settings.trim_edit_mode:
        return

    # Get active material and trim
    from ..utils import trimsheet_utils
    material = trimsheet_utils.get_active_material(context)
    if not material or not hasattr(material, 'uvv_trims'):
        return

    if material.uvv_trims_index < 0 or material.uvv_trims_index >= len(material.uvv_trims):
        return

    trim = material.uvv_trims[material.uvv_trims_index]

    if not trim.enabled:
        return

    region = context.region
    rv2d = region.view2d

    # Convert trim bounds to region coordinates
    bl_region = rv2d.view_to_region(trim.left, trim.bottom, clip=False)
    br_region = rv2d.view_to_region(trim.right, trim.bottom, clip=False)
    tr_region = rv2d.view_to_region(trim.right, trim.top, clip=False)
    tl_region = rv2d.view_to_region(trim.left, trim.top, clip=False)

    if not bl_region or not tr_region:
        return

    try:
        gpu.state.blend_set('ALPHA')

        # Get hover state to determine if hovering over trim
        global _hover_handle
        is_hovering_trim = _hover_handle is not None

        # Draw main blue outline rectangle
        # If hovering over any part of the trim, make border 1px thicker (3px instead of 2px)
        border_verts = [
            bl_region, br_region, tr_region, tl_region
        ]

        border_batch = batch_for_shader(shader_line, 'LINE_LOOP', {"pos": border_verts})

        shader_line.bind()

        if bpy.app.version >= (3, 4, 0):
            shader_line.uniform_float('viewportSize', (region.width, region.height))
            # Thicker border on hover: 3.0 instead of 2.0
            line_width = 3.0 if is_hovering_trim else 2.0
            shader_line.uniform_float('lineWidth', line_width)

        shader_line.uniform_float('color', EDIT_BORDER_COLOR)
        border_batch.draw(shader_line)

        # Draw corner handles (no hover color, always white)
        corners = {
            'bottom_left': bl_region,
            'bottom_right': br_region,
            'top_right': tr_region,
            'top_left': tl_region,
        }

        for corner_id, corner_pos in corners.items():
            draw_corner_handle(corner_pos)

        # Edge handles are invisible - no drawing needed!

        gpu.state.blend_set('NONE')

        # Draw dimension text
        draw_dimension_text(context, trim)

    except Exception as e:
        # Silently fail to avoid console spam
        pass


def update_hover_handle(context, mouse_region_x, mouse_region_y):
    """Update which handle is being hovered"""
    import time
    global _hover_handle, _hover_text_idx, _hover_text_start_time

    settings = context.scene.uvv_settings
    if not settings.trim_edit_mode:
        _hover_handle = None
        # Check if hovering over text label (when not in edit mode)
        current_text_idx = get_text_label_at_position(context, mouse_region_x, mouse_region_y)
        
        if current_text_idx is not None:
            # Start tracking hover time if this is a new hover
            if _hover_text_idx != current_text_idx:
                _hover_text_start_time = time.time()
            _hover_text_idx = current_text_idx
        else:
            # No longer hovering, reset
            _hover_text_idx = None
            _hover_text_start_time = None
        return

    # In edit mode, clear text hover
    _hover_text_idx = None
    _hover_text_start_time = None

    from ..utils import trimsheet_utils
    material = trimsheet_utils.get_active_material(context)
    if not material or not hasattr(material, 'uvv_trims'):
        _hover_handle = None
        return

    if material.uvv_trims_index < 0 or material.uvv_trims_index >= len(material.uvv_trims):
        _hover_handle = None
        return

    trim = material.uvv_trims[material.uvv_trims_index]
    handle_type, handle_id = get_handle_type_at_position(context, trim, mouse_region_x, mouse_region_y)

    _hover_handle = (handle_type, handle_id) if handle_type else None


def get_text_label_at_position(context, mouse_region_x, mouse_region_y):
    """Check if mouse is over any trim text label

    Args:
        context: Blender context
        mouse_region_x: Mouse X in region coordinates
        mouse_region_y: Mouse Y in region coordinates

    Returns:
        trim_index or None
    """
    from ..utils import trimsheet_utils
    material = trimsheet_utils.get_active_material(context)
    if not material or not hasattr(material, 'uvv_trims'):
        return None

    region = context.region
    if not region:
        return None
    rv2d = region.view2d
    if not rv2d:
        return None

    # Get font info for text dimensions
    font_id = 0
    ui_scale = context.preferences.system.ui_scale
    font_size = 12

    if bpy.app.version < (3, 4, 0):
        blf.size(font_id, int(font_size * ui_scale), 72)
    else:
        blf.size(font_id, font_size * ui_scale)

    for idx, trim in enumerate(material.uvv_trims):
        if not trim.enabled:
            continue

        # Calculate center position in UV space
        center_u = (trim.left + trim.right) / 2.0
        center_v = (trim.bottom + trim.top) / 2.0

        # Convert to screen space
        screen_pos = rv2d.view_to_region(center_u, center_v, clip=False)
        if not screen_pos:
            continue

        # Get text dimensions
        text = trim.name
        text_width, text_height = blf.dimensions(font_id, text)

        # Calculate text rectangle (centered on trim)
        text_left = screen_pos[0] - text_width / 2.0
        text_right = text_left + text_width
        text_bottom = screen_pos[1] - text_height / 2.0
        text_top = text_bottom + text_height

        # Check if mouse is over text
        if (text_left <= mouse_region_x <= text_right and
            text_bottom <= mouse_region_y <= text_top):
            return idx

    return None


def get_lock_button_at_position(context, mouse_region_x, mouse_region_y):
    """Check if mouse is over the lock button for the active trim

    Args:
        context: Blender context
        mouse_region_x: Mouse X in region coordinates
        mouse_region_y: Mouse Y in region coordinates

    Returns:
        True if mouse is over lock button, False otherwise
    """
    from ..utils import trimsheet_utils
    material = trimsheet_utils.get_active_material(context)
    if not material or not hasattr(material, 'uvv_trims'):
        print(f"UVV DEBUG: get_lock_button_at_position: No material")
        return False

    # Check if we have an active trim
    if material.uvv_trims_index < 0 or material.uvv_trims_index >= len(material.uvv_trims):
        print(f"UVV DEBUG: get_lock_button_at_position: Invalid trim index {material.uvv_trims_index}")
        return False

    settings = context.scene.uvv_settings
    # Don't show button in edit mode
    if settings.trim_edit_mode:
        print(f"UVV DEBUG: get_lock_button_at_position: In edit mode, skipping")
        return False

    trim = material.uvv_trims[material.uvv_trims_index]
    if not trim.enabled:
        print(f"UVV DEBUG: get_lock_button_at_position: Trim not enabled")
        return False

    region = context.region
    if not region:
        return False
    rv2d = region.view2d
    if not rv2d:
        return False

    # Convert top center of trim to region coordinates
    top_center_u = (trim.left + trim.right) / 2.0
    top_center_v = trim.top
    
    # Use same method as text labels for consistency
    screen_pos = trimsheet_utils.view_to_region(context, top_center_u, top_center_v)
    if not screen_pos:
        return False

    # Button settings (must match draw_lock_button)
    BUTTON_OFFSET_Y = 16  # 16px above the top edge
    BUTTON_PADDING = 8  # Padding around icon
    ICON_SIZE = 16  # Icon size in pixels
    
    # Make button square (must match draw_lock_button)
    button_size = ICON_SIZE + BUTTON_PADDING * 2
    
    # Calculate button position (centered horizontally, 16px above top edge)
    button_x = screen_pos[0] - button_size / 2.0
    button_y = screen_pos[1] + BUTTON_OFFSET_Y
    
    # Always print button position for debugging
    print(f"UVV DEBUG: Lock button check - Button at: ({button_x:.1f}, {button_y:.1f}) size: {button_size:.1f}x{button_size:.1f}, Mouse: ({mouse_region_x}, {mouse_region_y})")
    
    # Check if mouse is over button (square button)
    is_over = (button_x <= mouse_region_x <= button_x + button_size and
               button_y <= mouse_region_y <= button_y + button_size)
    
    print(f"UVV DEBUG: Lock button hit test: X={button_x:.1f} <= {mouse_region_x} <= {button_x + button_size:.1f} = {button_x <= mouse_region_x <= button_x + button_size}")
    print(f"UVV DEBUG: Lock button hit test: Y={button_y:.1f} <= {mouse_region_y} <= {button_y + button_size:.1f} = {button_y <= mouse_region_y <= button_y + button_size}")
    print(f"UVV DEBUG: Lock button is_over = {is_over}")
    
    if is_over:
        print(f"UVV DEBUG: *** LOCK BUTTON CLICK DETECTED! ***")
        return True

    return False


# Removed update_hover_button - no longer needed without buttons


def register_draw_handler():
    """Register the transform handles draw handler"""
    global _draw_handler

    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceImageEditor.draw_handler_add(
            draw_transform_handles, (), 'WINDOW', 'POST_PIXEL'
        )


def unregister_draw_handler():
    """Unregister the transform handles draw handler"""
    global _draw_handler

    if _draw_handler is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
