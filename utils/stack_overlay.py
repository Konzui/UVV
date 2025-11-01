"""GPU overlay system for stack groups in UV Editor

This module provides a ZenUV-inspired GPU-based overlay system that draws colored
shapes over UV islands based on their stack group assignments.
"""

import bpy
import bmesh
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
import numpy as np
import uuid
import ctypes


# Global handler references
_draw_handler = None
_draw_context = None
_depsgraph_handler = None
_rebuild_timer = None
_pending_rebuild = False
_selection_handler = None
_selection_msgbus_owner = None  # Owner object for msgbus subscription

# Namespace keys for shared state (ZenUV approach)
LITERAL_UVV_UPDATE = 'uvv_stack_overlay_update'
LITERAL_UVV_DELAYED_GIZMOS = 'uvv_stack_overlay_delayed'


# Generate listbase of appropriate type. None: generic (ZenUV approach)
def _listbase(type_=None):
    ptr = ctypes.POINTER(type_)
    fields = ("first", ptr), ("last", ptr)
    return type("ListBase", (ctypes.Structure,), {'_fields_': fields})


# Forward declaration of wmWindow (ZenUV approach)
class _wmWindow(ctypes.Structure):
    pass


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


class StackOverlayManager:
    """Singleton manager for stack group GPU overlays"""

    _instance = None

    def __init__(self):
        self.enabled = False
        self.cached_batches = []  # [(batch, color), ...]
        self.mesh_data = {}  # Track mesh changes with UUID approach
        self.mark_build = 0  # Build state: -1=force, 0=clean, 1=needs rebuild
        self.custom_shapes = []  # For compatibility
        self.label_data = []  # [(group_name, center_uv, color), ...] for drawing labels

        # Highlight cache for performance
        self.highlight_cached_batches = []  # Cached highlight batches
        self.highlight_cached_group_id = None  # Which group is cached

        # Flash effect when clicking group
        self.flash_active = False  # Is flash currently showing
        self.flash_start_time = None  # When flash started (for fade animation)
        self.flash_duration = 1.0  # Flash duration in seconds (from settings)
        self.flash_timer = None  # Timer to clear flash
        self.flash_redraw_timer = None  # Timer to continuously trigger redraws during animation

    @classmethod
    def instance(cls):
        """Get or create singleton instance"""
        if cls._instance is None:
            cls._instance = StackOverlayManager()
        return cls._instance

    def enable(self, context, force=False):
        """Enable the overlay by registering GPU draw handler
        
        Args:
            context: Blender context
            force: If True, force re-registration even if handler exists (for reloads)
        """
        global _draw_handler, _draw_context, _selection_handler

        # Always ensure msgbus is registered when overlay is enabled
        # This fixes the issue where msgbus subscription is lost on script reload
        register_selection_msgbus()

        # If handler exists and not forcing, just ensure msgbus is registered
        if _draw_handler is not None and not force:
            # Already enabled, but msgbus is now ensured to be registered
            return

        # If forcing or handler is None, clean up any existing handler first
        if _draw_handler is not None:
            # Remove stale handler (might exist from previous module instance)
            try:
                bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler, 'WINDOW')
            except:
                pass  # Ignore errors if handler was already removed
            _draw_handler = None
            _draw_context = None

        # Register draw handler for UV Editor
        _draw_handler = bpy.types.SpaceImageEditor.draw_handler_add(
            draw_stack_overlay_callback,
            (context,),
            'WINDOW',
            'POST_PIXEL'
        )
        _draw_context = context
        self.enabled = True
        self.mark_build = -1  # Force initial build

        # Tag all UV editors for redraw
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

    def disable(self, context):
        """Disable the overlay by removing GPU draw handler"""
        global _draw_handler, _draw_context, _rebuild_timer, _pending_rebuild

        if _draw_handler is None:
            # Already disabled
            return

        # Cancel any pending rebuild timer
        if _rebuild_timer is not None:
            try:
                if bpy.app.timers.is_registered(_rebuild_timer):
                    bpy.app.timers.unregister(_rebuild_timer)
            except:
                pass
            _rebuild_timer = None
        _pending_rebuild = False

        # Cancel flash timers if active
        if self.flash_timer is not None:
            try:
                if bpy.app.timers.is_registered(self.flash_timer):
                    bpy.app.timers.unregister(self.flash_timer)
            except:
                pass
            self.flash_timer = None
        if self.flash_redraw_timer is not None:
            try:
                if bpy.app.timers.is_registered(self.flash_redraw_timer):
                    bpy.app.timers.unregister(self.flash_redraw_timer)
            except:
                pass
            self.flash_redraw_timer = None
        self.flash_active = False
        self.flash_start_time = None

        # Unregister draw handler
        bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
        _draw_context = None
        self.enabled = False
        self.cached_batches.clear()
        self.mesh_data.clear()
        self.mark_build = 0

        # Clear highlight cache
        self.highlight_cached_batches.clear()
        self.highlight_cached_group_id = None

        # Unregister msgbus subscription
        unregister_selection_msgbus()

        # Tag all UV editors for redraw
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

    def _delayed_build(self):
        """Schedule a delayed build (ZenUV approach)"""
        global _rebuild_timer, _pending_rebuild

        if bpy.app.timers.is_registered(delayed_rebuild_timer):
            bpy.app.timers.unregister(delayed_rebuild_timer)

        _pending_rebuild = True
        _rebuild_timer = delayed_rebuild_timer
        bpy.app.timers.register(_rebuild_timer, first_interval=0.05)

    def get_group_for_selected_island(self, context):
        """Find which stack group the currently selected UV island belongs to

        Returns:
            str or None: Group ID if found, None otherwise
        """
        if context.mode != 'EDIT_MESH':
            return None

        try:
            from .stack_utils import StackSystem

            # Get selected UVs
            bm = bmesh.from_edit_mesh(context.active_object.data)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                return None

            # Find any selected face
            selected_faces = [face for face in bm.faces if face.select]
            if not selected_faces:
                return None

            # Use first selected face to find the group
            selected_face = selected_faces[0]

            # Get stack system and find which group contains this face
            stack_system = StackSystem(context)

            # Check stack groups on active object
            obj = context.active_object
            if not obj:
                return None

            for stack_group in obj.uvv_stack_groups:
                islands = stack_system.get_group_islands(stack_group.group_id, obj=obj)
                for island in islands:
                    if selected_face.index in island.face_indices:
                        return stack_group.group_id

            return None
        except Exception as e:
            # Silently fail
            return None

    def trigger_flash(self, context):
        """Trigger a flash effect on the currently selected group
        
        Args:
            context: Blender context (needed to get flash duration from settings)
        """
        import time

        # Cancel existing flash timers if present
        if self.flash_timer is not None:
            if bpy.app.timers.is_registered(self.flash_timer):
                bpy.app.timers.unregister(self.flash_timer)
        if self.flash_redraw_timer is not None:
            if bpy.app.timers.is_registered(self.flash_redraw_timer):
                bpy.app.timers.unregister(self.flash_redraw_timer)

        # Get flash duration from settings
        settings = context.scene.uvv_settings if hasattr(context.scene, 'uvv_settings') else None
        flash_duration = settings.stack_overlay_flash_duration if settings else 1.0

        # Start new flash
        self.flash_active = True
        self.flash_start_time = time.time()
        self.flash_duration = flash_duration  # Store duration for redraw timer

        # Schedule flash clear after specified duration
        self.flash_timer = clear_flash_timer
        bpy.app.timers.register(self.flash_timer, first_interval=flash_duration)

        # Schedule continuous redraws during animation (60 FPS = ~0.016s interval)
        self.flash_redraw_timer = flash_redraw_timer
        bpy.app.timers.register(self.flash_redraw_timer, first_interval=0.016)

        # Tag UV editors for initial redraw
        if bpy.context:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        area.tag_redraw()

    def get_highlight_batches(self, context, group_id):
        """Build GPU batches for highlighting a specific group (permanent border) - CACHED

        Args:
            context: Blender context
            group_id: ID of the group to highlight

        Returns:
            list: [(batch, color), ...] for highlighted group, or empty list
        """
        if group_id is None:
            # Clear cache when no group selected
            self.highlight_cached_batches.clear()
            self.highlight_cached_group_id = None
            return []

        # PERFORMANCE: Return cached batches if same group
        if self.highlight_cached_group_id == group_id and self.highlight_cached_batches:
            return self.highlight_cached_batches

        # Need to rebuild - different group selected
        try:
            from .stack_utils import StackSystem

            scene = context.scene
            settings = scene.uvv_settings if hasattr(scene, 'uvv_settings') else None
            obj = context.active_object
            if not obj:
                return []

            # Find the stack group on active object
            stack_group = None
            for sg in obj.uvv_stack_groups:
                if sg.group_id == group_id:
                    stack_group = sg
                    break

            if not stack_group:
                return []

            # Get islands in this group
            stack_system = StackSystem(context)
            islands = stack_system.get_group_islands(group_id, obj=obj)

            if not islands:
                return []

            # Build border batches for these islands
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            highlight_batches = []

            # Use bright white for permanent highlight
            highlight_color = (1.0, 1.0, 1.0, 1.0)  # Solid white

            for island in islands:
                try:
                    vertices = self._extract_island_uv_triangles(island)
                    if len(vertices) < 3:
                        continue

                    verts_uv = [(v.x, v.y) for v in vertices]
                    border_edges = self._extract_border_edges(verts_uv)

                    if border_edges:
                        batch_border = batch_for_shader(
                            shader,
                            'LINES',
                            {"pos": border_edges}
                        )
                        highlight_batches.append((batch_border, highlight_color))
                except Exception:
                    continue

            # CACHE the result for this group
            self.highlight_cached_batches = highlight_batches
            self.highlight_cached_group_id = group_id

            return highlight_batches

        except Exception:
            return []

    def check_valid_data(self, context):
        """Check if cached data is still valid (ZenUV UUID approach)

        Returns True if cache is still valid (no geometry/UV changes).
        Compares UUID strings stored in driver_namespace.

        Key optimization: Only checks geometry changes for stack overlays,
        ignores selection/shading changes to avoid unnecessary rebuilds.
        """
        # If mesh_data is empty, we haven't built yet - not valid
        if not self.mesh_data:
            return False

        try:
            # Get update tracking dict from shared namespace
            t_updates = bpy.app.driver_namespace.get(LITERAL_UVV_UPDATE, {})

            # Build current state
            check_data = {}
            for obj in context.objects_in_mode_unique_data:
                if obj.type == 'MESH':
                    check_data[obj.data] = t_updates.get(obj.data, ['', ''])

            # Compare with cached state - check object list first
            if self.mesh_data.keys() != check_data.keys():
                return False

            # For stack overlays, we only care about GEOMETRY changes (island topology)
            # NOT shading changes (UV selection). This prevents rebuilds on every click.
            # Similar to ZenUV's approach when UV sync is on.
            for key in self.mesh_data.keys():
                # Only compare geometry UUID (index 0), ignore shading UUID (index 1)
                if self.mesh_data[key][0] != check_data[key][0]:
                    return False

            return True
        except:
            return False

    def get_island_shapes(self, context):
        """Extract UV island shapes from stack groups

        Returns:
            dict: {group_id: [(vertices, color), ...]}
        """
        from .stack_utils import StackSystem

        if not context.mode == 'EDIT_MESH':
            return {}

        # Get active object and settings
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {}
        
        # All objects have uvv_stack_groups property (registered on Object type)
        stack_groups = obj.uvv_stack_groups
        if len(stack_groups) == 0:
            return {}
        
        scene = context.scene
        settings = scene.uvv_settings if hasattr(scene, 'uvv_settings') else None
        if not settings:
            return {}

        # Initialize StackSystem
        try:
            stack_system = StackSystem(context)
        except Exception as e:
            print(f"Stack overlay error: Failed to initialize StackSystem: {e}")
            return {}

        shapes_by_group = {}

        # Process each stack group
        for stack_group in stack_groups:
            group_id = stack_group.group_id
            color = (*stack_group.color, settings.stack_overlay_opacity)

            # Get islands in this group
            try:
                islands = stack_system.get_group_islands(group_id, obj=obj)
            except Exception as e:
                print(f"Stack overlay error: Failed to get islands for group {group_id}: {e}")
                continue

            if not islands:
                continue

            group_shapes = []

            # Extract UV coordinates for each island
            for island in islands:
                try:
                    vertices = self._extract_island_uv_triangles(island)
                    if vertices and len(vertices) >= 3:
                        group_shapes.append((vertices, color))
                except Exception as e:
                    print(f"Stack overlay error: Failed to extract island UVs: {e}")
                    continue

            if group_shapes:
                shapes_by_group[group_id] = group_shapes

        return shapes_by_group

    def _extract_island_uv_triangles(self, island):
        """Extract UV coordinates as triangles for an island

        Args:
            island: IslandData object

        Returns:
            list: List of (x, y) tuples representing triangle vertices
        """
        try:
            # Get fresh BMesh data
            bm = bmesh.from_edit_mesh(island.obj.data)
            bm.faces.ensure_lookup_table()

            # Get faces for this island
            faces = [bm.faces[idx] for idx in island.face_indices]

            vertices = []

            # Extract UV coordinates for each face (triangulate on the fly)
            for face in faces:
                # Get UV coordinates for this face
                face_uvs = [loop[island.uv_layer].uv.copy() for loop in face.loops]

                # Triangulate face
                if len(face_uvs) == 3:
                    # Already a triangle
                    vertices.extend(face_uvs)
                elif len(face_uvs) == 4:
                    # Quad - split into 2 triangles
                    vertices.extend([face_uvs[0], face_uvs[1], face_uvs[2]])
                    vertices.extend([face_uvs[0], face_uvs[2], face_uvs[3]])
                else:
                    # N-gon - fan triangulation
                    for i in range(1, len(face_uvs) - 1):
                        vertices.extend([face_uvs[0], face_uvs[i], face_uvs[i + 1]])

            return vertices

        except (ReferenceError, IndexError) as e:
            print(f"Stack overlay error: Invalid face reference: {e}")
            return []

    def _extract_border_edges(self, triangle_verts):
        """Extract unique border edges from triangulated vertices

        This finds the outer perimeter edges of a UV island by identifying
        edges that appear only once (not shared between triangles).

        Args:
            triangle_verts: List of vertex tuples [(x,y), ...] in groups of 3

        Returns:
            list: List of vertex tuples for line segments (pairs of vertices)
        """
        # Count edge occurrences
        edge_count = {}

        # Process triangles (every 3 vertices)
        for i in range(0, len(triangle_verts), 3):
            if i + 2 >= len(triangle_verts):
                break

            v0, v1, v2 = triangle_verts[i], triangle_verts[i+1], triangle_verts[i+2]

            # Create edges (normalize by sorting to make them undirected)
            edges = [
                tuple(sorted([v0, v1], key=lambda v: (v[0], v[1]))),
                tuple(sorted([v1, v2], key=lambda v: (v[0], v[1]))),
                tuple(sorted([v2, v0], key=lambda v: (v[0], v[1])))
            ]

            for edge in edges:
                edge_count[edge] = edge_count.get(edge, 0) + 1

        # Border edges appear only once (not shared)
        border_verts = []
        for edge, count in edge_count.items():
            if count == 1:
                # Add both vertices of the edge
                border_verts.extend(edge)

        return border_verts

    def build(self, context):
        """Build GPU batches from island shapes (ZenUV approach)

        This is the main build method that creates GPU batches from UV island data.
        Called when mark_build indicates a rebuild is needed.
        """
        # Reset build flag
        self.mark_build = 0

        # Clear cached data
        self.cached_batches.clear()
        self.mesh_data.clear()
        self.label_data.clear()

        # Clear highlight cache when geometry changes
        self.highlight_cached_batches.clear()
        self.highlight_cached_group_id = None

        # Get island shapes in UV coordinates (0-1)
        shapes = self.get_island_shapes(context)

        settings = context.scene.uvv_settings if hasattr(context.scene, 'uvv_settings') else None
        if not settings:
            return

        # Get shader
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        # Get overlay display settings
        show_fill = settings.stack_overlay_show_fill
        show_border = settings.stack_overlay_show_border
        show_labels = settings.stack_overlay_show_labels

        # Build batches in UV space (0-1), will transform during drawing
        # Also collect label positions if enabled (one label per island)
        for group_id, group_shapes in shapes.items():
            # Get group name for labels
            group_name = None
            obj = context.active_object
            if show_labels and obj:
                for sg in obj.uvv_stack_groups:
                    if sg.group_id == group_id:
                        group_name = sg.name
                        break

            for vertices, color in group_shapes:
                if len(vertices) < 3:
                    continue

                try:
                    # Keep vertices in UV space (0-1), convert Vector to tuple
                    verts_uv = [(v.x, v.y) for v in vertices]

                    # Calculate center of this island for label placement
                    if show_labels and group_name:
                        sum_x = sum(v[0] for v in verts_uv)
                        sum_y = sum(v[1] for v in verts_uv)
                        count = len(verts_uv)
                        island_center = (sum_x / count, sum_y / count)
                        # Store one label per island
                        self.label_data.append((group_name, island_center, color))

                    # Create fill batch if enabled
                    if show_fill:
                        batch_fill = batch_for_shader(
                            shader,
                            'TRIS',
                            {"pos": verts_uv}
                        )
                        self.cached_batches.append((batch_fill, color, 'FILL'))

                    # Create border batch if enabled
                    if show_border:
                        # Extract unique edges from triangles
                        border_edges = self._extract_border_edges(verts_uv)
                        if border_edges:
                            batch_border = batch_for_shader(
                                shader,
                                'LINES',
                                {"pos": border_edges}
                            )
                            # Make border slightly more opaque for visibility
                            border_color = (color[0], color[1], color[2], min(1.0, color[3] * 2.0))
                            self.cached_batches.append((batch_border, border_color, 'BORDER'))

                except Exception as e:
                    print(f"Stack overlay error: Failed to create batch: {e}")
                    continue

        # Cache mesh data for change detection (UUID approach)
        t_updates = bpy.app.driver_namespace.get(LITERAL_UVV_UPDATE, {})

        try:
            for obj in context.objects_in_mode_unique_data:
                if obj.type == 'MESH':
                    # Store current UUID state [geom_uuid, shade_uuid]
                    update_data = t_updates.get(obj.data, ['', ''])
                    # Make a copy of the list to avoid reference issues
                    self.mesh_data[obj.data] = [update_data[0], update_data[1]]
        except Exception as e:
            print(f"Stack overlay error: Failed to cache mesh data: {e}")


def draw_stack_overlay_callback(context):
    """GPU draw callback for stack overlays (ZenUV approach with state machine)"""

    # Check if overlay is enabled
    settings = context.scene.uvv_settings if hasattr(context.scene, 'uvv_settings') else None
    if not settings or not settings.stack_overlay_enabled:
        return

    # Only draw in UV Editor
    if context.area.type != 'IMAGE_EDITOR':
        return

    # Only draw in Edit Mode
    if context.mode != 'EDIT_MESH':
        return

    # Get region for coordinate transformation
    region = context.region
    if not region or not hasattr(region, 'view2d'):
        return

    # Get overlay manager
    manager = StackOverlayManager.instance()

    # PERFORMANCE OPTIMIZATION: Check if we need regular overlay batches
    # If only flash is enabled (no fill/border/labels), skip expensive builds
    need_regular_batches = (settings.stack_overlay_show_fill or
                           settings.stack_overlay_show_border or
                           settings.stack_overlay_show_labels)

    # Only run build/validation if we actually need regular overlay batches
    if need_regular_batches:
        # ZenUV state machine: Check if we need to build
        # mark_build: -1 = force build, 0 = clean (no build needed), 1 = needs rebuild
        if manager.mark_build:  # Any non-zero value (-1 or 1)
            # Need to build or force build
            if not is_modal_procedure(context):
                # Safe to build - no modal operation
                try:
                    manager.build(context)
                except Exception as e:
                    print(f"Stack overlay error: Failed to build: {e}")
                    return
            else:
                # Modal operation running - schedule delayed build
                manager._delayed_build()
                return  # Don't draw during modal ops
        elif not manager.check_valid_data(context):
            # mark_build is 0 but data changed - need delayed rebuild
            if not is_modal_procedure(context):
                manager._delayed_build()
            return  # Don't draw with invalid data

    # At this point, mark_build should be 0 and data should be valid
    batches = manager.cached_batches if need_regular_batches else []

    # Check for highlight feature
    settings = context.scene.uvv_settings if hasattr(context.scene, 'uvv_settings') else None
    obj = context.active_object
    has_highlight = (settings and
                     settings.stack_overlay_highlight_on_click and
                     obj and
                     obj.uvv_stack_groups_index >= 0 and
                     obj.uvv_stack_groups_index < len(obj.uvv_stack_groups))
    has_labels = (settings and
                  settings.stack_overlay_show_labels and
                  len(manager.label_data) > 0)

    # If no batches, no highlight, and no labels, nothing to draw
    if not batches and not has_highlight and not has_labels:
        return

    # Create transformation matrix (ZenUV approach)
    # This converts UV space (0-1) to screen space (pixels)
    from mathutils import Matrix

    uv_to_view = region.view2d.view_to_region
    width = region.width
    height = region.height

    # Get UV space corners in screen space
    origin_x, origin_y = uv_to_view(0.0, 0.0, clip=False)
    top_x, top_y = uv_to_view(1.0, 1.0, clip=False)
    axis_x = top_x - origin_x
    axis_y = top_y - origin_y

    # Build transformation matrix
    matrix = Matrix((
        [axis_x / width * 2, 0, 0, 2.0 * -((width - origin_x - 0.5 * width)) / width],
        [0, axis_y / height * 2, 0, 2.0 * -((height - origin_y - 0.5 * height)) / height],
        [0, 0, 1.0, 0],
        [0, 0, 0, 1.0]
    ))

    identity = Matrix.Identity(4)

    # Enable blending for transparency
    gpu.state.blend_set('ALPHA')

    # Get shader
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    try:
        # Draw all batches with matrix transformation
        with gpu.matrix.push_pop():
            gpu.matrix.load_matrix(matrix)

            with gpu.matrix.push_pop_projection():
                gpu.matrix.load_projection_matrix(identity)

                # Draw regular overlay batches (fills and borders based on settings)
                # Only if there are batches to draw
                if batches:
                    for batch_data in batches:
                        # Handle both old format (batch, color) and new format (batch, color, type)
                        if len(batch_data) == 2:
                            batch, color = batch_data
                            batch_type = 'FILL'
                        else:
                            batch, color, batch_type = batch_data

                        # Set line width for borders
                        if batch_type == 'BORDER':
                            gpu.state.line_width_set(2.0)

                        shader.bind()
                        shader.uniform_float("color", color)
                        batch.draw(shader)

                        # Reset line width
                        if batch_type == 'BORDER':
                            gpu.state.line_width_set(1.0)

                # Draw highlight for selected group (flash and/or permanent border)
                if has_highlight:
                    index = obj.uvv_stack_groups_index
                    selected_group = obj.uvv_stack_groups[index]

                    # Get highlight batches for selected group (cached for performance)
                    highlight_batches = manager.get_highlight_batches(context, selected_group.group_id)

                    if highlight_batches:
                        # Draw permanent border if enabled
                        if settings.stack_overlay_show_permanent_border:
                            gpu.state.line_width_set(4.0)
                            for batch, color in highlight_batches:
                                shader.bind()
                                shader.uniform_float("color", color)  # White
                                batch.draw(shader)
                            gpu.state.line_width_set(1.0)

                        # Draw flash effect on top if active
                        if manager.flash_active and manager.flash_start_time is not None:
                            import time
                            import math
                            elapsed = time.time() - manager.flash_start_time
                            fade_duration = manager.flash_duration  # Duration from settings

                            if elapsed < fade_duration:
                                # Normalized time (0.0 to 1.0)
                                t = elapsed / fade_duration

                                # === OPACITY ANIMATION ===
                                # Ease-out cubic for smooth fade: 1 - (1-t)^3
                                fade_alpha = 1.0 - (t * t * t)

                                # Draw flash with group's color (animated opacity, fixed thickness)
                                group_color = selected_group.color
                                flash_color = (group_color[0], group_color[1], group_color[2], fade_alpha)

                                # Use fixed border width from settings (no thickness animation)
                                gpu.state.line_width_set(settings.stack_overlay_flash_border_width)
                                for batch, _ in highlight_batches:
                                    shader.bind()
                                    shader.uniform_float("color", flash_color)
                                    batch.draw(shader)
                                gpu.state.line_width_set(1.0)

        # Draw labels if enabled (OUTSIDE matrix transform - in screen space)
        # This ensures text is drawn correctly without matrix transformations
        settings = context.scene.uvv_settings if hasattr(context.scene, 'uvv_settings') else None
        if settings and settings.stack_overlay_show_labels and manager.label_data:
            import blf

            font_id = 0
            blf.size(font_id, 14)

            # Prepare shader for background rectangles
            bg_shader = gpu.shader.from_builtin('UNIFORM_COLOR')

            for group_name, center_uv, color in manager.label_data:
                # Convert UV space (0-1) to screen space
                screen_x, screen_y = region.view2d.view_to_region(center_uv[0], center_uv[1], clip=False)

                # Only draw if label is visible in the viewport
                if 0 <= screen_x <= region.width and 0 <= screen_y <= region.height:
                    # Calculate text dimensions for centering
                    text_width, text_height = blf.dimensions(font_id, group_name)

                    # Color indicator square properties
                    color_square_size = 12
                    color_square_gap = 4
                    padding = 4

                    # Calculate total width including color square
                    total_content_width = color_square_size + color_square_gap + text_width

                    # Background rectangle dimensions
                    bg_x = screen_x - total_content_width / 2 - padding
                    bg_y = screen_y - text_height / 2 - padding
                    bg_width = total_content_width + padding * 2
                    bg_height = text_height + padding * 2

                    # Draw semi-transparent background rectangle
                    bg_vertices = [
                        (bg_x, bg_y),
                        (bg_x + bg_width, bg_y),
                        (bg_x + bg_width, bg_y + bg_height),
                        (bg_x, bg_y + bg_height)
                    ]

                    # Create two triangles for the rectangle
                    bg_indices = [(0, 1, 2), (0, 2, 3)]
                    bg_triangle_verts = []
                    for tri in bg_indices:
                        for idx in tri:
                            bg_triangle_verts.append(bg_vertices[idx])

                    # Draw background with semi-transparent dark color
                    bg_batch = batch_for_shader(bg_shader, 'TRIS', {"pos": bg_triangle_verts})
                    bg_shader.bind()
                    bg_shader.uniform_float("color", (0.0, 0.0, 0.0, 0.7))  # Dark semi-transparent
                    bg_batch.draw(bg_shader)

                    # Draw colored square indicator (group color)
                    color_square_x = screen_x - total_content_width / 2
                    color_square_y = screen_y - color_square_size / 2

                    color_square_verts = [
                        (color_square_x, color_square_y),
                        (color_square_x + color_square_size, color_square_y),
                        (color_square_x + color_square_size, color_square_y + color_square_size),
                        (color_square_x, color_square_y + color_square_size)
                    ]

                    color_square_triangle_verts = []
                    for tri in bg_indices:
                        for idx in tri:
                            color_square_triangle_verts.append(color_square_verts[idx])

                    # Draw color square with full opacity group color
                    color_batch = batch_for_shader(bg_shader, 'TRIS', {"pos": color_square_triangle_verts})
                    bg_shader.bind()
                    bg_shader.uniform_float("color", (color[0], color[1], color[2], 1.0))
                    color_batch.draw(bg_shader)

                    # Draw text in white for maximum contrast
                    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)

                    # Position text after the color square
                    text_x = color_square_x + color_square_size + color_square_gap
                    text_y = screen_y - text_height / 2

                    blf.position(font_id, text_x, text_y, 0)
                    blf.draw(font_id, group_name)

    except Exception as e:
        print(f"Stack overlay error: Failed to draw overlays: {e}")
    finally:
        # Restore state
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')


def delayed_rebuild_timer():
    """Timer callback to rebuild overlay after transform stops (ZenUV approach)

    This is called after a short delay when updates stop, allowing transforms
    to complete before rebuilding the overlay.
    """
    global _pending_rebuild, _rebuild_timer

    try:
        manager = StackOverlayManager.instance()
        if manager.enabled and _pending_rebuild:
            # Mark for rebuild on next draw (not forced, just needed)
            if not manager.mark_build:
                manager.mark_build = 1

            # Tag UV editors for redraw
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        area.tag_redraw()

        _pending_rebuild = False
        _rebuild_timer = None

    except Exception as e:
        # Silently fail
        pass

    # Return None to unregister timer
    return None


def flash_redraw_timer():
    """Timer callback to continuously trigger redraws during flash animation
    
    This ensures smooth animation even when the viewport is still.
    Runs at ~60 FPS during the animation period.
    """
    try:
        manager = StackOverlayManager.instance()
        
        # Check if flash is still active and animation hasn't completed
        if manager.flash_active and manager.flash_start_time is not None:
            import time
            elapsed = time.time() - manager.flash_start_time
            fade_duration = manager.flash_duration  # Duration from settings
            
            if elapsed < fade_duration:
                # Animation still in progress - trigger redraw
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'IMAGE_EDITOR':
                            area.tag_redraw()
                
                # Continue timer at 60 FPS
                return 0.016
            else:
                # Animation completed - stop redraw timer
                manager.flash_redraw_timer = None
                return None
        else:
            # Flash no longer active - stop redraw timer
            manager.flash_redraw_timer = None
            return None
    except Exception:
        return None


def clear_flash_timer():
    """Timer callback to clear the flash effect after 1 second"""
    try:
        manager = StackOverlayManager.instance()
        manager.flash_active = False
        manager.flash_start_time = None
        
        # Stop redraw timer if still running
        if manager.flash_redraw_timer is not None:
            try:
                if bpy.app.timers.is_registered(manager.flash_redraw_timer):
                    bpy.app.timers.unregister(manager.flash_redraw_timer)
            except:
                pass
            manager.flash_redraw_timer = None
        
        manager.flash_timer = None

        # Tag UV editors for redraw to remove flash
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()
    except Exception:
        pass

    # Return None to unregister timer
    return None


def depsgraph_update_handler(scene):
    """Handle depsgraph updates to track mesh changes (ZenUV UUID approach)

    Tracks both geometry (topology) and shading (UV coordinates) changes using
    unique UUIDs per update. This is more reliable than counters and matches
    ZenUV's approach exactly.
    """
    global _pending_rebuild, _rebuild_timer

    try:
        ctx = bpy.context
        if not ctx:
            return

        depsgraph = ctx.evaluated_depsgraph_get()
        if not depsgraph:
            return

        manager = StackOverlayManager.instance()
        if not manager.enabled:
            return

        # Get or create update tracking dict in shared namespace
        t_updates = bpy.app.driver_namespace.get(LITERAL_UVV_UPDATE, {})
        updates_found = False

        # Track geometry and shading updates per mesh (like ZenUV)
        for update in depsgraph.updates:
            if not isinstance(update.id, bpy.types.Mesh):
                continue

            # Check for geometry or shading updates
            b_geom = update.is_updated_geometry
            b_shade = update.is_updated_shading

            if b_geom or b_shade:
                updates_found = True

                # Generate unique UUID for this update
                s_uuid = str(uuid.uuid4())

                # Get or create update data for this mesh [geom_uuid, shade_uuid]
                p_data = t_updates.get(update.id.original, ['', ''])

                # Update UUIDs for changed data
                if b_geom:
                    p_data[0] = s_uuid
                if b_shade:
                    p_data[1] = s_uuid

                t_updates[update.id.original] = p_data

        # Store updated dict back to namespace
        if updates_found:
            bpy.app.driver_namespace[LITERAL_UVV_UPDATE] = t_updates

            # PERFORMANCE OPTIMIZATION: Only trigger rebuild if we need regular batches
            # Check settings to see if fill/border/labels are enabled
            scene = ctx.scene
            settings = scene.uvv_settings if hasattr(scene, 'uvv_settings') else None
            need_regular_batches = settings and (settings.stack_overlay_show_fill or
                                                settings.stack_overlay_show_border or
                                                settings.stack_overlay_show_labels)

            if need_regular_batches:
                # Cancel existing timer if present
                if _rebuild_timer is not None and bpy.app.timers.is_registered(_rebuild_timer):
                    bpy.app.timers.unregister(_rebuild_timer)

                # Always delay rebuild - this allows modal operations to complete
                # The draw callback will check is_modal_procedure() before building
                # Use slightly longer delay to reduce rebuild frequency and warnings
                _pending_rebuild = True
                _rebuild_timer = delayed_rebuild_timer
                bpy.app.timers.register(_rebuild_timer, first_interval=0.2)

                # Also clear highlight cache when regular batches are being rebuilt
                # (highlight shares the same island data)
                manager.highlight_cached_batches.clear()
                manager.highlight_cached_group_id = None

    except Exception as e:
        # Silently fail to avoid breaking Blender
        pass


def update_stack_overlay_state(self, context):
    """Update callback when overlay enabled state changes"""
    manager = StackOverlayManager.instance()

    if self.stack_overlay_enabled:
        manager.enable(context)
        register_depsgraph_handler()
    else:
        manager.disable(context)
        unregister_depsgraph_handler()


# Module-level functions for external access
def enable_overlay(context, force=False):
    """Enable stack overlay
    
    Args:
        context: Blender context
        force: If True, force re-registration (for reloads)
    """
    StackOverlayManager.instance().enable(context, force=force)


def disable_overlay(context):
    """Disable stack overlay"""
    StackOverlayManager.instance().disable(context)


def refresh_overlay():
    """Refresh stack overlay by marking it for rebuild"""
    manager = StackOverlayManager.instance()
    if manager.enabled:
        manager.mark_build = 1  # Mark for rebuild on next draw

        # Tag UV editors for redraw
        if bpy.context:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        area.tag_redraw()


def is_overlay_enabled():
    """Check if overlay is enabled"""
    return StackOverlayManager.instance().enabled


def register_depsgraph_handler():
    """Register depsgraph update handler"""
    global _depsgraph_handler

    if _depsgraph_handler is not None:
        return  # Already registered

    if depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_handler)
        _depsgraph_handler = depsgraph_update_handler


def unregister_depsgraph_handler():
    """Unregister depsgraph update handler"""
    global _depsgraph_handler, _rebuild_timer, _pending_rebuild

    if _depsgraph_handler is None:
        return  # Not registered

    # Cancel any pending rebuild timer
    if _rebuild_timer is not None:
        try:
            if bpy.app.timers.is_registered(_rebuild_timer):
                bpy.app.timers.unregister(_rebuild_timer)
        except:
            pass
        _rebuild_timer = None
    _pending_rebuild = False

    if depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_handler)
        _depsgraph_handler = None


# === Stack Group Selection Msgbus System ===

def stack_group_selection_changed():
    """Called when uvv_stack_groups_index changes"""
    try:
        context = bpy.context
        if not context.scene:
            return

        settings = context.scene.uvv_settings

        # Only trigger highlight if feature is enabled
        if not settings.stack_overlay_enabled or not settings.stack_overlay_highlight_on_click:
            return

        # Get selected group from active object
        obj = context.active_object
        if not obj:
            return
        
        index = obj.uvv_stack_groups_index
        if index < 0 or index >= len(obj.uvv_stack_groups):
            return

        selected_group = obj.uvv_stack_groups[index]

        # Trigger flash effect
        manager = StackOverlayManager.instance()
        if manager.enabled:
            manager.trigger_flash(context)

    except Exception as e:
        print(f"Stack group selection error: {e}")


def register_selection_msgbus():
    """Register msgbus subscription for stack group selection changes"""
    global _selection_msgbus_owner

    # Always unregister first to ensure clean state (fixes issues on script reload)
    if _selection_msgbus_owner is not None:
        try:
            bpy.msgbus.clear_by_owner(_selection_msgbus_owner)
        except:
            pass  # Ignore errors if already cleared
        _selection_msgbus_owner = None

    # Create owner object for msgbus
    _selection_msgbus_owner = object()

    # Subscribe to uvv_stack_groups_index changes on Object type
    # Note: This will notify for all objects, but stack_group_selection_changed checks the active object
    try:
        bpy.msgbus.subscribe_rna(
            key=(bpy.types.Object, "uvv_stack_groups_index"),
            owner=_selection_msgbus_owner,
            args=(),
            notify=stack_group_selection_changed,
        )
    except Exception as e:
        # If property not ready yet (during initial registration), schedule delayed registration
        print(f"UVV: msgbus registration delayed, will retry: {e}")
        _selection_msgbus_owner = None
        bpy.app.timers.register(delayed_msgbus_registration, first_interval=0.1)


def delayed_msgbus_registration():
    """Delayed msgbus registration for cases where properties aren't ready yet"""
    try:
        register_selection_msgbus()
    except Exception as e:
        # If still not ready, try once more after a longer delay
        print(f"UVV: msgbus registration still delayed, will retry once more: {e}")
        bpy.app.timers.register(delayed_msgbus_registration, first_interval=0.5)
        return None
    return None  # One-shot timer


def unregister_selection_msgbus():
    """Unregister msgbus subscription for stack group selection changes"""
    global _selection_msgbus_owner

    if _selection_msgbus_owner is None:
        return  # Not registered

    # Clear all subscriptions for this owner
    bpy.msgbus.clear_by_owner(_selection_msgbus_owner)
    _selection_msgbus_owner = None
