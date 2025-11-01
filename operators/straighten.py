# Straighten operator - ported from Mio3 UV addon
import bpy
import bmesh
import json
from bpy.props import BoolProperty, EnumProperty
from bpy.types import Operator
from ..utils.straighten_utils import straight_uv_nodes
from ..utils.uv_node_manager import UVNodeManager


class UVV_OT_straighten(Operator):
    """Straighten selected edge loop to a line"""
    bl_idname = "uv.uvv_straighten"
    bl_label = "Straighten"
    bl_description = "Unwrap selected edge loop to a straight line. Compatible with constraints (Parallel, Horizontal, Vertical)"
    bl_options = {"REGISTER", "UNDO"}

    align_type: EnumProperty(
        name="Align",
        items=[
            ("GEOMETRY", "Geometry", "Align based on 3D geometry distances"),
            ("EVEN", "Even", "Evenly distribute along the line"),
            ("NONE", "None", "Keep relative UV distances"),
        ],
        default="GEOMETRY"
    )

    keep_length: BoolProperty(
        name="Preserve Length",
        default=True,
        description="Maintain the original UV length of the edge loop"
    )

    # Constraint application settings
    apply_parallel_alignment: BoolProperty(
        name="Apply Parallel Alignment",
        default=False,
        description="Align parallel constraint edge groups after straightening"
    )

    # Parallel constraint controls
    parallel_align_group_1: BoolProperty(
        name="Align Group 1",
        default=True,
        description="Apply alignment to the first edge group of parallel constraint"
    )

    parallel_align_group_2: BoolProperty(
        name="Align Group 2",
        default=True,
        description="Apply alignment to the second edge group of parallel constraint"
    )

    parallel_alignment_mode: EnumProperty(
        name="Alignment Mode",
        items=[
            ("AUTO", "Auto Detect", "Automatically detect best axis for each group"),
            ("HORIZONTAL", "Horizontal", "Align Y values (create horizontal lines)"),
            ("VERTICAL", "Vertical", "Align X values (create vertical lines)"),
        ],
        default="AUTO",
        description="How to align the parallel constraint edge groups"
    )

    # Other constraints
    apply_horizontal_constraint: BoolProperty(
        name="Apply Horizontal Constraint",
        default=False,
        description="Apply horizontal constraints if found"
    )
    
    horizontal_constraint_mode: EnumProperty(
        name="Horizontal Alignment",
        items=[
            ("INDIVIDUAL", "Individual", "Align each edge separately"),
            ("GROUP", "Group", "Align all edges together as one group"),
        ],
        default="INDIVIDUAL",
        description="How to align horizontal constraint edges"
    )

    apply_vertical_constraint: BoolProperty(
        name="Apply Vertical Constraint",
        default=False,
        description="Apply vertical constraints if found"
    )
    
    vertical_constraint_mode: EnumProperty(
        name="Vertical Alignment",
        items=[
            ("INDIVIDUAL", "Individual", "Align each edge separately"),
            ("GROUP", "Group", "Align all edges together as one group"),
        ],
        default="INDIVIDUAL",
        description="How to align vertical constraint edges"
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

    @staticmethod
    def get_selected_objects(context):
        return [obj for obj in context.objects_in_mode if obj.type == "MESH"]

    def execute(self, context):
        objects = self.get_selected_objects(context)
        obj = context.active_object

        use_uv_select_sync = context.tool_settings.use_uv_select_sync

        # Store the originally selected island faces for later restoration
        bm = bmesh.from_edit_mesh(obj.data)
        original_selected_faces = [f for f in bm.faces if f.select]

        # Check if we have specific edge selection or full island selection
        has_edge_selection = self.has_specific_edge_selection(context, obj)

        # Initialize constraint variables (used throughout the function)
        constraint_edges_selected = False
        parallel_constraint = None
        horizontal_constraint = None
        vertical_constraint = None

        if not has_edge_selection:
            print("\n[Straighten] ========================================")
            print("[Straighten] NO specific edges selected - searching for constraints...")
            print("[Straighten] ========================================")

            # Find all applicable constraints for this island
            parallel_constraint = self.find_constraint_by_type(context, obj, original_selected_faces, 'PARALLEL')
            horizontal_constraint = self.find_constraint_by_type(context, obj, original_selected_faces, 'HORIZONTAL')
            vertical_constraint = self.find_constraint_by_type(context, obj, original_selected_faces, 'VERTICAL')

            print(f"\n[Straighten] Found constraints:")
            print(f"  - Parallel: {'✅ ' + parallel_constraint.name if parallel_constraint else '❌ None'}")
            print(f"  - Horizontal: {'✅ ' + horizontal_constraint.name if horizontal_constraint else '❌ None'}")
            print(f"  - Vertical: {'✅ ' + vertical_constraint.name if vertical_constraint else '❌ None'}")

            if parallel_constraint:
                print("\n[Straighten] ✅ PARALLEL CONSTRAINT FOUND!")
                print(f"[Straighten] Constraint name: {parallel_constraint.name}")
                print("[Straighten] ========================================\n")

                # Deselect everything first
                print("[Straighten] STEP 1: Deselecting all UV elements...")
                self.deselect_all_uv(context, obj)

                # Select only the constraint edges
                print("[Straighten] STEP 2: Selecting parallel constraint edges...")
                if not self.select_constraint_edges(context, obj, parallel_constraint):
                    print("[Straighten] ❌ ERROR: Failed to select constraint edges")
                    self.report({'WARNING'}, "Failed to apply parallel constraint edges")
                    return {'CANCELLED'}

                print("[Straighten] ✅ Constraint edges selected successfully")
                constraint_edges_selected = True

                print("[Straighten] STEP 3: Proceeding with parallel straighten operation...")
                print("[Straighten] ========================================\n")
            else:
                print("\n[Straighten] ❌ NO parallel constraint found")
                print("[Straighten] ========================================\n")
                self.report({'WARNING'}, "No specific edges selected and no applicable parallel constraints found")
                return {'CANCELLED'}

        # IMPORTANT: Only create node manager AFTER constraint edges are selected
        # Don't create it here if we're using constraints

        if use_uv_select_sync and not constraint_edges_selected:
            # Sync UV selection from mesh (only if NOT using constraints)
            self.sync_uv_from_mesh(context, objects)
            bpy.ops.mesh.select_linked(delimit={"UV"})
            context.tool_settings.use_uv_select_sync = False

        # Change UV select mode to EDGE for proper node detection
        uv_select_mode = context.tool_settings.uv_select_mode
        original_uv_select_mode = uv_select_mode
        if uv_select_mode == "FACE":
            print("[Straighten] Changing UV select mode from FACE to EDGE")
            context.tool_settings.uv_select_mode = "EDGE"

        # Debug: Check what's selected before creating node manager
        if constraint_edges_selected:
            print("\n[Straighten] ===== PRE-NODE-MANAGER DEBUG =====")
            bm_check = bmesh.from_edit_mesh(obj.data)
            uv_layer_check = bm_check.loops.layers.uv.active
            edge_count = sum(1 for e in bm_check.edges if e.select)
            face_count = sum(1 for f in bm_check.faces if f.select)
            uv_edge_sel_count = sum(1 for f in bm_check.faces for loop in f.loops if loop[uv_layer_check].select_edge)
            uv_vert_sel_count = sum(1 for f in bm_check.faces for loop in f.loops if loop[uv_layer_check].select)
            print(f"[Straighten] Mesh edges selected: {edge_count}")
            print(f"[Straighten] Mesh faces selected: {face_count}")
            print(f"[Straighten] UV edges with select_edge: {uv_edge_sel_count}")
            print(f"[Straighten] UV verts with select: {uv_vert_sel_count}")
            print("[Straighten] ====================================\n")

        # NOW create the node manager (after constraint edges are selected)
        if use_uv_select_sync and not constraint_edges_selected:
            node_manager = UVNodeManager(objects, mode="VERT")
        else:
            print("[Straighten] Creating UVNodeManager in EDGE mode...")
            node_manager = UVNodeManager(objects, mode="EDGE")

        # Store original selection
        print(f"[Straighten] Found {len(node_manager.groups)} node groups")
        for idx, group in enumerate(node_manager.groups):
            print(f"[Straighten] Group {idx}: {len(group.nodes)} nodes")
            group.store_selection()

        # Straighten UV nodes
        print("[Straighten] Starting straighten operation on node groups...")
        for idx, group in enumerate(node_manager.groups):
            print(f"[Straighten] Processing group {idx} with {len(group.nodes)} nodes...")
            straight_uv_nodes(group, self.align_type, self.keep_length, center=True)
            for node in group.nodes:
                node.update_uv(group.uv_layer)
            print(f"[Straighten] ✅ Group {idx} processed")

        # Pin, unwrap, and restore
        print("[Straighten] Pinning straightened edges...")
        bpy.ops.uv.pin(clear=False)

        print("[Straighten] Selecting linked UVs...")
        bpy.ops.uv.select_linked()

        print("[Straighten] Unwrapping...")
        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.001)

        print("[Straighten] Deselecting all...")
        bpy.ops.uv.select_all(action="DESELECT")

        print("[Straighten] Restoring node group selections...")
        for group in node_manager.groups:
            group.restore_selection()

        print("[Straighten] Clearing pins...")
        bpy.ops.uv.pin(clear=True)

        print("[Straighten] Updating UV meshes...")
        node_manager.update_uvmeshes()

        # Don't restore original island selection - leave constraint edges selected
        if constraint_edges_selected:
            print("[Straighten] Keeping constraint edges selected (not restoring island selection)")

        # Apply smart axis alignment for parallel constraints (if enabled)
        # IMPORTANT: Process each group in complete isolation to avoid merging them
        if parallel_constraint and self.apply_parallel_alignment:
            print("\n[Straighten] ========================================")
            print("[Straighten] APPLYING PARALLEL ALIGNMENT (USER ENABLED)")
            print(f"[Straighten] Mode: {self.parallel_alignment_mode}")
            print(f"[Straighten] Group 1: {'ENABLED' if self.parallel_align_group_1 else 'DISABLED'}")
            print(f"[Straighten] Group 2: {'ENABLED' if self.parallel_align_group_2 else 'DISABLED'}")
            print("[Straighten] ========================================\n")
            
            try:
                # Get edge groups from parallel constraint
                edge_indices1 = json.loads(parallel_constraint.edge_indices)
                edge_indices2 = json.loads(parallel_constraint.edge_indices2) if parallel_constraint.edge_indices2 else []
                
                # Process Group 1 (if enabled)
                if edge_indices1 and self.parallel_align_group_1:
                    print(f"\n[Straighten] Processing Edge Group 1 ({len(edge_indices1)} edges)...")
                    
                    # Determine alignment axis
                    if self.parallel_alignment_mode == "AUTO":
                        alignment_axis1 = self.detect_edge_group_axis(obj, edge_indices1)
                        print(f"[Straighten] → Auto-detected: {alignment_axis1}")
                    else:
                        alignment_axis1 = self.parallel_alignment_mode
                        print(f"[Straighten] → Manual override: {alignment_axis1}")
                    
                    print(f"[Straighten] → Applying {alignment_axis1} alignment to Group 1")
                    self.apply_alignment_to_edge_group(context, obj, edge_indices1, alignment_axis1)
                elif edge_indices1 and not self.parallel_align_group_1:
                    print(f"\n[Straighten] Group 1 alignment DISABLED by user - skipping")
                
                # Process Group 2 (if enabled)
                if edge_indices2 and self.parallel_align_group_2:
                    print(f"\n[Straighten] Processing Edge Group 2 ({len(edge_indices2)} edges)...")
                    
                    # Determine alignment axis
                    if self.parallel_alignment_mode == "AUTO":
                        alignment_axis2 = self.detect_edge_group_axis(obj, edge_indices2)
                        print(f"[Straighten] → Auto-detected: {alignment_axis2}")
                    else:
                        alignment_axis2 = self.parallel_alignment_mode
                        print(f"[Straighten] → Manual override: {alignment_axis2}")
                    
                    print(f"[Straighten] → Applying {alignment_axis2} alignment to Group 2")
                    self.apply_alignment_to_edge_group(context, obj, edge_indices2, alignment_axis2)
                elif edge_indices2 and not self.parallel_align_group_2:
                    print(f"\n[Straighten] Group 2 alignment DISABLED by user - skipping")
                    
            except Exception as e:
                print(f"[Straighten] ❌ ERROR in parallel alignment: {e}")
                import traceback
                traceback.print_exc()
        elif parallel_constraint and not self.apply_parallel_alignment:
            print("\n[Straighten] Parallel alignment DISABLED by user - skipping")

        # Apply horizontal constraints if they exist (for non-parallel constraints)
        if horizontal_constraint and not parallel_constraint and self.apply_horizontal_constraint:
            print("\n" + "="*80)
            print("HORIZONTAL CONSTRAINT ALIGNMENT")
            print("="*80)
            print(f"Constraint: {horizontal_constraint.name}")
            print(f"Mode: {self.horizontal_constraint_mode}")
            
            try:
                edge_indices = json.loads(horizontal_constraint.edge_indices)
                print(f"Edges to align: {len(edge_indices)}")
                print(f"Edge indices: {edge_indices}")
                
                # Apply alignment based on mode
                if self.horizontal_constraint_mode == "INDIVIDUAL":
                    print("→ INDIVIDUAL mode: Each edge aligns to its own center Y")
                    self.apply_alignment_to_edge_group_with_mode(context, obj, edge_indices, 'HORIZONTAL', 'INDIVIDUAL')
                else:  # GROUP
                    print("→ GROUP mode: All edges align to same Y position")
                    self.apply_alignment_to_edge_group_with_mode(context, obj, edge_indices, 'HORIZONTAL', 'ALIGN')
                
                print("✅ Horizontal constraint applied successfully")
                print("="*80 + "\n")
                    
            except Exception as e:
                print(f"❌ ERROR in horizontal constraint: {e}")
                import traceback
                traceback.print_exc()
                print("="*80 + "\n")

        # Apply vertical constraints if they exist (for non-parallel constraints)
        if vertical_constraint and not parallel_constraint and self.apply_vertical_constraint:
            print("\n" + "="*80)
            print("VERTICAL CONSTRAINT ALIGNMENT")
            print("="*80)
            print(f"Constraint: {vertical_constraint.name}")
            print(f"Mode: {self.vertical_constraint_mode}")
            
            try:
                edge_indices = json.loads(vertical_constraint.edge_indices)
                print(f"Edges to align: {len(edge_indices)}")
                print(f"Edge indices: {edge_indices}")
                
                # Apply alignment based on mode
                if self.vertical_constraint_mode == "INDIVIDUAL":
                    print("→ INDIVIDUAL mode: Each edge aligns to its own center X")
                    self.apply_alignment_to_edge_group_with_mode(context, obj, edge_indices, 'VERTICAL', 'INDIVIDUAL')
                else:  # GROUP
                    print("→ GROUP mode: All edges align to same X position")
                    self.apply_alignment_to_edge_group_with_mode(context, obj, edge_indices, 'VERTICAL', 'ALIGN')
                
                print("✅ Vertical constraint applied successfully")
                print("="*80 + "\n")
                    
            except Exception as e:
                print(f"❌ ERROR in vertical constraint: {e}")
                import traceback
                traceback.print_exc()
                print("="*80 + "\n")

        # Restore original UV select mode
        if original_uv_select_mode != context.tool_settings.uv_select_mode:
            print(f"[Straighten] Restoring UV select mode to {original_uv_select_mode}")
            context.tool_settings.uv_select_mode = original_uv_select_mode

        if use_uv_select_sync:
            context.tool_settings.use_uv_select_sync = True

        print("\n[Straighten] ========================================")
        print("[Straighten] OPERATION COMPLETE")
        print("[Straighten] ========================================\n")

        return {"FINISHED"}

    def has_specific_edge_selection(self, context, obj):
        """Check if specific edges are selected (not just face selection)"""
        if not obj or obj.type != 'MESH':
            return False

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active

        if not uv_layer:
            return False

        # Debug: Count selected elements
        selected_faces = [f for f in bm.faces if f.select]
        selected_edges = [e for e in bm.edges if e.select]

        print("\n===== STRAIGHTEN SELECTION DEBUG =====")
        print(f"UV Sync Mode: {context.tool_settings.use_uv_select_sync}")
        print(f"Total faces in mesh: {len(bm.faces)}")
        print(f"Selected faces: {len(selected_faces)}")
        print(f"Selected edges (mesh): {len(selected_edges)}")

        # Count UV edge selections
        uv_edge_count = 0
        uv_vert_count = 0
        for face in bm.faces:
            if not face.select:
                continue
            for loop in face.loops:
                if loop[uv_layer].select_edge:
                    uv_edge_count += 1
                if loop[uv_layer].select:
                    uv_vert_count += 1

        print(f"UV edges with select_edge: {uv_edge_count}")
        print(f"UV verts selected: {uv_vert_count}")

        # Check if entire island is selected (all faces, no specific edges)
        all_faces_selected = len(selected_faces) == len([f for f in bm.faces if not f.hide])

        print(f"All faces selected: {all_faces_selected}")

        # In UV sync mode, check if edges are selected
        if context.tool_settings.use_uv_select_sync:
            # Check if any edges are specifically selected (not just implied by face selection)
            has_edges = len(selected_edges) > 0
            print(f"Has specific edge selection (sync mode): {has_edges}")
            print("======================================\n")
            return has_edges

        # Check UV selection mode
        uv_select_mode = context.tool_settings.uv_select_mode
        print(f"UV Select Mode: {uv_select_mode}")

        # Count total UV edges in selected faces (to compare with selected edge count)
        total_uv_edges_in_selection = 0
        for face in selected_faces:
            total_uv_edges_in_selection += len(face.loops)

        print(f"Total UV edges in selected faces: {total_uv_edges_in_selection}")
        print(f"UV edges with select_edge flag: {uv_edge_count}")

        # Key logic: If ALL edges of the selected faces have select_edge = True,
        # then the entire island is selected (pressed L in UV editor or selected faces)
        # If only SOME edges have select_edge = True, then specific edges were selected

        if len(selected_faces) > 0 and uv_edge_count > 0:
            # Calculate selection ratio
            selection_ratio = uv_edge_count / total_uv_edges_in_selection if total_uv_edges_in_selection > 0 else 0
            print(f"Edge selection ratio: {selection_ratio:.2f} ({uv_edge_count}/{total_uv_edges_in_selection})")

            # If most edges are selected (>90%), it's likely full island selection
            # If only some edges selected (<90%), it's specific edge selection
            if selection_ratio > 0.9:
                print("DETECTED: Full island selection (>90% of edges selected)")
                print("======================================\n")
                return False  # Full island, use constraints
            else:
                print("DETECTED: Specific edge selection (<90% of edges)")
                print("======================================\n")
                return True  # Specific edges selected

        # In EDGE mode with edges selected
        if uv_select_mode == 'EDGE' and uv_edge_count > 0:
            print("DETECTED: Specific UV edges selected (edge mode)")
            print("======================================\n")
            return True

        # No edges selected at all
        if len(selected_faces) > 0 and uv_edge_count == 0:
            print("DETECTED: Faces selected, no edges (full island)")
            print("======================================\n")
            return False

        # No faces selected at all
        print("DETECTED: Nothing selected")
        print("======================================\n")
        return False

    def deselect_all_uv(self, context, obj):
        """Deselect all UV elements"""
        if not obj or obj.type != 'MESH':
            return

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active

        if not uv_layer:
            return

        print("[Straighten] Deselecting all UV elements")

        # Deselect all mesh elements
        for edge in bm.edges:
            edge.select = False
        for vert in bm.verts:
            vert.select = False

        # Deselect all UV elements
        for face in bm.faces:
            for loop in face.loops:
                loop[uv_layer].select = False
                loop[uv_layer].select_edge = False

        bmesh.update_edit_mesh(obj.data)

    def find_constraint_by_type(self, context, obj, selected_faces_list, constraint_type):
        """Find a constraint of specific type that applies to the selected island"""
        if not obj:
            print(f"[Straighten] find_constraint ({constraint_type}): No object provided")
            return None

        print(f"[Straighten] find_constraint ({constraint_type}): Searching...")

        # Get all enabled constraints of this type for this object
        for constraint in context.scene.uvv_constraints:
            if not constraint.enabled:
                continue
            if constraint.constraint_type != constraint_type:
                continue
            if constraint.object_name != obj.name:
                continue

            # Check if constraint edges are part of the selected island
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                continue

            # Check if any constraint edges belong to the selected island
            try:
                edge_indices = json.loads(constraint.edge_indices)
                bm.edges.ensure_lookup_table()

                # Check if any edge from the constraint is in the selected island
                for edge_idx in edge_indices:
                    if edge_idx < len(bm.edges):
                        edge = bm.edges[edge_idx]
                        # Check if this edge belongs to any selected face
                        for face in edge.link_faces:
                            if face in selected_faces_list:
                                print(f"[Straighten] find_constraint ({constraint_type}): ✅ Found '{constraint.name}'")
                                return constraint
            except Exception as e:
                print(f"[Straighten] find_constraint ({constraint_type}): ❌ ERROR: {e}")
                continue

        print(f"[Straighten] find_constraint ({constraint_type}): ❌ None found")
        return None

    def find_applicable_parallel_constraint(self, context, obj):
        """Find a parallel constraint that applies to the current object and selected island"""
        if not obj:
            print("[Straighten] find_constraint: No object provided")
            return None

        print(f"[Straighten] find_constraint: Searching for constraints on object '{obj.name}'...")
        print(f"[Straighten] find_constraint: Total constraints in scene: {len(context.scene.uvv_constraints)}")

        # Get all enabled parallel constraints for this object
        constraint_count = 0
        for constraint in context.scene.uvv_constraints:
            constraint_count += 1
            print(f"\n[Straighten] find_constraint: Checking constraint #{constraint_count}: '{constraint.name}'")
            print(f"[Straighten]   - Type: {constraint.constraint_type}")
            print(f"[Straighten]   - Enabled: {constraint.enabled}")
            print(f"[Straighten]   - Object: {constraint.object_name}")

            if not constraint.enabled:
                print(f"[Straighten]   ❌ SKIPPED: Not enabled")
                continue
            if constraint.constraint_type != 'PARALLEL':
                print(f"[Straighten]   ❌ SKIPPED: Not a parallel constraint")
                continue
            if constraint.object_name != obj.name:
                print(f"[Straighten]   ❌ SKIPPED: Wrong object (expected '{obj.name}')")
                continue

            print(f"[Straighten]   ✅ Constraint matches criteria, checking island...")

            # Check if constraint edges are part of the selected island
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                print(f"[Straighten]   ❌ SKIPPED: No UV layer")
                continue

            # Get selected faces (the island)
            selected_faces = [f for f in bm.faces if f.select]
            print(f"[Straighten]   Selected faces in island: {len(selected_faces)}")

            if not selected_faces:
                print(f"[Straighten]   ❌ SKIPPED: No selected faces")
                continue

            # Check if any constraint edges belong to the selected island
            try:
                edge_indices = json.loads(constraint.edge_indices)
                print(f"[Straighten]   Constraint has {len(edge_indices)} edges in group 1")
                bm.edges.ensure_lookup_table()

                # Check if any edge from the constraint is in the selected island
                for edge_idx in edge_indices:
                    if edge_idx < len(bm.edges):
                        edge = bm.edges[edge_idx]
                        # Check if this edge belongs to any selected face
                        for face in edge.link_faces:
                            if face in selected_faces:
                                print(f"[Straighten]   ✅✅✅ MATCH FOUND! Edge {edge_idx} belongs to selected island")
                                print(f"[Straighten]   Returning constraint: '{constraint.name}'")
                                return constraint
                print(f"[Straighten]   ❌ SKIPPED: No edges match selected island")
            except Exception as e:
                print(f"[Straighten]   ❌ ERROR parsing constraint: {e}")
                continue

        print(f"\n[Straighten] find_constraint: No applicable constraint found after checking {constraint_count} constraints")
        return None

    def detect_edge_group_axis(self, obj, edge_indices):
        """
        Detect the dominant direction of an edge group in UV space.
        Returns 'HORIZONTAL' if edges run more sideways, 'VERTICAL' if more up/down.
        
        This analyzes the actual edge directions (vectors), not just the bounding box.
        """
        try:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer or not edge_indices:
                return 'HORIZONTAL'  # Default fallback

            # Collect edge direction vectors
            edge_vectors = []
            for edge_idx in edge_indices:
                if edge_idx >= len(bm.edges):
                    continue
                edge = bm.edges[edge_idx]
                
                # Get UV coordinates for this edge
                for loop in edge.link_loops:
                    uv1 = loop[uv_layer].uv.copy()
                    uv2 = loop.link_loop_next[uv_layer].uv.copy()
                    
                    # Calculate direction vector for this edge
                    direction = uv2 - uv1
                    edge_vectors.append(direction)
                    break  # Only need one loop per edge

            if not edge_vectors:
                return 'HORIZONTAL'  # Default fallback

            # Calculate average direction by summing absolute X and Y components
            total_abs_x = sum(abs(vec.x) for vec in edge_vectors)
            total_abs_y = sum(abs(vec.y) for vec in edge_vectors)

            print(f"[Straighten] detect_axis: Analyzing {len(edge_vectors)} edge directions")
            print(f"[Straighten]   - Total absolute X displacement: {total_abs_x:.4f}")
            print(f"[Straighten]   - Total absolute Y displacement: {total_abs_y:.4f}")

            # If edges move more in X direction, they're horizontal edges
            # If edges move more in Y direction, they're vertical edges
            if total_abs_x > total_abs_y:
                detected_axis = 'HORIZONTAL'
                print(f"[Straighten]   → Detected HORIZONTAL edges (run left-right, align Y values)")
            else:
                detected_axis = 'VERTICAL'
                print(f"[Straighten]   → Detected VERTICAL edges (run up-down, align X values)")

            # Also show individual edge info for debugging
            print(f"[Straighten]   Edge directions:")
            for i, vec in enumerate(edge_vectors[:5]):  # Show first 5 edges
                print(f"[Straighten]     Edge {i+1}: X={vec.x:.4f}, Y={vec.y:.4f}")
            if len(edge_vectors) > 5:
                print(f"[Straighten]     ... and {len(edge_vectors) - 5} more edges")

            return detected_axis

        except Exception as e:
            print(f"[Straighten] detect_axis: ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return 'HORIZONTAL'  # Default fallback

    def apply_alignment_to_edge_group(self, context, obj, edge_indices, alignment_type):
        """Apply horizontal or vertical alignment to a specific edge group (uses INDIVIDUAL mode)"""
        return self.apply_alignment_to_edge_group_with_mode(context, obj, edge_indices, alignment_type, 'INDIVIDUAL')

    def apply_alignment_to_edge_group_with_mode(self, context, obj, edge_indices, alignment_type, align_mode):
        """
        Apply horizontal or vertical alignment to a specific edge group with mode control
        
        alignment_type: 'HORIZONTAL' or 'VERTICAL'
        align_mode: 'INDIVIDUAL' (each edge separately) or 'ALIGN' (all edges together)
        """
        try:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                print(f"  ❌ No UV layer")
                return

            # Deselect ALL mesh and UV edges first
            for edge in bm.edges:
                edge.select = False
            
                for face in bm.faces:
                    for loop in face.loops:
                        loop[uv_layer].select_edge = False
                        loop[uv_layer].select = False

            # Select ONLY the edges in this group
            selected_count = 0
            for edge_idx in edge_indices:
                if edge_idx >= len(bm.edges):
                    print(f"  ⚠ Edge {edge_idx} out of range")
                    continue

                edge = bm.edges[edge_idx]
                edge.select = True
                
                # Select vertices and UV
                for vert in edge.verts:
                    vert.select = True
                
                for loop in edge.link_loops:
                    loop[uv_layer].select_edge = True
                    loop[uv_layer].select = True

                selected_count += 1

            print(f"  Selected {selected_count} edges for alignment")
            bmesh.update_edit_mesh(obj.data)

            # Call the align operator
            if alignment_type == 'HORIZONTAL':
                bpy.ops.uv.uvv_align(direction='HORIZONTAL', mode=align_mode)
            else:  # VERTICAL
                bpy.ops.uv.uvv_align(direction='VERTICAL', mode=align_mode)

            # Deselect mesh edges after alignment
            for edge_idx in edge_indices:
                if edge_idx < len(bm.edges):
                    bm.edges[edge_idx].select = False

            bmesh.update_edit_mesh(obj.data)

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    def apply_alignment_constraint(self, context, obj, constraint, alignment_type):
        """Apply horizontal or vertical alignment to constraint edges (legacy method)"""
        print(f"[Straighten] apply_alignment_constraint: Starting {alignment_type} alignment...")
        
        try:
            edge_indices = json.loads(constraint.edge_indices)
            self.apply_alignment_to_edge_group(context, obj, edge_indices, alignment_type)
        except Exception as e:
            print(f"[Straighten] apply_alignment_constraint: ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    def select_constraint_edges(self, context, obj, constraint):
        """Select edges from a parallel constraint"""
        print(f"\n[Straighten] select_constraint_edges: Starting...")
        if not obj or not constraint:
            print(f"[Straighten] select_constraint_edges: ❌ No obj or constraint")
            return False

        try:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                print(f"[Straighten] select_constraint_edges: ❌ No UV layer")
                return False

            # Parse edge indices from both groups
            edge_indices1 = json.loads(constraint.edge_indices)
            edge_indices2 = json.loads(constraint.edge_indices2) if constraint.edge_indices2 else []

            print(f"[Straighten] select_constraint_edges: Group 1 has {len(edge_indices1)} edges: {edge_indices1}")
            print(f"[Straighten] select_constraint_edges: Group 2 has {len(edge_indices2)} edges: {edge_indices2}")

            # Deselect only UV elements (keep faces selected for visibility in 3D viewport)
            print(f"[Straighten] select_constraint_edges: Deselecting UV edges/verts (keeping faces)...")
            for face in bm.faces:
                for loop in face.loops:
                    loop[uv_layer].select_edge = False
                    loop[uv_layer].select = False

            # Deselect mesh edges (but keep faces!)
            for edge in bm.edges:
                edge.select = False

            # Select edges from both groups
            selected_count = 0
            all_indices = edge_indices1 + edge_indices2
            print(f"[Straighten] select_constraint_edges: Selecting {len(all_indices)} total edges...")

            for edge_idx in all_indices:
                if edge_idx < len(bm.edges):
                    edge = bm.edges[edge_idx]
                    edge.select = True
                    print(f"[Straighten]   ✅ Selected edge {edge_idx} (mesh)")

                    # Also select vertices of the edge (needed for UV editor visibility)
                    for vert in edge.verts:
                        vert.select = True

                    # Select in UV editor
                    loop_count = 0
                    for loop in edge.link_loops:
                        loop[uv_layer].select_edge = True  # Edge selection in UV
                        loop[uv_layer].select = True  # Vertex selection in UV
                        loop_count += 1
                    print(f"[Straighten]   ✅ Selected edge {edge_idx} in UV editor ({loop_count} loops)")
                    selected_count += 1
                else:
                    print(f"[Straighten]   ❌ Edge {edge_idx} out of range (max: {len(bm.edges)-1})")

            bmesh.update_edit_mesh(obj.data)

            # Force viewport and UV editor update
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type in {'VIEW_3D', 'IMAGE_EDITOR'}:
                        area.tag_redraw()

            print(f"[Straighten] select_constraint_edges: ✅ Selected {selected_count}/{len(all_indices)} edges successfully")
            return selected_count > 0

        except Exception as e:
            print(f"[Straighten] select_constraint_edges: ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def sync_uv_from_mesh(context, selected_objects):
        """Sync UV selection from mesh selection"""
        objects = selected_objects if selected_objects else context.objects_in_mode
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
            bmesh.update_edit_mesh(obj.data)

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = True
        
        # Straighten settings
        box = layout.box()
        box.label(text="Straighten Settings", icon='OUTLINER_DATA_CURVES')
        box.prop(self, "align_type", expand=True)
        box.prop(self, "keep_length")
        
        # Parallel constraint settings
        box = layout.box()
        box.label(text="Parallel Constraint", icon='MOD_ARRAY')
        box.prop(self, "apply_parallel_alignment")
        
        # Show detailed controls only when parallel alignment is enabled
        if self.apply_parallel_alignment:
            sub = box.box()
            sub.label(text="Alignment Settings:")
            sub.prop(self, "parallel_alignment_mode", text="Mode")
            
            row = sub.row(align=True)
            row.prop(self, "parallel_align_group_1", toggle=True)
            row.prop(self, "parallel_align_group_2", toggle=True)
        
        # Horizontal constraint settings
        box = layout.box()
        box.label(text="Horizontal Constraint", icon='TRIA_RIGHT')
        box.prop(self, "apply_horizontal_constraint")
        
        # Show mode control when horizontal constraint is enabled
        if self.apply_horizontal_constraint:
            sub = box.box()
            sub.prop(self, "horizontal_constraint_mode", text="Mode")
        
        # Vertical constraint settings
        box = layout.box()
        box.label(text="Vertical Constraint", icon='TRIA_UP')
        box.prop(self, "apply_vertical_constraint")
        
        # Show mode control when vertical constraint is enabled
        if self.apply_vertical_constraint:
            sub = box.box()
            sub.prop(self, "vertical_constraint_mode", text="Mode")


classes = [
    UVV_OT_straighten,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
