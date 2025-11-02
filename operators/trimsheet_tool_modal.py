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

    @classmethod
    def poll(cls, context):
        return (context.area and
                context.area.type == 'IMAGE_EDITOR')

    def invoke(self, context, event):
        """Start the modal operator"""
        # CRITICAL: Check reload flag first - prevents crashes during/after reload
        # Check if ANY module instance (old or new after reload) has reloading flag set
        global _uvv_trimsheet_reloading
        try:
            import sys
            # Quick check: if our own module has the flag set, we're reloading
            if _uvv_trimsheet_reloading:
                print("UVV DEBUG: Addon reloading, cancelling invoke")
                return {'CANCELLED'}
            # Also check for old module instances that might still have flag set
            for mod in sys.modules.values():
                if mod and mod != sys.modules.get(__name__) and hasattr(mod, 'UVV_OT_trimsheet_tool_modal') and hasattr(mod, '_uvv_trimsheet_reloading'):
                    if getattr(mod, '_uvv_trimsheet_reloading', False):
                        print("UVV DEBUG: Addon reloading (old module), cancelling invoke")
                        return {'CANCELLED'}
        except:
            pass  # If check fails, continue (safer than blocking)
        
        # Prevent multiple instances (defensive check)
        if UVV_OT_trimsheet_tool_modal._is_running:
            print("UVV DEBUG: Modal already running, cancelling invoke")
            return {'CANCELLED'}
        
        # Safety check: ensure context is valid and has required attributes
        if not context:
            print("UVV DEBUG: Invalid context (None), cancelling invoke")
            return {'CANCELLED'}
        
        if not hasattr(context, 'window_manager') or not context.window_manager:
            print("UVV DEBUG: Invalid context (no window_manager), cancelling invoke")
            return {'CANCELLED'}
        
        # Additional safety: check if window_manager is in a valid state
        # Try multiple ways to validate it's not a dangling pointer
        try:
            # Try to access a safe property to ensure window_manager is valid
            windows = context.window_manager.windows
            # Verify windows is actually a list/iterable (not None or invalid)
            if windows is None:
                print("UVV DEBUG: window_manager.windows is None, cancelling invoke")
                return {'CANCELLED'}
            # Try to get length to ensure it's a valid iterable
            _ = len(windows)
        except (AttributeError, RuntimeError, TypeError, SystemError) as e:
            print(f"UVV DEBUG: window_manager not ready: {e}, cancelling invoke")
            return {'CANCELLED'}
        except Exception as e:
            # Catch ALL exceptions - window_manager might be invalid memory
            print(f"UVV DEBUG: window_manager access failed: {e}, cancelling invoke")
            return {'CANCELLED'}

        print("UVV DEBUG: ========== TRIMSHEET MODAL STARTED ==========")
        UVV_OT_trimsheet_tool_modal._is_running = True
        try:
            # Use safe method to add modal handler
            # Double-check reload flag before attempting
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
        except (AttributeError, RuntimeError, SystemError, TypeError) as e:
            # Reset flag if handler add fails
            UVV_OT_trimsheet_tool_modal._is_running = False
            print(f"UVV DEBUG: Failed to add modal handler: {e}")
            # Don't print traceback to avoid recursion issues
            return {'CANCELLED'}
        except Exception as e:
            # Reset flag if handler add fails - catch ALL exceptions
            UVV_OT_trimsheet_tool_modal._is_running = False
            print(f"UVV DEBUG: Failed to add modal handler (unexpected error): {type(e).__name__}")
            return {'CANCELLED'}

    def modal(self, context, event):
        """Handle ALL mouse events for the tool"""
        # Debug: verify modal is processing ANY events at all
        if event.type in ('LEFTMOUSE', 'MOUSEMOVE', 'RIGHTMOUSE'):
            print(f"UVV DEBUG: Modal processing {event.type} = {event.value} at ({event.mouse_x}, {event.mouse_y})")
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
                        if event_in_uv_editor:
                            break
                if event_in_uv_editor:
                    break

            # If event is not in UV editor, pass through
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
            context = type('obj', (object,), {
                'area': uv_area,
                'region': uv_region,
                'window': uv_window,
                'screen': uv_window.screen,
                'scene': context.scene,
                'window_manager': context.window_manager,
                'space_data': uv_area.spaces.active,
                'preferences': context.preferences,
                'mode': context.mode,
                'active_object': context.active_object,
            })()

            settings = context.scene.uvv_settings
        except Exception as e:
            # If anything fails during context setup, just pass through
            print(f"UVV DEBUG: Error in modal context setup: {e}")
            import traceback
            traceback.print_exc()
            return {'PASS_THROUGH'}

        # Log all LEFTMOUSE events for debugging
        if event.type == 'LEFTMOUSE':
            print(f"UVV DEBUG: LEFTMOUSE event - value: {event.value}, position: ({mouse_region_x}, {mouse_region_y})")
            print(f"UVV DEBUG: Event in UV editor: {event_in_uv_editor}, settings.trim_edit_mode: {settings.trim_edit_mode if hasattr(settings, 'trim_edit_mode') else 'N/A'}")

        # MOUSEMOVE - Update hover states
        if event.type == 'MOUSEMOVE':
            try:
                from ..utils import trimsheet_transform_draw

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
            except Exception as e:
                print(f"UVV DEBUG: Error in MOUSEMOVE handler: {e}")
                return {'PASS_THROUGH'}

        # LEFTMOUSE PRESS - Handle transforms first if in edit mode
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            print(f"UVV DEBUG: LEFTMOUSE PRESS detected! Edit mode: {settings.trim_edit_mode}")
            try:
                from ..utils import trimsheet_transform_draw, trimsheet_utils

                # If in edit mode, prioritize transform handles over text labels
                if settings.trim_edit_mode:
                    print(f"UVV DEBUG: In edit mode, checking handles...")
                    material = trimsheet_utils.get_active_material(context)
                    if material and material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims):
                        trim = material.uvv_trims[material.uvv_trims_index]
                        
                        # Check if clicking on transform handles (includes center/inside trim)
                        handle_type, handle_id = trimsheet_transform_draw.get_handle_type_at_position(
                            context, trim, mouse_region_x, mouse_region_y
                        )
                        
                        if handle_type:
                            # Clicking on a handle (corner, edge, or center) - do transform
                            # This includes clicking on the trim name text since it's inside the trim
                            try:
                                override = {
                                    'window': self._uv_window,
                                    'area': self._uv_area,
                                    'region': self._uv_region,
                                    'space_data': self._uv_area.spaces.active,
                                }
                                with bpy.context.temp_override(**override):
                                    bpy.ops.uv.uvv_trim_edit_transform('INVOKE_DEFAULT')
                            except Exception as e:
                                print(f"UVV DEBUG: Error invoking transform: {e}")
                                import traceback
                                traceback.print_exc()
                            return {'PASS_THROUGH'}
                        else:
                            # Clicking outside trim area - exit edit mode
                            settings.trim_edit_mode = False
                            context.area.tag_redraw()
                            return {'RUNNING_MODAL'}

                # Not in edit mode - handle text label clicks for selection
                # First, ensure modal is running (in case it wasn't started on load)
                if not UVV_OT_trimsheet_tool_modal._is_running:
                    print("UVV DEBUG: Modal not running on trim click, attempting to start...")
                    # Try to start modal - use direct invocation since we're in modal context already
                    # This is safe because we're being called from the modal operator's modal() method
                    try:
                        override = {
                            'window': self._uv_window,
                            'area': self._uv_area,
                            'region': self._uv_region,
                            'space_data': self._uv_area.spaces.active,
                        }
                        with bpy.context.temp_override(**override):
                            # This should be safe since we're already in a modal context
                            bpy.ops.uv.uvv_trimsheet_tool_modal('INVOKE_DEFAULT')
                    except Exception as e:
                        print(f"UVV DEBUG: Failed to start modal on click: {e}")
                
                # Check if clicking on the lock button (before text label check)
                print(f"UVV DEBUG: Checking lock button at mouse position: ({mouse_region_x}, {mouse_region_y})")
                if trimsheet_transform_draw.get_lock_button_at_position(
                    context, mouse_region_x, mouse_region_y
                ):
                    # Toggle locked state
                    from ..utils import trimsheet_utils
                    material = trimsheet_utils.get_active_material(context)
                    if material and material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims):
                        trim = material.uvv_trims[material.uvv_trims_index]
                        trim.locked = not trim.locked
                        print(f"UVV DEBUG: Toggled lock for trim {material.uvv_trims_index}: {trim.locked}")
                        context.area.tag_redraw()
                        return {'RUNNING_MODAL'}
                
                # Check if clicking on a text label
                text_idx = trimsheet_transform_draw.get_text_label_at_position(
                    context, mouse_region_x, mouse_region_y
                )

                print(f"UVV DEBUG: Click detected, text_idx = {text_idx}")

                if text_idx is not None:
                    print(f"UVV DEBUG: Clicked on trim {text_idx}")
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
                            # Detect double-click
                            current_time = time.time()
                            is_double_click = (
                                text_idx == self.__class__._last_clicked_trim and
                                (current_time - self.__class__._last_click_time) < self.__class__._double_click_threshold
                            )

                            print(f"UVV DEBUG: is_double_click = {is_double_click}, last_trim = {self.__class__._last_clicked_trim}, time_diff = {current_time - self.__class__._last_click_time}")

                            if is_double_click:
                                # Double-click: Select trim and enter edit mode
                                print(f"UVV DEBUG: DOUBLE-CLICK - Entering edit mode for trim {text_idx}")
                                material.uvv_trims_index = text_idx
                                settings.trim_edit_mode = True
                                # Reset click tracking to prevent triple-click issues
                                self.__class__._last_clicked_trim = -1
                                self.__class__._last_click_time = 0.0
                            else:
                                # Single-click: Select trim only (don't enter edit mode)
                                print(f"UVV DEBUG: SINGLE-CLICK - Selecting trim {text_idx} (no edit mode)")
                                material.uvv_trims_index = text_idx
                                settings.trim_edit_mode = False
                                # Update click tracking for double-click detection
                                self.__class__._last_click_time = current_time
                                self.__class__._last_clicked_trim = text_idx

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

    def finish(self, context):
        """Clean up"""
        UVV_OT_trimsheet_tool_modal._is_running = False
        if context.window:
            context.window.cursor_modal_restore()
        print("UVV DEBUG: Modal finished and cleaned up")
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
                
                # Double-check modal isn't running (defensive check)
                if UVV_OT_trimsheet_tool_modal._is_running:
                    _starting_modal = False
                    return False
                
                # Use timer-based approach for safety (simpler and more reliable)
                def start_modal_timer():
                    """Timer callback that starts the modal (safe context)"""
                    global _starting_modal
                    
                    # CRITICAL: Check reload flag FIRST - prevents crashes during/after reload
                    # Check if current module or any old module instance has reloading flag
                    try:
                        import sys
                        # Check current module first (fast path)
                        current_mod = sys.modules.get(__name__)
                        if current_mod and hasattr(current_mod, '_uvv_trimsheet_reloading'):
                            if getattr(current_mod, '_uvv_trimsheet_reloading', False):
                                _starting_modal = False
                                return None
                        # Also check old module instances (after reload, old module may still exist)
                        for mod in sys.modules.values():
                            if mod and mod != current_mod and hasattr(mod, 'UVV_OT_trimsheet_tool_modal') and hasattr(mod, '_uvv_trimsheet_reloading'):
                                if getattr(mod, '_uvv_trimsheet_reloading', False):
                                    _starting_modal = False
                                    return None  # Stop timer immediately if reloading
                    except:
                        # If check fails, assume reloading (safe default)
                        _starting_modal = False
                        return None
                    
                    # Additional safety: verify operator is still registered
                    try:
                        if not hasattr(bpy.ops.uv, 'uvv_trimsheet_tool_modal'):
                            _starting_modal = False
                            return None  # Operator unregistered, abort
                    except:
                        _starting_modal = False
                        return None
                    
                    try:
                        # Final safety checks
                        if UVV_OT_trimsheet_tool_modal._is_running:
                            _starting_modal = False
                            return None  # Stop timer
                        
                        # Validate context is still valid - check multiple ways
                        if not bpy.context:
                            _starting_modal = False
                            return None
                        
                        # Validate window_manager exists and is valid
                        try:
                            if not hasattr(bpy.context, 'window_manager') or not bpy.context.window_manager:
                                _starting_modal = False
                                return None
                            
                            # Try to access window_manager properties to ensure it's valid
                            windows = bpy.context.window_manager.windows
                            if windows is None:
                                _starting_modal = False
                                return None
                            # Verify we can iterate (catch invalid memory access)
                            _ = len(windows)
                        except (AttributeError, RuntimeError, TypeError, SystemError):
                            _starting_modal = False
                            return None
                        except Exception:
                            # Catch ALL other exceptions (including potential access violations)
                            _starting_modal = False
                            return None
                        
                        # Find UV editor again (window/area references may have changed)
                        for w in windows:
                            try:
                                if not hasattr(w, 'screen') or not w.screen:
                                    continue
                                for a in w.screen.areas:
                                    try:
                                        if a.type == 'IMAGE_EDITOR' and hasattr(a, 'spaces') and a.spaces.active and a.spaces.active.mode == 'UV':
                                            # Double-check reload flag before invoking
                                            try:
                                                import sys
                                                current_mod = sys.modules.get(__name__)
                                                # Check current module
                                                if current_mod and hasattr(current_mod, '_uvv_trimsheet_reloading') and getattr(current_mod, '_uvv_trimsheet_reloading', False):
                                                    _starting_modal = False
                                                    return None
                                                # Check old modules
                                                for mod in sys.modules.values():
                                                    if mod and mod != current_mod and hasattr(mod, 'UVV_OT_trimsheet_tool_modal') and hasattr(mod, '_uvv_trimsheet_reloading'):
                                                        if getattr(mod, '_uvv_trimsheet_reloading', False):
                                                            _starting_modal = False
                                                            return None
                                            except:
                                                _starting_modal = False
                                                return None
                                            
                                            # Try to start modal
                                            override = {'window': w, 'screen': w.screen, 'area': a}
                                            with bpy.context.temp_override(**override):
                                                result = bpy.ops.uv.uvv_trimsheet_tool_modal('INVOKE_DEFAULT')
                                                if 'FINISHED' in result or 'RUNNING_MODAL' in result:
                                                    print("UVV DEBUG: Trimsheet modal started (from timer)")
                                                _starting_modal = False
                                                return None  # One-shot timer
                                    except Exception:
                                        continue  # Skip this area if there's an error
                            except Exception:
                                continue  # Skip this window if there's an error
                        
                        _starting_modal = False
                        return None  # Stop timer if no UV editor found
                    except Exception as e:
                        print(f"UVV DEBUG: Error in timer callback: {type(e).__name__}")
                        _starting_modal = False
                        UVV_OT_trimsheet_tool_modal._is_running = False
                        return None  # Stop timer on error
                
                # Register timer to start modal safely
                try:
                    timer_handle = bpy.app.timers.register(start_modal_timer, first_interval=0.1)
                    print("UVV DEBUG: Scheduled modal start via timer")
                    return True  # Indicate we scheduled the start
                except Exception as e:
                    print(f"UVV DEBUG: Failed to register timer: {e}")
                    _starting_modal = False
                    return False
                    
    _starting_modal = False  # Reset flag if no UV editor found
    return False

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
    
    # Register load_post handler (fires when .blend files are loaded)
    try:
        # Remove any existing handler first (in case of reload)
        if trimsheet_load_handler in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(trimsheet_load_handler)
        bpy.app.handlers.load_post.append(trimsheet_load_handler)
        print("UVV: Trimsheet modal load_post handler registered")
    except Exception as e:
        print(f"UVV: Error registering load_post handler: {e}")
    
    # Also use a delayed timer to catch the initial registration case
    # This handles: addon enable, addon reload, new Blender session
    def delayed_init():
        # Only start if modal is not already running
        if not UVV_OT_trimsheet_tool_modal._is_running:
            # Check if we have a valid context before trying to start modal
            # Modal operations require a valid window/context
            try:
                if bpy.context and bpy.context.window_manager and bpy.context.window_manager.windows:
                    _initialized_scenes.clear()  # Reset tracking on registration
                    trimsheet_load_handler(None)
                else:
                    # Context not ready yet, try again later
                    return 0.5  # Retry after 0.5 seconds
            except Exception as e:
                print(f"UVV: Error in delayed_init: {e}")
                return None  # Give up after error
        return None  # One-shot timer (or None to stop)
    
    # Cancel any existing timer and register new one
    try:
        bpy.app.timers.register(delayed_init, first_interval=0.5)  # Longer delay to ensure context is ready
    except Exception as e:
        print(f"UVV: Error registering delayed init timer: {e}")
    
    # DISABLED: Depsgraph handler causes recursion issues
    # The depsgraph handler fires too frequently and can cause infinite recursion
    # when trying to start the modal. We rely on load_post and timer instead.
    # if check_trimsheet_tool_active in bpy.app.handlers.depsgraph_update_post:
    #     bpy.app.handlers.depsgraph_update_post.remove(check_trimsheet_tool_active)
    #     print("UVV: Depsgraph handler disabled to prevent recursion")


def unregister():
    """Unregister handlers (classes are unregistered by operators/__init__.py)"""
    global _initialized_scenes, _starting_modal, _registered_draw_handlers
    
    # CRITICAL: Set reload flag FIRST to prevent any timer callbacks from executing
    # This must be set before any cleanup to prevent crashes
    global _uvv_trimsheet_reloading
    _uvv_trimsheet_reloading = True
    
    # IMPORTANT: Reset modal running state to prevent crashes on reload
    # The modal operator instance might still exist, so we force it to False
    UVV_OT_trimsheet_tool_modal._is_running = False
    _starting_modal = False
    
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
    
    # Note: We can't directly cancel timer functions, but setting _is_running = False
    # and _starting_modal = False should prevent them from doing anything harmful
