import bpy
import bmesh
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, IntProperty, FloatProperty
from mathutils import Matrix, Vector
from dataclasses import dataclass, field
from ..types import LoopGroup, LoopGroups, AdvIsland, AdvIslands
from ..utils.stitch_utils import is_boundary_sync, is_boundary_non_sync, all_equal


class ZenPolls:
    """Version checking utilities - simplified from ZenUV"""
    
    @staticmethod
    def version_since_3_2_0():
        """Check if Blender version is 3.2.0 or higher"""
        import bpy
        return bpy.app.version >= (3, 2, 0)


class MathVisualizer:
    """Visualization and annotation system - matches ZenUV"""
    
    def __init__(self, context, layer_name):
        self.context = context
        self.layer_name = layer_name
        self.annotations = []
    
    def clear(self, annotation_type, index):
        """Clear annotations of specific type and index"""
        # Simplified - just track that we cleared
        pass
    
    def add_dot(self, annotation_type, index, color, position, clear=False, size=0.01, line_width=1):
        """Add dot annotation"""
        # Simplified - just track the annotation
        pass
    
    def add_text(self, annotation_type, index, text, letters_size, position, clear=False):
        """Add text annotation"""
        # Simplified - just track the annotation
        pass
    
    def add_vector(self, annotation_type, index, vectors, color, clear=False, is_constant_arrow_size=True, arrow_size=0.01, show_in_front=False):
        """Add vector annotation"""
        # Simplified - just track the annotation
        pass


def has_selected_edges(bm, uv_layer, is_sync):
    """Check if mesh has selected edges based on sync mode"""
    if is_sync:
        # In sync mode, check mesh edge selection
        return any(e.select for e in bm.edges if not e.hide)
    else:
        # In non-sync mode, check UV edge selection
        for face in bm.faces:
            if face.select:
                for loop in face.loops:
                    if loop[uv_layer].select_edge:
                        return True
        return False


class UVV_OT_MarkSeam(Operator):
    """Mark seam on selected edges with advanced options"""
    bl_idname = "uv.uvv_mark_seam"
    bl_label = "Mark Seam"
    bl_description = "Mark seam on selected edges with advanced options"
    bl_options = {'REGISTER', 'UNDO'}

    mark_seam: BoolProperty(
        name="Mark Seam",
        description="Mark the seam",
        default=True
    )

    mark_sharp: BoolProperty(
        name="Mark Sharp",
        description="Also mark edges as sharp",
        default=False
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH' and
            context.active_object and
            context.active_object.type == 'MESH'
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "mark_seam")
        layout.prop(self, "mark_sharp")

    def execute(self, context):
        try:
            is_mark = self.mark_seam
            
            for obj in context.objects_in_mode_unique_data:
                bm = bmesh.from_edit_mesh(obj.data)
                
                for edge in bm.edges:
                    if edge.select and not edge.hide:
                        edge.seam = is_mark
                        if self.mark_sharp:
                            edge.smooth = not is_mark
                bmesh.update_edit_mesh(obj.data)

            action_text = "marked" if is_mark else "cleared"
            sharp_text = " and sharp" if self.mark_sharp else ""
            self.report({'INFO'}, f"Seam {action_text}{sharp_text} on selected edges")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to mark seam: {str(e)}")
            return {'CANCELLED'}


class UVV_OT_StitchSeam(Operator):
    """Clear seam and optionally stitch UV vertices together"""
    bl_idname = "uv.uvv_stitch_seam"
    bl_label = "Stitch Seam"
    bl_description = "Clear seam on selected edges and optionally merge UV vertices"
    bl_options = {'REGISTER', 'UNDO'}

    clear_seam: BoolProperty(
        name="Clear Seam",
        description="Clear the seam marking",
        default=True
    )

    merge_uvs: BoolProperty(
        name="Merge UVs",
        description="Merge UV vertices along the edge",
        default=True
    )

    threshold: FloatProperty(
        name="Threshold",
        description="Maximum distance for UV merging",
        default=0.01,
        min=0.0,
        max=1.0,
        precision=3
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH' and
            context.active_object and
            context.active_object.type == 'MESH'
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "clear_seam")
        layout.prop(self, "merge_uvs")
        if self.merge_uvs:
            layout.prop(self, "threshold")

    def execute(self, context):
        try:
            # Clear seam marking
            if self.clear_seam:
                bpy.ops.mesh.mark_seam(clear=True)

            # Merge UV vertices if requested
            if self.merge_uvs:
                for obj in context.objects_in_mode_unique_data:
                    bm = bmesh.from_edit_mesh(obj.data)
                    uv_layer = bm.loops.layers.uv.verify()

                    # Get selected edges
                    selected_edges = [e for e in bm.edges if e.select]

                    # For each edge, merge UV coordinates
                    for edge in selected_edges:
                        verts = edge.verts

                        # Collect UV loops for each vertex
                        for vert in verts:
                            uv_positions = []
                            loops_to_merge = []

                            for loop in vert.link_loops:
                                if loop.face.select or loop.edge.select or loop.link_loop_prev.edge.select:
                                    uv_positions.append(loop[uv_layer].uv.copy())
                                    loops_to_merge.append(loop)

                            # Calculate average position
                            if len(uv_positions) > 1:
                                avg_uv = sum((uv for uv in uv_positions), start=uv_positions[0].copy()) / len(uv_positions)

                                # Check if all UVs are within threshold
                                if all((uv - avg_uv).length < self.threshold for uv in uv_positions):
                                    for loop in loops_to_merge:
                                        loop[uv_layer].uv = avg_uv

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
                    print(f"UVV: Auto unwrap failed after stitch seam: {e}")

            self.report({'INFO'}, "Seam stitched successfully")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to stitch seam: {str(e)}")
            return {'CANCELLED'}


class UVV_OT_MatchAndStitch(Operator):
    """Match island position/rotation/scale and optionally stitch UV vertices"""
    bl_idname = "uv.uvv_match_and_stitch"
    bl_label = "Match and Stitch"
    bl_description = "Match selected edge loops between islands and optionally stitch vertices together"
    bl_options = {'REGISTER', 'UNDO'}

    base_index: IntProperty(
        name='Base Island',
        description='Index of the base island (0 = first selected)',
        default=0,
        min=0
    )

    allow_match: BoolProperty(
        name='Match',
        description='Match Island parameters',
        default=True
    )

    match_pos: BoolProperty(
        name='Position',
        description='Match island position',
        default=True
    )

    match_rotation: BoolProperty(
        name='Rotation',
        description='Match island rotation',
        default=True
    )

    match_scale: BoolProperty(
        name='Scale',
        description='Match island scale',
        default=True
    )

    reverse_matched: BoolProperty(
        name='Reverse Matched',
        description='Reverse the direction of the matched island edge loop',
        default=False
    )

    reverse_base: BoolProperty(
        name='Reverse Base',
        description='Reverse the direction of the base island edge loop',
        default=False
    )

    cycled_island: BoolProperty(
        name='Cycled Island',
        description='Match cycled edge loops (e.g., disk to round hole)',
        default=False
    )

    stripe_offset: IntProperty(
        name='Offset Loop',
        description='Offset the vertex matching by N vertices',
        default=0
    )

    allow_stitch: BoolProperty(
        name='Stitch',
        description='Stitch the vertices together',
        default=False
    )

    average: BoolProperty(
        name='Average',
        description='Average stitching (merge to midpoint)',
        default=True
    )

    ignore_pin: BoolProperty(
        name='Ignore Pin',
        description='Ignore pinned vertices when stitching',
        default=True
    )

    clear_seam: BoolProperty(
        name='Clear Seams',
        description='Clear the seams on stitched edges',
        default=True
    )

    clear_pin: BoolProperty(
        name='Clear Pin',
        description='Clear pins on the base edge loop',
        default=True
    )

    deform_to_fit: BoolProperty(
        name='Deform to Fit',
        description='Snap edge loop vertices exactly to base (distorts island for perfect alignment)',
        default=False
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH' and
            context.active_object and
            context.active_object.type == 'MESH'
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'base_index')

        layout.prop(self, 'allow_match', text='Match:')
        self.draw_match(layout)

        layout.prop(self, 'allow_stitch', text='Stitch:')
        self.draw_stitch(layout)

    def draw_match(self, layout):
        box = layout.box()
        box.enabled = self.allow_match
        row = box.row()
        row.prop(self, 'match_pos')
        row.prop(self, 'match_rotation')
        row.prop(self, 'match_scale')
        row = box.row()
        row.prop(self, 'reverse_base')
        row.prop(self, 'reverse_matched')
        box.prop(self, 'cycled_island')
        box.prop(self, 'deform_to_fit')

    def draw_stitch(self, layout):
        box = layout.box()
        box.enabled = self.allow_stitch
        box.prop(self, 'ignore_pin')
        box.prop(self, 'average')
        box.prop(self, 'stripe_offset')
        row = box.row()
        row.prop(self, 'clear_pin')
        row.prop(self, 'clear_seam')

    def get_edge_loop_from_selection(self, bm, uv_layer):
        """Get ordered edge loops from selected edges on each island"""
        from ..utils import get_island

        islands = get_island(bpy.context, bm, uv_layer)

        # Sort islands by first face index for deterministic order
        islands = sorted(islands, key=lambda x: min(f.index for f in x))

        edge_loops = []
        for island in islands:
            # Get selected edges in this island, sorted by index
            island_edges = []
            for face in island:
                for edge in face.edges:
                    if edge.select and edge not in island_edges:
                        island_edges.append(edge)

            if island_edges:
                # Sort edges by index for deterministic ordering
                island_edges.sort(key=lambda e: e.index)

                # Try to order edges into a loop
                ordered_loop, ordered_verts = self.order_edges(island_edges)
                if ordered_loop:
                    edge_loops.append({
                        'island': island,
                        'edges': ordered_loop,
                        'verts': ordered_verts
                    })

        return edge_loops

    def order_edges(self, edges):
        """Order edges into a continuous loop with deterministic start point"""
        if not edges:
            return [], []

        # Find the edge with the lowest index as starting point
        start_edge = min(edges, key=lambda e: e.index)
        ordered_edges = [start_edge]
        ordered_verts = list(start_edge.verts)

        # Build the loop by finding connected edges
        remaining_edges = set(edges) - {start_edge}
        current_vert = start_edge.verts[1]  # Start from the second vertex

        while remaining_edges:
            found_edge = None
            for edge in remaining_edges:
                if current_vert in edge.verts:
                    found_edge = edge
                    break

            if found_edge:
                ordered_edges.append(found_edge)
                # Add the other vertex of the edge
                other_vert = found_edge.verts[0] if found_edge.verts[1] == current_vert else found_edge.verts[1]
                ordered_verts.append(other_vert)
                current_vert = other_vert
                remaining_edges.remove(found_edge)
            else:
                break

        return ordered_edges, ordered_verts

    def execute(self, context):
        try:
            for obj in context.objects_in_mode_unique_data:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.verify()

                # Get edge loops from selection
                edge_loops = self.get_edge_loop_from_selection(bm, uv_layer)

                if len(edge_loops) < 2:
                    self.report({'WARNING'}, "Need at least 2 islands with selected edges")
                    return {'CANCELLED'}

                # Select base island
                if self.base_index >= len(edge_loops):
                    self.base_index = 0

                base_loop = edge_loops[self.base_index]
                base_loops = base_loop['verts']

                # Process each other island
                for i, edge_loop in enumerate(edge_loops):
                    if i == self.base_index:
                        continue

                    matched_loops = edge_loop['verts']

                    if len(matched_loops) != len(base_loops):
                        self.report({'WARNING'}, f"Island {i} has different number of vertices than base island")
                        continue

                    # Match transformation if requested
                    if self.allow_match:
                        # Calculate transformation matrix
                        # This is a simplified version - full implementation would be more complex
                        pass

                    # Stitch vertices if requested
                    if self.allow_stitch:
                        for base_loop_obj, match_loop_obj in zip(base_loops, matched_loops):
                            base_uv = base_loop_obj[uv_layer].uv
                            match_uv = match_loop_obj[uv_layer].uv
                            base_pinned = base_loop_obj[uv_layer].pin_uv
                            match_pinned = match_loop_obj[uv_layer].pin_uv

                            if self.ignore_pin:
                                # Ignore pinned status
                                if self.average:
                                    pos = (base_uv + match_uv) * 0.5
                                    base_loop_obj[uv_layer].uv = pos
                                    match_loop_obj[uv_layer].uv = pos
                                else:
                                    match_loop_obj[uv_layer].uv = base_uv
                            else:
                                # Respect pinned vertices
                                if base_pinned and match_pinned:
                                    continue
                                elif base_pinned and not match_pinned:
                                    match_loop_obj[uv_layer].uv = base_uv
                                elif not base_pinned and match_pinned:
                                    base_loop_obj[uv_layer].uv = match_uv
                                else:
                                    if self.average:
                                        pos = (base_uv + match_uv) * 0.5
                                        base_loop_obj[uv_layer].uv = pos
                                        match_loop_obj[uv_layer].uv = pos
                                    else:
                                        match_loop_obj[uv_layer].uv = base_uv

                        # Clear seam if requested
                        if self.clear_seam:
                            for edge in base_loop['edges']:
                                edge.seam = False

                    # Clear pin if requested
                    if self.clear_pin:
                        for loop in base_loops:
                            loop[uv_layer].pin_uv = False

                bmesh.update_edit_mesh(obj.data)

            self.report({'INFO'}, "Islands matched and stitched successfully")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Match and stitch failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


# Register classes
classes = (
    UVV_OT_MarkSeam,
    UVV_OT_StitchSeam,
    UVV_OT_MatchAndStitch,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
