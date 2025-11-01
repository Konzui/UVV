"""Snapping utilities for trimsheet transform operations"""

# Snap threshold in UV space (approximately 5 pixels at default zoom)
SNAP_THRESHOLD = 0.005


def find_snap_target_vertical(trims, active_trim_index, edge_value, edge_type='left'):
    """Find the nearest vertical edge to snap to

    Args:
        trims: Collection of all trims
        active_trim_index: Index of trim being transformed (to skip)
        edge_value: Current X coordinate of the edge being dragged
        edge_type: 'left' or 'right' - which edge is being dragged

    Returns:
        Snapped X coordinate, or original value if no snap target found
    """
    closest_snap = None
    closest_distance = SNAP_THRESHOLD

    for idx, trim in enumerate(trims):
        # Skip the active trim and disabled trims
        if idx == active_trim_index or not trim.enabled:
            continue

        # Check all vertical edges of this trim
        edges = [trim.left, trim.right]

        for edge in edges:
            distance = abs(edge - edge_value)
            if distance < closest_distance:
                closest_distance = distance
                closest_snap = edge

    return closest_snap if closest_snap is not None else edge_value


def find_snap_target_horizontal(trims, active_trim_index, edge_value, edge_type='top'):
    """Find the nearest horizontal edge to snap to

    Args:
        trims: Collection of all trims
        active_trim_index: Index of trim being transformed (to skip)
        edge_value: Current Y coordinate of the edge being dragged
        edge_type: 'top' or 'bottom' - which edge is being dragged

    Returns:
        Snapped Y coordinate, or original value if no snap target found
    """
    closest_snap = None
    closest_distance = SNAP_THRESHOLD

    for idx, trim in enumerate(trims):
        # Skip the active trim and disabled trims
        if idx == active_trim_index or not trim.enabled:
            continue

        # Check all horizontal edges of this trim
        edges = [trim.top, trim.bottom]

        for edge in edges:
            distance = abs(edge - edge_value)
            if distance < closest_distance:
                closest_distance = distance
                closest_snap = edge

    return closest_snap if closest_snap is not None else edge_value


def find_snap_target_position(trims, active_trim_index, position_x, position_y):
    """Find snap targets for both X and Y position (for moving)

    Args:
        trims: Collection of all trims
        active_trim_index: Index of trim being transformed (to skip)
        position_x: Current X coordinate
        position_y: Current Y coordinate

    Returns:
        Tuple of (snapped_x, snapped_y)
    """
    snapped_x = find_snap_target_vertical(trims, active_trim_index, position_x)
    snapped_y = find_snap_target_horizontal(trims, active_trim_index, position_y)

    return snapped_x, snapped_y
