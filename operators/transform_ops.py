import bpy
import math
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty
from mathutils import Vector
from ..utils.uv_classes import UVNodeManager, UVIslandManager


class UVV_OT_align(Operator):
    """Align UVs of vertices, edge loops and islands\n\nNormal Click: Move entire UV island\nShift+Click: Align selected points/edges (disabled in UV sync mode)"""
    bl_idname = "uv.uvv_align"
    bl_label = "Align UVs"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        items=[
            ("UPPER", "Top", ""),
            ("BOTTOM", "Bottom", ""),
            ("LEFT", "Left", ""),
            ("RIGHT", "Right", ""),
            ("VERTICAL", "Center Y", ""),
            ("HORIZONTAL", "Center X", ""),
            ("CENTER", "Center", ""),
        ],
        name="Direction",
        default="UPPER",
    )

    mode: EnumProperty(
        name="Mode",
        default='INDIVIDUAL',
        items=(
            ('INDIVIDUAL', 'Individual', 'Align each edge loop/selection independently'),
            ('ALIGN', 'Align', 'Align all selections together'),
        )
    )

    use_island_mode: BoolProperty(
        name="Island Mode",
        default=False,
        description="Move entire islands instead of aligning points (activated by Normal Click)"
    )

    use_trim_bounds: BoolProperty(
        name="Use Trim Bounds",
        default=False,
        description="Align islands to trim edges instead of 0-1 UV space (activated by CTRL+Click)",
        options={'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object is not None

    def draw(self, context):
        self.layout.prop(self, 'direction')
        self.layout.column(align=True).prop(self, 'mode', expand=True)

    def get_selected_objects(self, context):
        """Get all selected objects in edit mode"""
        return [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.mode == 'EDIT']

    def check_selected_face_objects(self, objects):
        """Check if any face is selected"""
        import bmesh
        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            if any(face.select for face in bm.faces):
                return True
        return False

    def sync_uv_from_mesh(self, context, objects):
        """Sync UV selection from mesh selection"""
        import bmesh
        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()
            for face in bm.faces:
                for loop in face.loops:
                    loop[uv_layer].select = False
                    loop[uv_layer].select_edge = False
            for vert in bm.verts:
                if vert.select:
                    for loop in vert.link_loops:
                        loop[uv_layer].select = True
            for edge in bm.edges:
                if edge.select:
                    for loop in edge.link_loops:
                        loop[uv_layer].select_edge = True

    def execute(self, context):
        objects = self.get_selected_objects(context)
        use_uv_select_sync = context.tool_settings.use_uv_select_sync

        # DEBUG: Print execution mode
        print(f"[UVV DEBUG] execute() - self.use_island_mode: {self.use_island_mode}")

        if self.use_island_mode:
            # NORMAL CLICK: Move entire islands to UV space boundaries
            print(f"[UVV DEBUG] ISLAND MODE - Moving islands to {self.direction}")
            
            # Use mesh_link_uv=True when UV sync is enabled to properly sync UV selection from mesh
            island_manager = UVIslandManager(objects, mesh_link_uv=use_uv_select_sync)

            if not island_manager.islands:
                return {"CANCELLED"}

            self.move_islands(context, island_manager, self.direction)
            island_manager.update_uvmeshes()

        else:
            # SHIFT CLICK: Use point alignment (INDIVIDUAL/ALIGN mode)
            print(f"[UVV DEBUG] POINT ALIGNMENT MODE - mode: {self.mode}, direction: {self.direction}")
            
            # Disable vertex alignment in UV sync mode
            if use_uv_select_sync:
                self.report({'WARNING'}, "Vertex alignment is disabled in UV sync mode. Use normal click to align UV islands instead.")
                return {"CANCELLED"}
            
            if self.mode == 'ALIGN':
                # Global alignment - all selections align together
                node_manager = UVNodeManager(objects, mode="FACE")

                if not node_manager.groups:
                    return {"CANCELLED"}

                # Align all nodes together
                all_nodes = []
                for group in node_manager.groups:
                    all_nodes.extend(group.nodes)
                self.align_nodes(all_nodes, self.direction)

                for group in node_manager.groups:
                    group.update_uvs()
                    for node in group.nodes:
                        node.select = True

                node_manager.update_uvmeshes()

            elif self.mode == 'INDIVIDUAL':
                # Individual alignment - each edge loop aligns separately
                self.individual_align(objects, use_uv_select_sync)

        return {"FINISHED"}

    def individual_align(self, objects, use_uv_select_sync):
        """Align each edge loop/group individually"""
        # DEBUG: Commented out for cleaner output
        # self.debug_print_edge_connectivity(objects)
        
        # Always use EDGE mode for consistent behavior regardless of UV sync
        node_manager = UVNodeManager(objects, mode="EDGE")

        if not node_manager.groups:
            return

        # Each group aligns independently
        for group in node_manager.groups:
            self.align_nodes(group.nodes, self.direction)
            group.update_uvs()
            for node in group.nodes:
                node.select = True

        node_manager.update_uvmeshes()

    def debug_print_edge_connectivity(self, objects):
        """Debug function to print edge connectivity information"""
        import bmesh
        
        print("\n" + "="*80)
        print("DEBUG: EDGE CONNECTIVITY ANALYSIS")
        print("="*80)
        
        for obj_idx, obj in enumerate(objects):
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()
            
            print(f"\n[Object {obj_idx + 1}/{len(objects)}]: {obj.name}")
            print("-" * 80)
            
            # Find all selected edges (in mesh selection)
            selected_edges = [edge for edge in bm.edges if edge.select]
            print(f"\n1. SELECTED EDGES (Mesh): {len(selected_edges)} edges")
            
            if not selected_edges:
                print("   No mesh edges selected!")
                continue
            
            # Find edges with UV select_edge
            uv_selected_edges = []
            for face in bm.faces:
                if face.select:
                    for loop in face.loops:
                        if loop[uv_layer].select_edge:
                            # Get the mesh edge corresponding to this loop
                            edge = loop.edge
                            if edge not in uv_selected_edges:
                                uv_selected_edges.append(edge)
            
            print(f"   UV-Selected Edges: {len(uv_selected_edges)} edges")
            
            # Collect all vertices from selected edges
            all_vertices = set()
            
            for edge_idx, edge in enumerate(selected_edges):
                v1, v2 = edge.verts
                all_vertices.add(v1)
                all_vertices.add(v2)
                
                # Check if this edge has UV selection
                has_uv_select = edge in uv_selected_edges
                
                print(f"\n   Edge #{edge.index} (Vertices: {v1.index}, {v2.index}) [UV Selected: {has_uv_select}]")
                
                # Print UV coordinates for this edge
                for face in edge.link_faces:
                    for loop in face.loops:
                        if loop.edge == edge:
                            uv_coord = loop[uv_layer].uv
                            uv_select = loop[uv_layer].select_edge
                            print(f"      UV in face {face.index}: ({uv_coord.x:.4f}, {uv_coord.y:.4f}) [select_edge={uv_select}]")
            
            print(f"\n2. VERTICES FROM SELECTED EDGES: {len(all_vertices)} vertices")
            
            for vert in sorted(all_vertices, key=lambda v: v.index):
                print(f"\n   Vertex #{vert.index}:")
                
                # Find all edges connected to this vertex
                connected_edges = vert.link_edges
                print(f"      Connected edges: {len(connected_edges)} total")
                
                for conn_edge in connected_edges:
                    is_selected = conn_edge.select
                    has_uv_select = conn_edge in uv_selected_edges
                    other_vert = conn_edge.other_vert(vert)
                    
                    status = []
                    if is_selected:
                        status.append("MESH_SELECTED")
                    if has_uv_select:
                        status.append("UV_SELECTED")
                    if not status:
                        status.append("NOT_SELECTED")
                    
                    status_str = ", ".join(status)
                    print(f"         Edge #{conn_edge.index} -> Vertex #{other_vert.index} [{status_str}]")
            
            print(f"\n3. SUMMARY:")
            print(f"   - Total edges in mesh: {len(bm.edges)}")
            print(f"   - Selected edges (mesh): {len(selected_edges)}")
            print(f"   - UV-selected edges: {len(uv_selected_edges)}")
            print(f"   - Vertices involved: {len(all_vertices)}")
            
            # Count edges that share vertices with selected edges but aren't selected
            connected_but_not_selected = set()
            for vert in all_vertices:
                for edge in vert.link_edges:
                    if edge not in selected_edges and edge not in uv_selected_edges:
                        connected_but_not_selected.add(edge)
            
            print(f"   - Connected edges NOT selected: {len(connected_but_not_selected)}")
            
            if connected_but_not_selected:
                print(f"\n   WARNING: {len(connected_but_not_selected)} edges share vertices with")
                print(f"            selected edges but are NOT selected. These will cause breaks!")
                print(f"   Edge indices: {sorted([e.index for e in connected_but_not_selected])}")
        
        print("\n" + "="*80)
        print("END OF CONNECTIVITY ANALYSIS")
        print("="*80 + "\n")

    def move_islands(self, context, island_manager, direction):
        """
        Move islands to align with UV space boundaries or trim bounds
        Does NOT change island scale, only moves them
        """
        # Determine target bounds (0-1 UV space or trim bounds)
        if self.use_trim_bounds:
            from ..utils import trimsheet_utils
            settings = context.scene.uvv_settings

            if settings.show_trim_overlays:
                material = trimsheet_utils.get_active_material(context)
                if material:
                    trim = trimsheet_utils.get_active_trim(context)
                    if trim and trim.enabled:
                        # Use trim bounds
                        target_left = trim.left
                        target_right = trim.right
                        target_bottom = trim.bottom
                        target_top = trim.top
                        target_center_x = (trim.left + trim.right) / 2
                        target_center_y = (trim.bottom + trim.top) / 2
                    else:
                        # Fallback to 0-1 UV space
                        target_left = 0.0
                        target_right = 1.0
                        target_bottom = 0.0
                        target_top = 1.0
                        target_center_x = 0.5
                        target_center_y = 0.5
                else:
                    # Fallback to 0-1 UV space
                    target_left = 0.0
                    target_right = 1.0
                    target_bottom = 0.0
                    target_top = 1.0
                    target_center_x = 0.5
                    target_center_y = 0.5
            else:
                # Fallback to 0-1 UV space
                target_left = 0.0
                target_right = 1.0
                target_bottom = 0.0
                target_top = 1.0
                target_center_x = 0.5
                target_center_y = 0.5
        else:
            # Use standard 0-1 UV space
            target_left = 0.0
            target_right = 1.0
            target_bottom = 0.0
            target_top = 1.0
            target_center_x = 0.5
            target_center_y = 0.5

        for island in island_manager.islands:
            # Get island bounding box
            min_uv = island.min_uv
            max_uv = island.max_uv

            # Calculate delta based on direction
            if direction == "LEFT":
                # Move so left edge aligns with target left edge
                delta = Vector((target_left - min_uv.x, 0))
            elif direction == "RIGHT":
                # Move so right edge aligns with target right edge
                delta = Vector((target_right - max_uv.x, 0))
            elif direction == "UPPER":
                # Move so top edge aligns with target top edge
                delta = Vector((0, target_top - max_uv.y))
            elif direction == "BOTTOM":
                # Move so bottom edge aligns with target bottom edge
                delta = Vector((0, target_bottom - min_uv.y))
            elif direction == "CENTER":
                # Move to center of target space
                center = (min_uv + max_uv) / 2
                delta = Vector((target_center_x, target_center_y)) - center
            elif direction == "VERTICAL":
                # Center horizontally (x-axis to target center)
                center_x = (min_uv.x + max_uv.x) / 2
                delta = Vector((target_center_x - center_x, 0))
            elif direction == "HORIZONTAL":
                # Center vertically (y-axis to target center)
                center_y = (min_uv.y + max_uv.y) / 2
                delta = Vector((0, target_center_y - center_y))
            else:
                delta = Vector((0, 0))

            # Move the island
            island.move(delta)

    def align_nodes(self, nodes, alignment_type):
        uv_coords = [node.uv for node in nodes]

        if alignment_type == "RIGHT":
            pos = max(uv.x for uv in uv_coords)
            for node in nodes:
                node.uv.x = pos
        elif alignment_type == "LEFT":
            pos = min(uv.x for uv in uv_coords)
            for node in nodes:
                node.uv.x = pos
        elif alignment_type == "UPPER":
            pos = max(uv.y for uv in uv_coords)
            for node in nodes:
                node.uv.y = pos
        elif alignment_type == "BOTTOM":
            pos = min(uv.y for uv in uv_coords)
            for node in nodes:
                node.uv.y = pos
        elif alignment_type == "VERTICAL":
            # Center X - aligns vertically (horizontal centering)
            min_x = min(uv.x for uv in uv_coords)
            max_x = max(uv.x for uv in uv_coords)
            center_x = (min_x + max_x) / 2
            for node in nodes:
                node.uv.x = center_x
        elif alignment_type == "HORIZONTAL":
            # Center Y - aligns horizontally (vertical centering)
            min_y = min(uv.y for uv in uv_coords)
            max_y = max(uv.y for uv in uv_coords)
            center_y = (min_y + max_y) / 2
            for node in nodes:
                node.uv.y = center_y
        elif alignment_type == "CENTER":
            min_x = min(uv.x for uv in uv_coords)
            max_x = max(uv.x for uv in uv_coords)
            min_y = min(uv.y for uv in uv_coords)
            max_y = max(uv.y for uv in uv_coords)
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            for node in nodes:
                node.uv.x = center_x
                node.uv.y = center_y


class UVV_OT_align_left(Operator):
    """Align UVs to left\n\nNormal Click: Move entire UV island to left edge\nShift+Click: Align selected points/edges (disabled in UV sync mode)\nCTRL+Click: Move entire UV island to trim left edge"""
    bl_idname = "uv.uvv_align_left"
    bl_label = "Align Left"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        # Detect modifier keys - SWAPPED BEHAVIOR:
        # Normal click: align UV islands
        # Shift click: align vertices/points
        # Ctrl click: align UV islands to trim
        use_island = not event.shift or event.ctrl
        use_trim = event.ctrl
        print(f"[UVV DEBUG] align_left invoke() - shift: {event.shift}, ctrl: {event.ctrl}")
        bpy.ops.uv.uvv_align(direction='LEFT', use_island_mode=use_island, use_trim_bounds=use_trim)
        return {'FINISHED'}

    def execute(self, context):
        # Called from redo panel or F9 - use default (no island mode)
        bpy.ops.uv.uvv_align(direction='LEFT', use_island_mode=False, use_trim_bounds=False)
        return {'FINISHED'}


class UVV_OT_align_right(Operator):
    """Align UVs to right\n\nNormal Click: Move entire UV island to right edge\nShift+Click: Align selected points/edges (disabled in UV sync mode)\nCTRL+Click: Move entire UV island to trim right edge"""
    bl_idname = "uv.uvv_align_right"
    bl_label = "Align Right"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        # SWAPPED BEHAVIOR: Normal click aligns UV islands, Shift click aligns vertices
        use_island = not event.shift or event.ctrl
        use_trim = event.ctrl
        bpy.ops.uv.uvv_align(direction='RIGHT', use_island_mode=use_island, use_trim_bounds=use_trim)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.uv.uvv_align(direction='RIGHT', use_island_mode=False, use_trim_bounds=False)
        return {'FINISHED'}


class UVV_OT_align_top(Operator):
    """Align UVs to top\n\nNormal Click: Move entire UV island to top edge\nShift+Click: Align selected points/edges (disabled in UV sync mode)\nCTRL+Click: Move entire UV island to trim top edge"""
    bl_idname = "uv.uvv_align_top"
    bl_label = "Align Top"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        # SWAPPED BEHAVIOR: Normal click aligns UV islands, Shift click aligns vertices
        use_island = not event.shift or event.ctrl
        use_trim = event.ctrl
        bpy.ops.uv.uvv_align(direction='UPPER', use_island_mode=use_island, use_trim_bounds=use_trim)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.uv.uvv_align(direction='UPPER', use_island_mode=False, use_trim_bounds=False)
        return {'FINISHED'}


class UVV_OT_align_bottom(Operator):
    """Align UVs to bottom\n\nNormal Click: Move entire UV island to bottom edge\nShift+Click: Align selected points/edges (disabled in UV sync mode)\nCTRL+Click: Move entire UV island to trim bottom edge"""
    bl_idname = "uv.uvv_align_bottom"
    bl_label = "Align Bottom"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        # SWAPPED BEHAVIOR: Normal click aligns UV islands, Shift click aligns vertices
        use_island = not event.shift or event.ctrl
        use_trim = event.ctrl
        bpy.ops.uv.uvv_align(direction='BOTTOM', use_island_mode=use_island, use_trim_bounds=use_trim)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.uv.uvv_align(direction='BOTTOM', use_island_mode=False, use_trim_bounds=False)
        return {'FINISHED'}


class UVV_OT_align_center(Operator):
    """Align UVs to center\n\nNormal Click: Move entire UV island to center\nShift+Click: Align selected points/edges (disabled in UV sync mode)\nCTRL+Click: Move entire UV island to trim center"""
    bl_idname = "uv.uvv_align_center"
    bl_label = "Align Center"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        # SWAPPED BEHAVIOR: Normal click aligns UV islands, Shift click aligns vertices
        use_island = not event.shift or event.ctrl
        use_trim = event.ctrl
        bpy.ops.uv.uvv_align(direction='CENTER', use_island_mode=use_island, use_trim_bounds=use_trim)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.uv.uvv_align(direction='CENTER', use_island_mode=False, use_trim_bounds=False)
        return {'FINISHED'}


class UVV_OT_align_center_horizontal(Operator):
    """Align UVs to horizontal center\n\nNormal Click: Move entire UV island to horizontal center\nShift+Click: Align selected points/edges (disabled in UV sync mode)\nCTRL+Click: Move entire UV island to trim horizontal center"""
    bl_idname = "uv.uvv_align_center_horizontal"
    bl_label = "Align Center Horizontal"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        # SWAPPED BEHAVIOR: Normal click aligns UV islands, Shift click aligns vertices
        use_island = not event.shift or event.ctrl
        use_trim = event.ctrl
        bpy.ops.uv.uvv_align(direction='VERTICAL', use_island_mode=use_island, use_trim_bounds=use_trim)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.uv.uvv_align(direction='VERTICAL', use_island_mode=False, use_trim_bounds=False)
        return {'FINISHED'}


class UVV_OT_align_center_vertical(Operator):
    """Align UVs to vertical center\n\nNormal Click: Move entire UV island to vertical center\nShift+Click: Align selected points/edges (disabled in UV sync mode)\nCTRL+Click: Move entire UV island to trim vertical center"""
    bl_idname = "uv.uvv_align_center_vertical"
    bl_label = "Align Center Vertical"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        # SWAPPED BEHAVIOR: Normal click aligns UV islands, Shift click aligns vertices
        use_island = not event.shift or event.ctrl
        use_trim = event.ctrl
        bpy.ops.uv.uvv_align(direction='HORIZONTAL', use_island_mode=use_island, use_trim_bounds=use_trim)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.uv.uvv_align(direction='HORIZONTAL', use_island_mode=False, use_trim_bounds=False)
        return {'FINISHED'}


class UVV_OT_rotate_90(Operator):
    """Rotate UV islands by specified angle"""
    bl_idname = "uv.uvv_rotate_90"
    bl_label = "Rotate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()

        # Rotate by the angle specified in settings (in radians)
        bpy.ops.transform.rotate(value=math.radians(settings.rotation_angle), orient_axis='Z')
        return {'FINISHED'}


class UVV_OT_mirror_horizontal(Operator):
    """Mirror UV islands horizontally"""
    bl_idname = "uv.uvv_mirror_horizontal"
    bl_label = "Mirror Horizontal"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        # Mirror on X axis
        bpy.ops.transform.mirror(orient_type='GLOBAL', constraint_axis=(True, False, False))
        return {'FINISHED'}


class UVV_OT_mirror_vertical(Operator):
    """Mirror UV islands vertically"""
    bl_idname = "uv.uvv_mirror_vertical"
    bl_label = "Mirror Vertical"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        # Mirror on Y axis
        bpy.ops.transform.mirror(orient_type='GLOBAL', constraint_axis=(False, True, False))
        return {'FINISHED'}


class UVV_OT_distribute_horizontal(Operator):
    """Distribute UV islands horizontally"""
    bl_idname = "uv.uvv_distribute_right"
    bl_label = "Distribute Horizontal"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        self.report({'INFO'}, "Distribute Horizontal - Feature coming soon!")
        return {'FINISHED'}


class UVV_OT_distribute_vertical(Operator):
    """Distribute UV islands vertically"""
    bl_idname = "uv.uvv_distribute_down"
    bl_label = "Distribute Vertical"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        self.report({'INFO'}, "Distribute Vertical - Feature coming soon!")
        return {'FINISHED'}


class UVV_OT_distribute_left(Operator):
    """Distribute UV islands to the left"""
    bl_idname = "uv.uvv_distribute_left"
    bl_label = "Distribute Left"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        self.report({'INFO'}, "Distribute Left - Feature coming soon!")
        return {'FINISHED'}


classes = [
    UVV_OT_align,
    UVV_OT_align_left,
    UVV_OT_align_right,
    UVV_OT_align_top,
    UVV_OT_align_bottom,
    UVV_OT_align_center,
    UVV_OT_align_center_horizontal,
    UVV_OT_align_center_vertical,
    UVV_OT_rotate_90,
    UVV_OT_mirror_horizontal,
    UVV_OT_mirror_vertical,
    UVV_OT_distribute_horizontal,
    UVV_OT_distribute_vertical,
    UVV_OT_distribute_left,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
