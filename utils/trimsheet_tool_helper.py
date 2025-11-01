"""Helper to auto-start trimsheet tool modal"""

import bpy


def ensure_tool_modal_running():
    """Ensure the trimsheet tool modal is running when tool is active"""
    # Check if trimsheet tool is active
    for area in bpy.context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            for space in area.spaces:
                if space.type == 'IMAGE_EDITOR':
                    # Check if our tool is active
                    try:
                        from ..operators.trimsheet_tool_modal import UVV_OT_trimsheet_tool_modal

                        # Start modal if not running
                        if not UVV_OT_trimsheet_tool_modal._is_running:
                            bpy.ops.uv.uvv_trimsheet_tool_modal('INVOKE_DEFAULT')
                            return True
                    except Exception as e:
                        return False
    return False


def register():
    """Register with a timer to check tool state"""
    # Start checking after a short delay
    if not bpy.app.timers.is_registered(ensure_tool_modal_running):
        bpy.app.timers.register(ensure_tool_modal_running, first_interval=0.5, persistent=True)


def unregister():
    """Unregister timer"""
    if bpy.app.timers.is_registered(ensure_tool_modal_running):
        bpy.app.timers.unregister(ensure_tool_modal_running)
