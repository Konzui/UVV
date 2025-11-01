"""Modal operator to handle hover effects for trimsheet transform handles"""

import bpy
from bpy.types import Operator


class UVV_OT_trim_hover_handler(Operator):
    """Update hover state for transform handles"""
    bl_idname = "uv.uvv_trim_hover_handler"
    bl_label = "Trim Hover Handler"

    _timer = None
    _is_running = False

    @classmethod
    def poll(cls, context):
        return (context.space_data and
                context.space_data.type == 'IMAGE_EDITOR' and
                context.scene.uvv_settings.trim_edit_mode)

    def modal(self, context, event):
        # Check if we should still be running
        if not context.scene.uvv_settings.trim_edit_mode:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'MOUSEMOVE':
            # Update hover state
            from ..utils import trimsheet_transform_draw
            trimsheet_transform_draw.update_hover_handle(
                context, event.mouse_region_x, event.mouse_region_y
            )
            context.area.tag_redraw()

        elif event.type == 'TIMER':
            # Periodic check
            pass

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        # Don't start if already running
        if UVV_OT_trim_hover_handler._is_running:
            return {'CANCELLED'}

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        UVV_OT_trim_hover_handler._is_running = True
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        UVV_OT_trim_hover_handler._is_running = False


def start_hover_handler(context):
    """Start the hover handler if it's not already running"""
    if not UVV_OT_trim_hover_handler._is_running:
        bpy.ops.uv.uvv_trim_hover_handler('INVOKE_DEFAULT')


def stop_hover_handler():
    """Stop the hover handler"""
    UVV_OT_trim_hover_handler._is_running = False


classes = [
    UVV_OT_trim_hover_handler,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
