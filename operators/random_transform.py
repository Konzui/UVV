# SPDX-License-Identifier: GPL-2.0-or-later
# Based on UniV addon by Oxicid - simplified for UVV

import bpy
import bmesh
import math
import random
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty
from mathutils import Vector, Matrix


class UVV_OT_Random(Operator):
    bl_idname = "uv.uvv_random"
    bl_label = "Random"
    bl_description = "Randomize selected UV islands or faces"
    bl_options = {'REGISTER', 'UNDO'}

    between: BoolProperty(
        name='Shuffle',
        description="Shuffle island positions between each other",
        default=False
    )
    bound_between: EnumProperty(
        name='Bound Shuffle',
        description="How to handle bounds when shuffling",
        default='OFF',
        items=(
            ('OFF', 'Off', 'No bounds checking'),
            ('CROP', 'Crop', 'Crop islands to fit'),
            ('CLAMP', 'Clamp', 'Clamp islands to bounds')
        )
    )
    round_mode: EnumProperty(
        name='Round Mode',
        description="How to round movement values",
        default='OFF',
        items=(
            ('OFF', 'Off', 'No rounding'),
            ('INT', 'Int', 'Round to integer'),
            ('STEPS', 'Steps', 'Round to step increments')
        )
    )
    steps: FloatVectorProperty(
        name='Steps',
        description="Step size for rounding movement",
        default=(0, 0),
        min=0,
        max=10,
        soft_min=0,
        soft_max=1,
        size=2,
        subtype='XYZ'
    )
    strength: FloatVectorProperty(
        name='Strength',
        description="Movement range for randomization",
        default=(1, 1),
        min=-10,
        max=10,
        soft_min=0,
        soft_max=1,
        size=2,
        subtype='XYZ'
    )
    flip_strength: FloatVectorProperty(
        name='Flip',
        description="Probability of flipping islands",
        default=(0, 0),
        min=0,
        max=1,
        size=2,
        subtype='XYZ'
    )
    rotation: FloatProperty(
        name='Rotation Range',
        description="Maximum rotation angle",
        default=0,
        min=0,
        soft_max=math.pi * 2,
        subtype='ANGLE'
    )
    rotation_steps: FloatProperty(
        name='Rotation Steps',
        description="Snap rotation to steps",
        default=0,
        min=0,
        max=math.pi,
        subtype='ANGLE'
    )
    scale_factor: FloatProperty(
        name="Scale Factor",
        description="Amount of random scaling",
        default=0,
        min=0,
        soft_max=1,
        subtype='FACTOR'
    )
    min_scale: FloatProperty(
        name='Min Scale',
        description="Minimum scale value",
        default=0.5,
        min=0,
        max=10,
        soft_min=0.1,
        soft_max=2
    )
    max_scale: FloatProperty(
        name='Max Scale',
        description="Maximum scale value",
        default=2,
        min=0,
        max=10,
        soft_min=0.1,
        soft_max=2
    )
    bool_bounds: BoolProperty(
        name="Within Image Bounds",
        description="Keep the UV faces/islands within the 0-1 UV domain",
        default=False
    )
    rand_seed: IntProperty(
        name='Seed',
        description="Random seed for reproducible results",
        default=0
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.data.uv_layers.active

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'rand_seed')

        if not self.between:
            layout.prop(self, 'round_mode', slider=True)
            if self.round_mode == 'STEPS':
                layout.prop(self, 'steps', slider=True)
            layout.prop(self, 'strength', slider=True)
        layout.prop(self, 'flip_strength', slider=True)

        if self.bound_between != 'CROP':
            layout.prop(self, 'scale_factor', slider=True)
            if self.scale_factor != 0:
                layout.prop(self, 'min_scale', slider=True)
                layout.prop(self, 'max_scale', slider=True)

        layout.prop(self, 'rotation', slider=True)
        if self.rotation != 0:
            layout.prop(self, 'rotation_steps', slider=True)

        if not self.between:
            layout.prop(self, 'bool_bounds')

        layout = self.layout.row()
        if self.between:
            layout.prop(self, 'bound_between', expand=True)
        layout = self.layout.row()
        layout.prop(self, 'between', toggle=1)

    def invoke(self, context, event):
        if event.value == 'PRESS':
            return self.execute(context)
        self.between = event.alt
        self.bound_between = 'CROP' if event.ctrl else 'OFF'
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)

        # Get the active UV layer
        if not bm.loops.layers.uv:
            self.report({'WARNING'}, 'No UV layer found')
            return {'CANCELLED'}

        uv_layer = bm.loops.layers.uv.active

        # Get selected islands
        islands = self.get_islands(bm, uv_layer)

        if not islands:
            self.report({'WARNING'}, 'No islands selected')
            return {'CANCELLED'}

        # Initialize random seed
        random.seed(self.rand_seed)

        if self.between:
            self.randomize_between(islands, uv_layer)
        else:
            self.randomize(islands, uv_layer)

        bmesh.update_edit_mesh(me)
        return {'FINISHED'}

    def get_islands(self, bm, uv_layer):
        """Get UV islands from selected faces"""
        islands = []
        processed_faces = set()

        uv_layer_data = bm.loops.layers.uv.active

        for face in bm.faces:
            if not face.select or face in processed_faces:
                continue

            # Find all connected faces
            island = self.get_connected_faces(face, processed_faces, uv_layer_data)
            if island:
                islands.append(island)

        return islands

    def get_connected_faces(self, start_face, processed_faces, uv_layer):
        """Get all UV-connected faces from a starting face"""
        island = []
        to_process = [start_face]

        while to_process:
            face = to_process.pop()
            if face in processed_faces:
                continue

            processed_faces.add(face)
            island.append(face)

            # Check neighbors through UV connectivity
            for loop in face.loops:
                uv = loop[uv_layer].uv
                for edge in loop.vert.link_edges:
                    for linked_face in edge.link_faces:
                        if linked_face.select and linked_face not in processed_faces:
                            # Check if UVs are connected
                            for linked_loop in linked_face.loops:
                                linked_uv = linked_loop[uv_layer].uv
                                if (linked_uv - uv).length < 0.0001:
                                    to_process.append(linked_face)
                                    break

        return island

    def get_island_bounds(self, island, uv_layer):
        """Get bounding box of an island"""
        min_uv = Vector((float('inf'), float('inf')))
        max_uv = Vector((float('-inf'), float('-inf')))

        for face in island:
            for loop in face.loops:
                uv = loop[uv_layer].uv
                min_uv.x = min(min_uv.x, uv.x)
                min_uv.y = min(min_uv.y, uv.y)
                max_uv.x = max(max_uv.x, uv.x)
                max_uv.y = max(max_uv.y, uv.y)

        center = (min_uv + max_uv) * 0.5
        size = max_uv - min_uv

        return {'min': min_uv, 'max': max_uv, 'center': center, 'size': size}

    def transform_island(self, island, uv_layer, offset=None, scale=None, rotation=None, pivot=None):
        """Apply transformations to an island"""
        if pivot is None:
            bounds = self.get_island_bounds(island, uv_layer)
            pivot = bounds['center']

        for face in island:
            for loop in face.loops:
                uv = loop[uv_layer].uv

                # Move to origin
                uv -= pivot

                # Apply scale
                if scale is not None:
                    uv.x *= scale.x
                    uv.y *= scale.y

                # Apply rotation
                if rotation is not None:
                    cos_a = math.cos(rotation)
                    sin_a = math.sin(rotation)
                    x = uv.x * cos_a - uv.y * sin_a
                    y = uv.x * sin_a + uv.y * cos_a
                    uv.x = x
                    uv.y = y

                # Move back and apply offset
                uv += pivot
                if offset is not None:
                    uv += offset

    def randomize(self, islands, uv_layer):
        """Randomize islands individually"""
        for i, island in enumerate(islands):
            seed = self.rand_seed + i

            bounds = self.get_island_bounds(island, uv_layer)
            pivot = bounds['center']

            # Random flip
            flip_scale = Vector((1, 1))
            if self.flip_strength[0] > 0:
                random.seed(seed + 1000)
                if random.random() < self.flip_strength[0]:
                    flip_scale.x = -1
            if self.flip_strength[1] > 0:
                random.seed(seed + 1001)
                if random.random() < self.flip_strength[1]:
                    flip_scale.y = -1

            # Random rotation
            rot_angle = 0
            if self.rotation > 0:
                random.seed(seed + 2000)
                rot_angle = random.uniform(-self.rotation, self.rotation)
                if self.rotation_steps > 0:
                    rot_angle = round(rot_angle / self.rotation_steps) * self.rotation_steps

            # Random scale
            scale = Vector((1, 1))
            if self.scale_factor > 0:
                random.seed(seed + 3000)
                scale_value = random.uniform(self.min_scale, self.max_scale)
                scale_value = 1.0 + (scale_value - 1.0) * self.scale_factor
                scale = Vector((scale_value, scale_value))

            # Apply scale and rotation
            total_scale = Vector((flip_scale.x * scale.x, flip_scale.y * scale.y))
            self.transform_island(island, uv_layer, scale=total_scale, rotation=rot_angle, pivot=pivot)

            # Random movement
            if not self.between and (self.strength[0] > 0 or self.strength[1] > 0):
                random.seed(seed + 4000)
                move_x = (random.random() - 0.5) * 2 * self.strength[0]
                random.seed(seed + 4001)
                move_y = (random.random() - 0.5) * 2 * self.strength[1]

                move = Vector((move_x, move_y))

                if self.round_mode == 'INT':
                    move.x = round(move.x)
                    move.y = round(move.y)
                elif self.round_mode == 'STEPS':
                    if self.steps[0] > 0:
                        move.x = round(move.x / self.steps[0]) * self.steps[0]
                    if self.steps[1] > 0:
                        move.y = round(move.y / self.steps[1]) * self.steps[1]

                # Apply movement with bounds check
                if self.bool_bounds:
                    new_bounds = self.get_island_bounds(island, uv_layer)
                    # Keep within 0-1 bounds
                    if new_bounds['min'].x + move.x < 0:
                        move.x = -new_bounds['min'].x
                    if new_bounds['min'].y + move.y < 0:
                        move.y = -new_bounds['min'].y
                    if new_bounds['max'].x + move.x > 1:
                        move.x = 1 - new_bounds['max'].x
                    if new_bounds['max'].y + move.y > 1:
                        move.y = 1 - new_bounds['max'].y

                self.transform_island(island, uv_layer, offset=move, pivot=Vector((0, 0)))

    def randomize_between(self, islands, uv_layer):
        """Shuffle island positions"""
        # Get all island centers
        positions = []
        for island in islands:
            bounds = self.get_island_bounds(island, uv_layer)
            positions.append(bounds['center'].copy())

        # Shuffle positions
        random.seed(self.rand_seed)
        random.shuffle(positions)

        # Move each island to a shuffled position
        for i, island in enumerate(islands):
            bounds = self.get_island_bounds(island, uv_layer)
            old_center = bounds['center']
            new_center = positions[i]
            move = new_center - old_center

            self.transform_island(island, uv_layer, offset=move, pivot=Vector((0, 0)))


classes = [
    UVV_OT_Random,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
