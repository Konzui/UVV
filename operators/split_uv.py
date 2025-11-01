"""
Split UV Operator
EXACT copy of ZenUV's split implementation
"""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import BoolProperty, FloatProperty
from mathutils import Vector
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from math import sqrt


@dataclass
class UvNode:
    """EXACT copy of ZenUV's UvNode"""
    vis_layer_name = 'ZenUV Split'
    vis_letter_size = None

    index: int = 0
    loops: list = field(default_factory=list)
    loops_count: int = 0
    neighbors: set = field(default_factory=set)
    neighbors_count: int = 0
    result_coordinates: dict = field(default_factory=dict)
    vis_directions: list = field(default_factory=list)

    def __hash__(self):
        return hash(self.index)

    def init(self):
        self.loops_count = len(self.loops)


class UvSplitProcessor:
    """EXACT copy of ZenUV's UvSplitProcessor"""
    
    def __init__(self, context: bpy.types.Context) -> None:
        self.show_in_annotations: bool = False
        self.is_not_sync: bool = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
        self.is_pure_uv_edge_mode: bool = context.space_data.type == 'IMAGE_EDITOR' and self.is_not_sync and context.scene.tool_settings.uv_select_mode == "EDGE"

    def compound_nodes(self, uv_layer: bmesh.types.BMLayerItem, groupped_bmesh_loops: list) -> list:
        p_node_groups = []
        for group in groupped_bmesh_loops:
            scp = defaultdict(list)
            for loop in group:
                scp[loop[uv_layer].uv.to_tuple()].append(loop)
            p_node_groups.append(scp)

        node_groups = []
        for node_group in p_node_groups:
            p_group = []
            for idx, lps in enumerate(node_group.items()):
                p_group.append(UvNode(index=idx, loops=lps[1]))
            node_groups.append(p_group)

        i_stats = 0

        if self.is_pure_uv_edge_mode:
            for node_group in node_groups:
                for node in node_group:
                    for loop in node.loops:
                        if loop[uv_layer].select_edge:
                            node.neighbors_count += 1
                            i_stats += 1
        else:
            for node_group in node_groups:
                for node in node_group:
                    node.neighbors_count = Counter([e.other_vert(node.loops[0].vert).select for e in node.loops[0].vert.link_edges])[True]

        return node_groups

    def calculate_loops_positions(self, uv_layer: bmesh.types.BMLayerItem, node_groups: list, distance: float, is_split_ends: bool, is_per_vertex: bool):
        loop: bmesh.types.BMLoop = None
        node: UvNode = None

        is_split_ends = False if is_per_vertex else is_split_ends

        for node_group in node_groups:
            for node in node_group:
                if node.neighbors_count >= 1:
                    if node.neighbors_count == 1 and len(node.loops) > 2:
                        if is_split_ends:
                            if self.is_not_sync:
                                for loop in node.loops:
                                    self._handle_simple_case(uv_layer, node, loop, distance)
                            else:
                                # Split ends in no sync
                                for loop in node.loops:
                                    if loop.edge.select or loop.link_loop_prev.edge.select:
                                        self._handle_simple_case(uv_layer, node, loop, distance)
                                    else:
                                        node.result_coordinates[loop.index] = loop[uv_layer].uv

                        else:
                            if is_per_vertex:
                                self._split_per_vertex(uv_layer, node, distance)
                            else:
                                for loop in node.loops:
                                    node.result_coordinates[loop.index] = loop[uv_layer].uv
                        continue

                    if is_per_vertex:
                        self._split_per_vertex(uv_layer, node, distance)
                    else:
                        self._calc_coordinates(uv_layer, node, distance)
                else:
                    # Handle nodes with ONE vertex selected
                    if is_per_vertex:
                        self._split_per_vertex(uv_layer, node, distance)
                    else:
                        for loop in node.loops:
                            node.result_coordinates[loop.index] = loop[uv_layer].uv

    def collect_neighbors(self, node_groups: list):
        for node_group in node_groups:
            for node in node_group:
                for loop in node.loops:
                    for adj_node in node_group:
                        if loop.link_loop_prev in adj_node.loops or loop.link_loop_next in adj_node.loops:
                            node.neighbors.add(adj_node)
                            adj_node.neighbors.add(node)
        return node_groups

    def set_uv_coordinates(self, node_groups: list, uv_layer: bmesh.types.BMLayerItem):
        if not len(node_groups):
            return
        if len(node_groups[0][0].result_coordinates) == 0:
            raise RuntimeError('The result_coordinates were not calculated')
        for node_group in node_groups:
            for node in node_group:
                for loop in node.loops:
                    loop[uv_layer].uv = node.result_coordinates[loop.index]

    def _calc_coordinates(self, uv_layer: bmesh.types.BMLayerItem, node: UvNode, distance: float):
        for loop in node.loops:
            if loop.index in node.result_coordinates:
                continue

            if self._is_no_selected(loop, uv_layer):
                coo = self._handle_two_vectors(uv_layer, loop, node, distance)
                node.result_coordinates[loop.index] = coo

                node.result_coordinates[loop.link_loop_radial_next.link_loop_next.index] = coo
                node.result_coordinates[loop.link_loop_prev.link_loop_radial_next.index] = coo

            elif self._is_all_selected(loop, uv_layer):
                coo = self._handle_two_vectors(uv_layer, loop, node, distance)
                node.result_coordinates[loop.index] = coo

            else:
                coo = self._handle_simple_case(uv_layer, node, loop, distance)

            if self.show_in_annotations:
                node.vis_directions.append((Vector(loop[uv_layer].uv.to_tuple()), coo))

    def _split_per_vertex(self, uv_layer: bmesh.types.BMLayerItem, node: UvNode, distance: float):
        for loop in node.loops:
            base_pos = loop[uv_layer].uv
            p_new_pos = base_pos + (loop.link_loop_next.link_loop_next[uv_layer].uv - base_pos).normalized() * distance
            loop[uv_layer].uv = p_new_pos
            node.result_coordinates[loop.index] = p_new_pos

    def _is_all_selected(self, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
        lp = loop
        lp_next = loop.link_loop_next
        lp_prev = loop.link_loop_prev

        if self.is_pure_uv_edge_mode:
            return lp[uv_layer].select_edge and lp_prev[uv_layer].select_edge

        elif self.is_not_sync:
            return lp[uv_layer].select and lp_next[uv_layer].select and lp_prev[uv_layer].select

        else:
            return lp.vert.select and lp_next.vert.select and lp_prev.vert.select

    def _is_no_selected(self, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
        lp = loop
        lp_next = loop.link_loop_next
        lp_prev = loop.link_loop_prev

        if self.is_pure_uv_edge_mode:
            return not lp[uv_layer].select_edge and not lp_prev[uv_layer].select_edge

        elif self.is_not_sync:
            return lp[uv_layer].select and not lp_next[uv_layer].select and not lp_prev[uv_layer].select

        else:
            return lp.vert.select and not lp_next.vert.select and not lp_prev.vert.select

    def _is_not_prev_selected(self, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
        lp = loop
        lp_prev = loop.link_loop_prev

        if self.is_pure_uv_edge_mode:
            return lp[uv_layer].select and not lp_prev[uv_layer].select_edge
        elif self.is_not_sync:
            return lp[uv_layer].select and not lp_prev[uv_layer].select
        else:
            return lp.vert.select and not lp_prev.vert.select

    def _is_not_next_selected(self, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
        lp = loop
        lp_next = loop.link_loop_next

        if self.is_pure_uv_edge_mode:
            return lp[uv_layer].select and lp_next[uv_layer].select_edge
        elif self.is_not_sync:
            return lp[uv_layer].select and not lp_next[uv_layer].select
        else:
            return lp.vert.select and not lp_next.vert.select

    def _handle_simple_case(self, uv_layer: bmesh.types.BMLayerItem, node: UvNode, loop: bmesh.types.BMLoop, distance: float) -> Vector:
        base_pos = Vector(loop[uv_layer].uv.to_tuple())
        if self.is_pure_uv_edge_mode:
            if loop[uv_layer].select_edge:
                coo = base_pos + (loop.link_loop_prev[uv_layer].uv - base_pos).normalized() * distance
                node.result_coordinates[loop.index] = coo
            elif loop.link_loop_prev[uv_layer].select_edge:
                coo = base_pos + (loop.link_loop_next[uv_layer].uv - base_pos).normalized() * distance
                node.result_coordinates[loop.index] = coo
            else:
                coo = node.result_coordinates[loop.index] = base_pos
        else:
            if self._is_not_prev_selected(loop, uv_layer):
                coo = base_pos + (loop.link_loop_prev[uv_layer].uv - base_pos).normalized() * distance
                node.result_coordinates[loop.index] = coo
            elif self._is_not_next_selected(loop, uv_layer):
                coo = base_pos + (loop.link_loop_next[uv_layer].uv - base_pos).normalized() * distance
                node.result_coordinates[loop.index] = coo
            else:
                coo = node.result_coordinates[loop.index] = base_pos

        if self.show_in_annotations:
            node.vis_directions.append((base_pos, coo))

        return coo

    def _handle_two_vectors(self, uv_layer: bmesh.types.BMLayerItem, loop: bmesh.types.BMLoop, node: UvNode, distance: float):
        base_pos = loop[uv_layer].uv.copy().freeze()
        p_v01 = (loop.link_loop_next[uv_layer].uv - base_pos)
        p_v02 = (loop.link_loop_prev[uv_layer].uv - base_pos)
        p_offset = sqrt(2) * distance
        p_direction = (p_v01.normalized() + p_v02.normalized()) * 0.5

        return base_pos + p_direction.normalized() * p_offset


class LoopsFactory:
    """EXACT copy of ZenUV's LoopsFactory"""
    
    @classmethod
    def loops_by_sel_mode(cls, context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, groupped: bool = True) -> list:
        loops = cls._loops_by_sel_mode(context, bm.faces, uv_layer)

        if groupped:
            if context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                return cls.compound_groups_from_loops(loops, uv_layer)
            else:
                p_face_idxs_groups = cls.compound_groups_from_loops_in_edit_mode_iterative(bm, loops)
                return [[lp for lp in loops if lp.edge.index in group] for group in p_face_idxs_groups]

        return loops

    @classmethod
    def _loops_by_sel_mode(cls, context: bpy.types.Context, inp_faces: list, uv_layer: bmesh.types.BMLayerItem):
        """ Return loops converted from selected elements """
        sync_uv = context.scene.tool_settings.use_uv_select_sync
        if context.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
            mode = context.scene.tool_settings.uv_select_mode
            if mode == 'VERTEX':
                return list({loop for face in inp_faces for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})
            elif mode == 'EDGE':
                return list({loop for face in inp_faces for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})
            else:
                return list({loop for face in inp_faces for loop in face.loops if not face.hide and face.select and loop[uv_layer].select})
        else:
            mesh_select_mode = context.tool_settings.mesh_select_mode

            if mesh_select_mode[1] or mesh_select_mode[0]:
                return [loop for vertex in [v for v in {v for f in inp_faces for v in f.verts} if v.select] for loop in vertex.link_loops if not loop.face.hide and loop.face in inp_faces]

            elif mesh_select_mode[2]:
                return [loop for face in [face for face in inp_faces if face.select and not face.hide] for loop in face.loops]

    @classmethod
    def compound_groups_from_loops_in_edit_mode_iterative(cls, bm, loops: list) -> list:
        # Create a set of selected edges
        selected_edges_idxs = {lp.edge.index for lp in loops}
        bm.edges.ensure_lookup_table()
        # Build adjacency list (graph representation)
        adjacency_list = {e_index: [] for e_index in selected_edges_idxs}
        for i in selected_edges_idxs:
            edge = bm.edges[i]
            for vert in edge.verts:
                for other_edge in vert.link_edges:
                    if other_edge != edge and other_edge.index in selected_edges_idxs:
                        adjacency_list[edge.index].append(other_edge.index)

        # Depth-first search (DFS) to find connected components iteratively
        def dfs_iterative(start_node):
            visited = set()
            stack = [start_node]
            component = []
            while stack:
                node = stack.pop()
                if node not in visited:
                    visited.add(node)
                    component.append(node)
                    stack.extend(neighbor for neighbor in adjacency_list[node] if neighbor not in visited)
            return component

        # Find connected components (groups of edges with common vertices) iteratively
        visited = set()
        edge_groups_indices = []
        for node in adjacency_list:
            if node not in visited:
                component = dfs_iterative(node)
                edge_groups_indices.append(component)
                visited.update(component)

        return edge_groups_indices

    @classmethod
    def compound_groups_from_loops(cls, loops: list, uv_layer: bmesh.types.BMLayerItem, _sorted: bool = True) -> list:
        _groups = []
        loops = set(loops)

        while len(loops) != 0:
            init_loop = loops.pop()
            cluster = {init_loop}
            stack = {init_loop}
            while len(stack) != 0:
                loop = stack.pop()

                linked = [lp for lp in loop.vert.link_loops if lp in loops and lp not in cluster and lp[uv_layer].uv == loop[uv_layer].uv]
                cluster.update(linked)
                stack.update(linked)
                linked.append(loop)

                adj = [lp.link_loop_next for lp in linked if lp.link_loop_next in loops and lp.link_loop_next not in cluster]
                adj.extend([lp.link_loop_prev for lp in linked if lp.link_loop_prev in loops and lp.link_loop_prev not in cluster])

                cluster.update(adj)
                stack.update(adj)

            _groups.append(list(cluster))
            loops -= cluster

        return _groups


def resort_by_type_mesh_in_edit_mode_and_sel(context):
    """ Return objects in edit mode and selected without instances """
    if context.mode == 'EDIT_MESH':
        return {
            obj for obj in context.objects_in_mode_unique_data
            if obj.type == 'MESH' and len(obj.data.polygons) != 0
            and obj.hide_get() is False
            and obj.hide_viewport is False
        }
    else:
        t_objects = {
            obj.data: obj for obj in context.selected_objects
            if obj.type == 'MESH'
            and len(obj.data.polygons) != 0
            and obj.hide_get() is False
            and obj.hide_viewport is False
        }
        return t_objects.values()


def resort_objects_by_selection(context: bpy.types.Context, objs: list):
    sync_uv = context.scene.tool_settings.use_uv_select_sync

    if context.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
        p_objects = []
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            me: bpy.types.Mesh = obj.data
            if me.total_face_sel > 0:
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    if any(loop[uv_layer].select for f in bm.faces for loop in f.loops if f.select and not f.hide):
                        p_objects.append(obj)
        return p_objects
    else:
        if context.mode == 'EDIT_MESH':
            p_objects = []
            for obj in objs:
                me = obj.data
                bm = bmesh.from_edit_mesh(me)
                if me.total_vert_sel > 0 or me.total_edge_sel > 0 or me.total_face_sel > 0:
                    p_objects.append(obj)
            return p_objects
        elif context.mode == 'OBJECT':
            return [obj for obj in objs if sum(obj.data.count_selected_items()) != 0]


def verify_uv_layer(bm: bmesh.types.BMesh):
    p_names = set(bm.loops.layers.uv.keys())
    s_name = "UVMap"

    p_uv_layer = bm.loops.layers.uv.active
    if not p_uv_layer:
        p_uv_layer = bm.loops.layers.uv.new(s_name)
    return p_uv_layer


class UVV_OT_SplitUV(Operator):
    """EXACT copy of ZenUV's Split operator"""
    bl_idname = "uv.uvv_split"
    bl_label = "Split UV"
    bl_description = "Splits selected in the UV"
    bl_options = {'REGISTER', 'UNDO'}

    set_minimum: BoolProperty(
        name='Minimum distance',
        description='Sets the smallest distance sufficient for splitting but not visible to the eye',
        default=False
    )
    
    distance: FloatProperty(
        name='Distance',
        description='The distance to which the vertices need to be moved',
        default=0.005,
        min=0.0,
        precision=3,
        step=0.1
    )
    
    per_vertex: BoolProperty(
        name='Per Vertex',
        description='Split each vertex separately',
        default=False
    )
    
    split_ends: BoolProperty(
        name='Split Ends',
        description='Splits the ends. The gap remains the same along the entire length',
        default=False
    )
    
    mark_seam: BoolProperty(
        name="Mark Seam",
        description="Mark split edges as seams",
        default=True
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
        layout.prop(self, 'set_minimum')
        row = layout.row()
        row.enabled = not self.set_minimum
        row.prop(self, 'distance')
        layout.prop(self, 'per_vertex')
        row = layout.row()
        row.enabled = not self.per_vertex
        row.prop(self, 'split_ends')
        layout.prop(self, "mark_seam")

    def execute(self, context):
        if self.set_minimum is False and self.distance == 0.0:
            self.report({'WARNING'}, "UVV: The split was not performed. Distance is zero")
            return {'FINISHED'}

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "UVV: There are no selected objects.")
            return {"CANCELLED"}

        objs = resort_objects_by_selection(context, objs)
        if not objs:
            self.report({'WARNING'}, "UVV: Select something.")
            return {'CANCELLED'}

        edges_split = 0
        seams_marked = 0

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            p_loops = LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)

            SP = UvSplitProcessor(context)

            node_groups = SP.compound_nodes(uv_layer, p_loops)

            # 1e-4 minimal value for native 'Select Linked' compatibility
            SP.calculate_loops_positions(
                uv_layer=uv_layer,
                node_groups=node_groups,
                distance=1e-4 if self.set_minimum else self.distance * 0.5,
                is_split_ends=self.split_ends,
                is_per_vertex=self.per_vertex)

            SP.set_uv_coordinates(node_groups, uv_layer)

            # Mark seams if requested - only on the actual selected edges
            if self.mark_seam:
                # Get the actual selected edges from the original selection
                selected_edges = set()
                
                # Collect edges from the original selection based on context
                if context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                    # UV Editor mode without sync - get edges from UV selection
                    for face in bm.faces:
                        if face.hide:
                            continue
                        for edge in face.edges:
                            # Check if this edge has selected UV loops
                            has_selected_uv = False
                            for face in edge.link_faces:
                                if face.hide:
                                    continue
                                for loop in face.loops:
                                    if loop.vert in edge.verts and loop[uv_layer].select:
                                        has_selected_uv = True
                                        break
                                if has_selected_uv:
                                    break
                            if has_selected_uv:
                                selected_edges.add(edge)
                else:
                    # 3D viewport mode or UV sync - get edges from mesh selection
                    for edge in bm.edges:
                        if edge.select and not edge.hide:
                            selected_edges.add(edge)
                
                # Mark seams only on the selected edges
                for edge in selected_edges:
                    if not edge.seam:
                        edge.seam = True
                        seams_marked += 1

            edges_split += len(p_loops)
            bmesh.update_edit_mesh(obj.data)

        # Report results
        if edges_split > 0:
            msg = f"Split {edges_split} UV edge(s)"
            if seams_marked > 0:
                msg += f", marked {seams_marked} seam(s)"
            self.report({'INFO'}, msg)
        else:
            self.report({'WARNING'}, "No edges selected to split")

        return {'FINISHED'}


# Classes to register
classes = [
    UVV_OT_SplitUV,
]