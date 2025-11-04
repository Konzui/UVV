# UVV Operators package

from . import uv_sync
from . import texel_density
from . import pack_presets
from . import seam_operations
from . import weld_univ
from . import weld_complete
from . import stitch_univ
from . import transform_ops
from . import gridify_normalize
from . import placeholders
from . import world_orient
from . import orient
from . import select_ops
from . import pack_ops
from . import quadrify
from . import stack_ops
from . import trimsheet_create
from . import trimsheet_ops
from . import trimsheet_from_plane
from . import trimsheet_transform
from . import trimsheet_edit_transform
from . import trimsheet_hover_handler
from . import trimsheet_tool_modal
from . import auto_unwrap
from . import uv_shift
from . import merge_unwrap
from . import triplanar_mapping
from . import unwrap_inplace
from . import unwrap_inplace_view3d
from . import project_unwrap
from . import parallel_constraint
from . import straighten
from . import constraint_ops
from . import relax_univ  # UniV-style relax operator
from . import preferences_ops  # Preferences and hotkey operators
from . import split_uv  # Split UV operator
from . import random_transform  # Random transform operator
from . import td_operators  # Texel density operators (manual update, presets)

# Optional imports - may not exist
try:
    from . import test_transform  # Test operator for transformation functions
except Exception as e:
    print(f"[INFO] test_transform not available: {e}")
    test_transform = None

try:
    from . import debug_weld  # Debug operator for weld analysis
except Exception as e:
    print(f"[INFO] debug_weld not available: {e}")
    debug_weld = None

try:
    from . import optimize_scale
except Exception as e:
    print(f"[ERROR] Failed to import optimize_scale: {e}")
    import traceback
    traceback.print_exc()
    optimize_scale = None

# Collect all classes from submodules
classes = []
classes.extend(uv_sync.classes)
classes.extend(texel_density.classes)
classes.extend(pack_presets.classes)
classes.extend(seam_operations.classes)
classes.extend(weld_univ.classes)
classes.extend(weld_complete.classes)
classes.extend(stitch_univ.classes)
classes.extend(transform_ops.classes)
classes.extend(gridify_normalize.classes)
classes.extend(placeholders.classes)
classes.extend(world_orient.classes)
classes.extend(orient.classes)
classes.extend(select_ops.classes)
classes.extend(pack_ops.classes)
classes.extend(quadrify.classes)
classes.extend(stack_ops.classes)
classes.extend(trimsheet_create.classes)
classes.extend(trimsheet_ops.classes)
classes.extend(trimsheet_from_plane.classes)
classes.extend(trimsheet_transform.classes)
classes.extend(trimsheet_edit_transform.classes)
classes.extend(trimsheet_hover_handler.classes)
classes.extend(trimsheet_tool_modal.classes)
classes.extend(auto_unwrap.classes)
classes.extend(uv_shift.classes)
classes.extend(merge_unwrap.classes)
classes.extend(triplanar_mapping.classes)
classes.extend(relax_univ.classes)  # UniV-style relax operator - MUST be before parent unwrap_inplace
classes.extend(preferences_ops.classes)  # Preferences and hotkey operators
classes.extend(split_uv.classes)  # Split UV operator
classes.extend(random_transform.classes)  # Random transform operator
classes.extend(td_operators.classes)  # Texel density operators
classes.extend(unwrap_inplace.classes)
classes.extend(unwrap_inplace_view3d.classes)
classes.extend(project_unwrap.classes)
classes.extend(parallel_constraint.classes)
classes.extend(straighten.classes)
classes.extend(constraint_ops.classes)
if test_transform and hasattr(test_transform, 'classes'):
    classes.extend(test_transform.classes)  # Test operator for transformation functions
if debug_weld and hasattr(debug_weld, 'classes'):
    classes.extend(debug_weld.classes)  # Debug operator for weld analysis

if optimize_scale and hasattr(optimize_scale, 'classes'):
    classes.extend(optimize_scale.classes)


def register():
    import bpy
    errors = []
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            # Verify it's actually registered
            if hasattr(cls, 'bl_idname'):
                parts = cls.bl_idname.split('.')
                if len(parts) == 2:
                    namespace, name = parts
                    try:
                        op = getattr(bpy.ops, namespace)
                        if not hasattr(op, name):
                            errors.append(f"   WARNING: {cls.__name__} ({cls.bl_idname}) NOT accessible after registration!")
                    except:
                        errors.append(f"   WARNING: Could not verify {cls.__name__} ({cls.bl_idname})")
        except Exception as e:
            errors.append(f"   ERROR: Failed to register {cls.__name__}: {e}")
            import traceback
            traceback.print_exc()

    if errors:
        print(f"[UVV operators] Registration issues:")
        for err in errors:
            print(err)
    else:
        print(f"[UVV operators] All {len(classes)} operators registered successfully")

    # Register the trimsheet tool modal handler
    print("[UVV operators] Registering trimsheet tool modal handler...")
    trimsheet_tool_modal.register()


def unregister():
    import bpy
    errors = []

    # Unregister the trimsheet tool modal handler first
    print("[UVV operators] Unregistering trimsheet tool modal handler...")
    trimsheet_tool_modal.unregister()

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            errors.append(f"   WARNING: Failed to unregister {cls.__name__}: {e}")

    if errors:
        print(f"[UVV operators] Unregistration issues:")
        for err in errors:
            print(err)