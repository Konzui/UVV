"""
UVV Generic Helper Functions
Helper utilities for mesh and object operations
"""

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from bmesh.types import BMLoop, BMLayerItem


class Scope:
    """Creates dict data with automatic structure"""
    def __init__(self) -> None:
        self.data = {}

    def append(self, key, value):
        """Creates dict {key: [value, ]}"""
        if key not in self.data.keys():
            self.data.update({key: [value]})
        else:
            self.data[key].append(value)

    def get_singles_keys(self):
        """Return keys where len(values) == 1"""
        for key, value in self.data.items():
            if len(value) == 1:
                yield key

    def get_mults_keys(self):
        """Return keys where len(values) > 1"""
        for key, value in self.data.items():
            if len(value) > 1:
                yield key

    def get_mults_values(self):
        """Return value from [values, ] where len([values, ]) > 1"""
        for key, value in self.data.items():
            if len(value) > 1:
                for v in value:
                    yield v


def linked_crn_uv_by_island_index_unordered_included(crn: BMLoop, uv: BMLayerItem, idx: int):
    """Linked to arg corner by island index with arg corner"""
    first_co = crn[uv].uv
    return [l_crn for l_crn in crn.vert.link_loops if l_crn.face.index == idx and l_crn[uv].uv == first_co]


class Distortion:
    """Random distortion vectors for UV operations"""

    @staticmethod
    def get_vector_2d(size=1):
        return Vector((np.random.rand(1, 2) * size).tolist()[0])

    @staticmethod
    def get_vector_3d(size=1):
        return Vector((np.random.rand(1, 3) * size).tolist()[0])


class MeshBuilder:
    """Helper for building mesh geometry"""

    def __init__(self, bm) -> None:
        self.bm = bm

    def create_vertices_3d(self, coors):
        verts = []
        for co in coors:
            verts.append(self.bm.verts.new(co))
        return verts

    def create_edge(self, coords):
        if len(coords) == 2:
            verts = self.create_vertices_3d(coords)
            return self.bm.edges.new(verts)
        else:
            print("Builder: Needed exactly 2 coordinates.")


def resort_by_type_mesh_in_edit_mode_and_sel(context):
    """Return objects in edit mode and selected without instances"""
    selected = ({obj for obj in context.selected_objects if obj.type == 'MESH' and len(obj.data.polygons) != 0})
    in_mode = ({obj for obj in context.objects_in_mode_unique_data if obj.type == 'MESH' and len(obj.data.polygons) != 0})
    common = filter_instances(selected.union(in_mode))
    return common


def filter_instances(objs):
    """Removes instance meshes from input list (objs)"""
    unique_data = {p_obj.data: p_obj for p_obj in objs if p_obj.type == 'MESH'}
    return unique_data.values()


def resort_objects(context, objs):
    """Filter objects that have UV selection"""
    objects = []
    sync_uv = context.scene.tool_settings.use_uv_select_sync

    if context.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()
            if True in [loop[uv_layer].select for f in bm.faces for loop in f.loops if not f.hide]:
                objects.append(obj)
    else:
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            if True in [e.select for e in bm.faces] or \
                True in [e.select for e in bm.edges] or \
                    True in [e.select for e in bm.verts]:
                objects.append(obj)
    return objects


def get_mesh_data(obj):
    """Return me as obj.data and bm as bmesh.from_edit_mesh(me)"""
    return obj.data, bmesh.from_edit_mesh(obj.data)


def face_indexes_by_sel_mode(context, bm):
    """Return face indexes converted from selected elements"""
    uv_layer = bm.loops.layers.uv.verify()
    selection = []
    sync_uv = context.scene.tool_settings.use_uv_select_sync

    if hasattr(context, 'space_data') and context.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
        sel_faces = set()
        # In non-sync mode, check both mesh-level face selection AND UV loop selection
        # Blender 3.2+ has select_edge attribute
        if bpy.app.version >= (3, 2, 0):
            sel_faces.update({f.index for f in bm.faces for loop in f.loops
                            if not f.hide and f.select and loop[uv_layer].select and loop[uv_layer].select_edge})
        else:
            sel_faces.update({f.index for f in bm.faces for loop in f.loops
                            if not f.hide and f.select and loop[uv_layer].select})
        if sel_faces:
            selection.extend(list(sel_faces))
    else:
        mode = context.tool_settings.mesh_select_mode
        if mode[1]:  # Edge mode
            selection = [face.index for edge in [e for e in bm.edges if e.select]
                        for face in edge.link_faces if not face.hide]
        elif mode[2]:  # Face mode
            selection = [face.index for face in bm.faces if face.select and not face.hide]
        elif mode[0]:  # Vertex mode
            selection = [face.index for vert in [v for v in bm.verts if v.select]
                        for face in vert.link_faces if not face.hide]
    return selection
