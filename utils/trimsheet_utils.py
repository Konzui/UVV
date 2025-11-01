"""Trimsheet utility functions"""

import bpy
import blf
import random
from mathutils import Color, Vector


def get_active_material(context):
    """Get the active material from the active object"""
    obj = context.active_object
    if obj and obj.active_material:
        return obj.active_material
    return None


def get_active_image(context):
    """Get the active image from UV editor"""
    if context.space_data and hasattr(context.space_data, 'image'):
        return context.space_data.image
    return None


def get_trims_from_material(material):
    """Get trimsheet collection from material"""
    if material and hasattr(material, 'uvv_trims'):
        return material.uvv_trims
    return None


def get_active_trim(context):
    """Get the active trim from current material"""
    material = get_active_material(context)
    if material and hasattr(material, 'uvv_trims') and hasattr(material, 'uvv_trims_index'):
        trims = material.uvv_trims
        idx = material.uvv_trims_index
        if 0 <= idx < len(trims):
            return trims[idx]
    return None


def get_selected_trims(material):
    """Get all selected trims from material"""
    if material and hasattr(material, 'uvv_trims'):
        return [trim for trim in material.uvv_trims if trim.selected]
    return []


def generate_trim_color(existing_trims):
    """Generate a random color for a new trim"""
    # Generate HSV color with good saturation and value
    color = Color((random.uniform(0.0, 1.0), random.uniform(0.0, 1.0), random.uniform(0.0, 1.0)))
    color.s = min(0.7, max(0.3, color.s))  # Keep saturation between 0.3-0.7
    color.v = min(0.7, max(0.4, color.v))  # Keep value between 0.4-0.7
    return color[:]


def point_in_rect(point, left, top, right, bottom):
    """Check if a point is inside a rectangle"""
    x, y = point
    return left < x < right and bottom < y < top


def region_to_view(context, x, y):
    """Convert region coordinates to UV view coordinates"""
    region = context.region
    view2d = region.view2d
    return view2d.region_to_view(x, y)


def view_to_region(context, x, y):
    """Convert UV view coordinates to region coordinates"""
    region = context.region
    view2d = region.view2d
    return view2d.view_to_region(x, y, clip=False)


def deselect_all_trims(material):
    """Deselect all trims in material"""
    if material and hasattr(material, 'uvv_trims'):
        for trim in material.uvv_trims:
            trim.selected = False


def select_trim(material, index):
    """Select a specific trim by index"""
    if material and hasattr(material, 'uvv_trims'):
        deselect_all_trims(material)
        if 0 <= index < len(material.uvv_trims):
            material.uvv_trims[index].selected = True
            material.uvv_trims_index = index
            return True
    return False


def get_object_materials(obj):
    """Get all materials from object"""
    if obj and hasattr(obj, 'material_slots'):
        return [slot.material for slot in obj.material_slots if slot.material]
    return []


def get_text_alignment_bounds(text_center, trim_width, trim_height, text, is_active, align='center'):
    """Calculate text position bounds based on alignment

    Args:
        text_center: Vector position of text center in screen space
        trim_width: Width of trim rectangle in screen space
        trim_height: Height of trim rectangle in screen space
        text: Text string to measure
        is_active: Whether trim is active
        align: Text alignment ('center', 'top_left', 'top_right', 'bottom_left', 'bottom_right')

    Returns:
        Tuple of (left, top, right, bottom) screen coordinates
    """
    # Get text dimensions
    text_width, text_height = blf.dimensions(0, text)

    # Default to center alignment
    x_offset = 0
    y_offset = 0

    if align == 'center':
        # Center the text
        x_offset = -text_width / 2.0
        y_offset = -text_height / 2.0

        # Slight offset for active trim
        if is_active:
            x_offset += 10
    elif align == 'top_left':
        x_offset = -trim_width / 2.0 + 5
        y_offset = trim_height / 2.0 - text_height - 5
    elif align == 'top_right':
        x_offset = trim_width / 2.0 - text_width - 5
        y_offset = trim_height / 2.0 - text_height - 5
    elif align == 'bottom_left':
        x_offset = -trim_width / 2.0 + 5
        y_offset = -trim_height / 2.0 + 5
    elif align == 'bottom_right':
        x_offset = trim_width / 2.0 - text_width - 5
        y_offset = -trim_height / 2.0 + 5

    # Calculate final bounds
    left = text_center.x + x_offset
    bottom = text_center.y + y_offset
    right = left + text_width
    top = bottom + text_height

    return left, top, right, bottom


# ============================================================================
# Trim Tagging System - REMOVED
# ============================================================================
