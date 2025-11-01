import bpy
import bmesh
import math
from bpy.types import Operator
from bpy.props import BoolProperty, FloatProperty


class UVV_OT_seam_by_angle(Operator):
    """Mark seams by angle threshold - from Mio3"""
    bl_idname = "uv.uvv_seam_by_angle"
    bl_label = "Seam by Angle"
    bl_options = {'REGISTER', 'UNDO'}

    threshold_rad: FloatProperty(
        name="Angle",
        default=math.radians(30.0),
        min=math.radians(1.0),
        max=math.radians(180.0),
        subtype="ANGLE",
        step=100,
    )

    remove_seam: BoolProperty(
        name="Clear Original Seam",
        default=False,
    )

    unwrap: BoolProperty(
        name="UV Unwrap",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object is not None and
                context.active_object.type == 'MESH')

    def execute(self, context):
        # Get all selected mesh objects in edit mode
        objects = [obj for obj in context.objects_in_mode if obj.type == 'MESH']

        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            selected_faces = {face for face in bm.faces if face.select}

            if not selected_faces:
                continue

            # Remove existing seams if requested
            if self.remove_seam:
                for face in selected_faces:
                    for edge in face.edges:
                        edge.seam = False

            # Mark seams by angle
            self.mark_seam_by_angle(selected_faces, self.threshold_rad)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data)

        # Unwrap if requested
        if self.unwrap:
            bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0)

        self.report({'INFO'}, f"Seams marked at {math.degrees(self.threshold_rad):.1f}° angle")
        return {'FINISHED'}

    @staticmethod
    def mark_seam_by_angle(selected_faces, angle_rad):
        """Mark seams on edges where adjacent faces have angle >= threshold"""
        target_edges = set()
        for face in selected_faces:
            for edge in face.edges:
                target_edges.add(edge)

        for edge in target_edges:
            if not edge.is_manifold:
                continue
            linked_faces = [f for f in edge.link_faces if f in selected_faces]
            if len(linked_faces) != 2:
                continue
            normal1 = linked_faces[0].normal
            normal2 = linked_faces[1].normal
            angle = normal1.angle(normal2)
            if angle >= angle_rad:
                edge.seam = True

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "threshold_rad")
        layout.prop(self, "remove_seam")
        layout.prop(self, "unwrap")


# Old placeholder relax operator removed - replaced with relax_univ.py


class UVV_OT_rotate_neg90(Operator):
    """Rotate UV islands -90 degrees"""
    bl_idname = "uv.uvv_rotate_neg90"
    bl_label = "Rotate -90°"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        self.report({'INFO'}, "Rotate -90° - Feature coming soon!")
        return {'FINISHED'}


class UVV_OT_rotate_180(Operator):
    """Rotate UV islands 180 degrees"""
    bl_idname = "uv.uvv_rotate_180"
    bl_label = "Rotate 180°"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        self.report({'INFO'}, "Rotate 180° - Feature coming soon!")
        return {'FINISHED'}


class UVV_OT_pack_selection(Operator):
    """Pack selected UV islands"""
    bl_idname = "uv.uvv_pack_selection"
    bl_label = "Pack Selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        self.report({'INFO'}, "Pack Selection - Feature coming soon!")
        return {'FINISHED'}


class UVV_OT_pack_all(Operator):
    """Pack all UV islands"""
    bl_idname = "uv.uvv_pack_all"
    bl_label = "Pack All"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        self.report({'INFO'}, "Pack All - Feature coming soon!")
        return {'FINISHED'}


classes = [
    UVV_OT_seam_by_angle,
    UVV_OT_rotate_neg90,
    UVV_OT_rotate_180,
    UVV_OT_pack_selection,
    UVV_OT_pack_all,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)