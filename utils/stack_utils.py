"""Stack utility functions for UV island stacking and similarity detection

Uses ZenUV-style similarity index calculation:
- Geometry factor: vert_count + edge_count + face_count
- Area/perimeter factor: float('0.' + str(area + perimeter).replace('.', ''))
- Diagonal improver for quads: sum of diagonal lengths
- Islands are grouped by exact sim_index match
"""

import bpy
import bmesh
import json
import hashlib
from mathutils import Vector, Matrix
from math import sqrt, pi, cos, sin, atan2
from collections import defaultdict


class IslandData:
    """Represents a UV island with its properties"""

    def __init__(self, obj, faces, uv_layer):
        self.obj = obj
        self.faces = faces
        self.uv_layer = uv_layer
        self.face_indices = [f.index for f in faces]

        # Calculate properties
        self._calc_properties()

    def _calc_properties(self):
        """Calculate island properties for comparison - ZenUV style"""
        # UV bounding box
        min_uv = Vector((float('inf'), float('inf')))
        max_uv = Vector((float('-inf'), float('-inf')))

        for face in self.faces:
            for loop in face.loops:
                uv = loop[self.uv_layer].uv
                min_uv.x = min(min_uv.x, uv.x)
                min_uv.y = min(min_uv.y, uv.y)
                max_uv.x = max(max_uv.x, uv.x)
                max_uv.y = max(max_uv.y, uv.y)

        self.bbox_min = min_uv
        self.bbox_max = max_uv
        self.bbox_size = max_uv - min_uv
        self.center = (min_uv + max_uv) / 2.0

        # Mesh properties (geometry factor)
        self.face_count = len(self.faces)
        self.vert_count = len(set(v for f in self.faces for v in f.verts))
        self.edge_count = len(set(e for f in self.faces for e in f.edges))

        # Calculate mesh area and perimeter
        self.mesh_area = round(sum([f.calc_area() for f in self.faces]), 3)
        self.perimeter = self._calc_perimeter()

        # Calculate ZenUV-style sim_index
        self.sim_index = self._calc_sim_index()

    def _calc_perimeter(self):
        """Calculate perimeter from UV boundary edges - Exact ZenUV copy"""
        from ZenUV.utils import get_uv_islands as island_util

        # Use ZenUV's exact boundary edge detection
        edge_indices = island_util.get_uv_bound_edges_indexes(self.faces, self.uv_layer)

        # Calculate perimeter from boundary edges
        edges = {e for f in self.faces for e in f.edges if e.index in edge_indices}
        perimeter = round(sum([e.calc_length() for e in edges]), 3)
        return perimeter

    def _calc_sim_index(self):
        """Calculate ZenUV-style similarity index"""
        # Geometry factor: total count of verts + edges + faces
        geometry_factor = self.vert_count + self.edge_count + self.face_count

        # Part 2: Create decimal from area + perimeter
        # Example: area=5.123 + perimeter=10.456 = 15.579
        # Convert to: float('0.15579') = 0.15579
        sim_index_p2 = float('0.' + str(self.mesh_area + self.perimeter).replace('.', ''))

        # Special case: quad islands get diagonal improver
        if self.face_count == 1:
            face = self.faces[0]
            if len(face.verts) == 4:
                # Calculate diagonal distances
                loops = list(face.loops)
                diagonal1 = (loops[0].vert.co - loops[2].vert.co).magnitude
                diagonal2 = (loops[1].vert.co - loops[3].vert.co).magnitude
                improver = round(diagonal1 + diagonal2, 3)
                sim_index_p2 += improver

        return geometry_factor + sim_index_p2

    def is_similar(self, other, threshold=0.1):
        """Check if this island is similar to another island using threshold-based comparison"""
        # Calculate similarity difference based on sim_index
        diff = abs(self.sim_index - other.sim_index)
        
        # Normalize by average sim_index to get percentage difference
        avg_sim = (abs(self.sim_index) + abs(other.sim_index)) / 2.0
        if avg_sim > 0:
            similarity_diff = diff / avg_sim
        else:
            similarity_diff = diff
        
        # Consider similar if difference is within threshold
        return similarity_diff <= threshold

    def get_identifier(self):
        """Generate stable identifier for this island (object_name + sorted_face_indices)"""
        sorted_faces = sorted(self.face_indices)
        identifier_data = {
            'object_name': self.obj.name,
            'face_indices': sorted_faces
        }
        # Create hash from identifier data
        identifier_str = json.dumps(identifier_data, sort_keys=True)
        identifier_hash = hashlib.md5(identifier_str.encode()).hexdigest()
        return identifier_hash

    def get_identifier_data(self):
        """Get raw identifier data for storage"""
        return {
            'object_name': self.obj.name,
            'face_indices': sorted(self.face_indices)
        }

    def calc_distortion(self):
        """Calculate UV distortion for this island - uses fresh BMesh data"""
        distortion = 0.0

        try:
            # Get fresh BMesh data to avoid stale references
            bm = bmesh.from_edit_mesh(self.obj.data)
            bm.faces.ensure_lookup_table()

            # Get fresh faces using stored indices
            fresh_faces = [bm.faces[idx] for idx in self.face_indices]

            for face in fresh_faces:
                for loop in face.loops:
                    # Mesh angle
                    mesh_angle = loop.calc_angle()

                    # UV angle
                    vec_0 = (loop.link_loop_next[self.uv_layer].uv - loop[self.uv_layer].uv).normalized()
                    vec_1 = (loop.link_loop_prev[self.uv_layer].uv - loop[self.uv_layer].uv).normalized()
                    uv_angle = vec_0.angle(vec_1, 0.00001)

                    distortion += abs(mesh_angle - uv_angle)
        except (ReferenceError, IndexError):
            # If faces are invalid, return high distortion
            return float('inf')

        # Position penalty (favor islands closer to origin)
        pos_penalty = self.center.length * 0.1

        return distortion + pos_penalty

    def calc_uv_area(self):
        """Calculate UV area of the island using shoelace formula
        
        Returns:
            float: Total UV area
        """
        area = 0.0
        
        for face in self.faces:
            if len(face.loops) >= 3:
                # Get UV coordinates for all loops in this face
                uvs = [loop[self.uv_layer].uv for loop in face.loops]
                
                # Calculate face area using shoelace formula
                face_area = 0.0
                for i in range(len(uvs)):
                    j = (i + 1) % len(uvs)
                    face_area += uvs[i].x * uvs[j].y
                    face_area -= uvs[j].x * uvs[i].y
                
                area += abs(face_area) * 0.5
        
        self.uv_area = area
        return area

    def select(self, state=True):
        """Select or deselect this island - uses fresh BMesh data"""
        sync_uv = bpy.context.scene.tool_settings.use_uv_select_sync

        try:
            # Get fresh BMesh data to avoid stale references
            bm = bmesh.from_edit_mesh(self.obj.data)
            bm.faces.ensure_lookup_table()

            # Get fresh faces using stored indices
            fresh_faces = [bm.faces[idx] for idx in self.face_indices]

            if sync_uv:
                for face in fresh_faces:
                    face.select = state
            else:
                for face in fresh_faces:
                    for loop in face.loops:
                        loop[self.uv_layer].select = state
        except (ReferenceError, IndexError):
            # Face indices might be invalid after mesh edits - skip
            pass

    def get_edge_orientation(self):
        """Calculate the dominant edge orientation angle of this island (in radians)

        Uses the longest edge as the primary orientation reference
        """
        try:
            # Get fresh BMesh data
            bm = bmesh.from_edit_mesh(self.obj.data)
            bm.faces.ensure_lookup_table()
            fresh_faces = [bm.faces[idx] for idx in self.face_indices]

            # Find the longest edge to determine primary orientation
            longest_edge_length = 0.0
            longest_edge_angle = 0.0

            for face in fresh_faces:
                for loop in face.loops:
                    uv1 = loop[self.uv_layer].uv
                    uv2 = loop.link_loop_next[self.uv_layer].uv

                    # Calculate edge vector and angle
                    edge_vec = uv2 - uv1
                    edge_length = edge_vec.length

                    if edge_length > longest_edge_length:
                        longest_edge_length = edge_length
                        longest_edge_angle = atan2(edge_vec.y, edge_vec.x)

            return longest_edge_angle

        except (ReferenceError, IndexError):
            return 0.0

    def _calculate_bbox_match_score(self, master, rotation_angle):
        """Calculate how well this island matches master after a given rotation

        Lower score = better match
        Compares vertex positions RELATIVE to each island's center (shape matching)

        Args:
            master: Master island to compare against
            rotation_angle: Rotation angle to test (in radians)

        Returns:
            Float score (lower is better) - average distance between corresponding vertices
        """
        try:
            # Build rotation matrix
            cos_a = cos(rotation_angle)
            sin_a = sin(rotation_angle)
            rot_matrix = Matrix(((cos_a, -sin_a), (sin_a, cos_a)))

            # Get fresh BMesh data for both islands
            self_bm = bmesh.from_edit_mesh(self.obj.data)
            self_bm.faces.ensure_lookup_table()
            self_faces = [self_bm.faces[idx] for idx in self.face_indices]

            master_bm = bmesh.from_edit_mesh(master.obj.data)
            master_bm.faces.ensure_lookup_table()
            master_faces = [master_bm.faces[idx] for idx in master.face_indices]

            # Collect this island's UV positions RELATIVE TO ITS CENTER, then rotate
            self_uvs = []
            for face in self_faces:
                for loop in face.loops:
                    uv = loop[self.uv_layer].uv.copy()
                    # Make relative to center, then rotate
                    uv -= self.center
                    uv = rot_matrix @ uv
                    # Don't translate - we're comparing shapes, not positions
                    self_uvs.append(uv)

            # Collect master island's UV positions RELATIVE TO ITS CENTER
            master_uvs = []
            for face in master_faces:
                for loop in face.loops:
                    uv = loop[master.uv_layer].uv.copy()
                    # Make relative to center
                    uv -= master.center
                    master_uvs.append(uv)

            # Calculate total distance between all corresponding vertices
            # Since topology is identical, we can compare vertex by vertex
            if len(self_uvs) != len(master_uvs):
                # Fallback to bbox comparison if vertex counts don't match
                return self._calculate_bbox_simple_score(master, rotation_angle)

            total_distance = 0.0
            for self_uv, master_uv in zip(self_uvs, master_uvs):
                dist = (self_uv - master_uv).length
                total_distance += dist

            # Return average distance per vertex
            avg_distance = total_distance / len(self_uvs)
            return avg_distance

        except (ReferenceError, IndexError):
            # Fallback to simple bbox comparison
            return self._calculate_bbox_simple_score(master, rotation_angle)

    def _calculate_bbox_simple_score(self, master, rotation_angle):
        """Simple bounding box aspect ratio comparison (fallback method)"""
        cos_a = cos(rotation_angle)
        sin_a = sin(rotation_angle)
        rot_matrix = Matrix(((cos_a, -sin_a), (sin_a, cos_a)))

        corners = [
            Vector((self.bbox_min.x - self.center.x, self.bbox_min.y - self.center.y)),
            Vector((self.bbox_max.x - self.center.x, self.bbox_min.y - self.center.y)),
            Vector((self.bbox_max.x - self.center.x, self.bbox_max.y - self.center.y)),
            Vector((self.bbox_min.x - self.center.x, self.bbox_max.y - self.center.y))
        ]

        rotated_corners = [rot_matrix @ c for c in corners]

        rot_width = max(c.x for c in rotated_corners) - min(c.x for c in rotated_corners)
        rot_height = max(c.y for c in rotated_corners) - min(c.y for c in rotated_corners)

        master_aspect = master.bbox_size.x / max(master.bbox_size.y, 0.001)
        rot_aspect = rot_width / max(rot_height, 0.001)

        return abs(master_aspect - rot_aspect)

    def calculate_best_rotation(self, master, rotation_mode='SNAP_90'):
        """Calculate the best rotation angle to match master island

        Args:
            master: Master island to match
            rotation_mode: 'SNAP_90', 'OPTIMAL', or 'OPTIMAL_MATCH'

        Returns:
            Best rotation angle in radians
        """
        if rotation_mode == 'NONE':
            return 0.0

        if rotation_mode == 'SNAP_90':
            # Get orientations of both islands
            self_angle = self.get_edge_orientation()
            master_angle = master.get_edge_orientation()

            # Calculate base rotation difference
            rotation_diff = master_angle - self_angle

            # Print debug info
            print(f"[ROTATION] Self angle: {self_angle:.3f} rad ({self_angle * 180 / pi:.1f}°)")
            print(f"[ROTATION] Master angle: {master_angle:.3f} rad ({master_angle * 180 / pi:.1f}°)")
            print(f"[ROTATION] Rotation diff: {rotation_diff:.3f} rad ({rotation_diff * 180 / pi:.1f}°)")

            # Snap to nearest 90° increment
            angles_90 = [0, pi/2, pi, 3*pi/2]  # 0°, 90°, 180°, 270°

            # Find the closest 90° angle to the rotation difference
            best_angle = min(angles_90, key=lambda a: abs((rotation_diff - a + pi) % (2*pi) - pi))

            print(f"[ROTATION] Best snap angle: {best_angle:.3f} rad ({best_angle * 180 / pi:.1f}°)")
            return best_angle

        elif rotation_mode == 'OPTIMAL_MATCH':
            # Test both no-rotation and 90° snapping, pick the one with best match
            print(f"[ROTATION] OPTIMAL_MATCH mode - testing no-rotation vs 90° snap")

            # Option 1: No rotation (keep original)
            no_rotation_score = self._calculate_bbox_match_score(master, 0.0)
            print(f"[ROTATION] No rotation score: {no_rotation_score:.4f}")

            # Option 2: Use 90° snapping
            self_angle = self.get_edge_orientation()
            master_angle = master.get_edge_orientation()
            rotation_diff = master_angle - self_angle
            angles_90 = [0, pi/2, pi, 3*pi/2]
            snap_angle = min(angles_90, key=lambda a: abs((rotation_diff - a + pi) % (2*pi) - pi))
            snap_score = self._calculate_bbox_match_score(master, snap_angle)
            print(f"[ROTATION] 90° snap ({snap_angle * 180 / pi:.1f}°) score: {snap_score:.4f}")

            # Pick the option with lower score (better match)
            if no_rotation_score <= snap_score:
                print(f"[ROTATION] Choosing no rotation (better match)")
                return 0.0
            else:
                print(f"[ROTATION] Choosing 90° snap at {snap_angle * 180 / pi:.1f}° (better match)")
                return snap_angle

        elif rotation_mode == 'OPTIMAL':
            # Try all 90° rotations and pick the one with best bounding box match
            angles_to_test = [0, pi/2, pi, 3*pi/2]

            best_angle = 0.0
            best_score = float('inf')

            for test_angle in angles_to_test:
                # Calculate what the bbox would be after this rotation
                cos_a = cos(test_angle)
                sin_a = sin(test_angle)

                # Rotate bbox corners
                corners = [
                    Vector((self.bbox_min.x - self.center.x, self.bbox_min.y - self.center.y)),
                    Vector((self.bbox_max.x - self.center.x, self.bbox_min.y - self.center.y)),
                    Vector((self.bbox_max.x - self.center.x, self.bbox_max.y - self.center.y)),
                    Vector((self.bbox_min.x - self.center.x, self.bbox_max.y - self.center.y))
                ]

                rotated_corners = []
                for corner in corners:
                    rotated_x = corner.x * cos_a - corner.y * sin_a
                    rotated_y = corner.x * sin_a + corner.y * cos_a
                    rotated_corners.append(Vector((rotated_x, rotated_y)))

                # Calculate rotated bbox size
                rot_min_x = min(c.x for c in rotated_corners)
                rot_max_x = max(c.x for c in rotated_corners)
                rot_min_y = min(c.y for c in rotated_corners)
                rot_max_y = max(c.y for c in rotated_corners)

                rot_width = rot_max_x - rot_min_x
                rot_height = rot_max_y - rot_min_y

                # Score based on how well it matches master bbox aspect ratio
                master_aspect = master.bbox_size.x / max(master.bbox_size.y, 0.001)
                rot_aspect = rot_width / max(rot_height, 0.001)

                # Lower score is better (smaller difference in aspect ratio)
                score = abs(master_aspect - rot_aspect)

                if score < best_score:
                    best_score = score
                    best_angle = test_angle

            return best_angle

        return 0.0

    def transform_to_match(self, master, rotation_mode='SNAP_90', scale_mode='UNIFORM', match_rotation=True, match_scale=True):
        """Transform this island to match the master island - uses fresh BMesh data

        Args:
            master: Master island to match
            rotation_mode: 'NONE', 'SNAP_90', or 'OPTIMAL'
            scale_mode: 'UNIFORM', 'BOUNDS', or 'NONE'
            match_rotation: Whether to apply rotation matching
            match_scale: Whether to apply scale matching
        """
        try:
            # Get fresh BMesh data to avoid stale references
            bm = bmesh.from_edit_mesh(self.obj.data)
            bm.faces.ensure_lookup_table()

            # Get fresh faces using stored indices
            fresh_faces = [bm.faces[idx] for idx in self.face_indices]

            # Calculate rotation angle if needed
            rotation_angle = 0.0
            if match_rotation and rotation_mode != 'NONE':
                rotation_angle = self.calculate_best_rotation(master, rotation_mode)

            # Build rotation matrix
            cos_a = cos(rotation_angle)
            sin_a = sin(rotation_angle)
            rot_matrix = Matrix(((cos_a, -sin_a), (sin_a, cos_a)))

            # Calculate scale factors
            scale_x = 1.0
            scale_y = 1.0

            if match_scale and scale_mode != 'NONE':
                if scale_mode == 'UNIFORM':
                    # Calculate what the bbox would be after rotation
                    if rotation_angle != 0.0:
                        # Rotate bbox to get actual size after rotation
                        corners = [
                            Vector((self.bbox_min.x - self.center.x, self.bbox_min.y - self.center.y)),
                            Vector((self.bbox_max.x - self.center.x, self.bbox_min.y - self.center.y)),
                            Vector((self.bbox_max.x - self.center.x, self.bbox_max.y - self.center.y)),
                            Vector((self.bbox_min.x - self.center.x, self.bbox_max.y - self.center.y))
                        ]

                        rotated_corners = [rot_matrix @ c for c in corners]

                        rot_width = max(c.x for c in rotated_corners) - min(c.x for c in rotated_corners)
                        rot_height = max(c.y for c in rotated_corners) - min(c.y for c in rotated_corners)
                    else:
                        rot_width = self.bbox_size.x
                        rot_height = self.bbox_size.y

                    # Calculate scale factors based on rotated dimensions
                    scale_x = master.bbox_size.x / max(rot_width, 0.001)
                    scale_y = master.bbox_size.y / max(rot_height, 0.001)

                    # Use uniform scale (average of both axes)
                    scale_x = scale_y = (scale_x + scale_y) / 2.0

                elif scale_mode == 'BOUNDS':
                    # Non-uniform scale to match exact bounds
                    scale_x = master.bbox_size.x / max(self.bbox_size.x, 0.001)
                    scale_y = master.bbox_size.y / max(self.bbox_size.y, 0.001)

            # Apply transformation to all loops
            for face in fresh_faces:
                for loop in face.loops:
                    uv = loop[self.uv_layer].uv

                    # 1. Translate to origin (relative to island center)
                    uv -= self.center

                    # 2. Rotate around origin
                    if rotation_angle != 0.0:
                        uv = rot_matrix @ uv

                    # 3. Scale
                    if match_scale and scale_mode != 'NONE':
                        uv.x *= scale_x
                        uv.y *= scale_y

                    # 4. Translate to master position
                    uv += master.center

                    loop[self.uv_layer].uv = uv

        except (ReferenceError, IndexError):
            # Face indices might be invalid after mesh edits - skip
            pass


class StackSystem:
    """Manages UV island stacking operations"""

    def __init__(self, context):
        self.context = context
        self.islands = []
        self.stacks = {}  # topology_hash -> list of islands
        self._collect_islands()

    def _collect_islands(self):
        """Collect all UV islands from objects - ZenUV style"""
        # Import ZenUV's get_islands function which gets ALL islands (not just selected)
        from ZenUV.utils import get_uv_islands as island_util

        for obj in self.context.objects_in_mode_unique_data:
            if obj.type != 'MESH':
                continue

            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                continue

            # Get ALL islands using ZenUV's method (not just selected)
            # This returns all islands in the mesh, respecting context (3D view vs UV editor)
            islands = island_util.get_islands(self.context, bm, is_include_hidden=False, use_seams_as_separator=False)

            for island_faces in islands:
                island_data = IslandData(obj, list(island_faces), uv_layer)
                self.islands.append(island_data)

    def group_by_similarity(self):
        """Group islands by similarity using threshold-based matching with user settings"""
        from ..properties import get_uvv_settings
        
        settings = get_uvv_settings()
        threshold = settings.stack_simi_threshold
        
        self.stacks = defaultdict(list)
        
        # Get settings
        adjust_scale = settings.stack_simi_adjust_scale
        check_holes = settings.stack_simi_check_holes and settings.stack_simi_mode == 'BORDER_SHAPE'
        
        print(f"\n[DEBUG] Total islands collected: {len(self.islands)}")
        print(f"[DEBUG] Similarity mode: {settings.stack_simi_mode}, threshold: {threshold}, adjust_scale: {adjust_scale}")

        # For now, use threshold-based grouping with sim_index
        # In future, we can enhance this to support different modes (Vertex Position, Topology)
        processed = set()
        stack_id = 0
        
        for i, island in enumerate(self.islands):
            if id(island) in processed:
                continue
            
            # Start a new group with this island
            current_group = [island]
            processed.add(id(island))
            
            # Find all similar islands
            for j, other_island in enumerate(self.islands):
                if i >= j or id(other_island) in processed:
                    continue
                
                # Check similarity using threshold
                if island.is_similar(other_island, threshold=threshold):
                    current_group.append(other_island)
                    processed.add(id(other_island))
            
            # Only create stack if we have 2+ islands
            if len(current_group) >= 2:
                self.stacks[stack_id] = current_group
                print(f"  Stack {stack_id}: {len(current_group)} island(s)")
                stack_id += 1

        print(f"\n[DEBUG] Final stacks: {len(self.stacks)}")
        return self.stacks

    def get_selected_stacks(self):
        """Get stacks that contain selected islands"""
        sync_uv = self.context.scene.tool_settings.use_uv_select_sync

        selected_stacks = {}

        for stack_hash, island_group in self.stacks.items():
            has_selected = False

            for island in island_group:
                try:
                    # Get fresh BMesh data for this object
                    bm = bmesh.from_edit_mesh(island.obj.data)
                    bm.faces.ensure_lookup_table()

                    # Get fresh faces using stored indices
                    fresh_faces = [bm.faces[idx] for idx in island.face_indices]

                    if sync_uv:
                        if any(f.select for f in fresh_faces):
                            has_selected = True
                            break
                    else:
                        if any(loop[island.uv_layer].select for f in fresh_faces for loop in f.loops):
                            has_selected = True
                            break
                except (ReferenceError, IndexError):
                    # Face indices might be invalid after mesh edits - skip this island
                    continue

            if has_selected:
                selected_stacks[stack_hash] = island_group

        return selected_stacks

    def find_master(self, island_group):
        """Find the best master island (lowest distortion)"""
        if not island_group:
            return None

        # Check if one is selected - use fresh BMesh data to avoid stale references
        sync_uv = self.context.scene.tool_settings.use_uv_select_sync

        for island in island_group:
            try:
                # Get fresh BMesh data for this object
                bm = bmesh.from_edit_mesh(island.obj.data)
                bm.faces.ensure_lookup_table()

                # Get fresh faces using stored indices
                fresh_faces = [bm.faces[idx] for idx in island.face_indices]

                if sync_uv:
                    if any(f.select for f in fresh_faces):
                        return island
                else:
                    if any(loop[island.uv_layer].select for f in fresh_faces for loop in f.loops):
                        return island
            except (ReferenceError, IndexError):
                # Face indices might be invalid after mesh edits - skip this island
                continue

        # Otherwise, use the one with lowest distortion
        # Use a safe distortion calculation that handles stale references
        def safe_distortion(island):
            try:
                return island.calc_distortion()
            except (ReferenceError, IndexError):
                return float('inf')  # Put invalid islands at the end

        return min(island_group, key=safe_distortion)

    def stack_all(self):
        """Stack all similar islands"""
        self.group_by_similarity()

        # Get settings from scene
        settings = self.context.scene.uvv_settings
        rotation_mode = settings.stack_rotation_mode if settings.stack_match_rotation else 'NONE'
        scale_mode = settings.stack_scale_mode if settings.stack_match_scale else 'NONE'
        match_rotation = settings.stack_match_rotation
        match_scale = settings.stack_match_scale

        stacked_count = 0

        for island_group in self.stacks.values():
            master = self.find_master(island_group)

            for island in island_group:
                if island is not master:
                    island.transform_to_match(
                        master,
                        rotation_mode=rotation_mode,
                        scale_mode=scale_mode,
                        match_rotation=match_rotation,
                        match_scale=match_scale
                    )
                    stacked_count += 1

        # Update all meshes
        for obj in self.context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bmesh.update_edit_mesh(obj.data)

        return stacked_count

    def stack_selected(self):
        """Stack only selected similar islands"""
        self.group_by_similarity()
        selected_stacks = self.get_selected_stacks()

        # Get settings from scene
        settings = self.context.scene.uvv_settings
        rotation_mode = settings.stack_rotation_mode if settings.stack_match_rotation else 'NONE'
        scale_mode = settings.stack_scale_mode if settings.stack_match_scale else 'NONE'
        match_rotation = settings.stack_match_rotation
        match_scale = settings.stack_match_scale

        stacked_count = 0

        for island_group in selected_stacks.values():
            master = self.find_master(island_group)

            for island in island_group:
                if island is not master:
                    island.transform_to_match(
                        master,
                        rotation_mode=rotation_mode,
                        scale_mode=scale_mode,
                        match_rotation=match_rotation,
                        match_scale=match_scale
                    )
                    stacked_count += 1

        # Update all meshes
        for obj in self.context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bmesh.update_edit_mesh(obj.data)

        return stacked_count

    def select_primaries(self):
        """Select primary (master) islands from each stack"""
        self.group_by_similarity()

        selected_count = 0

        for island_group in self.stacks.values():
            master = self.find_master(island_group)
            master.select(True)
            selected_count += 1

        # Update all meshes
        for obj in self.context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bmesh.update_edit_mesh(obj.data)

        return selected_count

    def select_replicas(self):
        """Select replica (non-master) islands from each stack"""
        self.group_by_similarity()

        selected_count = 0

        for island_group in self.stacks.values():
            master = self.find_master(island_group)

            for island in island_group:
                if island is not master:
                    island.select(True)
                    selected_count += 1

        # Update all meshes
        for obj in self.context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bmesh.update_edit_mesh(obj.data)

        return selected_count

    def select_singles(self):
        """Select unique islands (no similar copies)"""
        self.group_by_similarity()

        # Get all islands that are in stacks
        stacked_islands = set()
        for island_group in self.stacks.values():
            stacked_islands.update(island_group)

        # Select islands not in any stack
        selected_count = 0
        for island in self.islands:
            if island not in stacked_islands:
                island.select(True)
                selected_count += 1

        # Update all meshes
        for obj in self.context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bmesh.update_edit_mesh(obj.data)

        return selected_count

    def select_similar(self, target_island):
        """Select all islands with same sim_index as target island"""
        if not target_island:
            return 0

        self.group_by_similarity()
        target_sim_index = target_island.sim_index

        selected_count = 0
        for island in self.islands:
            if island.sim_index == target_sim_index:
                island.select(True)
                selected_count += 1

        # Update all meshes
        for obj in self.context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bmesh.update_edit_mesh(obj.data)

        return selected_count

    def get_selected_islands(self):
        """Get currently selected islands"""
        sync_uv = self.context.scene.tool_settings.use_uv_select_sync
        selected_islands = []

        for island in self.islands:
            try:
                bm = bmesh.from_edit_mesh(island.obj.data)
                bm.faces.ensure_lookup_table()
                fresh_faces = [bm.faces[idx] for idx in island.face_indices]

                if sync_uv:
                    if any(f.select for f in fresh_faces):
                        selected_islands.append(island)
                else:
                    if any(loop[island.uv_layer].select for f in fresh_faces for loop in f.loops):
                        selected_islands.append(island)
            except (ReferenceError, IndexError):
                continue

        return selected_islands

    def assign_to_group(self, islands, group_id):
        """Assign islands to a stack group"""
        if not self.context.active_object:
            return False
        
        obj = self.context.active_object

        # Find or create group
        stack_group = None
        for group in obj.uvv_stack_groups:
            if group.group_id == group_id:
                stack_group = group
                break

        if not stack_group:
            return False

        # Get current islands in group
        try:
            islands_data = json.loads(stack_group.islands_data) if stack_group.islands_data else []
        except json.JSONDecodeError:
            islands_data = []

        # Add new islands
        for island in islands:
            identifier_data = island.get_identifier_data()
            # Check if already in group (compare dicts properly)
            already_in_group = False
            for stored_data in islands_data:
                if (identifier_data.get('object_name') == stored_data.get('object_name') and
                    identifier_data.get('face_indices') == stored_data.get('face_indices')):
                    already_in_group = True
                    break
            if not already_in_group:
                islands_data.append(identifier_data)

        # Save back to group
        stack_group.islands_data = json.dumps(islands_data)
        
        # Update cached count for UI performance
        stack_group.cached_island_count = len(islands_data)

        return True

    def get_group_islands(self, group_id, obj=None):
        """Retrieve all islands that belong to a specific group"""
        if obj is None:
            if not self.context.active_object:
                return []
            obj = self.context.active_object

        # Find group on this object
        stack_group = None
        for group in obj.uvv_stack_groups:
            if group.group_id == group_id:
                stack_group = group
                break

        if not stack_group:
            return []

        # Parse stored island identifiers
        try:
            islands_data = json.loads(stack_group.islands_data) if stack_group.islands_data else []
        except json.JSONDecodeError:
            return []

        # Match islands by identifier - only return islands from this object
        group_islands = []
        for island in self.islands:
            # Only include islands from the target object
            if island.obj != obj:
                continue
                
            island_data = island.get_identifier_data()
            # Compare dicts properly (by checking all keys match)
            for stored_data in islands_data:
                if (island_data.get('object_name') == stored_data.get('object_name') and
                    island_data.get('face_indices') == stored_data.get('face_indices')):
                    group_islands.append(island)
                    break

        return group_islands

    def select_group(self, group_id):
        """Select all islands in a specific group"""
        group_islands = self.get_group_islands(group_id)

        selected_count = 0
        for island in group_islands:
            island.select(True)
            selected_count += 1

        # Update all meshes
        for obj in self.context.objects_in_mode_unique_data:
            if obj.type == 'MESH':
                bmesh.update_edit_mesh(obj.data)

        return selected_count

    def remove_from_group(self, islands, group_id):
        """Remove islands from a stack group"""
        if not self.context.active_object:
            return False
        
        obj = self.context.active_object

        # Find group
        stack_group = None
        for group in obj.uvv_stack_groups:
            if group.group_id == group_id:
                stack_group = group
                break

        if not stack_group:
            return False

        # Get current islands in group
        try:
            islands_data = json.loads(stack_group.islands_data) if stack_group.islands_data else []
        except json.JSONDecodeError:
            return False

        # Remove islands
        for island in islands:
            identifier_data = island.get_identifier_data()
            # Remove matching identifier data (compare dicts properly)
            for i, stored_data in enumerate(islands_data):
                if (identifier_data.get('object_name') == stored_data.get('object_name') and
                    identifier_data.get('face_indices') == stored_data.get('face_indices')):
                    islands_data.pop(i)
                    break

        # Save back to group
        stack_group.islands_data = json.dumps(islands_data)
        
        # Update cached count for UI performance
        stack_group.cached_island_count = len(islands_data)

        return True

    def get_group_island_count(self, group_id, obj=None):
        """Get count of islands in a group (optimized for UI performance)"""
        if obj is None:
            if not self.context.active_object:
                return 0
            obj = self.context.active_object
        
        # Find the group on this object
        for group in obj.uvv_stack_groups:
            if group.group_id == group_id:
                try:
                    # Parse the stored islands data to get count without full island processing
                    islands_data = json.loads(group.islands_data) if group.islands_data else []
                    return len(islands_data)
                except (json.JSONDecodeError, AttributeError):
                    return 0
        
        return 0

    def refresh_group_counts(self):
        """Refresh cached island counts for all groups (call when scene changes)"""
        # Iterate over all objects in mode
        for obj in self.context.objects_in_mode_unique_data:
            if obj.type != 'MESH':
                continue
            
            for group in obj.uvv_stack_groups:
                try:
                    islands_data = json.loads(group.islands_data) if group.islands_data else []
                    group.cached_island_count = len(islands_data)
                except (json.JSONDecodeError, AttributeError):
                    group.cached_island_count = 0
