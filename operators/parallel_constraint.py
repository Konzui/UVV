import bpy
import bmesh
from bpy.types import Operator
from bpy.props import BoolProperty
from json import dumps, loads
import json
from ..properties import get_uvv_settings


class UVV_OT_parallel_constraint(Operator):
    bl_idname = "uv.uvv_parallel_constraint"
    bl_label = "Parallel Constraint"
    bl_description = "Store two separate, non-connected edges for parallel constraint operations"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Only enable in Edit mode with edge selection"""
        obj = context.active_object
        if obj is None or obj.type != "MESH" or obj.mode != "EDIT":
            return False

        # Allow in UV editor OR 3D viewport
        is_uv_editor = context.area.type == 'IMAGE_EDITOR'
        is_3d_view = context.area.type == 'VIEW_3D'

        if not (is_uv_editor or is_3d_view):
            return False

        # Check if we're in edge selection mode
        tool_settings = context.tool_settings

        # In 3D viewport, always require mesh edge select mode
        if is_3d_view:
            return tool_settings.mesh_select_mode[1]  # Edge mode

        # In UV editor
        if tool_settings.use_uv_select_sync:
            # UV sync mode - check mesh select mode
            return tool_settings.mesh_select_mode[1]  # Edge mode
        else:
            # Non-sync UV mode - check UV select mode
            return tool_settings.uv_select_mode == 'EDGE'

    def execute(self, context):
        """Store the two selected edge groups"""
        obj = context.active_object
        settings = get_uvv_settings()

        # Get BMesh
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active

        if not uv_layer:
            print("[Parallel Constraint ERROR] No active UV layer found")
            self.report({'ERROR'}, "No active UV layer")
            return {'CANCELLED'}

        # Get selected edges (context-aware: works in both UV editor and 3D viewport)
        selected_edges = []

        # In 3D viewport or UV sync mode, use mesh edge selection
        if context.area.type == 'VIEW_3D' or context.tool_settings.use_uv_select_sync:
            selected_edges = [edge for edge in bm.edges if edge.select]
        else:
            # In UV editor (non-sync mode), check UV edge selection
            edge_indices_set = set()
            for face in bm.faces:
                if not face.select:
                    continue
                for edge in face.edges:
                    # Check if edge has UV selection
                    has_uv_selection = any(
                        loop[uv_layer].select_edge
                        for loop in edge.link_loops
                    )
                    if has_uv_selection and edge.index not in edge_indices_set:
                        edge_indices_set.add(edge.index)
                        selected_edges.append(edge)

        print(f"\n[SELECTION DEBUG] Context: {'3D Viewport' if context.area.type == 'VIEW_3D' else 'UV Editor'}")
        print(f"[SELECTION DEBUG] UV Sync: {context.tool_settings.use_uv_select_sync}")
        print(f"[SELECTION DEBUG] Total edges in mesh: {len(bm.edges)}")
        print(f"[SELECTION DEBUG] Selected edges: {len(selected_edges)}")
        print(f"[SELECTION DEBUG] Selected edge indices: {[e.index for e in selected_edges]}")

        if len(selected_edges) == 0:
            print("[Parallel Constraint ERROR] No edges selected")
            self.report({'ERROR'}, "No edges selected")
            return {'CANCELLED'}

        # Group connected edges together
        edge_groups = self.group_connected_edges(selected_edges)

        # Validation: Must have exactly 2 edge groups
        if len(edge_groups) != 2:
            print(f"[Parallel Constraint ERROR] Need exactly 2 separate edge groups (found {len(edge_groups)})")
            print(f"[Parallel Constraint] Total selected edges: {len(selected_edges)}")
            for i, group in enumerate(edge_groups):
                print(f"[Parallel Constraint] Group {i+1}: {len(group)} edges")
            self.report({'ERROR'}, f"Need exactly 2 separate edge groups (found {len(edge_groups)})")
            return {'CANCELLED'}

        group1, group2 = edge_groups

        # Store edge group data (we'll store the first edge of each group as representative)
        edge1 = group1[0]
        edge2 = group2[0]

        # Store edge data including the full group
        edge1_data = self.get_edge_group_data(group1, uv_layer)
        edge2_data = self.get_edge_group_data(group2, uv_layer)

        # Save to properties (legacy support)
        settings.parallel_edge1_object = obj.name
        settings.parallel_edge1_data = dumps(edge1_data)
        settings.parallel_edge2_object = obj.name
        settings.parallel_edge2_data = dumps(edge2_data)
        settings.parallel_constraint_stored = True

        # Detect context
        is_uv_context = context.area.type == 'IMAGE_EDITOR'

        # Also save to new constraint system
        constraint = context.scene.uvv_constraints.add()
        constraint.constraint_type = 'PARALLEL'
        constraint.name = f"Parallel ({len(group1)} + {len(group2)} edges)"
        constraint.object_name = obj.name

        # Store first edge group indices
        edge1_indices = [edge.index for edge in group1]
        constraint.edge_indices = json.dumps(edge1_indices)

        # Store second edge group indices
        constraint.object_name2 = obj.name
        edge2_indices = [edge.index for edge in group2]
        constraint.edge_indices2 = json.dumps(edge2_indices)

        constraint.enabled = True
        constraint.context_type = 'UV' if is_uv_context else '3D'

        # Console output
        print("\n[Parallel Constraint] Stored 2 edge groups successfully")
        print(f"[Parallel Constraint] Group 1: Object '{obj.name}', {len(group1)} edges")
        print(f"[Parallel Constraint] Group 2: Object '{obj.name}', {len(group2)} edges")

        self.report({'INFO'}, "Parallel constraint edge groups stored")
        return {'FINISHED'}

    def group_connected_edges(self, edges):
        """
        Group edges that share at least one vertex.
        """
        if not edges:
            return []
        
        # Print every edge and which vertices it has
        print("\n===== EDGES AND THEIR VERTICES =====")
        for edge in edges:
            print(f"Edge {edge.index}: Vertex {edge.verts[0].index}, Vertex {edge.verts[1].index}")
        
        # Build vertex to edges mapping
        vertex_to_edges = {}
        for edge in edges:
            v0_idx = edge.verts[0].index
            v1_idx = edge.verts[1].index
            
            if v0_idx not in vertex_to_edges:
                vertex_to_edges[v0_idx] = []
            vertex_to_edges[v0_idx].append(edge)
            
            if v1_idx not in vertex_to_edges:
                vertex_to_edges[v1_idx] = []
            vertex_to_edges[v1_idx].append(edge)
        
        # Print which edges connect to each vertex
        print("\n===== VERTICES AND THEIR EDGES =====")
        for vertex_idx in sorted(vertex_to_edges.keys()):
            edge_list = ", ".join([f"Edge {e.index}" for e in vertex_to_edges[vertex_idx]])
            print(f"Vertex {vertex_idx}: {edge_list}")
        print("====================================\n")
        
        # Group edges by connectivity
        unvisited = set(edges)
        groups = []
        
        while unvisited:
            # Start a new group
            current_edge = unvisited.pop()
            current_group = [current_edge]
            
            print(f"[GROUPING] Starting new group with Edge {current_edge.index}")
            
            # Find all connected edges
            edges_to_check = [current_edge]
            
            while edges_to_check:
                check_edge = edges_to_check.pop()
                
                # Get both vertices of this edge
                v0_idx = check_edge.verts[0].index
                v1_idx = check_edge.verts[1].index
                
                # Find all edges that share either vertex
                connected_edges = set()
                if v0_idx in vertex_to_edges:
                    connected_edges.update(vertex_to_edges[v0_idx])
                if v1_idx in vertex_to_edges:
                    connected_edges.update(vertex_to_edges[v1_idx])
                
                # Add unvisited connected edges to the group
                for connected_edge in connected_edges:
                    if connected_edge in unvisited:
                        print(f"[GROUPING]   -> Adding Edge {connected_edge.index} (shares vertex with Edge {check_edge.index})")
                        unvisited.remove(connected_edge)
                        current_group.append(connected_edge)
                        edges_to_check.append(connected_edge)
            
            print(f"[GROUPING] Group complete with {len(current_group)} edges\n")
            groups.append(current_group)
        
        return groups

    def get_edge_data(self, edge, uv_layer):
        """Extract edge data for storage"""
        data = {
            'edge_index': edge.index,
            'vert_indices': [edge.verts[0].index, edge.verts[1].index],
            'uv_coords': []
        }

        # Get UV coordinates for this edge
        # Each edge can have multiple UV coordinates if it's on a UV seam
        # We'll store the first occurrence
        if edge.link_loops:
            loop = edge.link_loops[0]
            # Get both UVs for the edge
            uv1 = loop[uv_layer].uv.copy()
            uv2 = loop.link_loop_next[uv_layer].uv.copy()
            data['uv_coords'] = [[uv1.x, uv1.y], [uv2.x, uv2.y]]

        return data

    def get_edge_group_data(self, edge_group, uv_layer):
        """Extract data for an entire edge group (edge loop)"""
        edges_data = []
        
        for edge in edge_group:
            edge_data = {
                'edge_index': edge.index,
                'vert_indices': [edge.verts[0].index, edge.verts[1].index]
            }
            edges_data.append(edge_data)
        
        return {
            'edges': edges_data,
            'count': len(edge_group)
        }


class UVV_OT_parallel_constraint_debug_select(Operator):
    bl_idname = "uv.uvv_parallel_constraint_debug_select"
    bl_label = "Debug Select"
    bl_description = "Re-select the stored parallel constraint edges for debugging"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Only enable if edges are stored and we're in edit mode"""
        obj = context.active_object
        if obj is None or obj.type != "MESH" or obj.mode != "EDIT":
            return False

        settings = get_uvv_settings()
        return settings.parallel_constraint_stored

    def execute(self, context):
        """Re-select the stored edges"""
        settings = get_uvv_settings()

        # Check if data exists
        if not settings.parallel_constraint_stored:
            print("[Debug ERROR] No stored edges found")
            self.report({'ERROR'}, "No stored edges found")
            return {'CANCELLED'}

        # Get the stored object
        obj_name = settings.parallel_edge1_object
        if obj_name not in bpy.data.objects:
            print(f"[Debug ERROR] Object '{obj_name}' not found")
            self.report({'ERROR'}, f"Object '{obj_name}' not found")
            return {'CANCELLED'}

        obj = bpy.data.objects[obj_name]

        # Make sure the object is the active object and in edit mode
        if context.active_object != obj:
            print(f"[Debug ERROR] Please select object '{obj_name}' first")
            self.report({'ERROR'}, f"Please select object '{obj_name}' first")
            return {'CANCELLED'}

        # Get BMesh
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active

        if not uv_layer:
            print("[Debug ERROR] No active UV layer found")
            self.report({'ERROR'}, "No active UV layer")
            return {'CANCELLED'}

        # Parse stored edge data
        try:
            edge1_data = loads(settings.parallel_edge1_data)
            edge2_data = loads(settings.parallel_edge2_data)
        except Exception as e:
            print(f"[Debug ERROR] Failed to parse stored edge data: {e}")
            self.report({'ERROR'}, "Failed to parse stored edge data")
            return {'CANCELLED'}

        # Clear current selection - deselect all edges
        print("[Debug] Clearing current selection...")
        for edge in bm.edges:
            edge.select = False
        
        # Also deselect vertices (for clean visualization)
        for vert in bm.verts:
            vert.select = False

        # Ensure lookup table is built
        bm.edges.ensure_lookup_table()

        # Select all edges from both groups
        total_selected = 0
        group1_count = 0
        group2_count = 0

        try:
            # Select edges from group 1
            if 'edges' in edge1_data:
                # New format: multiple edges in a group
                print(f"[Debug] Selecting group 1 ({len(edge1_data['edges'])} edges)...")
                for edge_info in edge1_data['edges']:
                    edge_index = edge_info['edge_index']
                    edge = bm.edges[edge_index]
                    edge.select = True
                    print(f"[Debug]   -> Selected edge {edge_index}")
                    group1_count += 1
            else:
                # Old format: single edge (backwards compatibility)
                edge_index = edge1_data['edge_index']
                edge = bm.edges[edge_index]
                edge.select = True
                group1_count += 1

            # Select edges from group 2
            if 'edges' in edge2_data:
                # New format: multiple edges in a group
                print(f"[Debug] Selecting group 2 ({len(edge2_data['edges'])} edges)...")
                for edge_info in edge2_data['edges']:
                    edge_index = edge_info['edge_index']
                    edge = bm.edges[edge_index]
                    edge.select = True
                    print(f"[Debug]   -> Selected edge {edge_index}")
                    group2_count += 1
            else:
                # Old format: single edge (backwards compatibility)
                edge_index = edge2_data['edge_index']
                edge = bm.edges[edge_index]
                edge.select = True
                group2_count += 1

            total_selected = group1_count + group2_count

            # Update mesh to reflect the selection
            bmesh.update_edit_mesh(obj.data)
            
            # Force viewport update
            context.view_layer.objects.active = obj
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

            print("\n[Debug] Re-selected stored edge groups")
            print(f"[Debug] Group 1: Object '{obj_name}', {group1_count} edges")
            print(f"[Debug] Group 2: Object '{obj_name}', {group2_count} edges")
            print(f"[Debug] Total: {total_selected} edges")

            self.report({'INFO'}, f"Re-selected {total_selected} edges from 2 groups")
            return {'FINISHED'}

        except IndexError as e:
            print(f"[Debug ERROR] Edge index not found in mesh: {e}")
            self.report({'ERROR'}, "Stored edge indices not found in current mesh")
            return {'CANCELLED'}


classes = [
    UVV_OT_parallel_constraint,
    UVV_OT_parallel_constraint_debug_select,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
