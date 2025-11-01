

"""UV Checker Mode Change Handler using msgbus subscription"""

import bpy


# Owner object for msgbus subscriptions
_msgbus_owner = object()


def _on_mode_change():
    """Callback when object mode changes"""
    # Get context
    context = bpy.context

    if not is_checker_auto_mode_active():
        return

    # Call refresh_checker to dynamically update checkers
    from .uvflow_style_checker import refresh_checker
    try:
        refresh_checker(context)
    except Exception as e:
        print(f"UVV Checker mode handler error: {e}")


def enable_checker_auto_mode(context):
    """
    Enable automatic checker mode switching.
    When enabled, checkers will be added/removed automatically based on object mode.
    """
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()
    
    if settings.checker_auto_mode_enabled:
        return

    settings.checker_auto_mode_enabled = True

    # Subscribe to mode changes on all objects
    # We subscribe to Object.mode property changes
    subscribe_key = (bpy.types.Object, "mode")

    bpy.msgbus.subscribe_rna(
        key=subscribe_key,
        owner=_msgbus_owner,
        args=(),
        notify=_on_mode_change,
        options={'PERSISTENT'}
    )

    # Initial refresh to set up checkers for current state
    from .uvflow_style_checker import refresh_checker
    refresh_checker(context)


def disable_checker_auto_mode(context):
    """
    Disable automatic checker mode switching.
    Removes all checkers and unsubscribes from mode changes.
    """
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()
    
    if not settings.checker_auto_mode_enabled:
        return

    settings.checker_auto_mode_enabled = False

    # Unsubscribe from mode changes
    bpy.msgbus.clear_by_owner(_msgbus_owner)

    # Clean up all existing checkers
    from .uvflow_style_checker import disable_checker_material

    checked_objects = [obj for obj in context.view_layer.objects
                      if obj.get('uvv_checker_enabled')]

    if checked_objects:
        disable_checker_material(context, checked_objects)


def is_checker_auto_mode_active():
    """Check if checker auto mode is currently active"""
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()
    return settings.checker_auto_mode_enabled


def cleanup():
    """Cleanup function called on addon unregister"""
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()
    
    if settings.checker_auto_mode_enabled:
        settings.checker_auto_mode_enabled = False
        bpy.msgbus.clear_by_owner(_msgbus_owner)
