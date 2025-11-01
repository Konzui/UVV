"""
World Orient Operator
Aligns UV islands to world axis
"""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty

from ..utils.generic_helpers import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    resort_objects,
    get_mesh_data
)
from ..utils import island_utils
from ..utils.base_clusters.base_cluster import (
    OrientCluster,
    BaseCluster,
    TransformCluster,
)
from ..utils.base_clusters.zen_cluster import ZenCluster


class oCluster(ZenCluster, TransformCluster, OrientCluster):
    """Combined cluster with all orient capabilities"""
    def __init__(self, context, obj, island, bm=None) -> None:
        BaseCluster.__init__(self, context, obj, island, bm)
        ZenCluster.__init__(self, context, obj, island, bm)
        OrientCluster.__init__(self)


class UVV_OT_WorldOrient(Operator):
    bl_idname = "uv.uvv_world_orient"
    bl_label = "World Orient"
    bl_description = "Orient UV islands to world axis"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(
        name="Method",
        description="Orientation method",
        items=[
            ("HARD", "Hard Surface", "Hard surface orientation"),
            ("ORGANIC", "Organic", "Organic orientation")
        ],
        default="HARD"
    )
    rev_x: BoolProperty(name="X", default=False, description="Reverse Axis X")
    rev_y: BoolProperty(name="Y", default=False, description="Reverse Axis Y")
    rev_z: BoolProperty(name="Z", default=False, description="Reverse Axis Z")
    rev_neg_x: BoolProperty(name="-X", default=False, description="Reverse Axis -X")
    rev_neg_y: BoolProperty(name="-Y", default=False, description="Reverse Axis -Y")
    rev_neg_z: BoolProperty(name="-Z", default=False, description="Reverse Axis -Z")

    further_orient: BoolProperty(
        name="Further Orient",
        default=True,
        description="Apply additional orientation refinement"
        )
    flip_by_axis: BoolProperty(
        name="Flip By Axis",
        default=False,
        description="Allow flip islands by axis"
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "method")
        layout.prop(self, "further_orient")
        layout.prop(self, "flip_by_axis")
        if self.flip_by_axis:
            layout.label(text="Reverse Axis:")
            box = layout.box()
            row = box.row(align=True)
            row.prop(self, "rev_x")
            row.prop(self, "rev_y")
            row.prop(self, "rev_z")
            row = box.row(align=True)
            row.prop(self, "rev_neg_x")
            row.prop(self, "rev_neg_y")
            row.prop(self, "rev_neg_z")

    @classmethod
    def poll(cls, context):
        """Validate context"""
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        objs = resort_objects(context, objs)
        if not objs:
            return {'CANCELLED'}

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.verify()
            islands = island_utils.get_island(context, bm, uv_layer)
            for ids, island in enumerate(islands):
                cluster = oCluster(context, obj, island, bm)
                cluster.f_orient = self.further_orient
                cluster.set_direction(
                    {
                        "x": self.rev_x,
                        "-x": self.rev_neg_x,
                        "y": self.rev_y,
                        "-y": self.rev_neg_y,
                        "z": self.rev_z,
                        "-z": self.rev_neg_z,
                    }
                )
                cluster.type = self.method
                cluster.orient_to_world()

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {'FINISHED'}


# Classes to register
classes = (
    UVV_OT_WorldOrient,
)
