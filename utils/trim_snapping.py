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
        Tuple of (snapped_x, snap_x) where:
        - snapped_x: Snapped X coordinate, or original value if no snap target found
        - snap_x: The snap target X coordinate if snapping occurred, None otherwise
    """
    closest_snap = None
    closest_distance = SNAP_THRESHOLD

    # Check UV space boundaries (0.0 and 1.0) - always snap to these
    uv_boundaries = [0.0, 1.0]
    for boundary in uv_boundaries:
        distance = abs(boundary - edge_value)
        if distance < closest_distance:
            closest_distance = distance
            closest_snap = boundary

    # Check all other trim edges
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

    if closest_snap is not None:
        return closest_snap, closest_snap
    return edge_value, None


def find_snap_target_horizontal(trims, active_trim_index, edge_value, edge_type='top'):
    """Find the nearest horizontal edge to snap to

    Args:
        trims: Collection of all trims
        active_trim_index: Index of trim being transformed (to skip)
        edge_value: Current Y coordinate of the edge being dragged
        edge_type: 'top' or 'bottom' - which edge is being dragged

    Returns:
        Tuple of (snapped_y, snap_y) where:
        - snapped_y: Snapped Y coordinate, or original value if no snap target found
        - snap_y: The snap target Y coordinate if snapping occurred, None otherwise
    """
    closest_snap = None
    closest_distance = SNAP_THRESHOLD

    # Check UV space boundaries (0.0 and 1.0) - always snap to these
    uv_boundaries = [0.0, 1.0]
    for boundary in uv_boundaries:
        distance = abs(boundary - edge_value)
        if distance < closest_distance:
            closest_distance = distance
            closest_snap = boundary

    # Check all other trim edges
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

    if closest_snap is not None:
        return closest_snap, closest_snap
    return edge_value, None


def find_snap_target_position(trims, active_trim_index, position_x, position_y):
    """Find snap targets for both X and Y position (for moving)

    Args:
        trims: Collection of all trims
        active_trim_index: Index of trim being transformed (to skip)
        position_x: Current X coordinate
        position_y: Current Y coordinate

    Returns:
        Tuple of (snapped_x, snapped_y, snap_x, snap_y) where:
        - snapped_x, snapped_y: Snapped coordinates
        - snap_x, snap_y: Snap target coordinates if snapping occurred, None otherwise
    """
    snapped_x, snap_x = find_snap_target_vertical(trims, active_trim_index, position_x)
    snapped_y, snap_y = find_snap_target_horizontal(trims, active_trim_index, position_y)

    return snapped_x, snapped_y, snap_x, snap_y
