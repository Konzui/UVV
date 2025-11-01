import bpy
import bmesh
import os
from bpy.types import WorkSpaceTool


class UVV_OT_SeamBrush(bpy.types.Operator):
    """Seam brush - timer-based click detection for intelligent edge seaming"""
    bl_idname = "uv.uvv_seam_brush"
    bl_label = "Seam Brush"
    bl_description = "Click edges to mark seams with intelligent click detection"
    bl_options = {'REGISTER', 'UNDO'}

    # Instance variables for tracking selection changes and mode
    _previous_selection = None
    _previous_mode = None

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH' and
            context.active_object and
            context.active_object.type == 'MESH'
        )

    def invoke(self, context, event):
        """Start modal operation for selection monitoring"""
        # Initialize selection and mode tracking
        self._previous_selection = set()
        self._previous_mode = context.mode

        # Ensure we're in edge select mode
        if not context.tool_settings.mesh_select_mode[1]:
            bpy.ops.mesh.select_mode(type='EDGE')
            print("UVV: Switched to edge select mode")

        # Handle existing selection when entering tool
        obj = context.active_object
        if obj and obj.type == 'MESH':
            bm = bmesh.from_edit_mesh(obj.data)
            existing_selection = [e.index for e in bm.edges if e.select]

            if existing_selection:
                print(f"UVV: Found existing selection: {sorted(existing_selection)}")
                # Mark existing selection as seams
                for edge_idx in existing_selection:
                    if edge_idx < len(bm.edges):
                        bm.edges[edge_idx].seam = True
                bmesh.update_edit_mesh(obj.data)
                # Clear the selection
                bpy.ops.mesh.select_all(action='DESELECT')
                print(f"UVV: Marked {len(existing_selection)} existing edges as seams and cleared selection")

        # Start modal operation
        if context.space_data.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            print("UVV: Seam Brush active - selections will auto-convert to seams")
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a 3D viewport")
            return {'CANCELLED'}

    def modal(self, context, event):
        # Exit conditions
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            print("UVV: Seam Brush exited")
            return {'CANCELLED'}

        # Check if we're still in the right context and if our tool is still active
        if (context.mode != 'EDIT_MESH' or
            not context.active_object or
            context.active_object.type != 'MESH' or
            context.workspace.tools.from_space_view3d_mode(context.mode, create=False).idname != "uvv.seam_brush"):
            print("UVV: Tool switched - exiting")
            return {'CANCELLED'}

        # Monitor selection changes and auto-convert to seams
        self.check_selection_changes(context, event)

        return {'PASS_THROUGH'}


    def check_selection_changes(self, context, event):
        """Monitor selection changes and auto-convert to seams"""
        try:
            obj = context.active_object
            if not obj or obj.type != 'MESH':
                return

            # Check if mode changed (e.g., tab out and back in)
            if context.mode != self._previous_mode:
                # Reset selection tracking when mode changes
                self._previous_selection = set()
                self._previous_mode = context.mode

            bm = bmesh.from_edit_mesh(obj.data)
            selected_edges = [e for e in bm.edges if e.select]
            current_selection = set(e.index for e in selected_edges)

            # Check if selection changed
            if current_selection != self._previous_selection:
                added = current_selection - self._previous_selection
                print(f"UVV: Selection changed! Current: {current_selection}, Added: {added}")

                # Only process if we have new selections
                if added:
                    print(f"UVV: Processing {len(added)} new edges")

                    # Check for SHIFT+ALT (clear edge loop seams)
                    if hasattr(event, 'shift') and event.shift and hasattr(event, 'alt') and event.alt:
                        print("UVV: SHIFT+ALT detected - clearing seams")
                        for edge in selected_edges:
                            edge.seam = False
                        bmesh.update_edit_mesh(obj.data)
                        bpy.ops.mesh.select_all(action='DESELECT')
                        current_selection = set()

                    # Check for ALT only (mark edge loop seams)
                    elif hasattr(event, 'alt') and event.alt:
                        print("UVV: ALT detected - marking seams")
                        for edge in selected_edges:
                            edge.seam = True
                        bmesh.update_edit_mesh(obj.data)
                        bpy.ops.mesh.select_all(action='DESELECT')
                        current_selection = set()

                    # Check for SHIFT only (toggle individual edges)
                    elif hasattr(event, 'shift') and event.shift:
                        print("UVV: SHIFT detected - toggling seams")
                        # Process each newly added edge
                        for edge_idx in added:
                            if edge_idx < len(bm.edges):
                                edge = bm.edges[edge_idx]
                                if edge.seam:
                                    edge.seam = False
                                else:
                                    edge.seam = True

                        bmesh.update_edit_mesh(obj.data)
                        bpy.ops.mesh.select_all(action='DESELECT')
                        current_selection = set()
                    else:
                        print(f"UVV: No modifiers detected - SHIFT: {hasattr(event, 'shift') and event.shift}, ALT: {hasattr(event, 'alt') and event.alt}")
                else:
                    print("UVV: Selection changed but no new edges added")

            # Fallback: If we have a selection but no change was detected (timing issue)
            elif len(current_selection) > 0 and hasattr(event, 'shift') and event.shift and not (hasattr(event, 'alt') and event.alt):
                print("UVV: Fallback triggered - processing existing selection")
                # Process all currently selected edges
                for edge in selected_edges:
                    if edge.seam:
                        edge.seam = False
                    else:
                        edge.seam = True

                bmesh.update_edit_mesh(obj.data)
                bpy.ops.mesh.select_all(action='DESELECT')
                current_selection = set()

            # Update previous selection
            self._previous_selection = current_selection

        except Exception as e:
            print(f"UVV: Error: {e}")






class UVV_WT_SeamBrush(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'

    # The prefix of the idname should be your add-on name.
    bl_idname = "uvv.seam_brush"
    bl_label = "Seam Brush"
    bl_description = "Select edges to mark seams. Alt+click for edge loops, Shift+Alt+click to clear edge loop seams"
    bl_icon = os.path.join(os.path.dirname(__file__), "..", "icons", "ops.seam.brush")
    bl_widget = None
    bl_keymap = (
        ("uv.uvv_seam_brush", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
    )

    @staticmethod
    def draw_settings(context, layout, tool):
        """Draw tool settings in the header"""
        layout.label(text="Click: Mark Seam | Alt+Click: Mark Edge Loop | Shift+Alt+Click: Clear Edge Loop")





def register():
    bpy.utils.register_class(UVV_OT_SeamBrush)


def register_tool():
    """Register the workspace tool separately - Simplified for stability"""
    print("UVV: Starting simple tool registration...")

    # Debug the icon path - comprehensive debugging
    icon_name = "ops.gpencil.draw.eraser.new"
    icon_path = os.path.join(os.path.dirname(__file__), "..", "icons", icon_name)
    icon_path_dat = icon_path + ".dat"

    print(f"UVV: Looking for icon: {icon_name}")
    print(f"UVV: Icon path: {icon_path}")
    print(f"UVV: Icon path exists: {os.path.exists(icon_path)}")
    print(f"UVV: Icon DAT path: {icon_path_dat}")
    print(f"UVV: Icon DAT path exists: {os.path.exists(icon_path_dat)}")

    # List all files in the icons directory
    icons_dir = os.path.join(os.path.dirname(__file__), "..", "icons")
    try:
        files_in_icons = os.listdir(icons_dir)
        print(f"UVV: Files in icons directory: {files_in_icons}")
        seam_files = [f for f in files_in_icons if "seam" in f.lower()]
        print(f"UVV: Seam-related files: {seam_files}")
    except Exception as e:
        print(f"UVV: Error listing icons directory: {e}")

    # Check file sizes
    if os.path.exists(icon_path):
        try:
            file_size = os.path.getsize(icon_path)
            print(f"UVV: Icon file size: {file_size} bytes")
        except Exception as e:
            print(f"UVV: Error getting file size: {e}")

    if os.path.exists(icon_path_dat):
        try:
            file_size = os.path.getsize(icon_path_dat)
            print(f"UVV: DAT file size: {file_size} bytes")
        except Exception as e:
            print(f"UVV: Error getting DAT file size: {e}")

    try:
        # Simple registration without complex operations
        bpy.utils.register_tool(UVV_WT_SeamBrush)
        print("UVV: Seam Brush tool registered successfully")
    except Exception as e:
        print(f"UVV: Failed to register Seam Brush tool: {e}")

    print("UVV: Tool registration complete.")


def unregister_tool():
    """Unregister the workspace tool separately"""
    print("UVV: Starting tool unregistration...")
    try:
        bpy.utils.unregister_tool(UVV_WT_SeamBrush)
        print("UVV: Seam Brush tool unregistered successfully")
    except Exception as e:
        print(f"UVV: Failed to unregister Seam Brush tool: {e}")

    # Debug: Print remaining tools
    print("UVV: Tools after unregistration:")
    for tool in bpy.types.WorkSpaceTool.__subclasses__():
        if hasattr(tool, 'bl_idname'):
            print(f"  - {tool.bl_idname}")


def unregister():
    unregister_tool()
    bpy.utils.unregister_class(UVV_OT_SeamBrush)