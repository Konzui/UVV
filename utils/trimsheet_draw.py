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

            # Determine border color and width based on active/locked state
            if is_active:
                # Active trim: gray if locked, white if unlocked
                if trim.locked:
                    border_color = (0.5, 0.5, 0.5, 0.8 * opacity)  # Gray for locked
                else:
                    border_color = (1.0, 1.0, 1.0, 0.5 * opacity)  # White for unlocked
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


def transform_svg_to_screen(svg_x, svg_y, center_x, center_y, size):
    """Transform SVG coordinates to screen coordinates with correct Y-axis flip
    
    Args:
        svg_x, svg_y: Coordinates in SVG space (0-32, Y=0 at top)
        center_x, center_y: Center position for the icon in screen space
        size: Target icon size in pixels
    
    Returns:
        (screen_x, screen_y) tuple in screen space (Y=0 at bottom)
    """
    scale = size / 32.0
    # SVG Y=0 is at top, screen Y=0 is at bottom
    # Correct transformation: screen_y = center_y - (svg_y - 16) * scale
    screen_x = center_x + (svg_x - 16.0) * scale
    screen_y = center_y - (svg_y - 16.0) * scale
    return (screen_x, screen_y)


def parse_simple_path(path_data):
    """Parse SVG path data including M, L, H, V, Z, and C (cubic Bezier) commands
    
    Args:
        path_data: SVG path string (d attribute)
    
    Returns:
        List of tuples: (subpath, is_closed) where subpath is list of (x, y) tuples in SVG space (0-32)
        and is_closed indicates if the path was explicitly closed with Z command
    """
    import re
    import math
    
    subpaths = []
    current_subpath = []
    current_x = 0.0
    current_y = 0.0
    start_x = 0.0
    start_y = 0.0
    is_closed = False
    
    # Normalize path data: add spaces around all commands (including H, V, C)
    normalized = re.sub(r'([MmLlHhVvCcZz])', r' \1 ', path_data)
    normalized = re.sub(r'(\d)([MmLlHhVvCcZz])', r'\1 \2', normalized)
    normalized = re.sub(r'([MmLlHhVvCcZz])(\d)', r'\1 \2', normalized)
    
    tokens = [t.strip() for t in normalized.split() if t.strip()]
    
    i = 0
    current_cmd = None
    
    def get_number_or_float(token):
        """Try to parse a number"""
        try:
            return float(token)
        except ValueError:
            return None
    
    while i < len(tokens):
        token = tokens[i]
        
        # Check if this is a command
        if token in 'MmLlHhVvCcZz':
            # Save previous subpath if starting a new one
            if token in 'Mm' and current_subpath:
                subpaths.append((current_subpath, is_closed))
                current_subpath = []
                is_closed = False
            
            current_cmd = token
            i += 1
            
            # Handle Z (close path)
            if token in 'Zz':
                if current_subpath and (abs(current_x - start_x) > 0.001 or abs(current_y - start_y) > 0.001):
                    current_subpath.append((start_x, start_y))
                current_x = start_x
                current_y = start_y
                is_closed = True  # Mark this path as explicitly closed
                current_cmd = None
                continue
        
        # Process coordinates based on current command
        if current_cmd:
            try:
                if current_cmd in 'Mm':
                    # Move to - read coordinates
                    if i < len(tokens):
                        x_val = get_number_or_float(tokens[i])
                        if x_val is not None:
                            i += 1
                            if i < len(tokens):
                                y_val = get_number_or_float(tokens[i])
                                if y_val is not None:
                                    i += 1
                                    
                                    if current_cmd == 'm':  # Relative
                                        current_x += x_val
                                        current_y += y_val
                                    else:  # Absolute
                                        current_x = x_val
                                        current_y = y_val
                                    
                                    start_x = current_x
                                    start_y = current_y
                                    current_subpath.append((current_x, current_y))
                                    current_cmd = 'L' if current_cmd == 'M' else 'l'
                                else:
                                    current_cmd = None
                            else:
                                current_cmd = None
                        else:
                            current_cmd = None
                
                elif current_cmd in 'Ll':
                    # Line to - read coordinates
                    if i + 1 < len(tokens):
                        x_val = get_number_or_float(tokens[i])
                        if x_val is not None:
                            i += 1
                            y_val = get_number_or_float(tokens[i])
                            if y_val is not None:
                                i += 1
                                
                                if current_cmd == 'l':  # Relative
                                    current_x += x_val
                                    current_y += y_val
                                else:  # Absolute
                                    current_x = x_val
                                    current_y = y_val
                                
                                # Only add vertex if it's different from the last one (prevents duplicates)
                                if not current_subpath or (
                                    abs(current_x - current_subpath[-1][0]) > 1e-6 or
                                    abs(current_y - current_subpath[-1][1]) > 1e-6
                                ):
                                    current_subpath.append((current_x, current_y))
                                
                                # Check for more coordinates (implicit line-to)
                                if i < len(tokens) and tokens[i] not in 'MmLlHhVvCcZz':
                                    if get_number_or_float(tokens[i]) is not None:
                                        continue  # Continue with same command
                                
                                current_cmd = None
                            else:
                                current_cmd = None
                                i += 1
                        else:
                            current_cmd = None
                    else:
                        current_cmd = None
                
                elif current_cmd in 'Hh':
                    # Horizontal line to - read x coordinate only
                    if i < len(tokens):
                        x_val = get_number_or_float(tokens[i])
                        if x_val is not None:
                            i += 1
                            
                            if current_cmd == 'h':  # Relative
                                current_x += x_val
                            else:  # Absolute
                                current_x = x_val
                            
                            # Only add vertex if it's different from the last one
                            if not current_subpath or (
                                abs(current_x - current_subpath[-1][0]) > 1e-6 or
                                abs(current_y - current_subpath[-1][1]) > 1e-6
                            ):
                                current_subpath.append((current_x, current_y))
                            
                            # Check for more coordinates
                            if i < len(tokens) and tokens[i] not in 'MmLlHhVvCcZz':
                                if get_number_or_float(tokens[i]) is not None:
                                    continue
                            
                            current_cmd = None
                        else:
                            current_cmd = None
                            i += 1
                    else:
                        current_cmd = None
                
                elif current_cmd in 'Vv':
                    # Vertical line to - read y coordinate only
                    if i < len(tokens):
                        y_val = get_number_or_float(tokens[i])
                        if y_val is not None:
                            i += 1
                            
                            if current_cmd == 'v':  # Relative
                                current_y += y_val
                            else:  # Absolute
                                current_y = y_val
                            
                            # Only add vertex if it's different from the last one
                            if not current_subpath or (
                                abs(current_x - current_subpath[-1][0]) > 1e-6 or
                                abs(current_y - current_subpath[-1][1]) > 1e-6
                            ):
                                current_subpath.append((current_x, current_y))
                            
                            # Check for more coordinates
                            if i < len(tokens) and tokens[i] not in 'MmLlHhVvCcZz':
                                if get_number_or_float(tokens[i]) is not None:
                                    continue
                            
                            current_cmd = None
                        else:
                            current_cmd = None
                            i += 1
                    else:
                        current_cmd = None
                
                elif current_cmd in 'Cc':
                    # Cubic Bezier curve - requires 6 coordinates (x1, y1, x2, y2, x, y)
                    if i + 5 < len(tokens):
                        coords = []
                        all_valid = True
                        for j in range(6):
                            if i + j < len(tokens):
                                val = get_number_or_float(tokens[i + j])
                                if val is not None:
                                    coords.append(val)
                                else:
                                    all_valid = False
                                    break
                            else:
                                all_valid = False
                                break
                        
                        if all_valid:
                            x1, y1, x2, y2, x, y = coords
                            i += 6
                            
                            if current_cmd == 'c':  # Relative
                                abs_x1 = current_x + x1
                                abs_y1 = current_y + y1
                                abs_x2 = current_x + x2
                                abs_y2 = current_y + y2
                                abs_x = current_x + x
                                abs_y = current_y + y
                            else:  # Absolute
                                abs_x1 = x1
                                abs_y1 = y1
                                abs_x2 = x2
                                abs_y2 = y2
                                abs_x = x
                                abs_y = y
                            
                            # Approximate cubic Bezier curve with line segments
                            # Adaptive segmentation: scale with curve length and ensure smoothness
                            # Calculate approximate curve length for adaptive segmentation
                            curve_length = (
                                math.sqrt((abs_x1 - current_x)**2 + (abs_y1 - current_y)**2) +
                                math.sqrt((abs_x2 - abs_x1)**2 + (abs_y2 - abs_y1)**2) +
                                math.sqrt((abs_x - abs_x2)**2 + (abs_y - abs_y2)**2)
                            ) / 3.0  # Average of control point distances
                            
                            # Scale segments with curve complexity and size
                            # Minimum 32 segments, scale up for longer curves or larger icons
                            # For a 16px icon, use ~32-48 segments. For larger icons, scale proportionally
                            base_segments = 48  # Higher base for smoother curves
                            # Scale with curve length (more segments for longer curves)
                            length_factor = max(1.0, curve_length / 4.0)
                            num_segments = int(base_segments * length_factor)
                            # Cap at reasonable maximum to avoid performance issues
                            num_segments = min(num_segments, 128)
                            
                            # Check if the start point already exists to avoid duplicates
                            # This is critical for exact connections between path segments (e.g., V command followed by C)
                            skip_first = False
                            if current_subpath:
                                last_x, last_y = current_subpath[-1]
                                # If start of curve matches last point exactly (within precision), skip first vertex
                                if abs(current_x - last_x) < 1e-6 and abs(current_y - last_y) < 1e-6:
                                    skip_first = True
                            
                            # Generate Bezier curve vertices
                            for j in range(num_segments + 1):
                                if skip_first and j == 0:
                                    continue  # Skip first point to avoid duplicate
                                t = j / num_segments
                                # Cubic Bezier formula: B(t) = (1-t)^3*P0 + 3*(1-t)^2*t*P1 + 3*(1-t)*t^2*P2 + t^3*P3
                                px = (1-t)**3 * current_x + 3*(1-t)**2*t * abs_x1 + 3*(1-t)*t**2 * abs_x2 + t**3 * abs_x
                                py = (1-t)**3 * current_y + 3*(1-t)**2*t * abs_y1 + 3*(1-t)*t**2 * abs_y2 + t**3 * abs_y
                                current_subpath.append((px, py))
                            
                            current_x = abs_x
                            current_y = abs_y
                            current_cmd = None
                        else:
                            current_cmd = None
                            i += 1
                    else:
                        current_cmd = None
                        i += 1
            except (ValueError, IndexError, TypeError):
                current_cmd = None
                i += 1
        else:
            i += 1
    
    # Add the last subpath if it exists
    if current_subpath:
        subpaths.append((current_subpath, is_closed))
    
    return subpaths


def extract_stroke_width(element, default=1.0):
    """Extract stroke-width from SVG element
    
    Args:
        element: XML element with potential stroke-width attribute
        default: Default stroke width if not specified
    
    Returns:
        Stroke width as float
    """
    stroke_width_str = element.get('stroke-width', str(default))
    try:
        return float(stroke_width_str)
    except (ValueError, TypeError):
        return default


def extract_fill_color(element):
    """Extract fill color and opacity from SVG element
    
    Args:
        element: XML element with potential fill and fill-opacity attributes
    
    Returns:
        Tuple of (has_fill, fill_color_rgb, fill_opacity) where:
        - has_fill: True if element has a fill (not "none")
        - fill_color_rgb: (r, g, b) tuple in 0-1 range
        - fill_opacity: Opacity in 0-1 range
    """
    fill_attr = element.get('fill', 'none')
    
    # Check if fill is none or not specified
    if fill_attr == 'none' or not fill_attr:
        return (False, None, 1.0)
    
    # Get fill opacity (can be from fill-opacity or opacity attribute)
    fill_opacity_str = element.get('fill-opacity', element.get('opacity', '1.0'))
    try:
        fill_opacity = float(fill_opacity_str)
    except (ValueError, TypeError):
        fill_opacity = 1.0
    
    # Parse fill color
    # Handle common formats: "white", "black", rgb(), hex, etc.
    fill_attr = fill_attr.strip().lower()
    
    if fill_attr == 'white':
        return (True, (1.0, 1.0, 1.0), fill_opacity)
    elif fill_attr == 'black':
        return (True, (0.0, 0.0, 0.0), fill_opacity)
    elif fill_attr.startswith('rgb('):
        # Parse rgb(r, g, b) format
        import re
        match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', fill_attr)
        if match:
            r = float(match.group(1)) / 255.0
            g = float(match.group(2)) / 255.0
            b = float(match.group(3)) / 255.0
            return (True, (r, g, b), fill_opacity)
    elif fill_attr.startswith('#'):
        # Parse hex color #RRGGBB or #RGB
        hex_color = fill_attr[1:]
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])  # Expand #RGB to #RRGGBB
        try:
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            return (True, (r, g, b), fill_opacity)
        except (ValueError, IndexError):
            pass
    
    # Default to white if we can't parse
    return (True, (1.0, 1.0, 1.0), fill_opacity)


def render_simple_rect(center_x, center_y, size, rect_x, rect_y, rect_width, rect_height, 
                       stroke_width, color, opacity, rotation=0.0, rot_center_x=None, rot_center_y=None,
                       fill_color=None, fill_opacity=1.0):
    """Render a simple rectangle (no rounded corners) with optional fill and stroke
    
    Args:
        center_x, center_y: Center position of icon in screen space
        size: Icon size in pixels
        rect_x, rect_y: Rectangle position in SVG space (0-32)
        rect_width, rect_height: Rectangle dimensions in SVG space
        stroke_width: Stroke width in SVG space (will be scaled)
        color: RGB color tuple (0-1) for stroke
        opacity: Opacity (0-1) for stroke
        rotation: Rotation angle in degrees (optional)
        rot_center_x, rot_center_y: Rotation center in SVG space (optional)
        fill_color: RGB color tuple (0-1) for fill, or None if no fill
        fill_opacity: Opacity (0-1) for fill
    """
    import math
    
    # Scale stroke width
    scaled_stroke = stroke_width * (size / 32.0)
    
    # Calculate rectangle corners in SVG space (center-aligned stroke, SVG default)
    corners_svg = [
        (rect_x, rect_y),
        (rect_x + rect_width, rect_y),
        (rect_x + rect_width, rect_y + rect_height),
        (rect_x, rect_y + rect_height)
    ]
    
    # Apply rotation if specified
    if rotation != 0.0:
        rot_rad = math.radians(rotation)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)
        
        # Default rotation center is rectangle center
        if rot_center_x is None:
            rot_center_x = rect_x + rect_width / 2.0
        if rot_center_y is None:
            rot_center_y = rect_y + rect_height / 2.0
        
        # Rotate corners around rotation center
        rotated_corners = []
        for cx, cy in corners_svg:
            dx = cx - rot_center_x
            dy = cy - rot_center_y
            new_x = dx * cos_r - dy * sin_r + rot_center_x
            new_y = dx * sin_r + dy * cos_r + rot_center_y
            rotated_corners.append((new_x, new_y))
        corners_svg = rotated_corners
    
    # Transform corners to screen space
    corners_screen = [
        transform_svg_to_screen(x, y, center_x, center_y, size)
        for x, y in corners_svg
    ]
    
    gpu.state.blend_set('ALPHA')
    
    # Draw fill if specified
    if fill_color is not None:
        fill_color_rgba = (*fill_color, fill_opacity * opacity)
        fill_verts = [
            corners_screen[0],
            corners_screen[1],
            corners_screen[2],
            corners_screen[0],
            corners_screen[2],
            corners_screen[3]
        ]
        fill_batch = batch_for_shader(shader_2d_uniform, 'TRIS', {"pos": fill_verts})
        shader_2d_uniform.bind()
        shader_2d_uniform.uniform_float("color", fill_color_rgba)
        fill_batch.draw(shader_2d_uniform)
    
    # Draw rectangle outline (if stroke width > 0)
    if scaled_stroke > 0:
        # LINE_LOOP automatically closes, so we don't need to duplicate the first vertex
        icon_color = (*color, opacity)
        outline_batch = batch_for_shader(shader_line, 'LINE_LOOP', {"pos": corners_screen})
        shader_line.bind()
        if bpy.app.version >= (3, 4, 0):
            region = bpy.context.region
            if region:
                shader_line.uniform_float('viewportSize', (region.width, region.height))
        shader_line.uniform_float('lineWidth', max(0.5, scaled_stroke))
        shader_line.uniform_float('color', icon_color)
        outline_batch.draw(shader_line)


def render_rounded_rect(center_x, center_y, size, rect_x, rect_y, rect_width, rect_height,
                         rx, stroke_width, color, opacity, rotation=0.0, rot_center_x=None, rot_center_y=None,
                         fill_color=None, fill_opacity=1.0):
    """Render a rounded rectangle with proper arc tessellation and optional fill
    
    Args:
        center_x, center_y: Center position of icon in screen space
        size: Icon size in pixels
        rect_x, rect_y: Rectangle position in SVG space (0-32)
        rect_width, rect_height: Rectangle dimensions in SVG space
        rx: Corner radius in SVG space
        stroke_width: Stroke width in SVG space (will be scaled)
        color: RGB color tuple (0-1) for stroke
        opacity: Opacity (0-1) for stroke
        rotation: Rotation angle in degrees (optional)
        rot_center_x, rot_center_y: Rotation center in SVG space (optional)
        fill_color: RGB color tuple (0-1) for fill, or None if no fill
        fill_opacity: Opacity (0-1) for fill
    """
    import math
    
    # Scale stroke width
    scaled_stroke = stroke_width * (size / 32.0)
    
    # Clamp rx to valid range
    rx = min(rx, rect_width / 2.0, rect_height / 2.0)
    
    # Build rounded rectangle path with proper arcs
    # We'll create vertices for the rounded corners with smooth arc tessellation
    # Use more segments for smoother corners - scale with corner radius
    # Each corner is a 90-degree arc, so we want enough segments for smoothness
    base_segments = 64  # Higher base for very smooth rounded corners
    # Scale with corner radius (larger radius = more segments needed)
    radius_factor = max(1.0, rx / 2.0)
    num_segments = int(base_segments * radius_factor)
    # Cap at reasonable maximum
    num_segments = min(num_segments, 128)
    
    vertices_svg = []
    
    # Build rounded rectangle going clockwise, starting from top-left corner after the arc
    # Note: SVG Y=0 is at top, so we work with that coordinate system
    
    # Build rounded rectangle ensuring exact connection points between arcs and edges
    # Top-left corner arc: from (rect_x, rect_y+rx) to (rect_x+rx, rect_y)
    tl_center_x = rect_x + rx
    tl_center_y = rect_y + rx
    # Start arc at the connection point to left edge (rect_x, rect_y+rx)
    vertices_svg.append((rect_x, rect_y + rx))
    for i in range(1, num_segments):  # Skip first (already added) and last (will be added by next edge)
        # Angle from 180 to 270 degrees
        angle = math.pi + (math.pi / 2) * (i / num_segments)
        vx = tl_center_x + rx * math.cos(angle)
        vy = tl_center_y + rx * math.sin(angle)
        vertices_svg.append((vx, vy))
    # End at connection point to top edge (rect_x+rx, rect_y)
    vertices_svg.append((rect_x + rx, rect_y))
    
    # Top edge (if there's space)
    if rect_width > rx * 2:
        vertices_svg.append((rect_x + rect_width - rx, rect_y))
    
    # Top-right corner arc: from (rect_x+rect_width-rx, rect_y) to (rect_x+rect_width, rect_y+rx)
    tr_center_x = rect_x + rect_width - rx
    tr_center_y = rect_y + rx
    # Start is already added (rect_x+rect_width-rx, rect_y)
    for i in range(1, num_segments):  # Skip first and last
        angle = (3 * math.pi / 2) + (math.pi / 2) * (i / num_segments)
        if angle >= 2 * math.pi:
            angle -= 2 * math.pi
        vx = tr_center_x + rx * math.cos(angle)
        vy = tr_center_y + rx * math.sin(angle)
        vertices_svg.append((vx, vy))
    # End at connection point to right edge
    vertices_svg.append((rect_x + rect_width, rect_y + rx))
    
    # Right edge (if there's space)
    if rect_height > rx * 2:
        vertices_svg.append((rect_x + rect_width, rect_y + rect_height - rx))
    
    # Bottom-right corner arc: from (rect_x+rect_width, rect_y+rect_height-rx) to (rect_x+rect_width-rx, rect_y+rect_height)
    br_center_x = rect_x + rect_width - rx
    br_center_y = rect_y + rect_height - rx
    # Start is already added
    for i in range(1, num_segments):  # Skip first and last
        angle = (math.pi / 2) * (i / num_segments)
        vx = br_center_x + rx * math.cos(angle)
        vy = br_center_y + rx * math.sin(angle)
        vertices_svg.append((vx, vy))
    # End at connection point to bottom edge
    vertices_svg.append((rect_x + rect_width - rx, rect_y + rect_height))
    
    # Bottom edge (if there's space)
    if rect_width > rx * 2:
        vertices_svg.append((rect_x + rx, rect_y + rect_height))
    
    # Bottom-left corner arc: from (rect_x+rx, rect_y+rect_height) to (rect_x, rect_y+rect_height-rx)
    bl_center_x = rect_x + rx
    bl_center_y = rect_y + rect_height - rx
    # Start is already added
    for i in range(1, num_segments):  # Skip first and last
        angle = (math.pi / 2) + (math.pi / 2) * (i / num_segments)
        vx = bl_center_x + rx * math.cos(angle)
        vy = bl_center_y + rx * math.sin(angle)
        vertices_svg.append((vx, vy))
    # End at connection point to left edge - this should exactly match the first vertex
    vertices_svg.append((rect_x, rect_y + rx))
    
    # Apply rotation if specified
    if rotation != 0.0:
        rot_rad = math.radians(rotation)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)
        
        # Default rotation center is rectangle center
        if rot_center_x is None:
            rot_center_x = rect_x + rect_width / 2.0
        if rot_center_y is None:
            rot_center_y = rect_y + rect_height / 2.0
        
        # Rotate all vertices
        rotated_vertices = []
        for cx, cy in vertices_svg:
            dx = cx - rot_center_x
            dy = cy - rot_center_y
            new_x = dx * cos_r - dy * sin_r + rot_center_x
            new_y = dx * sin_r + dy * cos_r + rot_center_y
            rotated_vertices.append((new_x, new_y))
        vertices_svg = rotated_vertices
    
    # Transform to screen space
    vertices_screen = [
        transform_svg_to_screen(x, y, center_x, center_y, size)
        for x, y in vertices_svg
    ]
    
    gpu.state.blend_set('ALPHA')
    
    # Draw fill if specified (triangulate the rounded rectangle)
    if fill_color is not None:
        fill_color_rgba = (*fill_color, fill_opacity * opacity)
        # Create triangles using fan triangulation from first vertex
        fill_verts = []
        first_vert = vertices_screen[0]
        for i in range(1, len(vertices_screen) - 1):
            fill_verts.extend([
                first_vert,
                vertices_screen[i],
                vertices_screen[i + 1]
            ])
        if fill_verts:
            fill_batch = batch_for_shader(shader_2d_uniform, 'TRIS', {"pos": fill_verts})
            shader_2d_uniform.bind()
            shader_2d_uniform.uniform_float("color", fill_color_rgba)
            fill_batch.draw(shader_2d_uniform)
    
    # Draw rounded rectangle outline (if stroke width > 0)
    if scaled_stroke > 0:
        # Use LINE_LOOP for proper closure (automatically closes the path)
        # Ensure first and last vertices match exactly for seamless closure
        if len(vertices_screen) > 2:
            # Remove duplicate last vertex if it exists (LINE_LOOP auto-closes)
            if (abs(vertices_screen[0][0] - vertices_screen[-1][0]) < 1e-6 and
                abs(vertices_screen[0][1] - vertices_screen[-1][1]) < 1e-6):
                vertices_screen = vertices_screen[:-1]
        
        icon_color = (*color, opacity)
        outline_batch = batch_for_shader(shader_line, 'LINE_LOOP', {"pos": vertices_screen})
        shader_line.bind()
        if bpy.app.version >= (3, 4, 0):
            region = bpy.context.region
            if region:
                shader_line.uniform_float('viewportSize', (region.width, region.height))
        shader_line.uniform_float('lineWidth', max(0.5, scaled_stroke))
        shader_line.uniform_float('color', icon_color)
        outline_batch.draw(shader_line)


# Cache for pixel data from PNG icons
_png_pixel_cache = {}

def draw_lock_icon(center_x, center_y, size, is_locked, color, opacity):
    """Draw lock or unlocked icon using pixel-perfect rendering from PNG
    
    Args:
        center_x, center_y: Center position of icon
        size: Icon size in pixels
        is_locked: True for lock icon, False for unlocked icon
        color: RGB color tuple (0-1)
        opacity: Opacity (0-1)
    """
    import os
    
    # Get PNG file path
    addon_path = os.path.dirname(os.path.dirname(__file__))
    if is_locked:
        png_file = os.path.join(addon_path, "icons", "lock_outline.png")
        cache_key = "lock"
    else:
        png_file = os.path.join(addon_path, "icons", "unlocked_outline.png")
        cache_key = "unlocked"
    
    # Check if file exists
    if not os.path.exists(png_file):
        print(f"UVV: Lock icon PNG not found: {png_file}")
        return
    
    # Get file modification time for cache invalidation
    file_mtime = 0
    try:
        file_mtime = os.path.getmtime(png_file)
    except:
        pass
    
    # Check cache - cache stores pixel data: (width, height, pixels)
    # pixels is a list of (x, y, r, g, b, a) tuples for non-transparent pixels
    cache_entry_key = f"{cache_key}_{file_mtime}"
    
    try:
        # Load or get cached pixel data
        if cache_entry_key in _png_pixel_cache:
            img_width, img_height, pixels_data = _png_pixel_cache[cache_entry_key]
        else:
            # Load PNG image using Blender's image loader
            try:
                # Load image (check_existing=False to ensure we get fresh data)
                temp_image = bpy.data.images.load(png_file, check_existing=False)
                
                # Get image dimensions
                img_width = temp_image.size[0]
                img_height = temp_image.size[1]
                
                # Get pixel data - pixels are stored as RGBA float array (0-1 range)
                # Format: [R, G, B, A, R, G, B, A, ...] for each pixel row by row
                # Note: Blender images are stored bottom-to-top
                pixels = list(temp_image.pixels)
                
                # Extract pixel data - only store non-transparent pixels
                pixels_data = []
                alpha_threshold = 0.01  # Ignore pixels with alpha < 1%
                
                for y in range(img_height):
                    for x in range(img_width):
                        # Calculate index in pixel array (RGBA format, bottom-to-top)
                        # Blender stores pixels bottom-to-top, so we need to flip Y
                        py = img_height - 1 - y
                        idx = (py * img_width + x) * 4
                        
                        if idx + 3 < len(pixels):
                            r = pixels[idx]
                            g = pixels[idx + 1]
                            b = pixels[idx + 2]
                            a = pixels[idx + 3]
                            
                            # Only store pixels with sufficient alpha
                            if a >= alpha_threshold:
                                pixels_data.append((x, y, r, g, b, a))
                
                # Cache the pixel data
                _png_pixel_cache[cache_entry_key] = (img_width, img_height, pixels_data)
                
                # Clean up temporary image
                bpy.data.images.remove(temp_image)
                
            except Exception as e:
                print(f"UVV: Failed to load lock icon PNG: {e}")
                return
        
        if not pixels_data:
            return
        
        # Calculate scale factor to fit icon to requested size
        scale_x = size / img_width
        scale_y = size / img_height
        # Use uniform scaling to maintain aspect ratio
        scale = min(scale_x, scale_y)
        
        # Calculate offset to center the icon
        scaled_width = img_width * scale
        scaled_height = img_height * scale
        offset_x = center_x - scaled_width / 2.0
        offset_y = center_y - scaled_height / 2.0
        
        # Enable alpha blending
        gpu.state.blend_set('ALPHA')
        
        # Build vertices for all visible pixels
        # We'll draw each pixel as a quad
        pixel_quads = []  # List of (quad_vertices, color) tuples
        pixel_size = scale  # Size of each pixel quad
        
        for px, py, pr, pg, pb, pa in pixels_data:
            # Calculate pixel position in screen space
            pixel_x = offset_x + px * scale
            pixel_y = offset_y + (img_height - 1 - py) * scale  # Flip Y for screen coordinates
            
            # Create quad vertices (two triangles)
            # Top-left, top-right, bottom-right, bottom-left
            v0 = (pixel_x, pixel_y + pixel_size)  # Top-left
            v1 = (pixel_x + pixel_size, pixel_y + pixel_size)  # Top-right
            v2 = (pixel_x + pixel_size, pixel_y)  # Bottom-right
            v3 = (pixel_x, pixel_y)  # Bottom-left
            
            # Apply color tint - multiply icon color with pixel color and opacity
            final_r = pr * color[0]
            final_g = pg * color[1]
            final_b = pb * color[2]
            final_a = pa * opacity
            
            final_color = (final_r, final_g, final_b, final_a)
            
            # Store quad data: two triangles making up the quad
            # Triangle 1: v0, v1, v2
            # Triangle 2: v0, v2, v3
            quad_tris = [
                v0, v1, v2,  # First triangle
                v0, v2, v3   # Second triangle
            ]
            
            pixel_quads.append((quad_tris, final_color))
        
        # Draw all pixels efficiently using batch rendering
        # Group pixels by color to reduce draw calls
        if pixel_quads:
            shader_2d_uniform.bind()
            
            # Batch pixels by color to reduce draw calls
            color_groups = {}
            for quad_tris, pixel_color in pixel_quads:
                # Round color to reduce number of batches (optional optimization)
                # For pixel-perfect rendering, we keep exact colors
                color_key = pixel_color
                
                if color_key not in color_groups:
                    color_groups[color_key] = []
                color_groups[color_key].extend(quad_tris)
            
            # Draw each color group as a batch
            for pixel_color, vertices in color_groups.items():
                batch = batch_for_shader(shader_2d_uniform, 'TRIS', {"pos": vertices})
                shader_2d_uniform.bind()
                shader_2d_uniform.uniform_float("color", pixel_color)
                batch.draw(shader_2d_uniform)
        
        # Reset blend mode
        gpu.state.blend_set('NONE')
    
    except Exception as e:
        print(f"UVV: Failed to draw lock icon: {e}")
        import traceback
        traceback.print_exc()
        return


def draw_lock_button(context, trim, opacity):
    """Draw lock button to the left of the active trim, vertically centered
    
    Args:
        context: Blender context
        trim: Trim to draw button for
        opacity: Opacity multiplier
    """
    region = context.region
    if not region:
        return
    rv2d = region.view2d
    if not rv2d:
        return

    # Convert left center of trim to region coordinates
    left_center_u = trim.left
    left_center_v = (trim.bottom + trim.top) / 2.0
    
    # Use same method as text labels for consistency
    screen_pos = trimsheet_utils.view_to_region(context, left_center_u, left_center_v)
    if not screen_pos:
        return

    # Button settings
    BUTTON_OFFSET_X = 16  # 16px to the left of the left edge
    BUTTON_PADDING = 8  # Padding around icon
    ICON_SIZE = 16  # Icon size in pixels
    
    # Make button square
    button_size = ICON_SIZE + BUTTON_PADDING * 2
    BUTTON_RADIUS = 8  # Rounded corner radius (much larger for pill-like appearance)
    
    # Calculate button position (vertically centered, 16px to the left)
    button_x = screen_pos[0] - button_size - BUTTON_OFFSET_X
    button_y = screen_pos[1] - button_size / 2.0
    
    # Enable alpha blending
    gpu.state.blend_set('ALPHA')
    
    # Draw button background with rounded corners (semi-transparent dark background)
    bg_color = (0.15, 0.15, 0.15, 0.85 * opacity)
    
    # Create rounded rectangle vertices for fill
    import math
    num_segments = 16  # Segments per corner
    vertices = []
    
    # Top-left corner arc
    tl_center_x = button_x + BUTTON_RADIUS
    tl_center_y = button_y + BUTTON_RADIUS
    for i in range(num_segments + 1):
        angle = math.pi + (math.pi / 2) * (i / num_segments)
        vx = tl_center_x + BUTTON_RADIUS * math.cos(angle)
        vy = tl_center_y + BUTTON_RADIUS * math.sin(angle)
        vertices.append((vx, vy))
    
    # Top edge
    if button_size > BUTTON_RADIUS * 2:
        vertices.append((button_x + button_size - BUTTON_RADIUS, button_y))
    
    # Top-right corner arc
    tr_center_x = button_x + button_size - BUTTON_RADIUS
    tr_center_y = button_y + BUTTON_RADIUS
    for i in range(num_segments + 1):
        angle = (3 * math.pi / 2) + (math.pi / 2) * (i / num_segments)
        if angle >= 2 * math.pi:
            angle -= 2 * math.pi
        vx = tr_center_x + BUTTON_RADIUS * math.cos(angle)
        vy = tr_center_y + BUTTON_RADIUS * math.sin(angle)
        vertices.append((vx, vy))
    
    # Right edge
    if button_size > BUTTON_RADIUS * 2:
        vertices.append((button_x + button_size, button_y + button_size - BUTTON_RADIUS))
    
    # Bottom-right corner arc
    br_center_x = button_x + button_size - BUTTON_RADIUS
    br_center_y = button_y + button_size - BUTTON_RADIUS
    for i in range(num_segments + 1):
        angle = (math.pi / 2) * (i / num_segments)
        vx = br_center_x + BUTTON_RADIUS * math.cos(angle)
        vy = br_center_y + BUTTON_RADIUS * math.sin(angle)
        vertices.append((vx, vy))
    
    # Bottom edge
    if button_size > BUTTON_RADIUS * 2:
        vertices.append((button_x + BUTTON_RADIUS, button_y + button_size))
    
    # Bottom-left corner arc
    bl_center_x = button_x + BUTTON_RADIUS
    bl_center_y = button_y + button_size - BUTTON_RADIUS
    for i in range(num_segments + 1):
        angle = (math.pi / 2) + (math.pi / 2) * (i / num_segments)
        vx = bl_center_x + BUTTON_RADIUS * math.cos(angle)
        vy = bl_center_y + BUTTON_RADIUS * math.sin(angle)
        vertices.append((vx, vy))
    
    # Left edge
    if button_size > BUTTON_RADIUS * 2:
        vertices.append((button_x, button_y + BUTTON_RADIUS))
    
    # Triangulate for fill using fan from first vertex
    if len(vertices) > 2:
        fill_verts = []
        first_vert = vertices[0]
        for i in range(1, len(vertices) - 1):
            fill_verts.extend([
                first_vert,
                vertices[i],
                vertices[i + 1]
            ])
        
        bg_batch = batch_for_shader(shader_2d_uniform, 'TRIS', {"pos": fill_verts})
        shader_2d_uniform.bind()
        shader_2d_uniform.uniform_float("color", bg_color)
        bg_batch.draw(shader_2d_uniform)
    
    # Draw lock/unlocked icon (centered in button)
    icon_center_x = button_x + button_size / 2.0
    icon_center_y = button_y + button_size / 2.0
    icon_color = (1.0, 1.0, 1.0)  # White
    
    draw_lock_icon(icon_center_x, icon_center_y, ICON_SIZE, trim.locked, icon_color, 0.9 * opacity)
    
    # Reset blend mode
    gpu.state.blend_set('NONE')


# Global flag to track if we need to check for modal start
_need_modal_check = False


def has_selected_uv_islands(context):
    """Check if there are any selected UV islands in edit mode
    
    Returns:
        True if any UV faces/loops are selected, False otherwise
    """
    if context.mode != 'EDIT_MESH':
        return False
    
    import bmesh
    
    use_uv_select_sync = context.tool_settings.use_uv_select_sync
    
    for obj in context.objects_in_mode:
        if obj.type != 'MESH':
            continue
        
        try:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue
            
            if use_uv_select_sync:
                # In sync mode, check mesh face selection
                if any(face.select for face in bm.faces):
                    return True
            else:
                # In non-sync mode, check UV selection
                if any(loop[uv_layer].select for face in bm.faces for loop in face.loops):
                    return True
        except:
            continue
    
    return False


def draw_trim_tooltip(context, trim, mouse_offset=(0, 0), text=None, mouse_pos_region=None):
    """Draw a tooltip near the mouse cursor or trim
    
    Args:
        context: Blender context
        trim: Trim to show tooltip for (or None if custom text)
        mouse_offset: Offset from mouse position (x, y)
        text: Custom text to display (if None, uses trim.name)
        mouse_pos_region: Mouse position in region coordinates (x, y) - if provided, uses this instead of window cursor
    """
    if not context.region:
        return
    
    # Get mouse position
    if mouse_pos_region:
        # Use provided region coordinates directly
        mouse_x, mouse_y = mouse_pos_region
    else:
        # Fallback: approximate center
        mouse_x = context.region.width / 2.0
        mouse_y = context.region.height / 2.0
        
        # Try to get actual mouse position from window
        try:
            # Get mouse position from window manager
            for window in context.window_manager.windows:
                if window == context.window:
                    # Try to get mouse position - but this might not be available in draw handler
                    # So we'll rely on mouse_pos_region parameter
                    break
        except:
            pass
    
    # Calculate tooltip position
    tooltip_x = mouse_x + mouse_offset[0]
    tooltip_y = mouse_y + mouse_offset[1]
    
    # Get text to display
    if text is None:
        text = trim.name if trim else ""
    
    # Setup font
    font_id = 0
    ui_scale = context.preferences.system.ui_scale
    font_size = 12
    
    if bpy.app.version < (3, 4, 0):
        blf.size(font_id, int(font_size * ui_scale), 72)
    else:
        blf.size(font_id, font_size * ui_scale)
    
    # Get text dimensions
    text_width, text_height = blf.dimensions(font_id, text)
    
    # Calculate background rectangle
    padding = 6
    bg_x = tooltip_x - text_width / 2.0 - padding
    bg_y = tooltip_y - text_height / 2.0 - padding
    bg_width = text_width + padding * 2
    bg_height = text_height + padding * 2
    
    # Draw background
    gpu.state.blend_set('ALPHA')
    bg_color = (0.0, 0.0, 0.0, 0.8)  # Semi-transparent black
    bg_verts = [
        (bg_x, bg_y),
        (bg_x + bg_width, bg_y),
        (bg_x + bg_width, bg_y + bg_height),
        (bg_x, bg_y + bg_height),
    ]
    bg_batch = batch_for_shader(shader_2d_uniform, 'TRI_FAN', {"pos": bg_verts})
    shader_2d_uniform.bind()
    shader_2d_uniform.uniform_float("color", bg_color)
    bg_batch.draw(shader_2d_uniform)
    
    # Draw text
    blf.position(font_id, bg_x + padding, bg_y + padding, 0)
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
    blf.draw(font_id, text)
    
    gpu.state.blend_set('NONE')

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

    # DO NOT start modal from draw handler - causes crashes during reload
    # Modal must be started explicitly by user action (clicking trim)

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

        # Draw lock button for active trim (only in Object mode, not in Edit mode)
        if (context.mode == 'OBJECT' and
            material.uvv_trims_index >= 0 and
            material.uvv_trims_index < len(trims)):
            active_trim = trims[material.uvv_trims_index]
            if active_trim.enabled:
                draw_lock_button(context, active_trim, opacity)

        # Draw tooltip if hovering over trim text (only when not in edit mode)
        # Only show after a delay to prevent instant tooltips
        import time
        from .trimsheet_transform_draw import _hover_text_idx, _hover_text_start_time, _mouse_pos_region
        
        TOOLTIP_DELAY = 0.5  # Delay in seconds before showing tooltip
        
        if _hover_text_idx is not None and not settings.trim_edit_mode:
            # Check if enough time has passed since hover started
            if _hover_text_start_time is not None:
                elapsed_time = time.time() - _hover_text_start_time
                if elapsed_time >= TOOLTIP_DELAY:
                    if 0 <= _hover_text_idx < len(trims):
                        trim = trims[_hover_text_idx]
                        if trim.enabled:
                            draw_trim_tooltip(context, trim, mouse_offset=(0, 25))
        
        # Removed ALT tooltip - now using ALT+Click to fit UV islands instead

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
