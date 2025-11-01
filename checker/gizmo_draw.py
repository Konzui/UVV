""" UVV Texel Density Gizmo - Complete Zen UV 1:1 Implementation """

import bpy
import gpu
import bmesh
import blf
import functools
import numpy as np
import uuid
from collections import defaultdict
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix

# Zen UV 1:1 Pattern - Global storage and literals
UVV_3D_GIZMOS = {}
UVV_UV_GIZMOS = {}

LITERAL_UVV_UPDATE = 'uvv_update'
LITERAL_UVV_GENERAL_UPDATE = 'uvv_general_update'
LITERAL_UVV_DELAYED_UV_GIZMOS = 'uvv_delayed_uv_gizmos'
LITERAL_UVV_TD_SCOPE = 'uvv_td_scope'


def is_modal_procedure(context):
    """Check if we're in a modal operation - Zen UV pattern"""
    return context.mode == 'EDIT_MESH' and hasattr(context, 'active_operator') and context.active_operator is not None


def uvv_delayed_overlay_build_uv():
    """Timer callback for delayed gizmo builds - Zen UV pattern"""
    try:
        t_delayed_gizmos = bpy.app.driver_namespace.get(LITERAL_UVV_DELAYED_UV_GIZMOS, set())

        if t_delayed_gizmos:
            context = bpy.context

            for gizmo in t_delayed_gizmos:
                if hasattr(gizmo, 'build'):
                    gizmo.build(context)

            bpy.app.driver_namespace[LITERAL_UVV_DELAYED_UV_GIZMOS] = set()

            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        area.tag_redraw()
    except Exception as e:
        print(f"UVV: Error in delayed build: {e}")

    return None


def uvv_depsgraph_delayed():
    """
    Delayed callback after depsgraph update - triggers area redraw
    This is THE KEY to automatic updates after UV operations!
    """
    try:
        ctx = bpy.context
        # Trigger redraw of UV editor areas
        for window in ctx.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()
    except Exception as e:
        print(f"UVV: Error in depsgraph delayed: {e}")

    return None  # Don't repeat timer


def get_unique_mesh_object_map_with_active(context):
    """Get unique mesh objects - Zen UV pattern"""
    mesh_obj_map = {}

    for obj in context.selected_objects:
        if obj.type == 'MESH' and obj.mode == 'EDIT':
            mesh_obj_map[obj.data] = obj

    if context.active_object and context.active_object.type == 'MESH':
        mesh_obj_map[context.active_object.data] = context.active_object

    return mesh_obj_map


@bpy.app.handlers.persistent
def uvv_depsgraph_ui_update(_):
    """
    Track mesh/UV changes for automatic gizmo updates - Zen UV 1:1 pattern
    This is the KEY to automatic updates without manual toggling!
    """
    ctx = bpy.context

    # Skip during render/bake
    if hasattr(bpy.app, 'is_job_running'):
        for s_job in {'RENDER', 'RENDER_PREVIEW', 'OBJECT_BAKE', 'COMPOSITE', 'SHADER_COMPILATION'}:
            if bpy.app.is_job_running(s_job):
                return

    depsgraph = ctx.evaluated_depsgraph_get()

    t_updates = None
    b_update_general = False

    for update in depsgraph.updates:
        if not isinstance(update.id, bpy.types.Mesh):
            continue

        b_geom = update.is_updated_geometry
        b_shade = update.is_updated_shading

        if b_geom or b_shade:
            if t_updates is None:
                t_updates = bpy.app.driver_namespace.get(LITERAL_UVV_UPDATE, {})

            s_uuid = str(uuid.uuid4())

            if not b_update_general:
                bpy.app.driver_namespace[LITERAL_UVV_GENERAL_UPDATE] = s_uuid
                b_update_general = True

            p_data = t_updates.get(update.id.original, ['', ''])

            if b_geom:
                p_data[0] = s_uuid
            if b_shade:
                p_data[1] = s_uuid

            t_updates[update.id.original] = p_data

    if t_updates is not None:
        bpy.app.driver_namespace[LITERAL_UVV_UPDATE] = t_updates

        # Register delayed timer to trigger redraw (ZEN UV CRITICAL PATTERN!)
        if bpy.app.timers.is_registered(uvv_depsgraph_delayed):
            bpy.app.timers.unregister(uvv_depsgraph_delayed)

        bpy.app.timers.register(uvv_depsgraph_delayed, first_interval=0.1)


class DrawCustomShape:
    """Wrapper for batch + shader - Zen UV pattern"""
    __slots__ = ('batch', 'shader', 'obj', 'color', 'mode')

    def __init__(self, batch, shader, obj, color_func, mode=0):
        self.batch = batch
        self.shader = shader
        self.obj = obj
        self.color = color_func
        self.mode = mode

    def get_shape(self):
        return self.batch, self.shader


# ============================================================================
# UV EDITOR GIZMO - COMPLETE ZEN UV 1:1 IMPLEMENTATION
# ============================================================================

class UVV_UVGizmoTexelDensity(bpy.types.Gizmo):
    """Gizmo for drawing texel density colored UV islands - Zen UV 1:1 architecture"""
    bl_idname = "UVV_GT_uv_texel_density"

    __slots__ = (
        "custom_shapes",
        "mesh_data",
        "uv_sync",
        "last_mode",
        "mark_build",
        "custom_data"
    )

    def setup(self):
        """Initialize gizmo - Zen UV pattern"""
        if not hasattr(self, "mesh_data"):
            self.custom_shapes = []
            self.mesh_data = {}
            self.uv_sync = False
            self.last_mode = 'TEXEL_DENSITY'
            self.mark_build = -1
            self.custom_data = {}

    def _delayed_build(self):
        """Schedule delayed build - Zen UV pattern"""
        if bpy.app.timers.is_registered(uvv_delayed_overlay_build_uv):
            bpy.app.timers.unregister(uvv_delayed_overlay_build_uv)

        t_delayed_gizmos = bpy.app.driver_namespace.get(LITERAL_UVV_DELAYED_UV_GIZMOS, set())
        t_delayed_gizmos.add(self)
        bpy.app.driver_namespace[LITERAL_UVV_DELAYED_UV_GIZMOS] = t_delayed_gizmos

        bpy.app.timers.register(uvv_delayed_overlay_build_uv, first_interval=0.05)

    def check_valid_data(self, context):
        """Check if current data is still valid - Zen UV pattern with depsgraph tracking"""
        b_is_uv_sync = context.scene.tool_settings.use_uv_select_sync
        if self.uv_sync != b_is_uv_sync:
            return False

        if self.last_mode != 'TEXEL_DENSITY':
            return False

        # Use depsgraph updates (Zen UV pattern) instead of geometry hash
        t_updates = bpy.app.driver_namespace.get(LITERAL_UVV_UPDATE, {})

        check_data = {}
        for me in get_unique_mesh_object_map_with_active(context).keys():
            check_data[me] = t_updates.get(me, ['', ''])

        # Check if geometry changed
        if not b_is_uv_sync:
            return self.mesh_data == check_data

        # In UV sync mode, check geometry only
        if self.mesh_data.keys() != check_data.keys():
            return False

        for key in self.mesh_data.keys():
            if self.mesh_data[key][0] != check_data[key][0]:
                return False

        return True

    def build(self, context):
        """
        Build texel density visualization - COMPLETE ZEN UV 1:1 PATTERN
        ISLAND-BASED calculation with caching - NOT per-face!
        """
        try:
            from .td_utils import TdUtils, TdContext, TdBmeshManager
            from .td_display_utils import TdColorProcessor

            # Reset build flag
            self.mark_build = 0

            # Clear old data
            self.custom_shapes.clear()
            self.mesh_data = {}
            self.custom_data = {}

            # Store current state
            self.uv_sync = context.scene.tool_settings.use_uv_select_sync
            self.last_mode = 'TEXEL_DENSITY'

            # Get settings
            if not hasattr(context.scene, 'uvv_settings'):
                return

            settings = context.scene.uvv_settings

            # Get mesh object map
            mesh_obj_map = get_unique_mesh_object_map_with_active(context)
            if not mesh_obj_map:
                return

            p_objects = list(mesh_obj_map.values())
            p_geometry_keys = []

            # Track geometry updates (Zen UV pattern)
            t_updates = bpy.app.driver_namespace.get(LITERAL_UVV_UPDATE, {})
            for me, p_obj in mesh_obj_map.items():
                update_data = t_updates.get(me, ['', ''])
                self.mesh_data[me] = update_data.copy()
                p_geometry_keys.append(update_data[0])

            # Create TD context
            td_inputs = TdContext(context)

            # Get TD scope with caching (Zen UV pattern)
            td_scope = None
            p_stored_td_scope = bpy.app.driver_namespace.get(LITERAL_UVV_TD_SCOPE, None)

            if p_stored_td_scope:
                if p_geometry_keys and p_geometry_keys == p_stored_td_scope[0]:
                    td_scope = p_stored_td_scope[1]

            # Calculate ISLAND-BASED TD if cache miss
            if not td_scope:
                td_scope = TdUtils.get_td_data_with_precision(context, p_objects, td_inputs, False)
                bpy.app.driver_namespace[LITERAL_UVV_TD_SCOPE] = (p_geometry_keys, td_scope)

            # Create properties object for TdColorProcessor
            class TdDrawProps:
                display_method = settings.td_display_method
                color_scheme_name = settings.td_color_scheme
                is_range_manual = settings.td_range_manual
                use_presets_only = False
                values_filter = 10.0

            # Process colors (Zen UV pattern)
            CP = TdColorProcessor(context, td_scope, TdDrawProps())
            CP.calc_output_range(context, td_inputs, settings.td_display_method)

            # Store texel data map for gradient display
            self.custom_data['texel_data_map'] = {}

            # Create GPU batches grouped by color (Zen UV pattern)
            alpha = settings.td_gradient_alpha

            for p_obj_name, p_islands in td_scope.get_islands_by_objects().items():
                if len(p_islands) == 0:
                    continue

                p_obj = context.scene.objects[p_obj_name]
                bm = TdBmeshManager.get_bm(td_inputs, p_obj)
                bm.faces.ensure_lookup_table()

                uv_layer = bm.loops.layers.uv.active
                if not uv_layer:
                    continue

                p_loops = bm.calc_loop_triangles()

                # Create color map (island index -> color)
                t_color_map = {
                    idx: [(round(island.color[0], 2), round(island.color[1], 2), round(island.color[2], 2)), island.td]
                    for island in p_islands for idx in island.indices
                }
                self.custom_data['texel_data_map'][p_obj_name] = t_color_map

                # Group triangles by color
                face_tri_indices = defaultdict(list)
                for looptris in p_loops:
                    p_face = looptris[0].face
                    if not p_face.hide and (self.uv_sync or p_face.select):
                        p_color, _ = t_color_map.get(p_face.index, [(0, 0, 0), 0])
                        for loop in looptris:
                            face_tri_indices[p_color].append(loop[uv_layer].uv.to_tuple(5))

                # Create batches (Zen UV pattern with numpy deduplication)
                if face_tri_indices:
                    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

                    for k, v in face_tri_indices.items():
                        if len(v) > 0:
                            # Numpy deduplication (CRITICAL for performance)
                            uv_verts, uv_indices = np.unique(v, return_inverse=True, axis=0)
                            uv_coords = uv_verts.tolist()
                            uv_indices = uv_indices.astype(np.int32)

                            batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                            batch.program_set(shader)

                            def get_color(p_color=k, p_alpha=alpha):
                                return (*p_color, p_alpha)

                            self.custom_shapes.append(
                                DrawCustomShape(batch, shader, p_obj, functools.partial(get_color, k, alpha)))

        except Exception as e:
            import traceback
            print(f"UVV: Error building UV gizmo: {e}")
            traceback.print_exc()
            self.mark_build = -1

    def draw_gradient(self, context):
        """Draw gradient bar - Zen UV pattern"""
        mesh_data = self.mesh_data
        if not mesh_data:
            return

        # Get cached TD scope
        p_stored_td_scope = bpy.app.driver_namespace.get(LITERAL_UVV_TD_SCOPE, None)
        if not p_stored_td_scope:
            return

        td_scope = p_stored_td_scope[1]
        if td_scope.is_empty():
            return

        min_density = td_scope.get_min_td_value()
        max_density = td_scope.get_max_td_value()

        if min_density == 0 and max_density == 0:
            return

        settings = context.scene.uvv_settings

        # Calculate bar position
        region = context.region
        bar_width = settings.td_gradient_width
        bar_height = settings.td_gradient_height
        x_pos = (region.width - bar_width) / 2
        y_pos = 40

        # Create gradient
        vertices = []
        colors = []
        num_segments = 100

        from .td_display_utils import TdColorManager

        # Get color scheme
        if settings.td_color_scheme == 'FULL_SPEC':
            color_scheme = TdColorManager.full
        elif settings.td_color_scheme == 'REVERSED_SPEC':
            color_scheme = list(reversed(TdColorManager.full))
        elif settings.td_color_scheme == 'MONO':
            color_scheme = TdColorManager.mono
        elif settings.td_color_scheme == 'USER_THREE':
            color_scheme = TdColorManager.get_user_three(context)
        elif settings.td_color_scheme == 'USER_LINEAR':
            color_scheme = TdColorManager.get_user_linear(context)
        else:
            color_scheme = TdColorManager.full

        for i in range(num_segments + 1):
            normalized = i / num_segments
            x = x_pos + normalized * bar_width

            vertices.append((x, y_pos))
            vertices.append((x, y_pos + bar_height))

            # Map to color scheme
            density = min_density + (1.0 - normalized) * (max_density - min_density)

            # Calculate color from scheme
            if max_density > min_density:
                norm_val = (density - min_density) / (max_density - min_density)
            else:
                norm_val = 0.5

            position = norm_val * (len(color_scheme) - 1)
            index = int(position)
            alpha_blend = position - index

            if index >= len(color_scheme) - 1:
                color = (*color_scheme[-1], settings.td_gradient_alpha)
            else:
                c1, c2 = color_scheme[index], color_scheme[index + 1]
                r = (1 - alpha_blend) * c1[0] + alpha_blend * c2[0]
                g = (1 - alpha_blend) * c1[1] + alpha_blend * c2[1]
                b = (1 - alpha_blend) * c1[2] + alpha_blend * c2[2]
                color = (r, g, b, settings.td_gradient_alpha)

            colors.extend([color, color])

        # Draw gradient
        shader = gpu.shader.from_builtin('SMOOTH_COLOR')
        batch = batch_for_shader(shader, 'TRI_STRIP', {"pos": vertices, "color": colors})
        shader.bind()
        batch.draw(shader)

        # Draw labels
        font_id = 0
        blf.size(font_id, 11)
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)

        min_text = f"{min_density:.1f}"
        text_width, text_height = blf.dimensions(font_id, min_text)
        blf.position(font_id, x_pos + bar_width + 5, y_pos + (bar_height - text_height) / 2, 0)
        blf.draw(font_id, min_text)

        max_text = f"{max_density:.1f}"
        text_width, text_height = blf.dimensions(font_id, max_text)
        blf.position(font_id, x_pos - text_width - 5, y_pos + (bar_height - text_height) / 2, 0)
        blf.draw(font_id, max_text)

    def _do_draw(self, context):
        """Internal draw method - Zen UV pattern"""
        if not hasattr(context.scene, 'uvv_settings'):
            return

        settings = context.scene.uvv_settings

        # Draw gradient first
        if settings.texel_density_display_mode in {'GRADIENT', 'ALL'}:
            self.draw_gradient(context)

        if self.mesh_data is None:
            return

        # Auto-rebuild logic (Zen UV pattern)
        wm = context.window_manager
        if self.mark_build == -1:
            if not is_modal_procedure(context):
                self.build(context)
            else:
                self._delayed_build()
        elif not self.check_valid_data(context):
            if not is_modal_procedure(context):
                self._delayed_build()
            return

        if not self.custom_shapes:
            return

        # Only draw viewport overlay if mode allows
        if settings.texel_density_display_mode not in {'VIEWPORT', 'ALL'}:
            return

        # Get UV to screen transformation matrix (Zen UV pattern)
        viewport_info = gpu.state.viewport_get()
        width = viewport_info[2]
        height = viewport_info[3]
        region = context.region

        uv_to_view = region.view2d.view_to_region

        origin_x, origin_y = uv_to_view(0, 0, clip=False)
        top_x, top_y = uv_to_view(1.0, 1.0, clip=False)
        axis_x = top_x - origin_x
        axis_y = top_y - origin_y

        matrix = Matrix((
            [axis_x / width * 2, 0, 0, 2.0 * -((width - origin_x - 0.5 * width)) / width],
            [0, axis_y / height * 2, 0, 2.0 * -((height - origin_y - 0.5 * height)) / height],
            [0, 0, 1.0, 0],
            [0, 0, 0, 1.0]
        ))
        identity = Matrix.Identity(4)

        gpu.state.blend_set('ALPHA')

        # Draw all custom shapes (Zen UV pattern)
        with gpu.matrix.push_pop():
            gpu.matrix.load_matrix(matrix)

            with gpu.matrix.push_pop_projection():
                gpu.matrix.load_projection_matrix(identity)

                draw_shape: DrawCustomShape
                for draw_shape in self.custom_shapes:
                    batch, shader = draw_shape.get_shape()

                    shader.bind()
                    if draw_shape.color is not None:
                        shader.uniform_float("color", draw_shape.color())
                    batch.draw()

        gpu.state.blend_set('NONE')

    def draw(self, context):
        """Draw texel density colored UV islands and gradient bar"""
        self._do_draw(context)

    def draw_select(self, context, select_id):
        pass

    def test_select(self, context, location):
        return -1


class UVV_UVGizmoGroup(bpy.types.GizmoGroup):
    """Gizmo group for UV editor texel density visualization"""
    bl_idname = "UVV_GG_uv_texel_density"
    bl_label = "UVV UV Texel Density Visualization"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'EDIT_MESH':
            return False
        if not hasattr(context.scene, 'uvv_settings'):
            return False
        settings = context.scene.uvv_settings
        return settings.uvv_texel_overlay_active

    def setup(self, context):
        self.gizmo = self.gizmos.new(UVV_UVGizmoTexelDensity.bl_idname)
        self.gizmo.use_draw_modal = True
        self.gizmo.use_draw_value = False
        self.gizmo.use_draw_hover = False

        UVV_UV_GIZMOS[context.area.as_pointer()] = self.gizmo

    def refresh(self, context):
        pass


# ============================================================================
# 3D VIEWPORT GIZMO (Disabled)
# ============================================================================

class UVV_GizmoTexelDensity(bpy.types.Gizmo):
    bl_idname = "UVV_GT_texel_density"

    def setup(self):
        pass

    def draw(self, context):
        pass

    def draw_select(self, context, select_id):
        pass

    def test_select(self, context, location):
        return -1


class UVV_GizmoGroup(bpy.types.GizmoGroup):
    bl_idname = "UVV_GG_texel_density"
    bl_label = "UVV Texel Density Visualization"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context):
        return False

    def setup(self, context):
        self.gizmo = self.gizmos.new(UVV_GizmoTexelDensity.bl_idname)

    def refresh(self, context):
        pass


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def mark_all_gizmos_for_rebuild():
    """Mark all UV gizmos for rebuild"""
    for gizmo in UVV_UV_GIZMOS.values():
        if hasattr(gizmo, 'mark_build'):
            gizmo.mark_build = 1


def update_all_gizmos(context):
    """Mark all gizmos for rebuild - Zen UV pattern"""
    for gizmo in UVV_UV_GIZMOS.values():
        if hasattr(gizmo, 'mark_build'):
            gizmo.mark_build = -1
            gizmo.mesh_data = {}

    # Clear TD cache to force recalculation
    if LITERAL_UVV_TD_SCOPE in bpy.app.driver_namespace:
        del bpy.app.driver_namespace[LITERAL_UVV_TD_SCOPE]

    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.tag_redraw()


# ============================================================================
# REGISTRATION
# ============================================================================

classes = [
    UVV_GizmoTexelDensity,
    UVV_GizmoGroup,
    UVV_UVGizmoTexelDensity,
    UVV_UVGizmoGroup,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    # Unregister timers if registered
    if bpy.app.timers.is_registered(uvv_delayed_overlay_build_uv):
        bpy.app.timers.unregister(uvv_delayed_overlay_build_uv)
    if bpy.app.timers.is_registered(uvv_depsgraph_delayed):
        bpy.app.timers.unregister(uvv_depsgraph_delayed)

    # Clear gizmo dictionaries
    UVV_3D_GIZMOS.clear()
    UVV_UV_GIZMOS.clear()

    # Clear driver namespace
    if LITERAL_UVV_DELAYED_UV_GIZMOS in bpy.app.driver_namespace:
        del bpy.app.driver_namespace[LITERAL_UVV_DELAYED_UV_GIZMOS]
    if LITERAL_UVV_TD_SCOPE in bpy.app.driver_namespace:
        del bpy.app.driver_namespace[LITERAL_UVV_TD_SCOPE]
    if LITERAL_UVV_UPDATE in bpy.app.driver_namespace:
        del bpy.app.driver_namespace[LITERAL_UVV_UPDATE]
    if LITERAL_UVV_GENERAL_UPDATE in bpy.app.driver_namespace:
        del bpy.app.driver_namespace[LITERAL_UVV_GENERAL_UPDATE]

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
