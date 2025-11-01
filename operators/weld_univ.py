# SPDX-FileCopyrightText: 2024 Oxicid  
# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from UniV addon weld implementation for UVV

"""
Weld operator - directly copied and minimally adapted from UniV addon.
This ensures weld works exactly like UniV.
"""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import BoolProperty, FloatProperty, EnumProperty
from mathutils import Vector

from ..utils.univ_weld_utils import weld_crn_edge_by_idx, copy_pos_to_target_with_select
from ..utils import sync
from ..utils.island_utils import get_islands_non_manifold
from ..utils.island_align import reorient_island_to_target, find_welded_edge_pairs
from .stitch_univ import Stitch


class UVV_OT_Weld(Operator):
    """Weld selected UV edges - UniV implementation"""
    bl_idname = "uv.uvv_weld"
    bl_label = "Weld"
    bl_description = "Weld selected UV edges"
    bl_options = {'REGISTER', 'UNDO'}

    use_by_distance: BoolProperty(name='By Distance', default=False)
    distance: FloatProperty(name='Distance', default=0.0005, min=0, soft_max=0.05, step=0.0001)
    weld_by_distance_type: EnumProperty(
        name='Weld by', 
        default='BY_ISLANDS', 
        items=(
            ('ALL', 'All', ''),
            ('BY_ISLANDS', 'By Islands', '')
        )
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        print("=== WELD OPERATION STARTED ===")
        print("Weld Executed.")
        is_sync = sync()
        print(f"Weld: Sync mode = {is_sync}")

        # Store islands for Phase 2 (like UniV's islands_of_mesh)
        all_objects_islands = []
        phase1_updated = False

        # PHASE 1: Weld edges within same island (UniV lines 683-732)
        print("Weld: Starting Phase 1")
        # Store original edge positions for alignment
        original_edge_positions = {}
        
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()
            update_tag = False
            print(f"Weld: Processing object {obj.name}")
            
            # Store original edge positions BEFORE welding
            for face in bm.faces:
                for loop in face.loops:
                    edge = loop.edge
                    if edge.index not in original_edge_positions:
                        # Store both corners of the edge
                        corner1 = loop
                        corner2 = loop.link_loop_next
                        original_edge_positions[edge.index] = {
                            'corner1_uv': corner1[uv_layer].uv.copy(),
                            'corner2_uv': corner2[uv_layer].uv.copy()
                        }

            # Calculate islands using non-manifold detection (UniV pattern)
            # In sync mode: use all non-hidden faces
            # In non-sync mode (UV editor): use selected faces (face.select)
            if is_sync:
                all_faces = [f for f in bm.faces if not f.hide]
            else:
                all_faces = [f for f in bm.faces if f.select]

            all_islands = get_islands_non_manifold(bm, all_faces, uv_layer)

            if not all_islands:
                continue

            # Filter islands: only keep islands with any selected edge (UniV behavior)
            # This matches Islands.calc_extended_any_edge_non_manifold filtering
            def island_has_selected_edge(island):
                if is_sync:
                    return any(e.select for f in island for e in f.edges)
                else:
                    return any(crn[uv_layer].select_edge for f in island for crn in f.loops)

            # Keep all islands for indexing, but only process filtered ones
            filtered_islands = [isl for isl in all_islands if island_has_selected_edge(isl)]
            print(f"Weld: Found {len(all_islands)} total islands, {len(filtered_islands)} with selected edges")

            if not filtered_islands:
                print("Weld: No islands with selected edges, skipping object")
                continue

            # Initialize all corner tags
            for face in bm.faces:
                for loop in face.loops:
                    loop.tag = False

            # Set face.index to island index (UniV's indexing() method)
            # CRITICAL: Use ALL islands for indexing, not just filtered ones
            for idx, island in enumerate(all_islands):
                for face in island:
                    face.index = idx

            # Process each filtered island using UniV's exact algorithm
            print(f"Weld: Processing {len(filtered_islands)} filtered islands")
            for island in filtered_islands:
                # Get the actual index from face.index (since we indexed all_islands)
                idx = island[0].index
                print(f"Weld: Processing island {idx} with {len(island)} faces")
                
                # Tag selected edges in this island (UniV's set_selected_crn_edge_tag)
                selected_edges_count = 0
                for face in island:
                    for crn in face.loops:
                        if is_sync:
                            crn.tag = crn.edge.select
                            if crn.edge.select:
                                selected_edges_count += 1
                                print(f"Weld: Found selected edge in sync mode: face={face.index}, edge={crn.edge.index}")
                        else:
                            crn.tag = crn[uv_layer].select_edge
                            if crn[uv_layer].select_edge:
                                selected_edges_count += 1
                                print(f"Weld: Found selected edge in non-sync mode: face={face.index}, edge={crn.edge.index}")
                
                print(f"Weld: Island {idx} has {selected_edges_count} selected edges")

                # Process tagged corners using UniV's exact algorithm (lines 693-731)
                welded_count = 0
                for face in island:
                    for crn in face.loops:
                        if not crn.tag:
                            continue

                        shared = crn.link_loop_radial_prev
                        if shared == crn:  # Boundary edge
                            crn.tag = False
                            print(f"Weld: Boundary edge, skipping")
                            continue

                        # CRITICAL: UniV line 699 - island boundary check
                        # UNIV BEHAVIOR: NEVER allow cross-island welding in basic weld operation
                        # Cross-island welding is handled by stitch operation, not weld
                        if shared.face.index != idx:  # island boundary skip
                            crn.tag = False
                            shared.tag = False
                            print(f"Weld: Cross-island edge, skipping (shared.face.index={shared.face.index}, idx={idx})")
                            continue

                        # Check if edge is split (UniV lines 711-712)
                        crn_next = crn.link_loop_next
                        shared_next = shared.link_loop_next

                        is_splitted_a = crn[uv_layer].uv != shared_next[uv_layer].uv
                        is_splitted_b = crn_next[uv_layer].uv != shared[uv_layer].uv

                        print(f"Weld: Edge analysis - is_splitted_a={is_splitted_a}, is_splitted_b={is_splitted_b}")

                        # UNIV behavior: Weld split edges even if only one side is selected
                        # This allows single edge selection to work
                        if is_splitted_a and is_splitted_b:
                            weld_crn_edge_by_idx(crn, shared_next, idx, uv_layer)
                            weld_crn_edge_by_idx(crn_next, shared, idx, uv_layer)
                            welded_count += 2
                            update_tag = True
                            print(f"Weld: Welded both sides")
                        elif is_splitted_a:
                            weld_crn_edge_by_idx(crn, shared_next, idx, uv_layer)
                            welded_count += 1
                            update_tag = True
                            print(f"Weld: Welded side A")
                        elif is_splitted_b:
                            weld_crn_edge_by_idx(crn_next, shared, idx, uv_layer)
                            welded_count += 1
                            update_tag = True
                            print(f"Weld: Welded side B")
                        else:
                            print(f"Weld: Edge not split, no welding needed")

                        # Clear seam after welding (UniV lines 725-728)
                        edge = crn.edge
                        if edge.seam:
                            edge.seam = False
                            update_tag = True
                            print(f"Weld: Cleared seam on edge {edge.index}")

                        # Mark as processed (UniV lines 730-731)
                        crn.tag = False
                        shared.tag = False

                print(f"Weld: Island {idx} welded {welded_count} edges")

            # Store for Phase 2 - store filtered_islands (ones with selection)
            # UniV stores the Islands object which was already filtered
            if filtered_islands:
                all_objects_islands.append((obj, bm, uv_layer, filtered_islands, update_tag))
                if update_tag:
                    phase1_updated = True
                    print(f"Weld: Phase 1 updated object {obj.name}")
        
        print(f"Weld: Phase 1 completed. Updated: {phase1_updated}")

        # Update meshes from Phase 1 and check for early return
        if phase1_updated:
            for obj, bm, uv_layer, all_islands, update_tag in all_objects_islands:
                if update_tag:
                    bmesh.update_edit_mesh(obj.data)
            
            # PHASE 2: Island Alignment (UNIV behavior)
            print("Weld: Starting Phase 2 - Island Alignment")
            self.align_islands_after_weld(all_objects_islands, is_sync, original_edge_positions)
            
            return {'FINISHED'}  # Early return - skip Phase 3

        # PHASE 2: Handle non-sync mode with remaining tagged corners (UniV lines 740-753)
        # This runs when Phase 1 didn't update anything
        print("Weld: Starting Phase 2")
        phase2_updated = False
        if not is_sync:
            # CRITICAL FIX: Add Univ's Phase 2 seam clearing logic
            # This is the missing piece that clears seams after copy_pos_to_target_with_select
            for obj, bm, uv_layer, all_islands, _ in all_objects_islands:
                update_tag = False
                
                for idx, island in enumerate(all_islands):
                    # Process remaining tagged corners (corners that weren't handled in Phase 1)
                    for face in island:
                        for crn in face.loops:
                            if crn.tag:  # Still tagged from Phase 1
                                # Use Univ's exact Phase 2 logic
                                copy_pos_to_target_with_select(crn, uv_layer, idx)
                                if crn.edge.seam:
                                    crn.edge.seam = False
                                update_tag = True

                if update_tag:
                    bmesh.update_edit_mesh(obj.data)
                    phase2_updated = True

        # Check if Phase 2 updated anything
        print(f"Weld: Phase 2 completed. Updated: {phase2_updated}")
        if phase2_updated:
            print("Weld: Phase 2 updated - returning early")
            return {'FINISHED'}  # Early return - skip Phase 3

        # PHASE 3: Only fallback to stitch in very specific cases
        # UNIV behavior: Only call stitch if there are actually edges that need stitching
        # Check if we have valid edges that could be stitched
        has_valid_edges = False
        edge_count = 0
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()
            
            if is_sync:
                # Check for 3D selected edges
                for face in bm.faces:
                    if not face.hide:
                        for edge in face.edges:
                            if edge.select:
                                has_valid_edges = True
                                edge_count += 1
            else:
                # Check for UV selected edges
                for face in bm.faces:
                    for loop in face.loops:
                        if loop[uv_layer].select_edge:
                            has_valid_edges = True
                            edge_count += 1
            if has_valid_edges:
                break
        
        print(f"Weld Phase 3: has_valid_edges={has_valid_edges}, edge_count={edge_count}")
        
        # Only call stitch if we have valid edges that could be stitched
        if has_valid_edges:
            print("Weld: Falling back to stitch (UNIV behavior)")
            return bpy.ops.uv.uvv_stitch('INVOKE_DEFAULT')
        else:
            print("Weld: No valid edges found - operation completed")
            # No valid edges found - weld operation completed successfully
            return {'FINISHED'}

    def align_islands_after_weld(self, all_objects_islands, is_sync, original_edge_positions):
        """
        Align islands after welding - UNIV behavior.
        This is what makes weld actually align the islands instead of just merging edges.
        """
        print("Weld: Aligning islands after welding")
        
        for obj, bm, uv_layer, all_islands, _ in all_objects_islands:
            # Create face to island index mapping
            face_to_island_idx = {}
            for idx, island in enumerate(all_islands):
                for face in island:
                    face_to_island_idx[face] = idx
            
            # Find welded edge pairs across islands
            welded_pairs = find_welded_edge_pairs(all_islands, face_to_island_idx, uv_layer)
            print(f"Weld: Found {len(welded_pairs)} welded edge pairs for alignment")
            
            for pair in welded_pairs:
                ref_island_idx = pair['ref_island_idx']
                trans_island_idx = pair['trans_island_idx']
                ref_edge_corners = pair['ref_edge_corners']
                trans_edge_corners = pair['trans_edge_corners']
                
                ref_island = all_islands[ref_island_idx]
                trans_island = all_islands[trans_island_idx]
                
                print(f"Weld: Aligning island {trans_island_idx} to island {ref_island_idx}")
                
                # Get ORIGINAL edge endpoints (before welding) for proper alignment
                # Find the edge that was welded
                ref_edge = ref_edge_corners[0].edge
                trans_edge = trans_edge_corners[0].edge
                
                # Use original positions for alignment calculation
                if ref_edge.index in original_edge_positions:
                    ref_pt1 = original_edge_positions[ref_edge.index]['corner1_uv']
                    ref_pt2 = original_edge_positions[ref_edge.index]['corner2_uv']
                else:
                    # Fallback to current positions if original not found
                    ref_pt1 = ref_edge_corners[0][uv_layer].uv
                    ref_pt2 = ref_edge_corners[1][uv_layer].uv
                
                if trans_edge.index in original_edge_positions:
                    trans_pt1 = original_edge_positions[trans_edge.index]['corner1_uv']
                    trans_pt2 = original_edge_positions[trans_edge.index]['corner2_uv']
                else:
                    # Fallback to current positions if original not found
                    trans_pt1 = trans_edge_corners[0][uv_layer].uv
                    trans_pt2 = trans_edge_corners[1][uv_layer].uv
                
                print(f"Weld: Using original edge positions for alignment")
                print(f"Weld: Ref edge original: {ref_pt1} - {ref_pt2}")
                print(f"Weld: Trans edge original: {trans_pt1} - {trans_pt2}")
                
                # Align the islands
                success = reorient_island_to_target(
                    ref_island, trans_island, 
                    ref_pt1, ref_pt2, trans_pt1, trans_pt2, 
                    uv_layer, aspect=1.0
                )
                
                if success:
                    print(f"Weld: Successfully aligned island {trans_island_idx}")
                else:
                    print(f"Weld: Failed to align island {trans_island_idx}")
            
            # Update the mesh after alignment
            bmesh.update_edit_mesh(obj.data)
            print(f"Weld: Updated mesh for object {obj.name}")



class UVV_OT_Weld_VIEW3D(Operator):
    """Weld from 3D viewport - UniV implementation"""
    bl_idname = "mesh.uvv_weld"
    bl_label = "Weld"
    bl_description = "Weld selected mesh edges in UV space"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        # 3D viewport is always in sync mode
        is_sync = True

        # Store islands for Phase 2
        all_objects_islands = []
        phase1_updated = False

        # PHASE 1: Weld edges within same island
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()
            update_tag = False

            # 3D viewport is always in sync mode - use non-manifold detection
            all_faces = [f for f in bm.faces if not f.hide]
            all_islands = get_islands_non_manifold(bm, all_faces, uv_layer)

            if not all_islands:
                continue

            # Filter islands: only keep islands with any selected edge
            # In 3D viewport (sync mode), check mesh edge selection
            filtered_islands = [isl for isl in all_islands if any(e.select for f in isl for e in f.edges)]

            if not filtered_islands:
                continue

            # Initialize tags
            for face in bm.faces:
                for loop in face.loops:
                    loop.tag = False

            # Set face.index to island index (UniV's indexing() method)
            # Use ALL islands for indexing, not just filtered ones
            for idx, island in enumerate(all_islands):
                for face in island:
                    face.index = idx

            # Process each filtered island using UniV's exact algorithm
            for island in filtered_islands:
                # Get the actual index from face.index (since we indexed all_islands)
                idx = island[0].index
                # Tag selected edges (3D viewport uses mesh edge selection)
                for face in island:
                    for crn in face.loops:
                        crn.tag = crn.edge.select

                # Process tagged corners using UniV's exact algorithm
                for face in island:
                    for crn in face.loops:
                        if not crn.tag:
                            continue

                        shared = crn.link_loop_radial_prev
                        if shared == crn:  # Boundary edge
                            crn.tag = False
                            continue

                        # CRITICAL: UniV line 699 - island boundary check
                        # UNIV BEHAVIOR: NEVER allow cross-island welding in basic weld operation
                        # Cross-island welding is handled by stitch operation, not weld
                        if shared.face.index != idx:  # island boundary skip
                            crn.tag = False
                            shared.tag = False
                            continue

                        # Check single select preserve system (UniV line 704)
                        if not shared.tag:
                            continue

                        # Check if edge is split (UniV lines 711-712)
                        crn_next = crn.link_loop_next
                        shared_next = shared.link_loop_next

                        is_splitted_a = crn[uv_layer].uv != shared_next[uv_layer].uv
                        is_splitted_b = crn_next[uv_layer].uv != shared[uv_layer].uv

                        # Weld the split edges (UniV lines 714-723)
                        if is_splitted_a and is_splitted_b:
                            weld_crn_edge_by_idx(crn, shared_next, idx, uv_layer)
                            weld_crn_edge_by_idx(crn_next, shared, idx, uv_layer)
                            update_tag = True
                        elif is_splitted_a:
                            weld_crn_edge_by_idx(crn, shared_next, idx, uv_layer)
                            update_tag = True
                        elif is_splitted_b:
                            weld_crn_edge_by_idx(crn_next, shared, idx, uv_layer)
                            update_tag = True

                        # Clear seam (UniV lines 725-728)
                        if crn.edge.seam:
                            crn.edge.seam = False
                            update_tag = True

                        # Mark as processed (UniV lines 730-731)
                        crn.tag = False
                        shared.tag = False

            # Store for Phase 2 - store filtered_islands (ones with selection)
            if filtered_islands:
                all_objects_islands.append((obj, bm, uv_layer, filtered_islands, update_tag))
                if update_tag:
                    phase1_updated = True

        # Update meshes from Phase 1
        if phase1_updated:
            for obj, bm, uv_layer, all_islands, update_tag in all_objects_islands:
                if update_tag:
                    bmesh.update_edit_mesh(obj.data)
            
            # Auto unwrap if enabled
            from ..properties import get_uvv_settings
            settings = get_uvv_settings()
            if settings and settings.auto_unwrap_enabled:
                try:
                    # Ensure we're in the right context for UV operations
                    # Switch to UV Editor if not already there
                    original_area_type = context.area.type if context.area else None
                    if context.area and context.area.type != 'IMAGE_EDITOR':
                        context.area.type = 'IMAGE_EDITOR'
                        context.area.ui_type = 'UV'
                    
                    bpy.ops.uv.unwrap(method='ANGLE_BASED', correct_aspect=True)
                    
                    # Restore original area type
                    if original_area_type and context.area:
                        context.area.type = original_area_type
                        
                except Exception as e:
                    print(f"UVV: Auto unwrap failed after weld: {e}")
            
            return {'FINISHED'}

        # PHASE 3: Only fallback to stitch in very specific cases
        # UNIV behavior: Only call stitch if there are actually edges that need stitching
        # Check if we have valid edges that could be stitched
        has_valid_edges = False
        edge_count = 0
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            
            # Check for 3D selected edges (3D viewport is always sync mode)
            for face in bm.faces:
                if not face.hide:
                    for edge in face.edges:
                        if edge.select:
                            has_valid_edges = True
                            edge_count += 1
            if has_valid_edges:
                break
        
        print(f"Weld 3D Phase 3: has_valid_edges={has_valid_edges}, edge_count={edge_count}")
        
        # Only call stitch if we have valid edges that could be stitched
        if has_valid_edges:
            print("Weld 3D: Falling back to stitch (UNIV behavior)")
            return bpy.ops.mesh.uvv_stitch('INVOKE_DEFAULT')
        else:
            print("Weld 3D: No valid edges found - operation completed")
            # No valid edges found - weld operation completed successfully
            return {'FINISHED'}


# Register classes
classes = (
    UVV_OT_Weld,
    UVV_OT_Weld_VIEW3D,
)
