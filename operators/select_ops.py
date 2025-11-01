import bpy
import bmesh
from math import radians
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from mathutils import Vector


class UVV_OT_SelectUVBorders(bpy.types.Operator):
    """Select UV border edges"""
    bl_idname = "uv.uvv_select_uv_borders"
    bl_label = "Select UV Borders"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: BoolProperty(
        name="Clear Selection",
        description="Clear previous selection",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.active_object is not None

    def execute(self, context):
        objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No objects in edit mode")
            return {'CANCELLED'}

        # Switch to edge selection mode
        uv_sync = context.scene.tool_settings.use_uv_select_sync
        if context.area.type == 'IMAGE_EDITOR' and not uv_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            # Get UV boundary edges
            boundary_edges = self._get_uv_boundary_edges(bm, uv_layer)

            # Clear selection if requested
            if self.clear_selection:
                if context.area.type == 'IMAGE_EDITOR' and not uv_sync:
                    # Clear UV selection
                    for face in bm.faces:
                        for loop in face.loops:
                            loop[uv_layer].select_edge = False
                else:
                    # Clear mesh selection
                    for edge in bm.edges:
                        edge.select = False

            # Select boundary edges
            if context.area.type == 'IMAGE_EDITOR' and not uv_sync:
                # UV editor mode - select UV edges
                for edge in boundary_edges:
                    for loop in edge.link_loops:
                        loop[uv_layer].select_edge = True
            else:
                # 3D view or UV sync mode
                for edge in boundary_edges:
                    edge.select = True

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}

    def _get_uv_boundary_edges(self, bm, uv_layer):
        """Get edges that are on UV island boundaries"""
        boundary_edges = set()

        # Build a dictionary of UV edge connections
        uv_edges = {}

        for face in bm.faces:
            if face.hide:
                continue

            loops = face.loops
            num_loops = len(loops)

            for i in range(num_loops):
                loop = loops[i]
                next_loop = loops[(i + 1) % num_loops]

                uv1 = loop[uv_layer].uv.copy().freeze()
                uv2 = next_loop[uv_layer].uv.copy().freeze()

                # Create edge key (sorted to be direction-independent)
                edge_key = tuple(sorted([uv1, uv2]))

                if edge_key in uv_edges:
                    uv_edges[edge_key].append(loop.edge)
                else:
                    uv_edges[edge_key] = [loop.edge]

        # Edges that appear only once are boundary edges
        for edge_key, edges in uv_edges.items():
            if len(edges) == 1:
                boundary_edges.add(edges[0])

        return list(boundary_edges)


class UVV_OT_SelectByDirection(bpy.types.Operator):
    """Select UV edges by direction (U or V axis)"""
    bl_idname = "uv.uvv_select_by_direction"
    bl_label = "Select Edges by Direction"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="Direction",
        description="Edge direction",
        items=[
            ("U", "U", "U Axis (Horizontal)"),
            ("V", "V", "V Axis (Vertical)"),
        ],
        default="U"
    )

    clear_selection: BoolProperty(
        name="Clear Selection",
        description="Clear previous selection",
        default=True
    )

    angle: FloatProperty(
        name="Angle Tolerance",
        description="Maximum angle deviation from axis (in degrees)",
        min=0,
        max=45,
        default=30,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.active_object is not None

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "direction")
        layout.prop(self, "angle")
        layout.prop(self, "clear_selection")

    def execute(self, context):
        objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No objects in edit mode")
            return {'CANCELLED'}

        # Switch to edge selection mode
        uv_sync = context.scene.tool_settings.use_uv_select_sync
        if context.area.type == 'IMAGE_EDITOR' and not uv_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        angle_rad = radians(self.angle)
        target_axis = Vector((1, 0)) if self.direction == 'U' else Vector((0, 1))

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            # Get selected islands
            islands = self._get_selected_islands(bm, uv_layer)

            if not islands:
                continue

            # Clear selection if requested
            if self.clear_selection:
                if context.area.type == 'IMAGE_EDITOR' and not uv_sync:
                    for face in bm.faces:
                        for loop in face.loops:
                            loop[uv_layer].select_edge = False
                else:
                    for edge in bm.edges:
                        edge.select = False

            # Select edges by direction
            for island in islands:
                edges_to_select = self._get_edges_by_direction(
                    island, bm, uv_layer, target_axis, angle_rad
                )

                if context.area.type == 'IMAGE_EDITOR' and not uv_sync:
                    for edge in edges_to_select:
                        for loop in edge.link_loops:
                            loop[uv_layer].select_edge = True
                else:
                    for edge in edges_to_select:
                        edge.select = True

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}

    def _get_selected_islands(self, bm, uv_layer):
        """Get UV islands from selected faces"""
        selected_faces = [f for f in bm.faces if f.select and not f.hide]
        if not selected_faces:
            return []

        islands = []
        remaining_faces = set(selected_faces)

        while remaining_faces:
            # Start a new island
            island = set()
            stack = [remaining_faces.pop()]

            while stack:
                face = stack.pop()
                if face in island:
                    continue

                island.add(face)

                # Find connected faces in UV space
                for loop in face.loops:
                    uv = loop[uv_layer].uv
                    for linked_loop in loop.vert.link_loops:
                        if linked_loop.face in remaining_faces:
                            linked_uv = linked_loop[uv_layer].uv
                            if (uv - linked_uv).length < 0.0001:
                                stack.append(linked_loop.face)
                                remaining_faces.discard(linked_loop.face)

            islands.append(list(island))

        return islands

    def _get_edges_by_direction(self, island, bm, uv_layer, target_axis, angle_tolerance):
        """Get edges that align with the target axis within tolerance"""
        edges_to_select = []

        # Collect all edges in the island
        island_edges = set()
        for face in island:
            for edge in face.edges:
                island_edges.add(edge)

        for edge in island_edges:
            # Get UV coordinates for edge vertices
            uv_coords = []
            for loop in edge.link_loops:
                if loop.face in island:
                    for vert in edge.verts:
                        for v_loop in vert.link_loops:
                            if v_loop.face in island and v_loop.edge == edge:
                                uv_coords.append(v_loop[uv_layer].uv.copy())
                    break

            if len(uv_coords) >= 2:
                # Calculate edge direction in UV space
                edge_vec = (uv_coords[1] - uv_coords[0]).normalized()

                # Calculate angle to target axis
                angle = abs(edge_vec.angle(target_axis))

                # Check if angle is within tolerance (or close to 180 degrees)
                import math
                if angle <= angle_tolerance or abs(angle - math.pi) <= angle_tolerance:
                    edges_to_select.append(edge)

        return edges_to_select


class UVV_OT_SelectSeamEdges(bpy.types.Operator):
    """Select seam edges"""
    bl_idname = "uv.uvv_select_seam_edges"
    bl_label = "Select Seam Edges"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: BoolProperty(
        name="Clear Selection",
        description="Clear previous selection before selecting seams",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.active_object is not None

    def execute(self, context):
        objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No objects in edit mode")
            return {'CANCELLED'}

        # Clear selection if requested
        if self.clear_selection:
            if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.uv.select_all(action='DESELECT')
            else:
                bpy.ops.mesh.select_all(action='DESELECT')

        # Switch to edge selection mode
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        seam_count = 0
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)

            seam_edges = [e for e in bm.edges if e.seam and not e.hide]

            # UV editor mode without sync
            if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                uv_layer = bm.loops.layers.uv.active
                if not uv_layer:
                    continue

                for edge in seam_edges:
                    for loop in edge.link_loops:
                        loop[uv_layer].select = True
                        loop[uv_layer].select_edge = True
                        loop.link_loop_next[uv_layer].select = True
                    seam_count += 1
            # 3D view or UV sync mode
            else:
                for edge in seam_edges:
                    edge.select = True
                    seam_count += 1

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        self.report({'INFO'}, f"Selected {seam_count} seam edges")
        return {'FINISHED'}


class UVV_OT_SelectSharpEdges(bpy.types.Operator):
    """Select sharp edges (non-smooth edges)"""
    bl_idname = "uv.uvv_select_sharp_edges"
    bl_label = "Select Sharp Edges"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: BoolProperty(
        name="Clear Selection",
        description="Clear previous selection before selecting sharp edges",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.active_object is not None

    def execute(self, context):
        objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No objects in edit mode")
            return {'CANCELLED'}

        # Clear selection if requested
        if self.clear_selection:
            if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.uv.select_all(action='DESELECT')
            else:
                bpy.ops.mesh.select_all(action='DESELECT')

        # Switch to edge selection mode
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        sharp_count = 0
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)

            sharp_edges = [e for e in bm.edges if not e.smooth and not e.hide]

            # UV editor mode without sync
            if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                uv_layer = bm.loops.layers.uv.active
                if not uv_layer:
                    continue

                for edge in sharp_edges:
                    for loop in edge.link_loops:
                        loop[uv_layer].select = True
                        loop[uv_layer].select_edge = True
                        loop.link_loop_next[uv_layer].select = True
                    sharp_count += 1
            # 3D view or UV sync mode
            else:
                for edge in sharp_edges:
                    edge.select = True
                    sharp_count += 1

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        self.report({'INFO'}, f"Selected {sharp_count} sharp edges")
        return {'FINISHED'}


class UVV_OT_SelectZeroAreaFaces(bpy.types.Operator):
    """Select faces with zero or near-zero UV area"""
    bl_idname = "uv.uvv_select_zero_area_faces"
    bl_label = "Select Zero Area Faces"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: BoolProperty(
        name="Clear Selection",
        description="Clear previous selection before selecting zero area faces",
        default=True
    )

    threshold: FloatProperty(
        name="Threshold",
        description="UV area threshold (faces with area below this are selected)",
        min=0.0,
        max=0.001,
        default=0.0000001,
        precision=7
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.active_object is not None

    def execute(self, context):
        objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No objects in edit mode")
            return {'CANCELLED'}

        # Clear selection if requested
        if self.clear_selection:
            if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.uv.select_all(action='DESELECT')
            else:
                bpy.ops.mesh.select_all(action='DESELECT')

        # Switch to face selection mode
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "FACE"
        else:
            bpy.ops.mesh.select_mode(type="FACE")

        zero_area_count = 0
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            # Select faces with zero or near-zero UV area
            for face in bm.faces:
                if face.hide:
                    continue

                # Calculate UV area
                uv_area = self._calculate_uv_area(face, uv_layer)

                if abs(uv_area) < self.threshold:
                    # UV editor mode without sync
                    if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                        for loop in face.loops:
                            loop[uv_layer].select = True
                    # 3D view or UV sync mode
                    else:
                        face.select = True
                    zero_area_count += 1

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        self.report({'INFO'}, f"Selected {zero_area_count} zero area faces")
        return {'FINISHED'}

    def _calculate_uv_area(self, face, uv_layer):
        """Calculate the UV area of a face using the shoelace formula"""
        # Get UV coordinates
        uv_coords = [loop[uv_layer].uv for loop in face.loops]

        if len(uv_coords) < 3:
            return 0.0

        # Shoelace formula for polygon area
        area = 0.0
        n = len(uv_coords)

        for i in range(n):
            j = (i + 1) % n
            area += uv_coords[i].x * uv_coords[j].y
            area -= uv_coords[j].x * uv_coords[i].y

        return abs(area) / 2.0


class UVV_OT_SelectFlippedIslands(bpy.types.Operator):
    """Select UV islands that are flipped (mirrored/inverted)"""
    bl_idname = "uv.uvv_select_flipped_islands"
    bl_label = "Select Flipped Islands"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: BoolProperty(
        name="Clear Selection",
        description="Clear previous selection before selecting flipped islands",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.active_object is not None

    def execute(self, context):
        objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No objects in edit mode")
            return {'CANCELLED'}

        # Clear selection if requested
        if self.clear_selection:
            if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.uv.select_all(action='DESELECT')
            else:
                bpy.ops.mesh.select_all(action='DESELECT')

        # Switch to face selection mode
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "FACE"
        else:
            bpy.ops.mesh.select_mode(type="FACE")

        flipped_count = 0
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                continue

            # Check each face for flipped UVs
            for face in bm.faces:
                if face.hide or len(face.loops) < 3:
                    continue

                # Get UV coordinates
                uv_coords = [loop[uv_layer].uv for loop in face.loops]

                # Calculate signed area (shoelace formula)
                # Positive = normal, Negative = flipped
                area = 0.0
                for i in range(len(uv_coords)):
                    j = (i + 1) % len(uv_coords)
                    area += uv_coords[i].x * uv_coords[j].y
                    area -= uv_coords[j].x * uv_coords[i].y

                # If area is negative, the UV face is flipped
                if area < 0:
                    # UV editor mode without sync
                    if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                        for loop in face.loops:
                            loop[uv_layer].select = True
                    # 3D view or UV sync mode
                    else:
                        face.select = True
                    flipped_count += 1

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        if flipped_count == 0:
            self.report({'INFO'}, "No flipped UV islands found")
        else:
            self.report({'INFO'}, f"Selected {flipped_count} flipped UV faces")

        return {'FINISHED'}


class UVV_OT_SelectFacesLessThanPixel(bpy.types.Operator):
    """Select faces with UV area less than one pixel"""
    bl_idname = "uv.uvv_select_faces_less_than_pixel"
    bl_label = "Select Faces < 1 Pixel"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: BoolProperty(
        name="Clear Selection",
        description="Clear previous selection",
        default=True
    )

    texture_size: EnumProperty(
        name="Texture Size",
        description="Texture resolution for pixel calculation",
        items=[
            ('512', "512", "512x512"),
            ('1024', "1024", "1024x1024"),
            ('2048', "2048", "2048x2048"),
            ('4096', "4096", "4096x4096"),
            ('8192', "8192", "8192x8192"),
        ],
        default='2048'
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.active_object is not None

    def execute(self, context):
        objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No objects in edit mode")
            return {'CANCELLED'}

        # Clear selection if requested
        if self.clear_selection:
            if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.uv.select_all(action='DESELECT')
            else:
                bpy.ops.mesh.select_all(action='DESELECT')

        # Switch to face selection mode
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "FACE"
        else:
            bpy.ops.mesh.select_mode(type="FACE")

        # Calculate pixel area threshold
        tex_size = int(self.texture_size)
        pixel_area = 1.0 / (tex_size * tex_size)  # Area of one pixel in UV space

        small_face_count = 0
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            for face in bm.faces:
                if face.hide:
                    continue

                # Calculate UV area
                uv_area = self._calculate_uv_area(face, uv_layer)

                # Select if smaller than one pixel
                if uv_area < pixel_area and uv_area > 0:
                    # UV editor mode without sync
                    if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                        for loop in face.loops:
                            loop[uv_layer].select = True
                    # 3D view or UV sync mode
                    else:
                        face.select = True
                    small_face_count += 1

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        self.report({'INFO'}, f"Selected {small_face_count} faces smaller than 1 pixel ({self.texture_size}x{self.texture_size})")
        return {'FINISHED'}

    def _calculate_uv_area(self, face, uv_layer):
        """Calculate UV area using shoelace formula"""
        uv_coords = [loop[uv_layer].uv for loop in face.loops]

        if len(uv_coords) < 3:
            return 0.0

        area = 0.0
        n = len(uv_coords)

        for i in range(n):
            j = (i + 1) % n
            area += uv_coords[i].x * uv_coords[j].y
            area -= uv_coords[j].x * uv_coords[i].y

        return abs(area) / 2.0


class UVV_OT_SelectHoleIslands(bpy.types.Operator):
    """Select UV islands that contain holes"""
    bl_idname = "uv.uvv_select_hole_islands"
    bl_label = "Select Hole Islands"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: BoolProperty(
        name="Clear Selection",
        description="Clear previous selection",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.active_object is not None

    def execute(self, context):
        objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No objects in edit mode")
            return {'CANCELLED'}

        # Clear selection if requested
        if self.clear_selection:
            if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.uv.select_all(action='DESELECT')
            else:
                bpy.ops.mesh.select_all(action='DESELECT')

        # Switch to face selection mode
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "FACE"
        else:
            bpy.ops.mesh.select_mode(type="FACE")

        hole_island_count = 0
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                continue

            # Get all UV islands
            islands = self._get_uv_islands(bm, uv_layer)

            for island in islands:
                # Check if island has holes using Euler characteristic
                if self._island_has_holes(island, uv_layer):
                    # Select all faces in this island
                    for face in island:
                        # UV editor mode without sync
                        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                            for loop in face.loops:
                                loop[uv_layer].select = True
                        # 3D view or UV sync mode
                        else:
                            face.select = True
                    hole_island_count += 1

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        self.report({'INFO'}, f"Selected {hole_island_count} islands with holes")
        return {'FINISHED'}

    def _get_uv_islands(self, bm, uv_layer):
        """Get UV islands from bmesh"""
        all_faces = [f for f in bm.faces if not f.hide]
        islands = []
        remaining_faces = set(all_faces)

        while remaining_faces:
            # Start new island
            island = set()
            stack = [remaining_faces.pop()]

            while stack:
                face = stack.pop()
                if face in island:
                    continue

                island.add(face)

                # Find UV-connected faces
                for loop in face.loops:
                    uv = loop[uv_layer].uv
                    for linked_loop in loop.vert.link_loops:
                        linked_face = linked_loop.face
                        if linked_face in remaining_faces:
                            linked_uv = linked_loop[uv_layer].uv
                            # Check if UVs are connected (distance < epsilon)
                            if (uv - linked_uv).length < 0.0001:
                                stack.append(linked_face)
                                remaining_faces.discard(linked_face)

            islands.append(list(island))

        return islands

    def _island_has_holes(self, island_faces, uv_layer):
        """Check if island has holes using boundary analysis"""
        # Count boundary edges
        uv_edge_count = {}

        for face in island_faces:
            for i, loop in enumerate(face.loops):
                next_loop = face.loops[(i + 1) % len(face.loops)]

                uv1 = loop[uv_layer].uv.copy().freeze()
                uv2 = next_loop[uv_layer].uv.copy().freeze()

                # Create edge key
                edge_key = tuple(sorted([uv1, uv2]))

                if edge_key in uv_edge_count:
                    uv_edge_count[edge_key] += 1
                else:
                    uv_edge_count[edge_key] = 1

        # Count boundary edges (edges that appear only once)
        boundary_edges = sum(1 for count in uv_edge_count.values() if count == 1)

        # Simple heuristic: if there are multiple separate boundary loops, there's a hole
        # For a simple island: boundary_edges should form one continuous loop
        # For island with holes: there will be multiple boundary loops
        # This is a simplified check - a more robust solution would trace boundary loops

        # If boundary edges > 2 * sqrt(face_count), likely has internal boundaries
        import math
        expected_boundary = 2 * math.sqrt(len(island_faces))

        return boundary_edges > expected_boundary * 2


classes = [
    UVV_OT_SelectUVBorders,
    UVV_OT_SelectByDirection,
    UVV_OT_SelectSeamEdges,
    UVV_OT_SelectSharpEdges,
    UVV_OT_SelectZeroAreaFaces,
    UVV_OT_SelectFlippedIslands,
    UVV_OT_SelectFacesLessThanPixel,
    UVV_OT_SelectHoleIslands,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
