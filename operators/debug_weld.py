# Debug operator for weld analysis

import bpy
import bmesh
from bpy.types import Operator
from mathutils import Vector

from ..utils import sync
from ..utils.island_utils import get_islands_non_manifold


class UVV_OT_Debug_Weld_Selection(Operator):
    """Debug: Print detailed info about selected UV edges and islands"""
    bl_idname = "uv.uvv_debug_weld_selection"
    bl_label = "Debug Weld Selection"
    bl_description = "Print detailed information about selected UV edges for debugging weld"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        is_sync = sync()

        print("\n" + "="*80)
        print("DEBUG WELD SELECTION - START")
        print("="*80)

        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            print(f"\nObject: {obj.name}")
            print(f"Sync mode: {is_sync}")

            # Get islands
            if is_sync:
                all_faces = [f for f in bm.faces if not f.hide]
            else:
                all_faces = [f for f in bm.faces if f.select]

            all_islands = get_islands_non_manifold(bm, all_faces, uv_layer)
            print(f"Total islands: {len(all_islands)}")

            # Create face to island mapping
            face_to_island_idx = {}
            for idx, island in enumerate(all_islands):
                for face in island:
                    face_to_island_idx[face] = idx

            # Find selected edges
            selected_edges = []
            for face in all_faces:
                for loop in face.loops:
                    if is_sync:
                        if loop.edge.select:
                            selected_edges.append(loop)
                    else:
                        if loop[uv_layer].select_edge:
                            selected_edges.append(loop)

            print(f"Selected edge corners: {len(selected_edges)}")

            # Analyze each island
            for idx, island in enumerate(all_islands):
                print(f"\n--- Island {idx} ({len(island)} faces) ---")

                # Find selected edges in this island
                island_selected_corners = []
                for face in island:
                    for crn in face.loops:
                        if is_sync:
                            if crn.edge.select:
                                island_selected_corners.append(crn)
                        else:
                            if crn[uv_layer].select_edge:
                                island_selected_corners.append(crn)

                if not island_selected_corners:
                    print(f"  No selected edges")
                    continue

                print(f"  Selected corners: {len(island_selected_corners)}")

                # Group by neighbor island
                neighbor_edges = {}
                for crn in island_selected_corners:
                    shared = crn.link_loop_radial_prev
                    if shared == crn:
                        print(f"  Corner at vert {crn.vert.index} is boundary edge (no neighbor)")
                        continue

                    neighbor_island_idx = face_to_island_idx.get(shared.face, -1)
                    if neighbor_island_idx == -1:
                        print(f"  Corner at vert {crn.vert.index} - neighbor face not in any island")
                        continue

                    if neighbor_island_idx == idx:
                        print(f"  Corner at vert {crn.vert.index} - neighbor is same island (internal edge)")
                        continue

                    if neighbor_island_idx not in neighbor_edges:
                        neighbor_edges[neighbor_island_idx] = []
                    neighbor_edges[neighbor_island_idx].append(crn)

                # Print edges grouped by neighbor
                for neighbor_idx, corners in neighbor_edges.items():
                    print(f"\n  Edges to island {neighbor_idx}: {len(corners)} corner(s)")

                    for i, crn in enumerate(corners):
                        crn_next = crn.link_loop_next
                        shared = crn.link_loop_radial_prev
                        shared_next = shared.link_loop_next

                        print(f"\n    Edge {i+1}:")
                        print(f"      Vertices: {crn.vert.index} - {crn_next.vert.index}")
                        print(f"      Island {idx} UV coords:")
                        print(f"        Corner[0]: {crn[uv_layer].uv}")
                        print(f"        Corner[1]: {crn_next[uv_layer].uv}")
                        print(f"      Island {neighbor_idx} UV coords:")
                        print(f"        Shared[0] (next): {shared_next[uv_layer].uv}")
                        print(f"        Shared[1]:        {shared[uv_layer].uv}")

                        # Check if split
                        is_split_a = crn[uv_layer].uv != shared_next[uv_layer].uv
                        is_split_b = crn_next[uv_layer].uv != shared[uv_layer].uv
                        print(f"      Split status: A={is_split_a}, B={is_split_b}")

                        if is_split_a or is_split_b:
                            print(f"      ✓ This edge WILL be welded")
                        else:
                            print(f"      ✗ This edge is already welded (will be skipped)")

        print("\n" + "="*80)
        print("DEBUG WELD SELECTION - END")
        print("="*80 + "\n")

        return {'FINISHED'}


classes = (
    UVV_OT_Debug_Weld_Selection,
)
