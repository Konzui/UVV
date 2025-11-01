import bpy
import bmesh
from bpy.types import Operator


class UVV_OT_ToggleUVSync(Operator):
    """Toggle UV Sync Mode"""
    bl_idname = "uv.uvv_toggle_uv_sync"
    bl_label = "Toggle UV Sync"
    bl_description = "Toggle UV Sync Mode - synchronizes UV and mesh selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def sync_selection_mode(self, context, uv_sync_enable):
        """Sync selection modes between UV and mesh"""
        scene = context.scene
        tool_settings = context.tool_settings

        vertex_mode = (True, False, False)
        edge_mode = (False, True, False)
        face_mode = (False, False, True)

        if uv_sync_enable:
            # UV Sync enabled: set mesh mode based on UV mode
            uv_select_mode = scene.tool_settings.uv_select_mode

            if uv_select_mode == 'VERTEX':
                tool_settings.mesh_select_mode = vertex_mode
            elif uv_select_mode == 'EDGE':
                tool_settings.mesh_select_mode = edge_mode
            elif uv_select_mode == 'FACE':
                tool_settings.mesh_select_mode = face_mode

        else:
            # UV Sync disabled: set UV mode based on mesh mode
            mesh_select_mode = tool_settings.mesh_select_mode[:]
            scene_tool_settings = scene.tool_settings

            if mesh_select_mode == vertex_mode:
                scene_tool_settings.uv_select_mode = 'VERTEX'
            elif mesh_select_mode == edge_mode:
                scene_tool_settings.uv_select_mode = 'EDGE'
            elif mesh_select_mode == face_mode:
                scene_tool_settings.uv_select_mode = 'FACE'

    def sync_selected_elements(self, context, uv_sync_enable):
        """Sync selected elements between UV and mesh"""
        for obj in context.objects_in_mode_unique_data:
            mesh_data = obj.data
            bm = bmesh.from_edit_mesh(mesh_data)

            # Get UV layer
            if not bm.loops.layers.uv:
                continue
            uv_layer = bm.loops.layers.uv.active

            if uv_sync_enable:
                # UV Sync enabled: select mesh elements based on UV selection
                # First deselect faces that don't have all UV loops selected
                for face in bm.faces:
                    for loop in face.loops:
                        loop_uv = loop[uv_layer]
                        if not loop_uv.select:
                            face.select = False
                            break

                # Select vertices based on UV selection
                for face in bm.faces:
                    for loop in face.loops:
                        loop_uv = loop[uv_layer]
                        if loop_uv.select:
                            loop.vert.select = True

                # Select edges if both vertices are selected
                for edge in bm.edges:
                    if all(vert.select for vert in edge.verts):
                        edge.select = True

            else:
                # UV Sync disabled: select UV elements based on mesh selection
                # Clear UV selection
                for face in bm.faces:
                    for loop in face.loops:
                        loop_uv = loop[uv_layer]
                        loop_uv.select = False

                mesh_select_mode = context.tool_settings.mesh_select_mode[:]

                if mesh_select_mode[2]:  # Face mode
                    # Select UV loops for selected faces
                    for face in bm.faces:
                        if face.select:
                            for loop in face.loops:
                                loop_uv = loop[uv_layer]
                                loop_uv.select = True
                else:
                    # Vertex/Edge mode: select UV loops for selected vertices
                    for face in bm.faces:
                        for loop in face.loops:
                            loop_uv = loop[uv_layer]
                            if loop.vert.select:
                                loop_uv.select = True

                # Select all faces when UV sync is disabled
                for face in bm.faces:
                    face.select = True

            bmesh.update_edit_mesh(mesh_data)

    def execute(self, context):
        tool_settings = context.tool_settings

        # Toggle UV sync mode
        current_sync = tool_settings.use_uv_select_sync
        new_sync = not current_sync
        tool_settings.use_uv_select_sync = new_sync

        # Sync selection modes
        self.sync_selection_mode(context, new_sync)

        # Sync selected elements
        self.sync_selected_elements(context, new_sync)

        # Report the change
        status = "enabled" if new_sync else "disabled"
        self.report({'INFO'}, f"UV Sync {status}")

        return {'FINISHED'}


class UVV_OT_IsolateIslands(Operator):
    """Isolate selected UV islands (Toggle) - Based on ZenUV implementation"""
    bl_idname = "uv.uvv_isolate_islands"
    bl_label = "Isolate Part"
    bl_description = "Isolate selected UV islands (Toggle) - Shows only selected islands or reveals all when already isolated"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Validate context"""
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ..utils import get_island, face_indexes_by_sel_mode
        
        b_is_image_editor = context.space_data.type == 'IMAGE_EDITOR'
        b_is_not_sync = b_is_image_editor and not context.scene.tool_settings.use_uv_select_sync
        
        b_all_isolated = True
        t_data = {}
        b_something_selected = False
        
        # Collect data for all objects
        for p_obj in context.objects_in_mode_unique_data:
            if p_obj.type == 'MESH':
                me = p_obj.data
                bm = bmesh.from_edit_mesh(me)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                uv_layer = bm.loops.layers.uv.active
                
                p_islands = []
                
                # Get selected face indices (context-aware: mesh selection in sync mode, UV selection in non-sync)
                selected_face_indices = face_indexes_by_sel_mode(context, bm)
                
                # Get islands from selection if there is any
                if len(selected_face_indices) > 0 and uv_layer:
                    p_islands = get_island(context, bm, uv_layer)
                
                # Build set of face indices to isolate
                p_faces_for_isolate = {
                    face.index
                    for island in p_islands
                    for face in island
                }
                
                t_data[me] = (bm, p_faces_for_isolate)
                
                if len(p_faces_for_isolate):
                    b_something_selected = True
        
        # If something is selected, isolate it
        if b_something_selected:
            mesh_sel_mode = context.tool_settings.mesh_select_mode
            b_has_vert_and_edges_in_selection_mode = mesh_sel_mode[0] or mesh_sel_mode[1]
            
            for me, (bm, p_faces_for_isolate) in t_data.items():
                b_changed = False
                
                for face in bm.faces:
                    if b_is_not_sync:
                        # In UV editor without sync: use selection instead of hiding
                        b_select = face.index in p_faces_for_isolate
                        
                        b_was_hidden = b_select and face.hide
                        if b_was_hidden:
                            face.hide_set(False)
                        
                        if b_was_hidden or face.select != b_select:
                            face.select_set(b_select)
                            b_all_isolated = False
                            b_changed = True
                    else:
                        # In 3D view or UV editor with sync: use hiding
                        b_hide = face.index not in p_faces_for_isolate
                        if face.hide != b_hide:
                            face.hide_set(b_hide)
                            b_all_isolated = False
                            b_changed = True
                
                if b_changed:
                    # Flush selection properly
                    if b_is_not_sync and b_has_vert_and_edges_in_selection_mode:
                        bm.select_flush(True)
                    else:
                        bm.select_flush_mode()
                    bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
        
        # If nothing selected or already isolated, reveal all
        if not b_something_selected or b_all_isolated:
            if b_is_not_sync:
                if bpy.ops.uv.reveal.poll():
                    bpy.ops.uv.reveal(select=False)
            else:
                if bpy.ops.mesh.reveal.poll():
                    bpy.ops.mesh.reveal(select=False)
        
        return {'FINISHED'}


class UVV_OT_OpenDocumentation(Operator):
    """Open UVV Documentation Website"""
    bl_idname = "uv.uvv_open_documentation"
    bl_label = "Documentation"
    bl_description = "Open UVV documentation website"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import webbrowser
        webbrowser.open("https://uvv.framer.website/")
        return {'FINISHED'}


class UVV_OT_OpenChangelog(Operator):
    """Open UVV Changelog"""
    bl_idname = "uv.uvv_open_changelog"
    bl_label = "Changelog"
    bl_description = "Open UVV changelog"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import webbrowser
        webbrowser.open("https://uvv.framer.website/changelog")
        return {'FINISHED'}


class UVV_OT_ShowVersionInfo(Operator):
    """Show UVV Version Information"""
    bl_idname = "uv.uvv_show_version_info"
    bl_label = "Version Info"
    bl_description = "Show UVV version information"
    bl_options = {'REGISTER'}

    version: bpy.props.StringProperty(
        name='Version',
        description='Available version',
        default=''
    )

    def execute(self, context):
        import webbrowser
        webbrowser.open("https://uvv.framer.website/downloads")
        self.report({'INFO'}, f"UVV: Opening download page for version {self.version}")
        return {'FINISHED'}


class UVV_OT_CheckForUpdates(Operator):
    """Check for UVV Updates"""
    bl_idname = "uv.uvv_check_for_updates"
    bl_label = "Check for Updates"
    bl_description = "Check for the latest version of UVV"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..utils.version_check import check_for_updates
        
        self.report({'INFO'}, "UVV: Checking for updates...")
        
        success = check_for_updates(context)
        
        if success:
            settings = context.scene.uvv_settings
            if settings.latest_version_available:
                self.report({'INFO'}, f"UVV: New version {settings.latest_version_available} available!")
            else:
                self.report({'INFO'}, "UVV: You are up to date!")
        else:
            self.report({'WARNING'}, "UVV: Failed to check for updates. Check console for details.")
        
        return {'FINISHED'}


class UVV_OT_DebugVersionCheck(Operator):
    """Debug Version Check - Test website fetch manually"""
    bl_idname = "uv.uvv_debug_version_check"
    bl_label = "Debug Version Check"
    bl_description = "Debug version check by testing website fetch manually"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..utils.version_check import debug_website_fetch
        
        self.report({'INFO'}, "UVV: Running debug version check...")
        
        result = debug_website_fetch()
        
        if result:
            self.report({'INFO'}, f"UVV: Debug found version: {result}")
        else:
            self.report({'WARNING'}, "UVV: Debug found no version. Check console for details.")
        
        return {'FINISHED'}


classes = [
    UVV_OT_ToggleUVSync,
    UVV_OT_IsolateIslands,
    UVV_OT_OpenDocumentation,
    UVV_OT_OpenChangelog,
    UVV_OT_ShowVersionInfo,
    UVV_OT_CheckForUpdates,
    UVV_OT_DebugVersionCheck,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)