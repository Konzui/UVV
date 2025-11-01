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
        for submodule_name in ['uv_sync', 'texel_density', 'seam_ops', 'transform_ops', 'gridify_normalize', 'placeholders', 'optimize_scale', 'world_orient', 'orient', 'select_ops', 'stack_ops', 'straighten', 'trimsheet_create', 'trimsheet_ops', 'trimsheet_from_plane', 'trimsheet_transform', 'trimsheet_debug', 'auto_unwrap', 'uv_shift', 'merge_unwrap', 'triplanar_mapping', 'unwrap_inplace', 'pack_presets']:
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
        ("accept", "accept.png"),
        ("3d_plane", "3d_plane.png"),
        ("trim_rect", "trim_rect.png"),
        ("trim_circle", "trim_circle.png"),
        ("smart_pack_trim", "smart_pack_trim.png"),
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

    # Cleanup checker mode handler (msgbus subscription)
    try:
        from .checker import checker_mode_handler
        checker_mode_handler.cleanup()
        print("UVV: Checker mode handler cleaned up")
    except Exception as e:
        print(f"UVV: Failed to cleanup checker mode handler: {e}")

    # Unregister keymaps first
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

    # Unregister workspace tools
    try:
        from . import tools
        if hasattr(tools, 'unregister_tools'):
            tools.unregister_tools()
        else:
            print("UVV: unregister_tools function not found in tools module")
    except ImportError as e:
        print(f"UVV: Failed to import tools module: {e}")
    except Exception as e:
        print(f"UVV: Failed to unregister tools: {e}")

    for module in reversed(modules):
        if hasattr(module, 'unregister'):
            module.unregister()

    # Unload icons last
    unload_icons()

    print("UVV addon unregistered successfully!")


if __name__ == "__main__":
    register()