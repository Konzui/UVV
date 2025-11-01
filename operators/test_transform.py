"""
Test operator for island transformation functions.
This allows testing move, rotate, and scale operations on selected UV islands.
"""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import FloatProperty, EnumProperty
from mathutils import Vector
from ..utils.transform import (
    move_island,
    rotate_island_with_aspect,
    scale_island_with_pivot,
    set_island_position,
    calc_island_bbox_center,
    BoundingBox2d
)
from ..utils.island_utils import zen_get_islands


class UVV_OT_TestTransform(Operator):
    """Test island transformation functions"""
    bl_idname = "uv.uvv_test_transform"
    bl_label = "Test Transform"
    bl_description = "Test island transformation functions (move, rotate, scale)"
    bl_options = {'REGISTER', 'UNDO'}

    operation: EnumProperty(
        name="Operation",
        items=[
            ('MOVE', 'Move', 'Move island by delta'),
            ('ROTATE', 'Rotate', 'Rotate island around center'),
            ('SCALE', 'Scale', 'Scale island from center'),
            ('SET_POS', 'Set Position', 'Move island to specific position'),
        ],
        default='MOVE'
    )

    # Move parameters
    move_x: FloatProperty(name="Move X", default=0.1, step=0.01)
    move_y: FloatProperty(name="Move Y", default=0.1, step=0.01)

    # Rotate parameters
    rotate_angle: FloatProperty(
        name="Rotate Angle",
        default=45.0,
        min=-360.0,
        max=360.0,
        description="Rotation angle in degrees"
    )

    # Scale parameters
    scale_x: FloatProperty(name="Scale X", default=1.5, min=0.1, max=5.0)
    scale_y: FloatProperty(name="Scale Y", default=1.5, min=0.1, max=5.0)

    # Set position parameters
    target_x: FloatProperty(name="Target X", default=0.5, step=0.1)
    target_y: FloatProperty(name="Target Y", default=0.5, step=0.1)

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "operation", expand=True)

        box = layout.box()
        if self.operation == 'MOVE':
            box.label(text="Move Parameters:")
            box.prop(self, "move_x")
            box.prop(self, "move_y")
        elif self.operation == 'ROTATE':
            box.label(text="Rotate Parameters:")
            box.prop(self, "rotate_angle")
            box.label(text="Rotates around island center", icon='INFO')
        elif self.operation == 'SCALE':
            box.label(text="Scale Parameters:")
            box.prop(self, "scale_x")
            box.prop(self, "scale_y")
            box.label(text="Scales from island center", icon='INFO')
        elif self.operation == 'SET_POS':
            box.label(text="Set Position Parameters:")
            box.prop(self, "target_x")
            box.prop(self, "target_y")
            box.label(text="Moves island to target position", icon='INFO')

    def execute(self, context):
        print("\n" + "="*60)
        print(f"[TEST_TRANSFORM] Starting test: {self.operation}")
        print("="*60)

        total_transformed = 0

        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.verify()

            # Get selected faces
            selected_faces = [f for f in bm.faces if f.select and not f.hide]
            if not selected_faces:
                continue

            print(f"\n[TEST_TRANSFORM] Object: {obj.name}, selected faces: {len(selected_faces)}")

            # Get islands from selected faces using Zen UV pattern
            islands = zen_get_islands(bm, selected_faces, has_selected_faces=True)
            print(f"[TEST_TRANSFORM] Found {len(islands)} island(s)")

            for idx, island in enumerate(islands):
                print(f"\n[TEST_TRANSFORM] Processing island {idx+1}/{len(islands)} with {len(island)} faces")

                # Calculate island center for pivot operations
                bbox = BoundingBox2d(islands=[island], uv_layer=uv_layer)
                center = bbox.center
                print(f"[TEST_TRANSFORM] Island center: {center}")
                print(f"[TEST_TRANSFORM] Island bbox: min={bbox.bot_left}, max={bbox.top_right}")

                success = False

                if self.operation == 'MOVE':
                    delta = Vector((self.move_x, self.move_y))
                    success = move_island(island, uv_layer, delta)

                elif self.operation == 'ROTATE':
                    import math
                    angle_rad = math.radians(self.rotate_angle)
                    success = rotate_island_with_aspect(island, uv_layer, angle_rad, center, aspect=1.0)

                elif self.operation == 'SCALE':
                    scale = Vector((self.scale_x, self.scale_y))
                    success = scale_island_with_pivot(island, uv_layer, scale, center)

                elif self.operation == 'SET_POS':
                    target_pos = Vector((self.target_x, self.target_y))
                    success = set_island_position(island, uv_layer, target_pos, from_pos=center)

                if success:
                    total_transformed += 1
                    print(f"[TEST_TRANSFORM] Island {idx+1} transformed successfully")
                else:
                    print(f"[TEST_TRANSFORM] Island {idx+1} transformation skipped (no change)")

            # Update mesh
            bmesh.update_edit_mesh(obj.data)

        print("\n" + "="*60)
        print(f"[TEST_TRANSFORM] Test completed: {total_transformed} island(s) transformed")
        print("="*60 + "\n")

        if total_transformed > 0:
            self.report({'INFO'}, f"Transformed {total_transformed} island(s) using {self.operation}")
        else:
            self.report({'WARNING'}, "No islands transformed. Select UV islands to test.")

        return {'FINISHED'}


# Register classes
classes = (
    UVV_OT_TestTransform,
)
