"""
🌀 UVV - Universal UV Toolkit
A collection of UV tools for Blender 4.4+
"""

bl_info = {
    "name": "🌀 UVV - Universal UV Toolkit",
    "author": "UVV Team",
    "version": (0, 0, 8),
    "blender": (4, 2, 0),
    "location": "UV Editor > Sidebar (N panel)",
    "description": "Universal UV Toolkit with texel density tools, UV sync controls, and seam operations",
    "warning": "",
    "doc_url": "",
    "category": "UV",
}

# Version constant for easy access
__version__ = "0.0.8"

import bpy

# Reload modules when addon is reloaded (F3 -> Reload Scripts)
if "bpy" in locals():
    import importlib

    # Reload in dependency order: types -> utils -> properties -> operators (with submodules) -> tools -> ui
    if "types" in locals():
        importlib.reload(types)
    if "utils" in locals():
        importlib.reload(utils)
    if "properties" in locals():
        importlib.reload(properties)

    # Reload operator submodules first, then the operators module
    if "operators" in locals():
        from . import operators as ops_module
        for submodule_name in ['uv_sync', 'texel_density', 'seam_ops', 'transform_ops', 'gridify_normalize', 'placeholders', 'optimize_scale', 'world_orient', 'orient', 'select_ops', 'stack_ops', 'straighten', 'trimsheet_create', 'trimsheet_ops', 'trimsheet_from_plane', 'trimsheet_transform', 'trimsheet_debug', 'auto_unwrap', 'uv_shift', 'merge_unwrap', 'triplanar_mapping', 'unwrap_inplace', 'pack_presets', 'random_transform']:
            if hasattr(ops_module, submodule_name):
                importlib.reload(getattr(ops_module, submodule_name))
        importlib.reload(operators)

    if "tools" in locals():
        importlib.reload(tools)

    # Reload UI submodules first, then the ui module
    if "ui" in locals():
        from . import ui as ui_module
        for submodule_name in ['menus', 'trimsheet_panel', 'viewport_3d_panel']:
            if hasattr(ui_module, submodule_name):
                importlib.reload(getattr(ui_module, submodule_name))
        importlib.reload(ui)

    # Reload checker submodules
    if "checker" in locals():
        from . import checker as checker_module
        for submodule_name in ['get_prefs', 'checker_labels', 'files', 'checker', 'darken_image', 'display_modes', 'gizmo_draw', 'texel_calculator']:
            if hasattr(checker_module, submodule_name):
                importlib.reload(getattr(checker_module, submodule_name))
        importlib.reload(checker)

    # Reload gizmos submodules
    if "gizmos" in locals():
        importlib.reload(gizmos)

# Import modules
from . import types
from . import utils
from . import properties
from . import operators
from . import tools
from . import ui
from . import checker
from . import gizmos

import os
import bpy.utils.previews

# Global variable for stack groups menu timer
_stack_groups_menu_timer = None

# Global icon collections like UV Toolkit
icons_collections = {}

def load_icons():
    """Load icons for the addon"""
    import bpy

    # Create new previews collection
    pcoll = bpy.utils.previews.new()

    # Path to icons folder - icons are directly in UVV/icons
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    icons_dir = os.path.abspath(icons_dir)

    # Load existing icons
    # Try both naming conventions (with and without -24 suffix)
    td_get_path = os.path.join(icons_dir, "td_get.png")
    if not os.path.exists(td_get_path):
        td_get_path = os.path.join(icons_dir, "td-get-24.png")

    td_set_path = os.path.join(icons_dir, "td_set.png")
    if not os.path.exists(td_set_path):
        td_set_path = os.path.join(icons_dir, "td-set-24.png")

    seam_brush_path = os.path.join(icons_dir, "seam-brush-24.png")

    if os.path.exists(td_get_path):
        pcoll.load("td_get", td_get_path, 'IMAGE')

    if os.path.exists(td_set_path):
        pcoll.load("td_set", td_set_path, 'IMAGE')

    if os.path.exists(seam_brush_path):
        pcoll.load("seam_brush", seam_brush_path, 'IMAGE')

    # Load new Mio3 icons
    icon_files = [
        ("relax", "relax.png"),
        ("grid", "grid.png"),
        ("normalize", "normalize.png"),
        ("straight", "straight.png"),
        ("seam", "seam.png"),
        ("stitch", "stitch.png"),
        ("z", "z.png"),
        ("align_top", "align_top.png"),
        ("align_bottom", "align_bottom.png"),
        ("align_left", "align_left.png"),
        ("align_right", "align_right.png"),
        ("align_center", "align_center.png"),
        ("align_center_h", "align_center_h.png"),
        ("align_center_v", "align_center_v.png"),
        ("rotate_transform", "rotate_transform.png"),
        ("flip_h", "flip_h.png"),
        ("flip_v", "flip_v.png"),
        ("p90", "p90.png"),
        ("n90", "n90.png"),
        ("p180", "p180.png"),
        ("cube", "cube.png"),
        ("stack", "stack.png"),
        ("arrow_left", "arrow_left.png"),
        ("arrow_right", "arrow_right.png"),
        ("arrow_top", "arrow_top.png"),
        ("arrow_bot", "arrow_bot.png"),
        ("split_uv", "split_uv.png"),
        ("match_stitch", "match_stitch.png"),
        ("settings", "settings.png"),
        ("isolate_islands", "isolate_islands.png"),
        ("auto_unwrap", "auto_unwrap.png"),
        ("unwrap", "unwrap.png"),
        ("merge_unwrap", "merge_unwrap.png"),
        ("pack", "pack.png"),
        ("texture", "texture.png"),
        ("orient", "orient.png"),
        ("stretched", "stretched.png"),
        ("flipped", "flipped.png"),
        ("quadrify", "quadrify.png"),
        ("add_trim_plane", "add_trim_plane.png"),
        ("edit_trim_plane", "edit_trim_plane.png"),
        ("trim_set", "trim_set.png"),
        ("lock", "lock.png"),
        ("unlocked", "unlocked.png"),
        ("accept", "accept.png"),
        ("3d_plane", "3d_plane.png"),
        ("trim_rect", "trim_rect.png"),
        ("trim_circle", "trim_circle.png"),
        ("smart_pack_trim", "smart_pack_trim.png"),
        ("add_trim", "add_trim.png"),
        ("add_trim_circle", "add_trim_circle.png"),
        ("fit_trim", "fit_trim.png"),
        ("remove_trim", "remove_trim.png"),
        ("overlay_trim", "overlay_trim.png"),
        ("darken", "darken.png"),
        ("uv_checker_thumbnail", "uv_checker_thumbnail.png"),
        ("uv_checker_thumbnail_blendergrid", "uv_checker_thumbnail_blendergrid.png"),
        ("uv_checker_thumbnail_blendercolorgrid", "uv_checker_thumbnail_blendercolorgrid.png"),
        ("uv_checker_thumbnail_arrowgrid", "uv_checker_thumbnail_arrowgrid.png"),
        ("debug_uvs", "debug_uvs.png"),
        ("import", "import.png"),
        ("export", "export.png"),
        ("straighten", "straighten.png"),
        ("parallel_constraint", "parallel_constraint.png"),
        ("horizontal_constraint", "horizontal_constraint.png"),
        ("vertical_constraint", "vertical_constraint.png"),
        ("stack_primaries", "Stack_Primaries.png"),
        ("stack_replicas", "Stack_Replicas.png"),
        ("stack_singles", "Stack_Singles.png"),
        ("stack_selected", "stack_selected.png"),
        ("camera_unwrap", "camera_unwrap.png"),
        ("triplanar", "triplanar.png"),
        ("uvpackmaster", "uvpackmaster.png"),
        ("blender", "blender.png"),
        ("auto_group", "auto_group.png"),
        ("add", "add.png"),
        ("select", "select.png"),
        ("add_stack", "add_stack.png"),
        ("select_stack", "select_stack.png"),
        ("remove_stack", "remove_stack.png"),
        ("assign_stack", "assign_stack.png"),
        ("delete_stack", "delete_stack.png"),
        ("random", "random.png"),
    ]

    for icon_id, filename in icon_files:
        icon_path = os.path.join(icons_dir, filename)
        if os.path.exists(icon_path):
            pcoll.load(icon_id, icon_path, 'IMAGE')

    # Store in global collection like UV Toolkit
    icons_collections["main"] = pcoll

def unload_icons():
    """Unload icons"""
    for pcoll in icons_collections.values():
        bpy.utils.previews.remove(pcoll)
    icons_collections.clear()

def get_icons_set():
    """Get icon collection for UI - UV Toolkit style"""
    return icons_collections.get("main")


# Module registration
modules = [
    properties,
    operators,
    tools,
    ui,
    checker,
    gizmos,
]


def register():
    """Register all addon classes and properties"""
    print("Registering UVV addon...")

    # Load icons first
    load_icons()

    for module in modules:
        if hasattr(module, 'register'):
            module.register()

    # Register workspace tools after everything else is loaded
    try:
        from . import tools
        if hasattr(tools, 'register_tools'):
            tools.register_tools()
        else:
            print("UVV: register_tools function not found in tools module")
    except ImportError as e:
        print(f"UVV: Failed to import tools module: {e}")
    except Exception as e:
        print(f"UVV: Failed to register tools: {e}")

    # Register transform draw handler
    try:
        from .utils import trimsheet_transform_draw
        trimsheet_transform_draw.register_draw_handler()
    except Exception as e:
        print(f"UVV: Failed to register transform draw handler: {e}")

    # Register trimsheet draw handler
    try:
        from .utils import trimsheet_draw
        trimsheet_draw.register_draw_handler()
    except Exception as e:
        print(f"UVV: Failed to register trimsheet draw handler: {e}")

    # Register depsgraph update handler for automatic gizmo updates (Zen UV pattern)
    try:
        from .checker import gizmo_draw
        if gizmo_draw.uvv_depsgraph_ui_update not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(gizmo_draw.uvv_depsgraph_ui_update)
        print("UVV: Depsgraph handler registered")
    except Exception as e:
        print(f"UVV: Failed to register depsgraph handler: {e}")

    # Register keymaps for pie menu
    try:
        from .ui import keymap
        keymap.register()
        print("UVV: Keymaps registered")
    except Exception as e:
        print(f"UVV: Failed to register keymaps: {e}")

    # Initialize stack overlay system (persistent handler approach)
    try:
        from .utils.stack_overlay import (
            update_stack_overlay_state,
            StackOverlayManager
        )

        # Reset singleton instance to ensure clean state after reload
        StackOverlayManager._instance = None

        # Global variable to track if we've initialized the current scene
        _stack_overlay_initialized_scenes = set()

        def stack_overlay_load_handler(dummy):
            """Ensure stack overlay is initialized when files are loaded or scenes change"""
            try:
                if not bpy.context or not bpy.context.scene:
                    return

                scene = bpy.context.scene
                scene_id = id(scene)  # Use object id to track scenes

                # Check if we've already initialized this scene
                if scene_id in _stack_overlay_initialized_scenes:
                    return

                # Check if scene has uvv_settings
                if not hasattr(scene, 'uvv_settings'):
                    return

                settings = scene.uvv_settings

                # If overlay is enabled, manually trigger the update callback
                # This ensures initialization happens even though the property
                # was set to its default value (and update callback didn't fire)
                if settings.stack_overlay_enabled:
                    # Call the update callback directly to initialize
                    update_stack_overlay_state(settings, bpy.context)
                    print(f"UVV: Stack overlay initialized for scene '{scene.name}'")

                    # Mark this scene as initialized
                    _stack_overlay_initialized_scenes.add(scene_id)

            except Exception as e:
                print(f"UVV: Failed to initialize stack overlay: {e}")
                import traceback
                traceback.print_exc()

        # Register load_post handler (fires when .blend files are loaded)
        if stack_overlay_load_handler not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(stack_overlay_load_handler)
            print("UVV: Stack overlay load_post handler registered")

        # Also use a delayed timer to catch the initial registration case
        # This handles: addon enable, addon reload, new Blender session
        def delayed_init():
            _stack_overlay_initialized_scenes.clear()  # Reset tracking on registration
            stack_overlay_load_handler(None)
            return None  # One-shot timer

        bpy.app.timers.register(delayed_init, first_interval=0.1)

    except Exception as e:
        print(f"UVV: Failed to setup stack overlay system: {e}")
        import traceback
        traceback.print_exc()

    # Register handler to auto-collapse/expand trims menu based on trim count
    try:
        global _last_trims_state, _update_trims_menu_collapse
        _last_trims_state = [None, None, 0]  # [object_id, material_id, trim_count] - Use list to allow modification

        def _update_trims_menu_collapse():
            """Check active material and collapse/expand menu based on trim count"""
            try:
                context = bpy.context
                if not context or not context.scene:
                    return 0.5  # Return interval to keep timer running

                obj = context.active_object
                current_obj_id = id(obj) if obj else None

                # Get active material
                material = None
                if obj and obj.type == 'MESH':
                    material = obj.active_material
                current_material_id = id(material) if material else None

                # Check if material has trims
                has_trims = False
                trim_count = 0
                if material and hasattr(material, 'uvv_trims'):
                    trim_count = len(material.uvv_trims)
                    has_trims = trim_count > 0

                # Check if state changed (object, material, or trim count)
                last_obj_id, last_material_id, last_trim_count = _last_trims_state
                state_changed = (current_obj_id != last_obj_id or
                               current_material_id != last_material_id or
                               trim_count != last_trim_count)

                if state_changed:
                    _last_trims_state[0] = current_obj_id
                    _last_trims_state[1] = current_material_id
                    _last_trims_state[2] = trim_count

                    settings = context.scene.uvv_settings
                    if not settings:
                        return 0.5

                    # Collapse menu if no trims exist, expand if trims were just added
                    if not has_trims:
                        settings.show_trims_list = False
                    elif last_trim_count == 0 and trim_count > 0:
                        # Trims were just added - auto-expand
                        settings.show_trims_list = True

                    # Tag UI for redraw
                    for window in context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type == 'IMAGE_EDITOR':
                                area.tag_redraw()

                return 0.5  # Return interval to keep timer running

            except Exception:
                return 0.5  # Return interval even on error to keep timer running

        # Register as a timer that runs frequently (every 0.5 seconds)
        if not bpy.app.timers.is_registered(_update_trims_menu_collapse):
            bpy.app.timers.register(_update_trims_menu_collapse, persistent=True)
            print("UVV: Trims menu collapse/expand handler registered")
    except Exception as e:
        print(f"UVV: Failed to register trims menu handler: {e}")

    # Register handler to auto-collapse stack groups menu when no groups exist
    try:
        _last_stack_groups_state = [None, 0]  # [object_id, group_count] - Use list to allow modification

        def update_stack_groups_menu_collapse():
            """Check active object and collapse menu if no stack groups exist"""
            try:
                context = bpy.context
                if not context or not context.scene:
                    return

                obj = context.active_object
                current_obj_id = id(obj) if obj else None

                # Check if active object has stack groups
                has_stack_groups = False
                group_count = 0
                if obj and obj.type == 'MESH' and hasattr(obj, 'uvv_stack_groups'):
                    group_count = len(obj.uvv_stack_groups)
                    has_stack_groups = group_count > 0

                # Check if state changed (object or group count)
                last_obj_id, last_group_count = _last_stack_groups_state
                state_changed = (current_obj_id != last_obj_id or group_count != last_group_count)

                if state_changed:
                    _last_stack_groups_state[0] = current_obj_id
                    _last_stack_groups_state[1] = group_count

                    settings = context.scene.uvv_settings
                    if not settings:
                        return

                    # Collapse menu if no groups exist (but don't force expand if groups exist - let user control)
                    if not has_stack_groups:
                        settings.show_stack_groups_list = False

                    # Tag UI for redraw
                    for window in context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type == 'IMAGE_EDITOR':
                                area.tag_redraw()

            except Exception:
                pass  # Silently fail to avoid breaking Blender
        
        # Register timer to check periodically (every 0.3 seconds)
        def check_stack_groups_menu():
            update_stack_groups_menu_collapse()
            return 0.3  # Run every 0.3 seconds
        
        # Store reference for unregistration
        global _stack_groups_menu_timer
        _stack_groups_menu_timer = check_stack_groups_menu
        
        bpy.app.timers.register(_stack_groups_menu_timer, first_interval=0.3)
        print("UVV: Stack groups menu collapse handler registered")
    except Exception as e:
        print(f"UVV: Failed to register stack groups menu handler: {e}")

    print("UVV addon registered successfully!")
    
    # Trigger automatic version check after a short delay
    try:
        from .utils.version_check import auto_check_for_updates
        bpy.app.timers.register(auto_check_for_updates, first_interval=0.5)
        print("UVV: Automatic version check scheduled")
    except Exception as e:
        print(f"UVV: Failed to schedule version check: {e}")


def unregister():
    """Unregister all addon classes and properties"""
    print("Unregistering UVV addon...")

    # CRITICAL: Unregister workspace tools FIRST before anything else
    # This prevents crashes from old tool keymaps trying to invoke freed operators
    try:
        from . import tools
        if hasattr(tools, 'unregister_tools'):
            tools.unregister_tools()
            print("UVV: Workspace tools unregistered")
        else:
            print("UVV: unregister_tools function not found in tools module")
    except ImportError as e:
        print(f"UVV: Failed to import tools module: {e}")
    except Exception as e:
        print(f"UVV: Failed to unregister tools: {e}")

    # Cleanup checker mode handler (msgbus subscription)
    try:
        from .checker import checker_mode_handler
        checker_mode_handler.cleanup()
        print("UVV: Checker mode handler cleaned up")
    except Exception as e:
        print(f"UVV: Failed to cleanup checker mode handler: {e}")

    # Unregister keymaps
    try:
        from .ui import keymap
        keymap.unregister()
        print("UVV: Keymaps unregistered")
    except Exception as e:
        print(f"UVV: Failed to unregister keymaps: {e}")

    # Unregister depsgraph handler first (Zen UV pattern)
    try:
        from .checker import gizmo_draw
        if gizmo_draw.uvv_depsgraph_ui_update in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(gizmo_draw.uvv_depsgraph_ui_update)
        print("UVV: Depsgraph handler unregistered")
    except Exception as e:
        print(f"UVV: Failed to unregister depsgraph handler: {e}")

    # Unregister draw handlers
    try:
        from .utils import trimsheet_draw
        trimsheet_draw.unregister_draw_handler()
    except Exception as e:
        print(f"UVV: Failed to unregister trimsheet draw handler: {e}")

    try:
        from .utils import trimsheet_transform_draw
        trimsheet_transform_draw.unregister_draw_handler()
    except Exception as e:
        print(f"UVV: Failed to unregister transform draw handler: {e}")

    # Unregister stack overlay system
    try:
        from .utils.stack_overlay import disable_overlay, unregister_depsgraph_handler

        # Disable overlay if context available
        if bpy.context:
            disable_overlay(bpy.context)

        # Unregister depsgraph handler
        unregister_depsgraph_handler()

        # Unregister load_post handler
        handlers_to_remove = []
        for handler in bpy.app.handlers.load_post:
            if hasattr(handler, '__name__') and 'stack_overlay_load_handler' in handler.__name__:
                handlers_to_remove.append(handler)

        for handler in handlers_to_remove:
            bpy.app.handlers.load_post.remove(handler)

        print("UVV: Stack overlay system unregistered")
    except Exception as e:
        print(f"UVV: Failed to unregister stack overlay system: {e}")

    # Unregister trims menu collapse/expand timer
    try:
        global _update_trims_menu_collapse
        if '_update_trims_menu_collapse' in globals() and _update_trims_menu_collapse is not None:
            if bpy.app.timers.is_registered(_update_trims_menu_collapse):
                bpy.app.timers.unregister(_update_trims_menu_collapse)
                print("UVV: Trims menu collapse/expand timer unregistered")
    except Exception as e:
        print(f"UVV: Failed to unregister trims menu timer: {e}")

    # Unregister stack groups menu collapse timer
    try:
        global _stack_groups_menu_timer
        if '_stack_groups_menu_timer' in globals() and _stack_groups_menu_timer is not None:
            if bpy.app.timers.is_registered(_stack_groups_menu_timer):
                bpy.app.timers.unregister(_stack_groups_menu_timer)
            _stack_groups_menu_timer = None
            print("UVV: Stack groups menu collapse timer unregistered")
    except Exception as e:
        print(f"UVV: Failed to unregister stack groups menu timer: {e}")

    # Unregister modules
    for module in reversed(modules):
        if hasattr(module, 'unregister'):
            module.unregister()

    # Unload icons last
    unload_icons()

    print("UVV addon unregistered successfully!")


if __name__ == "__main__":
    register()