"""UV Island Shift operator - Move islands by 1 UV unit in cardinal directions"""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import EnumProperty


class UVV_OT_shift_uv(Operator):
    """Shift selected UV islands by 1 UV unit in the specified direction"""
    bl_idname = "uv.uvv_shift_uv"
    bl_label = "Shift UV Island"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="Direction",
        items=[
            ('LEFT', 'Left', 'Move left by 1 UV unit', 'TRIA_LEFT', 0),
            ('RIGHT', 'Right', 'Move right by 1 UV unit', 'TRIA_RIGHT', 1),
            ('UP', 'Up', 'Move up by 1 UV unit', 'TRIA_UP', 2),
            ('DOWN', 'Down', 'Move down by 1 UV unit', 'TRIA_DOWN', 3),
        ],
        default='LEFT'
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object is not None and
                context.active_object.type == 'MESH')

    def execute(self, context):
        # Get offset vector based on direction
        offset_map = {
            'LEFT': (-1.0, 0.0),
            'RIGHT': (1.0, 0.0),
            'UP': (0.0, 1.0),
            'DOWN': (0.0, -1.0),
        }

        offset = offset_map[self.direction]

        # Process all selected objects
        for obj in context.objects_in_mode_unique_data:
            if obj.type != 'MESH':
                continue

            # Get mesh data
            mesh = obj.data
            bm = bmesh.from_edit_mesh(mesh)

            # Get UV layer
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            # Check if we're in UV sync mode
            use_uv_sync = context.tool_settings.use_uv_select_sync

            # Move selected UVs
            if use_uv_sync:
                # In sync mode, move UVs of selected faces
                for face in bm.faces:
                    if face.select:
                        for loop in face.loops:
                            loop[uv_layer].uv.x += offset[0]
                            loop[uv_layer].uv.y += offset[1]
            else:
                # In non-sync mode, move selected UV vertices
                for face in bm.faces:
                    for loop in face.loops:
                        if loop[uv_layer].select:
                            loop[uv_layer].uv.x += offset[0]
                            loop[uv_layer].uv.y += offset[1]

            # Update the mesh
            bmesh.update_edit_mesh(mesh, loop_triangles=False)

        # Report success
        direction_name = self.direction.lower()
        self.report({'INFO'}, f"Shifted UV island {direction_name}")

        return {'FINISHED'}


classes = [
    UVV_OT_shift_uv,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
