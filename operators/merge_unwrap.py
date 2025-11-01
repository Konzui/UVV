"""
Merge Unwrap Operator
Merges selected UV islands by clearing internal seams and unwrapping as one island
"""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import EnumProperty


class UVV_OT_MergeUnwrap(Operator):
    """Merge selected faces into one UV island by clearing internal seams and unwrapping"""
    bl_idname = "uv.uvv_merge_unwrap"
    bl_label = "Merge Unwrap"
    bl_description = "Clear internal seams between selected faces and unwrap as one island"
    bl_options = {'REGISTER', 'UNDO'}

    unwrap_method: EnumProperty(
        name="Unwrap Method",
        items=[
            ('ANGLE_BASED', 'Angle Based', 'Angle Based unwrapping'),
            ('CONFORMAL', 'Conformal', 'Conformal unwrapping'),
        ],
        default='ANGLE_BASED'
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object is not None and
                context.active_object.type == 'MESH')

    def execute(self, context):
        # Check if UV sync mode is on
        sync_mode = context.scene.tool_settings.use_uv_select_sync

        # Get all selected mesh objects in edit mode
        objects = [obj for obj in context.objects_in_mode if obj.type == 'MESH']

        # Check if any UV islands are selected (in non-sync mode)
        has_uv_selection = False
        if not sync_mode:
            for obj in objects:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    for face in bm.faces:
                        if face.select:
                            # Check if any UV in this face is selected
                            if any(loop[uv_layer].select for loop in face.loops):
                                has_uv_selection = True
                                break
                if has_uv_selection:
                    break

        # If no UV selection and not in sync mode, select UVs from selected faces
        if not sync_mode and not has_uv_selection:
            for obj in objects:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    for face in bm.faces:
                        if face.select:
                            # Select all UVs in this face
                            for loop in face.loops:
                                loop[uv_layer].select = True
                    bmesh.update_edit_mesh(obj.data)

        total_merged = 0

        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            selected_faces = {face for face in bm.faces if face.select}

            if not selected_faces:
                continue

            # Process edges: clear internal seams, mark boundary seams
            edges_cleared = 0
            edges_marked = 0

            for edge in bm.edges:
                # Get selected faces connected to this edge
                selected_link_faces = [f for f in edge.link_faces if f.select]

                # Internal edge: both faces are selected
                if len(selected_link_faces) == 2:
                    if edge.seam:
                        edges_cleared += 1
                    edge.seam = False

                # Boundary edge: only one face is selected
                elif len(selected_link_faces) == 1:
                    if not edge.seam:
                        edges_marked += 1
                    edge.seam = True

            # Update mesh before unwrapping
            bmesh.update_edit_mesh(obj.data)

            total_merged += 1

        # Unwrap the merged selection
        if total_merged > 0:
            if bpy.ops.uv.unwrap.poll():
                bpy.ops.uv.unwrap(method=self.unwrap_method, margin=0.001)

                # Select UVs for the merged islands (in non-sync mode)
                if not sync_mode:
                    for obj in objects:
                        bm = bmesh.from_edit_mesh(obj.data)
                        uv_layer = bm.loops.layers.uv.active
                        if uv_layer:
                            for face in bm.faces:
                                if face.select:
                                    # Select all UVs in this face
                                    for loop in face.loops:
                                        loop[uv_layer].select = True
                            bmesh.update_edit_mesh(obj.data)

                self.report({'INFO'}, f"Merged and unwrapped {total_merged} object(s)")
            else:
                self.report({'WARNING'}, "Could not unwrap - check UV selection")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "No faces selected")
            return {'CANCELLED'}

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "unwrap_method")


classes = [
    UVV_OT_MergeUnwrap,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
