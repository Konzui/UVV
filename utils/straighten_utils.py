# Straighten utility functions - ported from Mio3 UV addon
from mathutils import Vector


def straight_uv_nodes(node_group, mode="GEOMETRY", keep_length=False, center=False):
    """Straighten UV nodes to a line

    Args:
        node_group: UVNodeGroup containing the nodes to straighten
        mode: Alignment mode - "GEOMETRY" (3D distance), "EVEN" (equal spacing), or "NONE" (UV distance)
        keep_length: Whether to preserve the original UV length
        center: Whether to center the result at the original position
    """
    uv_nodes = list(node_group.nodes)
    uv_layer = node_group.uv_layer

    # Find start node (endpoint with only one neighbor)
    start_node = next((node for node in uv_nodes if len(node.neighbors) == 1), None)
    if start_node is None:
        start_node = min(uv_nodes)

    # Order nodes from start to end
    ordered_nodes = []
    visited = set()
    current_node = start_node
    while len(ordered_nodes) < len(uv_nodes):
        if current_node not in visited:
            ordered_nodes.append(current_node)
            visited.add(current_node)
        next_node = next((n for n in current_node.neighbors if n not in visited), None)
        if next_node is None:
            unvisited = set(uv_nodes) - visited
            if unvisited:
                current_node = min(unvisited, key=lambda n: (n.uv - current_node.uv).length)
            else:
                break
        else:
            current_node = next_node

    start_uv = ordered_nodes[0].uv
    end_uv = ordered_nodes[-1].uv
    direction = end_uv - start_uv

    # Determine if we should align horizontally or vertically
    if abs(direction.x) > abs(direction.y):
        direction.y = 0
    else:
        direction.x = 0

    # Calculate original length if preserving
    original_uv_length = (
        sum((ordered_nodes[i + 1].uv - ordered_nodes[i].uv).length for i in range(len(ordered_nodes) - 1))
        if keep_length
        else 0
    )

    if len(ordered_nodes) <= 1:
        return

    # Calculate new positions based on mode
    if mode == "GEOMETRY":
        # Align based on 3D geometry distances
        total_3d_distance = 0
        cumulative_3d_distances = [0]
        for i in range(1, len(ordered_nodes)):
            dist = (ordered_nodes[i].vert.co - ordered_nodes[i - 1].vert.co).length
            total_3d_distance += dist
            cumulative_3d_distances.append(total_3d_distance)

        if total_3d_distance <= 0:
            return

        new_positions = {}
        for i, node in enumerate(ordered_nodes):
            t = cumulative_3d_distances[i] / total_3d_distance
            new_position = start_uv + direction * t
            new_positions[node] = new_position

    elif mode == "EVEN":
        # Even spacing
        new_positions = {}
        for i, node in enumerate(ordered_nodes):
            t = i / (len(ordered_nodes) - 1)
            new_position = start_uv + direction * t
            new_positions[node] = new_position

    else:  # mode == "NONE"
        # Maintain relative UV distances
        total_uv_distance = sum(
            (ordered_nodes[i + 1].uv - ordered_nodes[i].uv).length for i in range(len(ordered_nodes) - 1)
        )
        if total_uv_distance <= 0:
            return

        new_positions = {}
        cumulative_uv_distance = 0
        for i, node in enumerate(ordered_nodes):
            if i > 0:
                cumulative_uv_distance += (node.uv - ordered_nodes[i - 1].uv).length
            t = cumulative_uv_distance / total_uv_distance
            new_position = start_uv + direction * t
            new_positions[node] = new_position

    # Scale to preserve original length if requested
    if keep_length:
        new_uv_length = sum(
            (new_positions[ordered_nodes[i + 1]] - new_positions[ordered_nodes[i]]).length
            for i in range(len(ordered_nodes) - 1)
        )
        scale_factor = original_uv_length / new_uv_length if new_uv_length > 0 else 1
        for node, new_position in new_positions.items():
            scaled_position = start_uv + (new_position - start_uv) * scale_factor
            new_positions[node] = scaled_position

    # Center the result if requested
    if center:
        original_center = Vector((0, 0))
        for node in ordered_nodes:
            original_center += node.uv
        original_center /= len(ordered_nodes)

        aligned_center = Vector((0, 0))
        for pos in new_positions.values():
            aligned_center += pos
        aligned_center /= len(new_positions)

        center_offset = original_center - aligned_center

        for node in new_positions:
            new_positions[node] += center_offset

    # Apply new positions
    for node, new_position in new_positions.items():
        node.uv = new_position
