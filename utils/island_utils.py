import bmesh
import bpy
from mathutils import Vector
from .generic_helpers import face_indexes_by_sel_mode


def get_uv_islands_from_selected_faces(bm, uv_layer):
    """Get UV islands that contain selected faces"""
    if not uv_layer:
        return []

    selected_faces = [face for face in bm.faces if face.select]
    if not selected_faces:
        return []

    # Clear tags for island detection
    for face in bm.faces:
        face.tag = False

    islands = []

    for start_face in selected_faces:
        if start_face.tag:
            continue  # Already processed

        # Find connected island
        island = []
        stack = [start_face]
        start_face.tag = True

        while stack:
            current_face = stack.pop()
            island.append(current_face)

            # Check adjacent faces through UV connectivity
            for loop in current_face.loops:
                uv_coord = loop[uv_layer].uv

                # Find faces sharing this UV coordinate
                for other_face in bm.faces:
                    if other_face.tag or other_face == current_face:
                        continue

                    # Check if any loop in other_face shares the UV coordinate
                    for other_loop in other_face.loops:
                        other_uv = other_loop[uv_layer].uv
                        if (uv_coord - other_uv).length < 0.0001:  # UV tolerance
                            # Found connected face
                            other_face.tag = True
                            stack.append(other_face)
                            break

        if island:
            islands.append(island)

    return islands


def get_island_boundary_loops(island_faces, uv_layer):
    """Get the boundary loops of a UV island"""
    boundary_loops = []

    for face in island_faces:
        for loop in face.loops:
            # Check if this edge is on the boundary
            edge = loop.edge
            adjacent_faces = [f for f in edge.link_faces if f in island_faces]

            if len(adjacent_faces) == 1:  # Boundary edge
                boundary_loops.append(loop)

    return boundary_loops


def get_island_center(island_faces, uv_layer):
    """Calculate the center point of a UV island"""
    if not island_faces:
        return Vector((0, 0))

    total_uv = Vector((0, 0))
    loop_count = 0

    for face in island_faces:
        for loop in face.loops:
            total_uv += loop[uv_layer].uv
            loop_count += 1

    if loop_count == 0:
        return Vector((0, 0))

    return total_uv / loop_count


def scale_island_around_center(island_faces, uv_layer, scale_factor):
    """Scale a UV island around its center"""
    if not island_faces or scale_factor <= 0:
        return

    # Get island center
    center = get_island_center(island_faces, uv_layer)

    # Scale all UV coordinates in the island
    for face in island_faces:
        for loop in face.loops:
            uv = loop[uv_layer].uv
            direction = uv - center
            loop[uv_layer].uv = center + direction * scale_factor


def uv_bound_edges_indexes(faces, uv_layer):
    """Return indexes of border edges of given island (faces) from current UV Layer"""
    if faces:
        edges = {edge for face in faces for edge in face.edges if edge.link_loops}
        return [edge.index for edge in edges
                if edge.link_loops[0][uv_layer].uv
                != edge.link_loops[0].link_loop_radial_next.link_loop_next[uv_layer].uv
                or edge.link_loops[len(edge.link_loops)-1][uv_layer].uv
                != edge.link_loops[len(edge.link_loops)-1].link_loop_radial_next.link_loop_next[uv_layer].uv]
    return []


def get_island(context, bm, uv_layer):
    """Return island(s) by selected faces, edges or vertices"""
    bm.faces.ensure_lookup_table()
    selection = [bm.faces[index] for index in face_indexes_by_sel_mode(context, bm)]
    return zen_get_islands(bm, selection, has_selected_faces=True)


def zen_get_islands(
    bm: bmesh.types.BMesh,
    _selection: list,
    has_selected_faces: bool = False,
    selected_only: bool = False,
    _sorted: bool = False
    ) -> list:
    """Get UV islands from bmesh - Zen UV pattern"""
    uv_layer = bm.loops.layers.uv.verify()
    if not selected_only:
        _bounds = uv_bound_edges_indexes(bm.faces, uv_layer)
    else:
        _bounds = get_bound_edges([e for f in _selection for e in f.edges])
    bm.edges.ensure_lookup_table()
    for edge in bm.edges:
        edge.tag = False
    # Tag all edges in uv borders
    for index in _bounds:
        bm.edges[index].tag = True

    _islands = []
    if has_selected_faces:
        faces = set(_selection)
    else:
        faces = set(bm.faces)
    while len(faces) != 0:
        init_face = faces.pop()
        island = {init_face}
        stack = [init_face]
        while len(stack) != 0:
            face = stack.pop()
            for e in face.edges:
                if not e.tag:
                    for f in e.link_faces:
                        if f not in island:
                            stack.append(f)
                            island.add(f)
        for f in island:
            faces.discard(f)
        if True in [f.hide for f in island]:
            continue
        _islands.append(list(island))  # Convert to list for consistency
    for index in _bounds:
        bm.edges[index].tag = False

    if _sorted:
        return [sorted(island, key=lambda f: f.index) for island in _islands]

    return _islands


def get_islands_ignore_context(bm, is_include_hidden=False):
    """Get all UV islands ignoring selection context - Zen UV pattern"""
    uv_layer = bm.loops.layers.uv.verify()
    _bounds = uv_bound_edges_indexes(bm.faces, uv_layer)

    bm.edges.ensure_lookup_table()
    for edge in bm.edges:
        edge.tag = False

    # Tag all UV border edges
    for index in _bounds:
        bm.edges[index].tag = True

    _islands = []
    faces = set(bm.faces)

    while len(faces) != 0:
        init_face = faces.pop()
        island = {init_face}
        stack = [init_face]

        while len(stack) != 0:
            face = stack.pop()
            for e in face.edges:
                if not e.tag:
                    for f in e.link_faces:
                        if f not in island:
                            stack.append(f)
                            island.add(f)

        for f in island:
            faces.discard(f)

        # Skip hidden islands unless requested
        if not is_include_hidden and True in [f.hide for f in island]:
            continue

        _islands.append(list(island))

    # Clean up tags
    for index in _bounds:
        bm.edges[index].tag = False

    return _islands


def get_bound_edges(edges_from_polygons):
    """Get boundary edges from polygon edges"""
    boundary_edges = []
    for edge in edges_from_polygons:
        if False in [f.select for f in edge.link_faces] or edge.is_boundary:
            boundary_edges.append(edge.index)
    return boundary_edges


def get_islands_non_manifold(bm: bmesh.types.BMesh, faces: list, uv_layer) -> list:
    """
    Get UV islands using non-manifold detection (OR logic).
    
    This function uses OR logic for UV connectivity, allowing faces connected by 
    partially-welded edges to remain in the same island. This is essential for 
    weld operations to properly detect and process partially-split UV edges.
    
    Based on uniV's calc_iter_non_manifold_ex algorithm.
    
    Args:
        bm: BMesh object
        faces: List of faces to process
        uv_layer: UV layer to use for connectivity check
    
    Returns:
        List of islands, where each island is a list of faces
    """
    # Tag faces for processing
    for face in bm.faces:
        face.tag = False
    for face in faces:
        face.tag = True
    
    islands = []
    
    for face in bm.faces:
        if not face.tag:  # Skip untagged and already processed faces
            continue
        face.tag = False  # Mark as processed
        
        # Start new island
        island = []
        parts_of_island = [face]  # Current batch of faces to process
        temp = []  # Temporary storage for next batch
        
        while parts_of_island:  # Process until no more connected faces
            for f in parts_of_island:
                for loop in f.loops:  # Check all neighboring faces
                    shared_crn = loop.link_loop_radial_prev
                    neighbor_face = shared_crn.face
                    
                    if not neighbor_face.tag:
                        continue
                    
                    # Non-manifold connectivity check: OR logic
                    # Faces are connected if AT LEAST ONE vertex of the shared edge matches in UV space
                    uv_match_a = loop[uv_layer].uv == shared_crn.link_loop_next[uv_layer].uv
                    uv_match_b = loop.link_loop_next[uv_layer].uv == shared_crn[uv_layer].uv
                    
                    if uv_match_a or uv_match_b:
                        temp.append(neighbor_face)
                        neighbor_face.tag = False
            
            island.extend(parts_of_island)
            parts_of_island = temp
            temp = []
        
        if island:
            # Skip hidden islands
            if not any(f.hide for f in island):
                islands.append(island)
    
    return islands


def get_3d_mesh_islands(bm: bmesh.types.BMesh, faces: list) -> list:
    """
    Get 3D mesh islands using face connectivity in 3D space.
    
    This function groups faces that are connected through shared edges in 3D space,
    regardless of UV connectivity. This is used for MeshIsland operations.
    
    Args:
        bm: BMesh object
        faces: List of faces to process
    
    Returns:
        List of islands, where each island is a list of faces
    """
    # Tag faces for processing
    for face in bm.faces:
        face.tag = False
    for face in faces:
        face.tag = True
    
    islands = []
    
    for face in bm.faces:
        if not face.tag:  # Skip untagged and already processed faces
            continue
        face.tag = False  # Mark as processed
        
        # Start new island
        island = []
        parts_of_island = [face]  # Current batch of faces to process
        temp = []  # Temporary storage for next batch
        
        while parts_of_island:  # Process until no more connected faces
            for f in parts_of_island:
                for edge in f.edges:  # Check all edges of current face
                    for neighbor_face in edge.link_faces:
                        if neighbor_face == f or not neighbor_face.tag:
                            continue
                        
                        # Faces are connected if they share an edge in 3D space
                        temp.append(neighbor_face)
                        neighbor_face.tag = False
            
            island.extend(parts_of_island)
            parts_of_island = temp
            temp = []
        
        if island:
            # Skip hidden islands
            if not any(f.hide for f in island):
                islands.append(island)
    
    return islands