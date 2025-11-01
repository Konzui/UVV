"""Modal operator that runs when trimsheet tool is active to handle mouse clicks"""

import bpy
from bpy.types import Operator
from bpy.app.handlers import persistent


class UVV_OT_trimsheet_tool_modal(Operator):
    """Modal operator for trimsheet tool - handles all mouse interactions"""
    bl_idname = "uv.uvv_trimsheet_tool_modal"
    bl_label = "Trimsheet Tool"

    _is_running = False

    @classmethod
    def poll(cls, context):
        return (context.area and
                context.area.type == 'IMAGE_EDITOR')

    def invoke(self, context, event):
        """Start the modal operator"""
        # Prevent multiple instances
        if UVV_OT_trimsheet_tool_modal._is_running:
            return {'CANCELLED'}

        UVV_OT_trimsheet_tool_modal._is_running = True
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """Handle ALL mouse events for the tool"""

        # Stop if not in UV editor
        if not context.area or context.area.type != 'IMAGE_EDITOR':
            return self.finish(context)

        settings = context.scene.uvv_settings

        # MOUSEMOVE - Update hover states
        if event.type == 'MOUSEMOVE':
            from ..utils import trimsheet_transform_draw

            # Update handle hover only in edit mode
            if settings.trim_edit_mode:
                trimsheet_transform_draw.update_hover_handle(
                    context, event.mouse_region_x, event.mouse_region_y
                )

                # Update cursor based on hover
                hover_handle = trimsheet_transform_draw._hover_handle
                if hover_handle:
                    handle_type, handle_id = hover_handle
                    if handle_type == 'corner':
                        # Set cursor for corner resize
                        context.window.cursor_modal_set('SCROLL_XY')
                    elif handle_type == 'edge':
                        # Set cursor for edge resize
                        if handle_id in ['left', 'right']:
                            context.window.cursor_modal_set('SCROLL_X')
                        else:
                            context.window.cursor_modal_set('SCROLL_Y')
                    elif handle_type == 'center':
                        context.window.cursor_modal_set('HAND')
                else:
                    context.window.cursor_modal_restore()
            else:
                # Outside edit mode: check if hovering over text label
                text_idx = trimsheet_transform_draw.get_text_label_at_position(
                    context, event.mouse_region_x, event.mouse_region_y
                )
                if text_idx is not None:
                    context.window.cursor_modal_set('HAND')
                else:
                    context.window.cursor_modal_restore()

            context.area.tag_redraw()
            return {'PASS_THROUGH'}

        # LEFTMOUSE PRESS - Handle text label clicks, then transforms
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            from ..utils import trimsheet_transform_draw, trimsheet_utils

            # Check if clicking on a text label
            text_idx = trimsheet_transform_draw.get_text_label_at_position(
                context, event.mouse_region_x, event.mouse_region_y
            )

            if text_idx is not None:
                material = trimsheet_utils.get_active_material(context)

                if material:
                    # CTRL+Click: Fit UV selection to trim
                    if event.ctrl:
                        if context.mode == 'EDIT_MESH':
                            try:
                                bpy.ops.uv.uvv_trim_fit_selection(trim_index=text_idx)
                            except:
                                pass
                            context.area.tag_redraw()
                            return {'RUNNING_MODAL'}
                    else:
                        # Regular click: Select trim and enter edit mode
                        material.uvv_trims_index = text_idx
                        settings.trim_edit_mode = True
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}

            # No text clicked - handle transforms if in edit mode
            if settings.trim_edit_mode:
                from ..utils.trimsheet_transform_draw import get_handle_type_at_position
                
                # Check if clicking on transform handles
                material = trimsheet_utils.get_active_material(context)
                if material and material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims):
                    trim = material.uvv_trims[material.uvv_trims_index]
                    handle_type, handle_id = get_handle_type_at_position(
                        context, trim, event.mouse_region_x, event.mouse_region_y
                    )
                    
                    if handle_type:
                        # Clicking on a handle - do transform
                        try:
                            bpy.ops.uv.uvv_trim_edit_transform('INVOKE_DEFAULT')
                        except:
                            pass
                        return {'PASS_THROUGH'}
                    else:
                        # Clicking in empty space - exit edit mode
                        settings.trim_edit_mode = False
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}

        # ENTER key - Exit edit mode
        if event.type == 'RET' and event.value == 'PRESS':
            if settings.trim_edit_mode:
                settings.trim_edit_mode = False
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}

        # Pass through all other events
        return {'PASS_THROUGH'}

    def finish(self, context):
        """Clean up"""
        UVV_OT_trimsheet_tool_modal._is_running = False
        if context.window:
            context.window.cursor_modal_restore()
        return {'FINISHED'}


@persistent
def check_trimsheet_tool_active(dummy):
    """Check if trimsheet tool is active and start modal if needed"""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                # Check if trimsheet tool is the active tool
                if hasattr(area.spaces.active, 'show_region_tool_header'):
                    try:
                        # Get the active tool
                        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
                        tool_context = ToolSelectPanelHelper._tool_get_active(
                            bpy.context, area.spaces.active.type, area.spaces.active.mode, with_icon=False
                        )

                        if tool_context and tool_context.idname == "uvv.trimsheet_tool":
                            # Trimsheet tool is active - ensure modal is running
                            if not UVV_OT_trimsheet_tool_modal._is_running:
                                # Override context to run in this area
                                override = {'window': window, 'screen': window.screen, 'area': area}
                                with bpy.context.temp_override(**override):
                                    bpy.ops.uv.uvv_trimsheet_tool_modal('INVOKE_DEFAULT')
                    except Exception as e:
                        pass


classes = [
    UVV_OT_trimsheet_tool_modal,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Add depsgraph update handler to check if tool is active
    if check_trimsheet_tool_active not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(check_trimsheet_tool_active)


def unregister():
    # Remove handler
    if check_trimsheet_tool_active in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(check_trimsheet_tool_active)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
