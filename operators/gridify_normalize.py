# Copied from Mio3 UV addon - gridify and normalize operators
import bpy
import math
from bpy.props import BoolProperty, EnumProperty
from bpy.types import Operator
from mathutils import Vector
from ..utils.uv_classes import UVIslandManager


class UVV_OT_gridify(Operator):
    bl_idname = "uv.uvv_gridify"
    bl_label = "Gridify"
    bl_description = "Align UVs of a quadrangle in a grid"
    bl_options = {"REGISTER", "UNDO"}

    normalize: BoolProperty(name="Normalize", default=False)
    keep_aspect: BoolProperty(name="Keep Aspect Ratio", default=False)
    even: BoolProperty(name="Even", default=False)
    mode: EnumProperty(
        name="Method",
        items=[
            ("LENGTH_AVERAGE", "Standard", ""),
            ("EVEN", "Even", ""),
        ],
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

    @staticmethod
    def get_selected_objects(context):
        return [obj for obj in context.objects_in_mode if obj.type == "MESH"]

    def execute(self, context):
        objects = self.get_selected_objects(context)
        use_uv_select_sync = context.tool_settings.use_uv_select_sync

        if use_uv_select_sync:
            context.tool_settings.use_uv_select_sync = False
            island_manager = UVIslandManager(objects, mesh_link_uv=True)
        else:
            island_manager = UVIslandManager(objects, extend=False)

        for island in island_manager.islands:
            island.store_selection()
            island.deselect_all_uv()

        for obj in objects:
            islands = island_manager.islands_by_object[obj]
            for island in islands:
                island.restore_selection()
                bm = island.bm
                uv_layer = island.uv_layer

                quad = self.get_base_face(uv_layer, island.faces)
                if not quad:
                    island.deselect_all_uv()
                    continue
                bm.faces.active = quad

                self.align_square(uv_layer, bm.faces.active)

                for face in island.faces:
                    if all(loop[uv_layer].select for loop in face.loops):
                        for loop in face.loops:
                            loop[uv_layer].pin_uv = True
                    else:
                        for loop in face.loops:
                            loop[uv_layer].pin_uv = False

                try:
                    bpy.ops.uv.follow_active_quads(mode=self.mode)
                except:
                    pass

        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0)
        bpy.ops.uv.pin(clear=True)

        if use_uv_select_sync:
            island_manager.restore_vertex_selection()
            context.tool_settings.use_uv_select_sync = True

        island_manager.update_uvmeshes()

        if self.normalize:
            bpy.ops.uv.uvv_normalize(keep_aspect=self.keep_aspect)

        return {"FINISHED"}

    def get_base_face(self, uv_layer, selected_faces):
        best_face = None
        best_score = float("inf")

        total_area = sum(face.calc_area() for face in selected_faces)
        avg_area = total_area / len(selected_faces)

        for face in selected_faces:
            if len(face.loops) == 4 and all(loop[uv_layer].select for loop in face.loops):
                max_angle_diff = 0
                for i in range(4):
                    v1 = face.loops[i][uv_layer].uv - face.loops[(i - 1) % 4][uv_layer].uv
                    v2 = face.loops[(i + 1) % 4][uv_layer].uv - face.loops[i][uv_layer].uv
                    angle_diff = abs(math.degrees(math.atan2(v1.x * v2.y - v1.y * v2.x, v1.dot(v2))) - 90)
                    if angle_diff > max_angle_diff:
                        max_angle_diff = angle_diff

                area_diff = abs(face.calc_area() - avg_area)

                angle_weight = 0.5
                area_weight = 1.0
                score = angle_weight * max_angle_diff + area_weight * (area_diff / avg_area)

                if score < best_score:
                    best_score = score
                    best_face = face

        return best_face

    def align_square(self, uv_layer, active_face):
        uv_coords = [loop[uv_layer].uv for loop in active_face.loops]
        min_uv = Vector((min(uv.x for uv in uv_coords), min(uv.y for uv in uv_coords)))
        max_uv = Vector((max(uv.x for uv in uv_coords), max(uv.y for uv in uv_coords)))
        center_uv = (min_uv + max_uv) / 2

        edge_uv = uv_coords[1] - uv_coords[0]
        current_angle = math.atan2(edge_uv.y, edge_uv.x)
        rotation_angle = (round(math.degrees(current_angle) / 90) * 90 - math.degrees(current_angle) + 45) % 90 - 45
        rotation_rad = math.radians(rotation_angle)
        sin_rot, cos_rot = math.sin(rotation_rad), math.cos(rotation_rad)

        rotated_uvs = []
        for uv in uv_coords:
            uv_local = uv - center_uv
            uv_rotated = (
                Vector(
                    (
                        uv_local.x * cos_rot - uv_local.y * sin_rot,
                        uv_local.x * sin_rot + uv_local.y * cos_rot,
                    )
                )
                + center_uv
            )
            rotated_uvs.append(uv_rotated)

        min_x = min(uv.x for uv in rotated_uvs)
        max_x = max(uv.x for uv in rotated_uvs)
        min_y = min(uv.y for uv in rotated_uvs)
        max_y = max(uv.y for uv in rotated_uvs)

        new_uvs = [
            Vector((min_x, min_y)),
            Vector((max_x, min_y)),
            Vector((max_x, max_y)),
            Vector((min_x, max_y)),
        ]

        center = Vector(((min_x + max_x) / 2, (min_y + max_y) / 2))
        sorted_pairs = sorted(
            zip(rotated_uvs, active_face.loops),
            key=lambda pair: ((pair[0] - center).angle_signed(Vector((1, 0))) if (pair[0] - center).length > 0 else 0),
        )

        for (_, loop), new_uv in zip(sorted_pairs, new_uvs):
            loop[uv_layer].uv = new_uv

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        layout.use_property_split = True
        row = layout.row()
        row.prop(self, "mode", expand=True)
        layout.prop(self, "normalize")

        row = layout.row()
        row.enabled = self.normalize
        row.prop(self, "keep_aspect")


class UVV_OT_normalize(Operator):
    bl_idname = "uv.uvv_normalize"
    bl_label = "Normalize"
    bl_description = "Normalize UVs\nHold SHIFT to normalize each island individually\nHold CTRL to normalize to 0-1 UV space when trim is selected"
    bl_options = {"REGISTER", "UNDO"}

    keep_aspect: BoolProperty(name="Keep Aspect Ratio", default=False)
    individual: BoolProperty(name="Individual", default=False)
    axis: EnumProperty(
        name="Axis",
        default="XY",
        items=[
            ("XY", "Both", "Scale both X and Y axes"),
            ("X", "X", "Scale only X axis"),
            ("Y", "Y", "Scale only Y axis"),
        ]
    )
    constrain_to_trim: BoolProperty(
        name="Constrain to Trim",
        description="Normalize within active trim bounds instead of full 0-1 UV space",
        default=False,
        options={'SKIP_SAVE'}
    )
    override_trim: BoolProperty(
        name="Override Trim",
        description="Override trim constraint and use 0-1 UV space",
        default=False,
        options={'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

    def invoke(self, context, event):
        """Handle trim constraint logic based on CTRL modifier

        - Normal click with trim selected + overlays enabled: normalize to trim bounds
        - CTRL+click: override and normalize to 0-1 UV space
        - Shift+click: normalize each island individually
        """
        # Check if Shift is held to enable individual island normalization
        self.individual = event.shift
        
        # Check if trim overlays are enabled and we have an active trim
        settings = context.scene.uvv_settings
        has_active_trim = False

        if settings.show_trim_overlays:
            from ..utils import trimsheet_utils
            material = trimsheet_utils.get_active_material(context)
            if material:
                active_trim = trimsheet_utils.get_active_trim(context)
                if active_trim and active_trim.enabled:
                    has_active_trim = True

        # Inverted logic:
        # - If we have an active trim and CTRL is NOT held: use trim constraint
        # - If CTRL is held: override trim constraint (force 0-1 UV space)
        if has_active_trim and not event.ctrl:
            self.constrain_to_trim = True
            self.override_trim = False
        elif event.ctrl:
            self.constrain_to_trim = False
            self.override_trim = True

        return self.execute(context)

    @staticmethod
    def get_selected_objects(context):
        return [obj for obj in context.objects_in_mode if obj.type == "MESH"]

    def execute(self, context):
        objects = self.get_selected_objects(context)
        use_uv_select_sync = context.tool_settings.use_uv_select_sync

        # Handle UV sync mode like univ addon
        if use_uv_select_sync:
            # Temporarily disable UV sync
            context.tool_settings.use_uv_select_sync = False
            island_manager = UVIslandManager(objects, mesh_link_uv=True)
        else:
            island_manager = UVIslandManager(objects, extend=False)

        if self.individual:
            for island in island_manager.islands:
                self.normalize_island(context, island)
        else:
            self.normalize_all_islands(context, island_manager.islands)

        island_manager.update_uvmeshes()

        # Restore UV sync state if it was enabled
        if use_uv_select_sync:
            context.tool_settings.use_uv_select_sync = True

        # User feedback
        if self.constrain_to_trim:
            from ..utils import trimsheet_utils
            trim = trimsheet_utils.get_active_trim(context)
            if trim:
                self.report({'INFO'}, f"Normalized to trim '{trim.name}'")
        elif self.override_trim:
            self.report({'INFO'}, "Normalized to 0-1 UV space (trim override)")

        return {"FINISHED"}

    def normalize_island(self, context, island):
        current_width = island.width
        current_height = island.height

        # Determine target space (0-1 UV space or trim bounds)
        if self.constrain_to_trim:
            from ..utils import trimsheet_utils
            trim = trimsheet_utils.get_active_trim(context)
            if trim:
                target_width = trim.right - trim.left
                target_height = trim.top - trim.bottom
                target_min = Vector((trim.left, trim.bottom))
            else:
                # Fallback to normal 0-1 space if no trim found
                target_width = 1.0
                target_height = 1.0
                target_min = Vector((0, 0))
        else:
            # Normal 0-1 space
            target_width = 1.0
            target_height = 1.0
            target_min = Vector((0, 0))

        if self.keep_aspect:
            scale_factor = min(target_width, target_height) / max(current_width, current_height)
            scale_x = scale_y = scale_factor
        else:
            scale_x = target_width / current_width
            scale_y = target_height / current_height

        # Apply axis constraint
        if self.axis == "X":
            scale_y = 1.0
        elif self.axis == "Y":
            scale_x = 1.0
        # For "XY", use both scales as calculated

        self.apply_scale(context, island, scale_x, scale_y, anchor=target_min)

    def normalize_all_islands(self, context, islands):
        min_uv = Vector((float('inf'), float('inf')))
        max_uv = Vector((float('-inf'), float('-inf')))

        for island in islands:
            min_uv.x = min(min_uv.x, island.min_uv.x)
            min_uv.y = min(min_uv.y, island.min_uv.y)
            max_uv.x = max(max_uv.x, island.max_uv.x)
            max_uv.y = max(max_uv.y, island.max_uv.y)

        total_width = max_uv.x - min_uv.x
        total_height = max_uv.y - min_uv.y

        # Determine target space (0-1 UV space or trim bounds)
        if self.constrain_to_trim:
            from ..utils import trimsheet_utils
            trim = trimsheet_utils.get_active_trim(context)
            if trim:
                target_width = trim.right - trim.left
                target_height = trim.top - trim.bottom
                target_min = Vector((trim.left, trim.bottom))
            else:
                # Fallback to normal 0-1 space if no trim found
                target_width = 1.0
                target_height = 1.0
                target_min = Vector((0, 0))
        else:
            # Normal 0-1 space
            target_width = 1.0
            target_height = 1.0
            target_min = Vector((0, 0))

        if self.keep_aspect:
            scale_factor = min(target_width, target_height) / max(total_width, total_height)
            scale_x = scale_y = scale_factor
        else:
            scale_x = target_width / total_width
            scale_y = target_height / total_height

        # Apply axis constraint
        if self.axis == "X":
            scale_y = 1.0
        elif self.axis == "Y":
            scale_x = 1.0
        # For "XY", use both scales as calculated

        for island in islands:
            self.apply_scale(context, island, scale_x, scale_y, min_uv, target_min)

    def apply_scale(self, context, island, scale_x, scale_y, global_min_uv=None, anchor=None, target_min=None):
        selected_loops = []
        for face in island.faces:
            for loop in face.loops:
                selected_loops.append(loop)

        # Use provided anchor or default to (0, 0)
        if anchor is None:
            anchor = Vector((0, 0))

        # For backward compatibility, target_min defaults to anchor
        if target_min is None:
            target_min = anchor

        min_uv = global_min_uv if global_min_uv else island.min_uv
        for face in island.faces:
            for loop in face.loops:
                uv = loop[island.uv_layer]
                new_x = (uv.uv.x - min_uv.x) * scale_x
                new_y = (uv.uv.y - min_uv.y) * scale_y
                uv.uv = target_min + Vector((new_x, new_y))

        island.update_bounds()

        if not global_min_uv:
            offset = target_min - island.min_uv
            island.move(offset)


classes = [
    UVV_OT_gridify,
    UVV_OT_normalize,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
