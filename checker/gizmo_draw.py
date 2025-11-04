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


class GradientProperties:
    """
    Dynamic gradient properties - ZenUV 1:1 pattern
    Updated by display factories to control gradient visualization
    """
    r = (1, 0, 0)
    g = (0, 1, 0)
    b = (0, 0, 1)

    white = (1, 1, 1)
    black = (0, 0, 0)

    # Dynamic values set by TD display system
    range_values = [0, 50, 100, 150, 200, 250]
    range_colors = [r, g, b, white, r, g]
    range_labels = [0, 50, 100, 150, 200, 250]


import ctypes

# Forward declaration of wmWindow (ZenUV approach)
class _wmWindow(ctypes.Structure):
    pass


# Generate listbase of appropriate type. None: generic (ZenUV approach)
def _listbase(type_=None):
    ptr = ctypes.POINTER(type_)
    fields = ("first", ptr), ("last", ptr)
    return type("ListBase", (ctypes.Structure,), {'_fields_': fields})


# Define version-specific wmWindow struct fields (ZenUV approach)
if bpy.app.version < (2, 93, 0):
    _wmWindow._fields_ = (  # from DNA_windowmanager_types.h
        ("next", ctypes.POINTER(_wmWindow)),
        ("prev", ctypes.POINTER(_wmWindow)),
        ("ghostwin", ctypes.c_void_p),
        ("gpuctx", ctypes.c_void_p),
        ("parent", ctypes.POINTER(_wmWindow)),
        ("scene", ctypes.c_void_p),
        ("new_scene", ctypes.c_void_p),
        ("view_layer_name", ctypes.c_char * 64),
        ("workspace_hook", ctypes.c_void_p),
        ("global_areas", _listbase(type_=None) * 3),
        ("screen", ctypes.c_void_p),
        ("posx", ctypes.c_short),
        ("posy", ctypes.c_short),
        ("sizex", ctypes.c_short),
        ("sizey", ctypes.c_short),
        ("windowstate", ctypes.c_char),
        ("active", ctypes.c_char),
        ("_pad0", ctypes.c_char * 4),
        ("cursor", ctypes.c_short),
        ("lastcursor", ctypes.c_short),
        ("modalcursor", ctypes.c_short),
        ("grabcursor", ctypes.c_short)
    )
elif bpy.app.version < (3, 3, 0):
    _wmWindow._fields_ = (  # from DNA_windowmanager_types.h
        ("next", ctypes.POINTER(_wmWindow)),
        ("prev", ctypes.POINTER(_wmWindow)),
        ("ghostwin", ctypes.c_void_p),
        ("gpuctx", ctypes.c_void_p),
        ("parent", ctypes.POINTER(_wmWindow)),
        ("scene", ctypes.c_void_p),
        ("new_scene", ctypes.c_void_p),
        ("view_layer_name", ctypes.c_char * 64),
        ("workspace_hook", ctypes.c_void_p),
        ("global_areas", _listbase(type_=None) * 3),
        ("screen", ctypes.c_void_p),
        ("winid", ctypes.c_int),
        ("posx", ctypes.c_short),
        ("posy", ctypes.c_short),
        ("sizex", ctypes.c_short),
        ("sizey", ctypes.c_short),
        ("windowstate", ctypes.c_char),
        ("active", ctypes.c_char),
        ("cursor", ctypes.c_short),
        ("lastcursor", ctypes.c_short),
        ("modalcursor", ctypes.c_short),
        ("grabcursor", ctypes.c_short)
    )
else:
    _wmWindow._fields_ = (  # from DNA_windowmanager_types.h
        ("next", ctypes.POINTER(_wmWindow)),
        ("prev", ctypes.POINTER(_wmWindow)),
        ("ghostwin", ctypes.c_void_p),
        ("gpuctx", ctypes.c_void_p),
        ("parent", ctypes.POINTER(_wmWindow)),
        ("scene", ctypes.c_void_p),
        ("new_scene", ctypes.c_void_p),
        ("view_layer_name", ctypes.c_char * 64),
        ("unpinned_scene", ctypes.c_void_p),
        ("workspace_hook", ctypes.c_void_p),
        ("global_areas", _listbase(type_=None) * 3),
        ("screen", ctypes.c_void_p),
        ("winid", ctypes.c_int),
        ("posx", ctypes.c_short),
        ("posy", ctypes.c_short),
        ("sizex", ctypes.c_short),
        ("sizey", ctypes.c_short),
        ("windowstate", ctypes.c_char),
        ("active", ctypes.c_char),
        ("cursor", ctypes.c_short),
        ("lastcursor", ctypes.c_short),
        ("modalcursor", ctypes.c_short),
        ("grabcursor", ctypes.c_short)
    )


def is_modal_procedure(context):
    """Check if a modal operation is currently running (ZenUV approach)

    This uses ctypes to directly check Blender's internal window state
    to detect if a modal operator (like transform) is active.

    Returns:
        bool: True if modal operation is active, False otherwise
    """
    try:
        b_is_modal = False
        for wnd in context.window_manager.windows:
            p_win = ctypes.cast(wnd.as_pointer(), ctypes.POINTER(_wmWindow)).contents
            b_is_modal = p_win.modalcursor != 0 or p_win.grabcursor != 0
            if b_is_modal:
                break
        return b_is_modal
    except Exception as e:
        # If we can't check (e.g., struct changes in Blender version),
        # assume modal IS running (safe mode) to avoid corruption
        return True


def uvv_delayed_overlay_build_uv():
    """Timer callback for delayed gizmo builds - EXACT Zen UV 1:1 pattern"""
    try:
        ctx = bpy.context
        t_delayed_gizmos = bpy.app.driver_namespace.get(LITERAL_UVV_DELAYED_UV_GIZMOS, set())
        
        # Zen UV pattern: Set mark_build = 1 instead of calling build() directly
        while t_delayed_gizmos:
            p_gizmo = t_delayed_gizmos.pop()
            try:
                if not p_gizmo.mark_build:
                    p_gizmo.mark_build = 1  # Mark for rebuild - triggers rebuild in _do_draw()
            except Exception as e:
                print(f"UVV: Error marking gizmo for rebuild: {e}")

        bpy.app.driver_namespace[LITERAL_UVV_DELAYED_UV_GIZMOS] = set()
        
        # Trigger redraw of UV editor areas
        for window in ctx.window_manager.windows:
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
        # Don't validate during modal operations (Zen UV pattern) - keep current data
        if is_modal_procedure(context):
            return True
        
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
        Dispatches to build_texel_density() method
        """
        if not hasattr(context.scene, 'uvv_settings'):
            return
        
        settings = context.scene.uvv_settings
        
        # Check draw_mode_UV matches
        if settings.draw_mode_UV != 'TEXEL_DENSITY':
            return
        
        # Reset build flag and clear data (Zen UV pattern)
        self.mark_build = 0
        
        # Store current state BEFORE calling build method (Zen UV pattern)
        b_is_uv_sync = context.scene.tool_settings.use_uv_select_sync
        self.custom_shapes.clear()
        self.mesh_data = {}
        self.last_mode = settings.draw_mode_UV
        self.uv_sync = b_is_uv_sync
        
        # Dispatch to build_texel_density method (Zen UV pattern)
        self.build_texel_density(context)

    def build_texel_density(self, context):
        """
        Build texel density visualization - COMPLETE ZEN UV 1:1 PATTERN
        ISLAND-BASED calculation with caching - NOT per-face!
        """
        try:
            from .td_utils import TdUtils, TdContext, TdBmeshManager
            from .td_display_utils import TdColorProcessor

            # Get settings
            if not hasattr(context.scene, 'uvv_settings'):
                return

            settings = context.scene.uvv_settings

            # Check draw_sub_TD_UV early - return if not VIEWPORT/ALL (Zen UV pattern)
            if settings.draw_sub_TD_UV not in {'VIEWPORT', 'ALL'}:
                return

            # Get mesh object map
            mesh_obj_map = get_unique_mesh_object_map_with_active(context)
            if not mesh_obj_map:
                return

            # Store objects in list and track geometry (Zen UV pattern)
            p_objects = []
            p_geometry_keys = []
            t_updates = bpy.app.driver_namespace.get(LITERAL_UVV_UPDATE, {})
            
            for me, p_obj in mesh_obj_map.items():
                update_data = t_updates.get(me, ['', ''])
                self.mesh_data[me] = update_data.copy()
                p_geometry_keys.append(update_data[0])
                p_objects.append(p_obj)

            if len(p_objects) == 0:
                return

            # Create TD context
            td_inputs = TdContext(context)

            # Get TD scope with caching (EXACT ZenUV pattern)
            td_scope = None

            p_stored_td_scope = bpy.app.driver_namespace.get(LITERAL_UVV_TD_SCOPE, None)
            if p_stored_td_scope:
                if p_geometry_keys and p_geometry_keys == p_stored_td_scope[0]:
                    td_scope = p_stored_td_scope[1]

            if not td_scope:
                # Get influence from settings - EXACT ZenUV pattern (pass string directly)
                td_influence = settings.influence if hasattr(settings, 'influence') and settings.influence else 'ISLAND'

                td_scope = TdUtils.get_td_data_with_precision(context, p_objects, td_inputs, td_influence)
                bpy.app.driver_namespace[LITERAL_UVV_TD_SCOPE] = (p_geometry_keys, td_scope)

            # Process colors - EXACT ZenUV pattern (pass settings directly)
            # Don't update UI limits during gizmo build (not allowed in that context)
            # Always use SPECTRUM mode (Full Spectrum)
            CP = TdColorProcessor(context, td_scope, settings, update_ui_limits=False)
            CP.calc_output_range(context, td_inputs, 'SPECTRUM')

            # Update GradientProperties for enhanced gradient display (ZenUV 1:1)
            from .td_display_utils import TdSysUtils
            p_td_values, p_colors = td_scope.get_referenced_values_for_gradient(td_inputs)
            GradientProperties.range_values = p_td_values
            GradientProperties.range_colors = p_colors
            GradientProperties.range_labels = TdSysUtils.td_labels_filter(p_td_values, settings.values_filter)

            # Get alpha from preferences (Zen UV pattern)
            # For now, use settings - may need to add to preferences later
            alpha = settings.td_gradient_alpha if hasattr(settings, 'td_gradient_alpha') else 0.5

            def get_color(p_color):
                return (*p_color, alpha)

            # Store texel data map for gradient display
            self.custom_data['texel_data_map'] = {}

            for p_obj_name, p_islands in td_scope.get_islands_by_objects().items():
                if len(p_islands) == 0:
                    continue

                p_obj = context.scene.objects[p_obj_name]
                
                # Create color map (island index -> color) - Zen UV pattern
                t_color_map = {
                    idx: [(round(island.color[0], 2), round(island.color[1], 2), round(island.color[2], 2)), island.td]
                    for island in p_islands for idx in island.indices
                }
                self.custom_data['texel_data_map'][p_obj_name] = t_color_map

                # Extract UV triangles using stack overlay approach (fresh BMesh, face loops)
                # Group triangles by color for batch creation
                face_tri_indices = defaultdict(list)
                
                try:
                    # Get fresh BMesh data (like stack overlay - avoids stale data during transforms)
                    bm = bmesh.from_edit_mesh(p_obj.data)
                    bm.faces.ensure_lookup_table()
                    
                    uv_layer = bm.loops.layers.uv.active
                    if not uv_layer:
                        continue
                    
                    # Process each island's faces
                    for island in p_islands:
                        island_color, _ = t_color_map.get(island.indices[0] if island.indices else None, [(0, 0, 0), 0])
                        
                        # Extract UV triangles for this island's faces
                        for face_idx in island.indices:
                            try:
                                # Get face from BMesh (may fail if face was deleted during transform)
                                face = bm.faces[face_idx]
                                
                                # Skip hidden faces and check selection if needed
                                if face.hide:
                                    continue
                                if not self.uv_sync and not face.select:
                                    continue
                                
                                # Get UV coordinates for this face (like stack overlay)
                                face_uvs = [loop[uv_layer].uv.copy() for loop in face.loops]
                                
                                # Triangulate face manually (stack overlay pattern)
                                if len(face_uvs) == 3:
                                    # Already a triangle
                                    for uv in face_uvs:
                                        face_tri_indices[island_color].append((uv.x, uv.y))
                                elif len(face_uvs) == 4:
                                    # Quad - split into 2 triangles
                                    face_tri_indices[island_color].extend([
                                        (face_uvs[0].x, face_uvs[0].y),
                                        (face_uvs[1].x, face_uvs[1].y),
                                        (face_uvs[2].x, face_uvs[2].y),
                                        (face_uvs[0].x, face_uvs[0].y),
                                        (face_uvs[2].x, face_uvs[2].y),
                                        (face_uvs[3].x, face_uvs[3].y),
                                    ])
                                elif len(face_uvs) > 4:
                                    # N-gon - fan triangulation
                                    for i in range(1, len(face_uvs) - 1):
                                        face_tri_indices[island_color].extend([
                                            (face_uvs[0].x, face_uvs[0].y),
                                            (face_uvs[i].x, face_uvs[i].y),
                                            (face_uvs[i + 1].x, face_uvs[i + 1].y),
                                        ])
                            except (ReferenceError, IndexError, KeyError):
                                # Face was deleted or invalid during transform - skip gracefully
                                continue
                    
                except (ReferenceError, IndexError, RuntimeError) as e:
                    # BMesh became invalid during transform - skip this object
                    continue

                # Create batches from grouped triangles (stack overlay pattern)
                if face_tri_indices:
                    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
                    
                    for color_tuple, vertices in face_tri_indices.items():
                        if len(vertices) < 3:
                            continue
                        
                        try:
                            # Create batch directly from triangles (like stack overlay)
                            # No deduplication needed - GPU handles it efficiently
                            batch = batch_for_shader(shader, 'TRIS', {"pos": vertices})
                            batch.program_set(shader)

                            self.custom_shapes.append(
                                DrawCustomShape(batch, shader, p_obj, functools.partial(get_color, color_tuple)))
                        except Exception as e:
                            # Skip this color group if there's an error
                            continue

        except Exception as e:
            import traceback
            print(f"UVV: Error building UV gizmo: {e}")
            traceback.print_exc()
            self.mark_build = -1

    def draw_gradient(self, context):
        """Draw gradient bar - Full ZenUV 1:1 implementation with labels"""
        from .td_display_utils import TdColorManager
        from ..utils.units_converter import get_current_units_string, get_td_round_value

        settings = context.scene.uvv_settings

        # Get current units string for display
        units_string = get_current_units_string(settings.td_unit)

        # Get gradient data from GradientProperties (set by display factories)
        td_values = GradientProperties.range_values
        td_colors = GradientProperties.range_colors
        td_labels = GradientProperties.range_labels

        n_input_count = len(td_values)
        if n_input_count == 0:
            return

        # Validation check
        if len(set([n_input_count, len(td_colors), len(td_labels)])) != 1:
            print(f'DRAW GRADIENT: MISMATCH - td_values:{len(td_values)}, td_colors:{len(td_colors)}, td_labels:{len(td_labels)}')
            return

        # Handle single value case
        if n_input_count == 1:
            td_values = [td_values[0], td_values[0]]
            td_colors = [td_colors[0], td_colors[0]]
            td_labels = [td_labels[0], td_labels[0]]

        # Try to get active face TD value (ZenUV pattern - currently disabled as it's buggy in UV context)
        s_act_obj_td_value = ''

        # Get UI scale and font size
        ui_scale = context.preferences.system.ui_scale
        i_font_size = 11
        blf.size(0, int(i_font_size * ui_scale))

        i_height = settings.td_gradient_height
        d_font_offset_top = i_font_size * ui_scale
        d_font_offset_bottom = i_font_size * 2 * ui_scale

        # Calculate gradient position - CENTER it horizontally
        p_area = context.area
        region = context.region

        # Center the gradient bar horizontally
        bar_width = settings.td_gradient_width
        start_x = (region.width - bar_width) / 2

        # Ensure it doesn't go off-screen on small windows
        if start_x < 20 * ui_scale:
            start_x = 20 * ui_scale
        if start_x + bar_width > region.width - 20 * ui_scale:
            start_x = region.width - bar_width - 20 * ui_scale

        end_x = start_x + bar_width
        start_y = 10 * ui_scale + d_font_offset_bottom
        
        # Corner radius in pixels (8px)
        corner_radius = 8.0

        # Build gradient geometry with rounded corners
        indices = []
        vertices = []
        vertex_colors = []

        # Process labels for alternating positioning
        p_td_labels = []
        idx = 0
        for v in td_labels:
            p_td_labels.append([idx if v != '' else 0, v])
            if v != '':
                idx += 1

        i_last_top_x = 0
        i_last_bottom_x = 0
        n_max_values = len(td_values)

        # Helper function for label text (ZenUV pattern)
        def map_range(value, in_min, in_max, out_min, out_max):
            return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

        for idx in range(n_max_values):
            val = td_values[idx]
            if idx == 0:
                val = start_x
            elif idx == n_max_values - 1:
                val = end_x
            else:
                val = map_range(val, td_values[0], td_values[-1], start_x, end_x)

            vertices.append((val, start_y))
            vertices.append((val, start_y + i_height))
            vertex_colors.append((*td_colors[idx], 1))
            vertex_colors.append((*td_colors[idx], 1))

            # Draw label with alternating top/bottom positioning
            b_is_odd = p_td_labels[idx][0] % 2 == 1
            label_value = p_td_labels[idx][1]
            
            # Format label with units if not empty
            if label_value != '':
                s_label_name = f"{label_value} {units_string}"
            else:
                s_label_name = ''

            pos_x = val
            pos_y = start_y + i_height + d_font_offset_top if not b_is_odd else start_y - d_font_offset_bottom
            t_width, _ = blf.dimensions(0, s_label_name)

            b_enable_draw_label = False

            # Prevent label overlap
            if not b_is_odd:
                i_new_last_x = pos_x + t_width
                if pos_x > i_last_top_x + 10:
                    i_last_top_x = i_new_last_x
                    b_enable_draw_label = True
            else:
                i_new_last_x = pos_x + t_width
                if pos_x > i_last_bottom_x + 10:
                    i_last_bottom_x = i_new_last_x
                    b_enable_draw_label = True

            if b_enable_draw_label and s_label_name:
                blf.position(0, pos_x, pos_y, 0)
                blf.color(0, 1, 1, 1, 1)
                blf.draw(0, s_label_name)

            # Build triangle indices
            if idx != 0:
                n_v_idx = len(vertices) - 4
                indices.extend([
                    (n_v_idx, n_v_idx + 1, n_v_idx + 2),
                    (n_v_idx + 2, n_v_idx + 1, n_v_idx + 3)])

        # Display method label removed - no longer shown above gradient

        # Draw gradient bar with rounded corners
        gpu.state.blend_set('ALPHA')
        shader = gpu.shader.from_builtin('SMOOTH_COLOR')
        
        # Adjust first and last vertices to account for rounded corners
        # This creates a gap that we'll fill with rounded corner caps
        import math
        
        # Adjust vertices: move first pair inward and last pair inward
        adjusted_vertices = vertices.copy()
        adjusted_colors = vertex_colors.copy()
        
        left_edge_x = start_x + corner_radius
        right_edge_x = end_x - corner_radius
        
        if len(adjusted_vertices) >= 2:
            # Adjust left edge vertices
            if adjusted_vertices[0][0] < left_edge_x:
                adjusted_vertices[0] = (left_edge_x, adjusted_vertices[0][1])
            if adjusted_vertices[1][0] < left_edge_x:
                adjusted_vertices[1] = (left_edge_x, adjusted_vertices[1][1])
        
        if len(adjusted_vertices) >= 2:
            # Adjust right edge vertices
            last_idx = len(adjusted_vertices) - 1
            if adjusted_vertices[last_idx - 1][0] > right_edge_x:
                adjusted_vertices[last_idx - 1] = (right_edge_x, adjusted_vertices[last_idx - 1][1])
            if adjusted_vertices[last_idx][0] > right_edge_x:
                adjusted_vertices[last_idx] = (right_edge_x, adjusted_vertices[last_idx][1])
        
        # Draw main gradient
        batch = batch_for_shader(
            shader, 'TRIS',
            {"pos": adjusted_vertices, "color": adjusted_colors}, indices=indices
        )
        shader.bind()
        batch.draw(shader)
        
        # Draw rounded corner caps
        uniform_shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        
        # Left rounded corner cap
        if len(vertex_colors) >= 2:
            left_color = vertex_colors[0]
            left_cap_verts = []
            left_cap_indices = []
            
            # Top-left corner arc
            tl_center_x = start_x + corner_radius
            tl_center_y = start_y + corner_radius
            for seg in range(17):
                angle = math.pi + (math.pi / 2) * (seg / 16)
                x = tl_center_x + corner_radius * math.cos(angle)
                y = tl_center_y + corner_radius * math.sin(angle)
                left_cap_verts.append((x, y))
            
            # Add connection point to main gradient
            left_cap_verts.append((left_edge_x, start_y))
            left_cap_verts.append((start_x, start_y + corner_radius))
            
            # Bottom-left corner arc
            bl_center_x = start_x + corner_radius
            bl_center_y = start_y + i_height - corner_radius
            for seg in range(17):
                angle = (math.pi / 2) + (math.pi / 2) * (seg / 16)
                x = bl_center_x + corner_radius * math.cos(angle)
                y = bl_center_y + corner_radius * math.sin(angle)
                left_cap_verts.append((x, y))
            
            # Add connection point to main gradient
            left_cap_verts.append((start_x, start_y + i_height - corner_radius))
            left_cap_verts.append((left_edge_x, start_y + i_height))
            
            # Triangulate left cap (fan from center)
            num_left_verts = len(left_cap_verts)
            for i in range(1, num_left_verts - 1):
                left_cap_indices.append((0, i, i + 1))
            
            if left_cap_indices:
                left_cap_batch = batch_for_shader(
                    uniform_shader, 'TRIS',
                    {"pos": left_cap_verts}, indices=left_cap_indices
                )
                uniform_shader.bind()
                uniform_shader.uniform_float("color", (*left_color[:3], 1))
                left_cap_batch.draw(uniform_shader)
        
        # Right rounded corner cap
        if len(vertex_colors) >= 2:
            right_color = vertex_colors[-1]
            right_cap_verts = []
            right_cap_indices = []
            
            # Top-right corner arc
            tr_center_x = end_x - corner_radius
            tr_center_y = start_y + corner_radius
            for seg in range(17):
                angle = (3 * math.pi / 2) + (math.pi / 2) * (seg / 16)
                if angle >= 2 * math.pi:
                    angle -= 2 * math.pi
                x = tr_center_x + corner_radius * math.cos(angle)
                y = tr_center_y + corner_radius * math.sin(angle)
                right_cap_verts.append((x, y))
            
            # Add connection point to main gradient
            right_cap_verts.append((right_edge_x, start_y))
            right_cap_verts.append((end_x, start_y + corner_radius))
            
            # Bottom-right corner arc
            br_center_x = end_x - corner_radius
            br_center_y = start_y + i_height - corner_radius
            for seg in range(17):
                angle = (math.pi / 2) * (seg / 16)
                x = br_center_x + corner_radius * math.cos(angle)
                y = br_center_y + corner_radius * math.sin(angle)
                right_cap_verts.append((x, y))
            
            # Add connection point to main gradient
            right_cap_verts.append((end_x, start_y + i_height - corner_radius))
            right_cap_verts.append((right_edge_x, start_y + i_height))
            
            # Triangulate right cap (fan from center)
            num_right_verts = len(right_cap_verts)
            for i in range(1, num_right_verts - 1):
                right_cap_indices.append((0, i, i + 1))
            
            if right_cap_indices:
                right_cap_batch = batch_for_shader(
                    uniform_shader, 'TRIS',
                    {"pos": right_cap_verts}, indices=right_cap_indices
                )
                uniform_shader.bind()
                uniform_shader.uniform_float("color", (*right_color[:3], 1))
                right_cap_batch.draw(uniform_shader)
        
        gpu.state.blend_set('NONE')

    def _do_draw(self, context, select_id=None):
        """Internal draw method - EXACT ZenUV 1:1 pattern (lines 817-879)"""
        # Draw label first (ZenUV pattern - we skip label for now)
        # self.draw_label(context)

        # Special case: Draw gradient for texel density - moved to end to render on top
        if not hasattr(context.scene, 'uvv_settings'):
            return

        settings = context.scene.uvv_settings

        # When we assigned nothing (EXACT ZenUV pattern line 826)
        if self.mesh_data is None:
            # Draw gradient before early return
            if settings.draw_mode_UV == 'TEXEL_DENSITY':
                if settings.draw_sub_TD_UV in {'GRADIENT', 'ALL'}:
                    self.draw_gradient(context)
            return

        # ZenUV state machine: Check if we need to build (stack overlay pattern)
        # mark_build: -1 = force build, 0 = clean (no build needed), 1 = needs rebuild
        if self.mark_build:  # Any non-zero value (-1 or 1)
            # Need to build or force build
            if not is_modal_procedure(context):
                # Safe to build - no modal operation
                try:
                    self.build(context)
                except Exception as e:
                    print(f"UVV: Error building texel density overlay: {e}")
                    # Draw gradient before early return on error
                    if settings.draw_mode_UV == 'TEXEL_DENSITY':
                        if settings.draw_sub_TD_UV in {'GRADIENT', 'ALL'}:
                            self.draw_gradient(context)
                    return
            else:
                # Modal operation running - schedule delayed build
                self._delayed_build()
                # Draw gradient before early return (don't draw stale overlay data)
                if settings.draw_mode_UV == 'TEXEL_DENSITY':
                    if settings.draw_sub_TD_UV in {'GRADIENT', 'ALL'}:
                        self.draw_gradient(context)
                return  # Don't draw during modal ops
        elif not self.check_valid_data(context):
            # mark_build is 0 but data changed - need delayed rebuild
            if not is_modal_procedure(context):
                self._delayed_build()
            # Draw gradient before early return (don't draw stale overlay data)
            if settings.draw_mode_UV == 'TEXEL_DENSITY':
                if settings.draw_sub_TD_UV in {'GRADIENT', 'ALL'}:
                    self.draw_gradient(context)
            return  # Don't draw with invalid data

        if not self.custom_shapes:
            # Draw gradient before early return
            if settings.draw_mode_UV == 'TEXEL_DENSITY':
                if settings.draw_sub_TD_UV in {'GRADIENT', 'ALL'}:
                    self.draw_gradient(context)
            return

        # Only draw viewport overlay if mode allows - check draw_sub_TD_UV (Zen UV pattern)
        if settings.draw_sub_TD_UV not in {'VIEWPORT', 'ALL'}:
            # Draw gradient before early return
            if settings.draw_mode_UV == 'TEXEL_DENSITY':
                if settings.draw_sub_TD_UV in {'GRADIENT', 'ALL'}:
                    self.draw_gradient(context)
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
        
        # Draw gradient last so it renders on top of UV islands
        if settings.draw_mode_UV == 'TEXEL_DENSITY':
            if settings.draw_sub_TD_UV in {'GRADIENT', 'ALL'}:
                self.draw_gradient(context)

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
    # CRITICAL: EXCLUDE_MODAL prevents gizmo from blocking transform operations (Zen UV pattern)
    bl_options = {
        'PERSISTENT', 'SCALE',
    } if bpy.app.version < (3, 0, 0) else {
        'PERSISTENT', 'EXCLUDE_MODAL', 'SCALE'
    }
    tool_mode = {'DISPLAY'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'EDIT_MESH':
            return False
        if not hasattr(context.scene, 'uvv_settings'):
            return False
        settings = context.scene.uvv_settings
        p_space_data = context.space_data
        
        # Check overlay sync (Zen UV pattern)
        if hasattr(p_space_data, 'overlay') and hasattr(p_space_data.overlay, 'show_overlays'):
            if hasattr(settings, 'use_draw_overlay_sync') and settings.use_draw_overlay_sync:
                if not p_space_data.overlay.show_overlays:
                    return False
        
        # Check gizmo visibility (Zen UV pattern)
        if hasattr(p_space_data, 'show_gizmo') and not p_space_data.show_gizmo:
            return False
        
        # Check draw_mode_UV instead of boolean flag (Zen UV pattern)
        return settings.draw_mode_UV == 'TEXEL_DENSITY'

    def setup(self, context):
        self.gizmo = self.gizmos.new(UVV_UVGizmoTexelDensity.bl_idname)
        # CRITICAL: These settings prevent gizmo from intercepting mouse events (Zen UV pattern)
        self.gizmo.use_draw_modal = True
        self.gizmo.use_draw_value = False
        self.gizmo.use_draw_hover = False
        self.gizmo.use_select_background = False
        self.gizmo.use_event_handle_all = False
        self.gizmo.use_grab_cursor = False
        self.gizmo.hide_select = True

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


def update_all_gizmos(context, force=False):
    """Mark all gizmos for rebuild - Zen UV pattern"""
    for gizmo in UVV_UV_GIZMOS.values():
        if hasattr(gizmo, 'mark_build'):
            gizmo.mark_build = -1
            gizmo.mesh_data = {}

    # Clear TD cache to force recalculation (always clear if force=True)
    if force or LITERAL_UVV_TD_SCOPE in bpy.app.driver_namespace:
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
