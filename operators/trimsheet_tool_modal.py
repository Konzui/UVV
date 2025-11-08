"""Modal operator that runs when trimsheet tool is active to handle mouse clicks"""

import bpy
import time
from bpy.types import Operator
from bpy.app.handlers import persistent
import gpu


class UVV_OT_trimsheet_tool_modal(Operator):
    """Modal operator for trimsheet tool - handles all mouse interactions"""
    bl_idname = "uv.uvv_trimsheet_tool_modal"
    bl_label = "Trimsheet Tool"

    _is_running = False

    # Double-click detection
    _last_click_time = 0.0
    _last_clicked_trim = -1
    _double_click_threshold = 0.3  # seconds

    # Lock toggle protection
    _last_lock_toggle_time = 0.0
    _lock_toggle_cooldown = 0.2  # Prevent toggling faster than 200ms
    
    # Drag detection - prevent accidental drags when clicking while moving mouse
    _pending_transform = None  # Store (handle_type, handle_id, click_pos) when entering edit mode
    _drag_threshold = 5.0  # Minimum pixel distance to start drag

    @classmethod
    def poll(cls, context):
        # Allow in both Object Mode (for trim interaction) and Edit Mode (for ALT tooltip tracking)
        return (context.area and
                context.area.type == 'IMAGE_EDITOR' and
                context.mode in {'OBJECT', 'EDIT_MESH'})

    def invoke(self, context, event):
        """Start the modal operator"""
        # CRITICAL: Check reload flag first - prevents crashes during/after reload
        global _uvv_trimsheet_reloading
        try:
            import sys
            # Quick check: if our own module has the flag set, we're reloading
            if _uvv_trimsheet_reloading:
                return {'CANCELLED'}
            # Also check for old module instances that might still have flag set
            for mod in sys.modules.values():
                if mod and mod != sys.modules.get(__name__) and hasattr(mod, 'UVV_OT_trimsheet_tool_modal') and hasattr(mod, '_uvv_trimsheet_reloading'):
                    if getattr(mod, '_uvv_trimsheet_reloading', False):
                        return {'CANCELLED'}
        except:
            pass  # If check fails, continue (safer than blocking)

        # Prevent multiple instances (defensive check)
        if UVV_OT_trimsheet_tool_modal._is_running:
            return {'CANCELLED'}

        # Safety check: ensure context is valid and has required attributes
        if not context:
            return {'CANCELLED'}

        if not hasattr(context, 'window_manager') or not context.window_manager:
            return {'CANCELLED'}

        # Additional safety: check if window_manager is in a valid state
        try:
            windows = context.window_manager.windows
            if windows is None:
                return {'CANCELLED'}
            _ = len(windows)
        except (AttributeError, RuntimeError, TypeError, SystemError) as e:
            return {'CANCELLED'}
        except Exception as e:
            return {'CANCELLED'}

        UVV_OT_trimsheet_tool_modal._is_running = True
        try:
            # Use safe method to add modal handler
            if _uvv_trimsheet_reloading:
                UVV_OT_trimsheet_tool_modal._is_running = False
                return {'CANCELLED'}
            # Also check for old module instances
            try:
                import sys
                for mod in sys.modules.values():
                    if mod and mod != sys.modules.get(__name__) and hasattr(mod, 'UVV_OT_trimsheet_tool_modal') and hasattr(mod, '_uvv_trimsheet_reloading'):
                        if getattr(mod, '_uvv_trimsheet_reloading', False):
                            UVV_OT_trimsheet_tool_modal._is_running = False
                            return {'CANCELLED'}
            except:
                pass
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        except (AttributeError, RuntimeError, SystemError, TypeError):
            UVV_OT_trimsheet_tool_modal._is_running = False
            return {'CANCELLED'}
        except Exception:
            UVV_OT_trimsheet_tool_modal._is_running = False
            return {'CANCELLED'}

    def modal(self, context, event):
        """Handle ALL mouse events for the tool"""
        # CRITICAL: Safety check to prevent multiple instances from running simultaneously
        if not self.__class__._is_running:
            return {'CANCELLED'}
        
        # Removed excessive debug output

        try:
            # Safety check: ensure context is valid
            if not context or not context.window_manager:
                return {'PASS_THROUGH'}

            # CRITICAL: Check if event is happening in a UV editor region
            # Modal receives events from ALL areas, we need to filter
            event_in_uv_editor = False
            uv_area = None
            uv_region = None
            uv_window = None
            mouse_region_x = -1
            mouse_region_y = -1

            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        for region in area.regions:
                            # Only process clicks in WINDOW region, ignore UI panels (type == 'UI')
                            if region.type == 'WINDOW':
                                # Calculate mouse position relative to this region
                                mx = event.mouse_x - region.x
                                my = event.mouse_y - region.y
                                # Check if mouse is in this region
                                if 0 <= mx < region.width and 0 <= my < region.height:
                                    event_in_uv_editor = True
                                    uv_area = area
                                    uv_region = region
                                    uv_window = window
                                    mouse_region_x = mx
                                    mouse_region_y = my
                                    break
                            # Explicitly check if click is in UI region and ignore it
                            elif region.type == 'UI':
                                mx = event.mouse_x - region.x
                                my = event.mouse_y - region.y
                                if 0 <= mx < region.width and 0 <= my < region.height:
                                    # Click is in UI panel - pass through immediately
                                    return {'PASS_THROUGH'}
                        if event_in_uv_editor:
                            break
                if event_in_uv_editor:
                    break

            # If event is not in UV editor WINDOW region, pass through
            if not event_in_uv_editor:
                return {'PASS_THROUGH'}

            # Safety check: ensure we have valid area/region before proceeding
            if not uv_area or not uv_region or not uv_window:
                return {'PASS_THROUGH'}

            # Store real Blender context items for operator invocations
            self._uv_window = uv_window
            self._uv_area = uv_area
            self._uv_region = uv_region

            # Safety check: ensure scene exists
            if not context.scene or not hasattr(context.scene, 'uvv_settings'):
                return {'PASS_THROUGH'}

            # Override context to this specific area/region
            # Include tool_settings and other necessary attributes
            original_context = context
            context = type('obj', (object,), {
                'area': uv_area,
                'region': uv_region,
                'window': uv_window,
                'screen': uv_window.screen,
                'scene': original_context.scene,
                'window_manager': original_context.window_manager,
                'space_data': uv_area.spaces.active,
                'preferences': original_context.preferences,
                'mode': original_context.mode,
                'active_object': original_context.active_object,
                'tool_settings': original_context.tool_settings,  # Needed for has_selected_uv_islands
                'edit_object': original_context.edit_object,  # May be needed for bmesh operations
                'selected_objects': original_context.selected_objects,  # May be needed
                'objects_in_mode': original_context.objects_in_mode,  # Needed for has_selected_uv_islands
            })()

            settings = context.scene.uvv_settings
        except Exception as e:
            # If anything fails during context setup, just pass through
            print(f"UVV DEBUG: Error in modal context setup: {e}")
            import traceback
            traceback.print_exc()
            return {'PASS_THROUGH'}

        # Removed excessive debug output

        # MOUSEMOVE - Update hover states (only in Object Mode for interaction)
        # Also track for ALT tooltip in Edit Mode when UV islands are selected
        if event.type == 'MOUSEMOVE':
            try:
                from ..utils import trimsheet_transform_draw, trimsheet_draw
                
                # Check if there's a pending transform and mouse has moved enough to start drag
                if self.__class__._pending_transform:
                    pending = self.__class__._pending_transform
                    dx = mouse_region_x - pending['click_x']
                    dy = mouse_region_y - pending['click_y']
                    distance = (dx * dx + dy * dy) ** 0.5
                    
                    if distance >= self.__class__._drag_threshold:
                        # Mouse has moved enough - start the transform
                        handle_type = pending['handle_type']
                        handle_id = pending['handle_id']
                        uv_window = pending['uv_window']
                        uv_area = pending['uv_area']
                        uv_region = pending['uv_region']
                        
                        # Clear pending transform
                        self.__class__._pending_transform = None
                        
                        try:
                            # Mark our modal as not running BEFORE starting transform
                            self.__class__._is_running = False
                            
                            # Use context override to ensure region is available
                            with bpy.context.temp_override(
                                window=uv_window,
                                area=uv_area,
                                region=uv_region,
                                screen=uv_window.screen,
                                scene=context.scene,
                                space_data=uv_area.spaces.active,
                            ):
                                # Directly invoke the appropriate transform operator
                                if handle_type == 'corner':
                                    result = bpy.ops.uv.uvv_trim_edit_scale_corner('INVOKE_DEFAULT', corner=handle_id)
                                elif handle_type == 'edge':
                                    result = bpy.ops.uv.uvv_trim_edit_scale_edge('INVOKE_DEFAULT', edge=handle_id)
                                elif handle_type == 'center':
                                    result = bpy.ops.uv.uvv_trim_edit_move('INVOKE_DEFAULT')
                                else:
                                    result = {'CANCELLED'}
                        except Exception as e:
                            # If transform fails, restore modal state
                            self.__class__._is_running = False
                            import traceback
                            traceback.print_exc()
                            return {'RUNNING_MODAL'}
                
                # ALWAYS update mouse position for tooltip placement (regardless of mode)
                trimsheet_transform_draw._mouse_pos_region = (mouse_region_x, mouse_region_y)
                
                # Note: ALT hover tracking removed - we now use ALT+Click directly instead of tooltip
                
                # In Object Mode: Update hover states for trim interaction
                if context.mode == 'OBJECT':
                    # Update handle hover only in edit mode
                    if settings.trim_edit_mode:
                        trimsheet_transform_draw.update_hover_handle(
                            context, mouse_region_x, mouse_region_y
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
                        # Outside edit mode: update hover state for tooltip
                        trimsheet_transform_draw.update_hover_handle(
                            context, mouse_region_x, mouse_region_y
                        )
                        # Check if hovering over lock button
                        if trimsheet_transform_draw.get_lock_button_at_position(
                            context, mouse_region_x, mouse_region_y
                        ):
                            context.window.cursor_modal_set('HAND')
                        # Use the hover state that was just updated
                        elif trimsheet_transform_draw._hover_text_idx is not None:
                            context.window.cursor_modal_set('HAND')
                        else:
                            context.window.cursor_modal_restore()

                    context.area.tag_redraw()
                    return {'PASS_THROUGH'}
                else:
                    # Not in Object Mode, just pass through
                    return {'PASS_THROUGH'}
            except Exception:
                return {'PASS_THROUGH'}
        
        # ALWAYS track mouse position and ALT state for tooltip (works even during transform)
        # Update these on any event that provides them
        try:
            from ..utils import trimsheet_transform_draw, trimsheet_draw
            
            # Update mouse position whenever we have it
            if mouse_region_x >= 0 and mouse_region_y >= 0:
                trimsheet_transform_draw._mouse_pos_region = (mouse_region_x, mouse_region_y)
            
            # Update ALT key state from event if available
            if hasattr(event, 'alt'):
                trimsheet_transform_draw._alt_key_pressed = event.alt
            
            # Note: ALT hover tracking removed - we now use ALT+Click directly instead of tooltip
        except:
            pass
        
        # Check ALT key state changes to update tooltip visibility
        if event.type in {'LEFT_ALT', 'RIGHT_ALT'}:
            from ..utils import trimsheet_transform_draw
            # Update ALT key state based on event value
            if event.value == 'PRESS':
                trimsheet_transform_draw._alt_key_pressed = True
            elif event.value == 'RELEASE':
                trimsheet_transform_draw._alt_key_pressed = False
            context.area.tag_redraw()
            return {'PASS_THROUGH'}

        # LEFTMOUSE - Handle ALT+Click to fit UV islands (both PRESS and RELEASE during transform)
        if event.type == 'LEFTMOUSE' and event.value in {'PRESS', 'RELEASE'}:
            try:
                import time
                from ..utils import trimsheet_transform_draw, trimsheet_utils, trimsheet_draw

                # SPECIAL CASE: In Edit Mode, ALT+Click fits UV islands to trim
                # Check both PRESS and RELEASE since transform might consume PRESS
                if context.mode == 'EDIT_MESH' and event.alt:
                    # Check if UV islands are selected
                    had_selection = trimsheet_draw.has_selected_uv_islands(context)
                    
                    # Check hover once - calculate trim at current mouse position
                    hovered_trim_idx = trimsheet_transform_draw.get_trim_at_position(
                        context, mouse_region_x, mouse_region_y
                    )
                    # Also check text label as fallback
                    if hovered_trim_idx is None:
                        hovered_trim_idx = trimsheet_transform_draw.get_text_label_at_position(
                            context, mouse_region_x, mouse_region_y
                        )
                    
                    if hovered_trim_idx is not None and had_selection:
                        # Execute fit on RELEASE
                        # Since Blender's operator panel system doesn't work for programmatic calls,
                        # we'll invoke the fit operator which has its own draw() method
                        # The fit operator will execute and be in the operator stack, even if the panel doesn't auto-switch
                        if event.value == 'RELEASE':
                            # Calculate alignment based on click position within trim
                            alignment = self._get_alignment_from_click_position(
                                context, hovered_trim_idx, mouse_region_x, mouse_region_y
                            )
                            
                            # Call fit operator - it will show confirmation dialog, then execute and show panel
                            try:
                                if uv_area and uv_region:
                                    with bpy.context.temp_override(area=uv_area, region=uv_region):
                                        # Set module-level flag to indicate Alt+Click call, then invoke fit operator
                                        from . import trimsheet_ops
                                        trimsheet_ops._fit_from_alt_click = True
                                        bpy.ops.uv.uvv_trim_fit_selection(
                                            'INVOKE_DEFAULT',
                                            trim_index=hovered_trim_idx,
                                            fit_alignment=alignment
                                        )
                                        uv_area.tag_redraw()
                                else:
                                    # Set module-level flag to indicate Alt+Click call
                                    from . import trimsheet_ops
                                    trimsheet_ops._fit_from_alt_click = True
                                    bpy.ops.uv.uvv_trim_fit_selection(
                                        'INVOKE_DEFAULT',
                                        trim_index=hovered_trim_idx,
                                        fit_alignment=alignment
                                    )
                                return {'RUNNING_MODAL'}
                            except Exception as e:
                                print(f"UVV ERROR: Failed to call fit operator: {e}")
                                import traceback
                                traceback.print_exc()
                                return {'PASS_THROUGH'}
                    
                    # If ALT+Click didn't match, pass through
                    return {'PASS_THROUGH'}

                # In Edit Mode (without ALT), trims are visual only - pass through
                # But only on PRESS, allow RELEASE to pass through normally
                if context.mode == 'EDIT_MESH' and event.value == 'PRESS':
                    return {'PASS_THROUGH'}

                # In Object Mode, we can interact with trims
                if context.mode != 'OBJECT':
                    return {'PASS_THROUGH'}

                # PRIORITY 0: Check lock button FIRST (always highest priority)
                lock_button_hit = trimsheet_transform_draw.get_lock_button_at_position(
                    context, mouse_region_x, mouse_region_y
                )
                if lock_button_hit:
                    # Check cooldown to prevent rapid toggling
                    current_time = time.time()
                    if (current_time - self.__class__._last_lock_toggle_time) >= self.__class__._lock_toggle_cooldown:
                        material = trimsheet_utils.get_active_material(context)
                        if material and material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims):
                            trim = material.uvv_trims[material.uvv_trims_index]
                            trim.locked = not trim.locked
                            self.__class__._last_lock_toggle_time = current_time

                            # If we just locked the trim and we're in edit mode, exit edit mode
                            if trim.locked and settings.trim_edit_mode:
                                settings.trim_edit_mode = False

                            context.area.tag_redraw()
                            return {'RUNNING_MODAL'}
                    else:
                        return {'RUNNING_MODAL'}

                # PRIORITY 1: If in edit mode, check transform handles
                if settings.trim_edit_mode:
                    material = trimsheet_utils.get_active_material(context)
                    if material and material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims):
                        trim = material.uvv_trims[material.uvv_trims_index]
                        
                        # SAFETY CHECK: If trim is locked, exit edit mode immediately
                        if trim.locked:
                            print(f"UVV DEBUG: Trim is locked, forcing exit from edit mode")
                            settings.trim_edit_mode = False
                            context.area.tag_redraw()
                            return {'RUNNING_MODAL'}

                        # Check if clicking on transform handles
                        handle_type, handle_id = trimsheet_transform_draw.get_handle_type_at_position(
                            context, trim, mouse_region_x, mouse_region_y
                        )

                        if handle_type:
                            if event.value == 'PRESS':
                                # Store pending transform - only start if mouse moves beyond threshold
                                # This prevents accidental drags when clicking while moving mouse quickly
                                self.__class__._pending_transform = {
                                    'handle_type': handle_type,
                                    'handle_id': handle_id,
                                    'click_x': mouse_region_x,
                                    'click_y': mouse_region_y,
                                    'uv_window': uv_window,
                                    'uv_area': uv_area,
                                    'uv_region': uv_region,
                                }
                                # Don't start transform yet - wait for mouse movement
                                return {'RUNNING_MODAL'}
                            elif event.value == 'RELEASE':
                                # If mouse was released without starting drag, cancel pending transform
                                if self.__class__._pending_transform:
                                    self.__class__._pending_transform = None
                                return {'RUNNING_MODAL'}
                        # If no handle was clicked, check if clicking on another trim
                        # Allow selecting other trims even in edit mode (both rectangle and text clicks)
                        clicked_trim_idx = trimsheet_transform_draw.get_trim_at_position(
                            context, mouse_region_x, mouse_region_y
                        )
                        # Also check text label as fallback (in case rectangle detection missed it)
                        if clicked_trim_idx is None:
                            clicked_trim_idx = trimsheet_transform_draw.get_text_label_at_position(
                                context, mouse_region_x, mouse_region_y
                            )
                        
                        if clicked_trim_idx is not None and clicked_trim_idx != material.uvv_trims_index:
                            # Clicking on a different trim - select it and exit edit mode
                            print(f"UVV DEBUG: Clicked on different trim (index {clicked_trim_idx}) in edit mode - selecting it")
                            clicked_trim = material.uvv_trims[clicked_trim_idx]
                            material.uvv_trims_index = clicked_trim_idx
                            # Exit edit mode when selecting a different trim
                            settings.trim_edit_mode = False
                            context.area.tag_redraw()
                            return {'RUNNING_MODAL'}
                        # else: clicking outside trim - will be handled below

                # PRIORITY 2: Check trim rectangle click (anywhere in trim, not just text)
                trim_idx = trimsheet_transform_draw.get_trim_at_position(
                    context, mouse_region_x, mouse_region_y
                )

                # If trim rectangle didn't detect it, try text label as fallback
                # (Text should be inside trim rectangle, but this handles edge cases)
                if trim_idx is None:
                    text_idx = trimsheet_transform_draw.get_text_label_at_position(
                        context, mouse_region_x, mouse_region_y
                    )
                    if text_idx is not None:
                        trim_idx = text_idx

                if trim_idx is not None:
                    material = trimsheet_utils.get_active_material(context)
                    if material:
                        clicked_trim = material.uvv_trims[trim_idx]
                        
                        # CTRL+Click: Fit UV selection to trim
                        if event.ctrl:
                            if context.mode == 'EDIT_MESH':
                                try:
                                    bpy.ops.uv.uvv_trim_fit_selection(trim_index=trim_idx)
                                except:
                                    pass
                                context.area.tag_redraw()
                                return {'RUNNING_MODAL'}
                        else:

                            # Detect double-click
                            current_time = time.time()
                            is_double_click = (
                                trim_idx == self.__class__._last_clicked_trim and
                                (current_time - self.__class__._last_click_time) < self.__class__._double_click_threshold
                            )

                            # Select the trim
                            material.uvv_trims_index = trim_idx

                            # Enter edit mode if unlocked (both single-click and double-click)
                            if not clicked_trim.locked:
                                settings.trim_edit_mode = True
                            else:
                                # Locked trim: don't enter edit mode and make sure we exit if we were in it
                                settings.trim_edit_mode = False

                            # Update click tracking for double-click detection
                            if is_double_click:
                                # Reset click tracking to prevent triple-click issues
                                self.__class__._last_clicked_trim = -1
                                self.__class__._last_click_time = 0.0
                            else:
                                # Update click tracking for potential double-click
                                self.__class__._last_click_time = current_time
                                self.__class__._last_clicked_trim = trim_idx

                            context.area.tag_redraw()
                            return {'RUNNING_MODAL'}

                # PRIORITY 4: Click outside any trim - exit edit mode and deselect
                # (If we got here, no trim text was clicked)
                if settings.trim_edit_mode:
                    # In edit mode: exit edit mode and deselect
                    settings.trim_edit_mode = False
                    material = trimsheet_utils.get_active_material(context)
                    if material:
                        material.uvv_trims_index = -1
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                else:
                    # Not in edit mode: just deselect if something is selected
                    material = trimsheet_utils.get_active_material(context)
                    if material and material.uvv_trims_index >= 0:
                        material.uvv_trims_index = -1
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
            except Exception as e:
                print(f"UVV DEBUG: Error in LEFTMOUSE handler: {e}")
                import traceback
                traceback.print_exc()
                return {'PASS_THROUGH'}

        # ENTER key - Exit edit mode
        if event.type == 'RET' and event.value == 'PRESS':
            if settings.trim_edit_mode:
                settings.trim_edit_mode = False
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}

        # Pass through all other events
        return {'PASS_THROUGH'}

    def _get_alignment_from_click_position(self, context, trim_index, mouse_region_x, mouse_region_y):
        """Calculate alignment enum value based on where user clicked within the trim
        
        Args:
            context: Blender context
            trim_index: Index of the trim that was clicked
            mouse_region_x: Mouse X position in region coordinates
            mouse_region_y: Mouse Y position in region coordinates
        
        Returns:
            str: Alignment enum value (e.g., 'TOP_LEFT', 'CENTER', etc.)
        """
        from ..utils import trimsheet_utils
        
        material = trimsheet_utils.get_active_material(context)
        if not material or not hasattr(material, 'uvv_trims'):
            return 'CENTER'  # Default fallback
        
        if trim_index < 0 or trim_index >= len(material.uvv_trims):
            return 'CENTER'  # Default fallback
        
        trim = material.uvv_trims[trim_index]
        region = context.region
        if not region:
            return 'CENTER'  # Default fallback
        
        rv2d = region.view2d
        if not rv2d:
            return 'CENTER'  # Default fallback
        
        # Convert mouse position from region coordinates to UV coordinates
        mouse_uv = rv2d.region_to_view(mouse_region_x, mouse_region_y)
        mouse_u, mouse_v = mouse_uv
        
        # Get trim bounds
        trim_left = trim.left
        trim_right = trim.right
        trim_bottom = trim.bottom
        trim_top = trim.top
        
        # Calculate relative position within trim (0.0 to 1.0)
        trim_width = trim_right - trim_left
        trim_height = trim_top - trim_bottom
        
        if trim_width <= 0 or trim_height <= 0:
            return 'CENTER'  # Invalid trim dimensions
        
        rel_x = (mouse_u - trim_left) / trim_width
        rel_y = (mouse_v - trim_bottom) / trim_height
        
        # Map relative position to alignment zones (0-1 divided into 3 zones: 0-0.33, 0.33-0.67, 0.67-1.0)
        # Horizontal alignment
        if rel_x < 0.33:
            h_align = 'LEFT'
        elif rel_x < 0.67:
            h_align = 'CENTER'
        else:
            h_align = 'RIGHT'
        
        # Vertical alignment
        if rel_y < 0.33:
            v_align = 'BOTTOM'
        elif rel_y < 0.67:
            v_align = 'CENTER'
        else:
            v_align = 'TOP'
        
        # Combine into alignment enum value
        if v_align == 'CENTER' and h_align == 'CENTER':
            return 'CENTER'
        elif v_align == 'TOP' and h_align == 'LEFT':
            return 'TOP_LEFT'
        elif v_align == 'TOP' and h_align == 'CENTER':
            return 'TOP_CENTER'
        elif v_align == 'TOP' and h_align == 'RIGHT':
            return 'TOP_RIGHT'
        elif v_align == 'CENTER' and h_align == 'LEFT':
            return 'CENTER_LEFT'
        elif v_align == 'CENTER' and h_align == 'RIGHT':
            return 'CENTER_RIGHT'
        elif v_align == 'BOTTOM' and h_align == 'LEFT':
            return 'BOTTOM_LEFT'
        elif v_align == 'BOTTOM' and h_align == 'CENTER':
            return 'BOTTOM_CENTER'
        elif v_align == 'BOTTOM' and h_align == 'RIGHT':
            return 'BOTTOM_RIGHT'
        
        return 'CENTER'  # Fallback

    def finish(self, context):
        """Clean up"""
        UVV_OT_trimsheet_tool_modal._is_running = False
        if context.window:
            context.window.cursor_modal_restore()
        return {'FINISHED'}


# Track initialized scenes to avoid re-initializing
_initialized_scenes = set()
_starting_modal = False  # Flag to prevent recursive calls from depsgraph handler
_registered_draw_handlers = []  # Track draw handlers for cleanup
_uvv_trimsheet_reloading = False  # Flag to prevent timer callbacks from running during/after reload

def start_trimsheet_modal_if_needed(context=None):
    """Start the trimsheet modal if UV editor is open and modal is not running"""
    global _starting_modal, _registered_draw_handlers


    # Safety checks: don't start if already running or in process of starting
    if UVV_OT_trimsheet_tool_modal._is_running or _starting_modal:
        return False

    if context is None:
        context = bpy.context

    # Enhanced context validation
    if not context:
        return False
    
    if not hasattr(context, 'window_manager') or not context.window_manager:
        return False
    
    # Check if window_manager has windows (indicates it's initialized)
    try:
        windows = context.window_manager.windows
        if not windows:
            return False
    except (AttributeError, RuntimeError):
        return False
    
    # Set flag to prevent recursive calls
    _starting_modal = True

    try:
        # Check if we have UV editor open
        for window in windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    # Check if area has valid space_data
                    if not area.spaces or not area.spaces.active:
                        continue

                    # Check if space is in UV mode (not image mode)
                    space = area.spaces.active
                    if space.mode != 'UV':
                        continue

                    # Allow modal in both Object Mode (for trim interaction) and Edit Mode (for ALT tooltip tracking)
                    # Double-check modal isn't running (defensive check)
                    if UVV_OT_trimsheet_tool_modal._is_running:
                        _starting_modal = False
                        return False

                    # Start modal directly - no timer needed!
                    try:
                        override = {'window': window, 'screen': window.screen, 'area': area}
                        with bpy.context.temp_override(**override):
                            result = bpy.ops.uv.uvv_trimsheet_tool_modal('INVOKE_DEFAULT')
                            if 'RUNNING_MODAL' in result:
                                return True
                            else:
                                return False
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        return False

        # No UV editor found
        return False
    finally:
        _starting_modal = False

@persistent
def check_trimsheet_tool_active(dummy):
    """Check if UV editor is open and start modal if needed (deprecated, kept for compatibility)"""
    global _starting_modal
    
    # CRITICAL: Prevent recursive calls from depsgraph handler
    # The depsgraph handler fires very frequently and can cause infinite recursion
    # if it tries to start the modal, which triggers more depsgraph updates
    if _starting_modal:
        return
    
    # Don't try to start if already running
    if UVV_OT_trimsheet_tool_modal._is_running:
        return
    
    # Skip if modal was recently attempted (give it time to initialize)
    # This prevents rapid-fire attempts that can cause recursion
    _starting_modal = True
    try:
        start_trimsheet_modal_if_needed()
    finally:
        # Reset flag after a short delay to allow modal to start
        # Use a simple approach: just reset immediately since start_trimsheet_modal_if_needed
        # should complete quickly
        _starting_modal = False

@persistent
def trimsheet_load_handler(dummy):
    """Ensure trimsheet modal is initialized when files are loaded or scenes change"""
    global _initialized_scenes
    
    try:
        if not bpy.context or not bpy.context.scene:
            return

        scene = bpy.context.scene
        scene_id = id(scene)  # Use object id to track scenes

        # Check if we've already initialized this scene
        if scene_id in _initialized_scenes:
            return

        # Check if scene has uvv_settings (might not exist during early initialization)
        if not hasattr(scene, 'uvv_settings'):
            return

        # load_post handler is a safe context, so we can try to start directly
        # But still use the deferral mechanism to be safe
        # Start the modal if UV editor is open
        if start_trimsheet_modal_if_needed():
            # Mark this scene as initialized
            _initialized_scenes.add(scene_id)
            print(f"UVV: Trimsheet modal initialized for scene '{scene.name}'")

    except Exception as e:
        print(f"UVV: Failed to initialize trimsheet modal: {e}")
        import traceback
        traceback.print_exc()


classes = [
    UVV_OT_trimsheet_tool_modal,
]


def register():
    """Register handlers and initialize modal (classes are registered by operators/__init__.py)"""
    global _initialized_scenes

    # IMPORTANT: Reset modal state on register (for reloads)
    # This ensures clean state when reloading
    global _starting_modal, _uvv_trimsheet_reloading
    UVV_OT_trimsheet_tool_modal._is_running = False
    _starting_modal = False
    _uvv_trimsheet_reloading = False  # Clear reload flag on register
    _initialized_scenes.clear()

    # CRITICAL FIX: Clear reload flag on ALL module instances (including old ones from previous reloads)
    print("UVV DEBUG: Clearing reload flags on all module instances...")
    try:
        import sys
        for mod in list(sys.modules.values()):
            if mod and hasattr(mod, '_uvv_trimsheet_reloading'):
                old_value = getattr(mod, '_uvv_trimsheet_reloading', None)
                mod._uvv_trimsheet_reloading = False
                if old_value:
                    print(f"UVV DEBUG: Cleared reload flag on module: {getattr(mod, '__name__', 'unknown')}")
    except Exception as e:
        print(f"UVV DEBUG: Error clearing reload flags: {e}")
    
    # DISABLED: load_post handler auto-start causes crashes on reload
    # # Register load_post handler (fires when .blend files are loaded)
    # try:
    #     # Remove any existing handler first (in case of reload)
    #     if trimsheet_load_handler in bpy.app.handlers.load_post:
    #         bpy.app.handlers.load_post.remove(trimsheet_load_handler)
    #     bpy.app.handlers.load_post.append(trimsheet_load_handler)
    #     print("UVV: Trimsheet modal load_post handler registered")
    # except Exception as e:
    #     print(f"UVV: Error registering load_post handler: {e}")
    print("UVV DEBUG: load_post handler DISABLED")
    
    # DISABLED: Auto-start causes crashes on reload
    # Modal must be started manually for now
    print("UVV DEBUG: Auto-start DISABLED - modal will NOT start automatically")

    # # Also use a delayed timer to catch the initial registration case
    # # This handles: addon enable, addon reload, new Blender session
    # def delayed_init():
    #     # Only start if modal is not already running
    #     if not UVV_OT_trimsheet_tool_modal._is_running:
    #         # Check if we have a valid context before trying to start modal
    #         # Modal operations require a valid window/context
    #         try:
    #             if bpy.context and bpy.context.window_manager and bpy.context.window_manager.windows:
    #                 _initialized_scenes.clear()  # Reset tracking on registration
    #                 trimsheet_load_handler(None)
    #             else:
    #                 # Context not ready yet, try again later
    #                 return 0.5  # Retry after 0.5 seconds
    #         except Exception as e:
    #             print(f"UVV: Error in delayed_init: {e}")
    #             return None  # Give up after error
    #     return None  # One-shot timer (or None to stop)
    #
    # # Cancel any existing timer and register new one
    # try:
    #     # CRITICAL: Use longer delay after reload to give Blender time to clean up old handlers
    #     # This prevents crashes from accessing freed memory
    #     bpy.app.timers.register(delayed_init, first_interval=2.0)  # 2 second delay to prevent reload crashes
    #     print("UVV DEBUG: Delayed init scheduled for 2.0 seconds")
    # except Exception as e:
    #     print(f"UVV: Error registering delayed init timer: {e}")
    
    # DISABLED: Depsgraph handler causes recursion issues
    # The depsgraph handler fires too frequently and can cause infinite recursion
    # when trying to start the modal. We rely on load_post and timer instead.
    # if check_trimsheet_tool_active in bpy.app.handlers.depsgraph_update_post:
    #     bpy.app.handlers.depsgraph_update_post.remove(check_trimsheet_tool_active)
    #     print("UVV: Depsgraph handler disabled to prevent recursion")


def unregister():
    """Unregister handlers (classes are unregistered by operators/__init__.py)"""
    global _initialized_scenes, _starting_modal, _registered_draw_handlers

    print("UVV DEBUG: ========== UNREGISTER CALLED - CLEANING UP ==========")

    # CRITICAL: Set reload flag FIRST to prevent any timer callbacks from executing
    # This must be set before any cleanup to prevent crashes
    global _uvv_trimsheet_reloading
    _uvv_trimsheet_reloading = True

    # CRITICAL: Force stop any running modal operators by simulating ESC key
    # This prevents crashes when reloading the addon while modal is running
    if UVV_OT_trimsheet_tool_modal._is_running:
        print("UVV DEBUG: Modal is running - attempting to cancel it...")
        try:
            # Try to cancel the modal operator by sending ESC event
            # This is safer than just setting the flag
            import bpy
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        # Simulate pressing ESC to cancel the modal
                        with bpy.context.temp_override(window=window, area=area):
                            # Force finish the modal
                            # Note: We can't actually send events, so we just set the flag
                            UVV_OT_trimsheet_tool_modal._is_running = False
                            print("UVV DEBUG: Modal flag set to False")
                            break
        except Exception as e:
            print(f"UVV DEBUG: Error canceling modal: {e}")
            UVV_OT_trimsheet_tool_modal._is_running = False

    # IMPORTANT: Reset modal running state to prevent crashes on reload
    # The modal operator instance might still exist, so we force it to False
    UVV_OT_trimsheet_tool_modal._is_running = False
    _starting_modal = False

    print("UVV DEBUG: Modal state reset complete")
    
    # Clean up any registered draw handlers
    for handler_ref in _registered_draw_handlers[:]:  # Copy list to avoid modification during iteration
        try:
            if handler_ref:
                bpy.types.SpaceImageEditor.draw_handler_remove(handler_ref, 'WINDOW')
        except:
            pass
    _registered_draw_handlers.clear()
    
    # Remove handlers
    try:
        if trimsheet_load_handler in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(trimsheet_load_handler)
    except Exception as e:
        print(f"UVV: Error removing load_post handler: {e}")
    
    # Remove depsgraph handler if it exists (from previous versions)
    try:
        if check_trimsheet_tool_active in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(check_trimsheet_tool_active)
            print("UVV: Removed legacy depsgraph handler")
    except Exception as e:
        pass  # Ignore if already removed or doesn't exist
    
    # Reset initialization tracking
    _initialized_scenes.clear()

    # CRITICAL FIX: Unregister ALL active timers to prevent callbacks after reload
    # This is the main cause of crashes - timers fire after module is unloaded
    try:
        # Get all registered timer functions and unregister any that belong to this module
        if hasattr(bpy.app.timers, 'is_registered'):
            # Try to unregister common timer functions from this module
            timer_functions = [
                start_trimsheet_modal_if_needed,
                check_trimsheet_tool_active,
                trimsheet_load_handler
            ]
            for func in timer_functions:
                try:
                    if bpy.app.timers.is_registered(func):
                        bpy.app.timers.unregister(func)
                        print(f"UVV DEBUG: Unregistered timer: {func.__name__}")
                except:
                    pass
        print("UVV DEBUG: Timer cleanup complete")
    except Exception as e:
        print(f"UVV DEBUG: Error during timer cleanup: {e}")
