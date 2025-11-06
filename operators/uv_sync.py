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


class UVV_OT_InstallUpdate(Operator):
    """Install UVV Update"""
    bl_idname = "uv.uvv_install_update"
    bl_label = "Install Update"
    bl_description = "Download and install the latest version of UVV"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        """Show confirmation dialog before installing"""
        if not context or not hasattr(context.scene, 'uvv_settings'):
            return {'CANCELLED'}
        
        settings = context.scene.uvv_settings
        
        if not settings.latest_version_available:
            self.report({'WARNING'}, "UVV: No update available")
            return {'CANCELLED'}
        
        version = settings.latest_version_available
        
        # Show confirmation dialog
        return context.window_manager.invoke_confirm(self, event)
    
    def draw(self, context):
        """Draw confirmation dialog"""
        layout = self.layout
        settings = context.scene.uvv_settings
        version = settings.latest_version_available
        
        layout.label(text=f"Install UVV version {version}?")
        layout.label(text="The addon will be updated automatically.")
        layout.label(text="Blender may need to be restarted after installation.")

    def execute(self, context):
        import os
        import tempfile
        import urllib.request
        import urllib.error
        import zipfile
        import shutil
        
        if not context or not hasattr(context.scene, 'uvv_settings'):
            self.report({'ERROR'}, "UVV: No valid context")
            return {'CANCELLED'}
        
        settings = context.scene.uvv_settings
        
        # Check if update is available
        if not settings.latest_version_available:
            self.report({'WARNING'}, "UVV: No update available")
            return {'CANCELLED'}
        
        # Check if download URL is available
        if not settings.update_download_url:
            self.report({'ERROR'}, "UVV: Download URL not available. Please check for updates first.")
            return {'CANCELLED'}
        
        download_url = settings.update_download_url
        version = settings.latest_version_available
        
        self.report({'INFO'}, f"UVV: Downloading version {version}...")
        
        try:
            # Create temporary directory for download
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, "uvv_update.zip")
            
            # Download the zip file
            try:
                request = urllib.request.Request(download_url)
                request.add_header('User-Agent', 'UVV-Addon/1.0')
                
                with urllib.request.urlopen(request, timeout=30) as response:
                    # Check if it's actually a zip file
                    content_type = response.headers.get('Content-Type', '')
                    if 'zip' not in content_type.lower() and not download_url.endswith('.zip'):
                        self.report({'ERROR'}, "UVV: Downloaded file is not a zip file")
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {'CANCELLED'}
                    
                    # Download with progress
                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0
                    chunk_size = 8192
                    
                    with open(zip_path, 'wb') as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Update progress (Blender doesn't have great progress reporting, but we can log)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                if downloaded % (chunk_size * 100) == 0:  # Log every ~800KB
                                    print(f"UVV: Download progress: {percent:.1f}%")
                
                print(f"UVV: Download complete: {os.path.getsize(zip_path)} bytes")
                
            except urllib.error.URLError as e:
                self.report({'ERROR'}, f"UVV: Network error downloading update: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {'CANCELLED'}
            except urllib.error.HTTPError as e:
                self.report({'ERROR'}, f"UVV: HTTP error downloading update: {e.code} - {e.reason}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {'CANCELLED'}
            
            # Validate zip file
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Check if zip is valid
                    bad_file = zip_ref.testzip()
                    if bad_file:
                        self.report({'ERROR'}, f"UVV: Corrupted zip file: {bad_file}")
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return {'CANCELLED'}
                    
                    # List files in zip (for debugging)
                    file_list = zip_ref.namelist()
                    print(f"UVV: Zip contains {len(file_list)} files")
                    
            except zipfile.BadZipFile:
                self.report({'ERROR'}, "UVV: Invalid zip file")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {'CANCELLED'}
            
            # Install the addon using Blender's built-in operator
            self.report({'INFO'}, "UVV: Installing update...")
            
            # Use Blender's addon install operator
            try:
                # The addon module name is always "UVV" because that's what the zip contains
                # The zip structure is: UVV/__init__.py, so Blender installs it as "UVV"
                addon_module_name = "UVV"
                
                # Try to find if UVV is already installed (might be under different name)
                # Search through installed addons to find UVV by checking bl_info
                found_addon_name = None
                for addon_name, addon_module in bpy.context.preferences.addons.items():
                    try:
                        # Check if this addon has UVV's bl_info
                        if hasattr(addon_module, 'module') and addon_module.module:
                            if hasattr(addon_module.module, 'bl_info'):
                                bl_info = addon_module.module.bl_info
                                if bl_info.get('name', '').startswith('🌀 UVV'):
                                    found_addon_name = addon_name
                                    break
                    except:
                        continue
                
                # IMPORTANT: Don't disable the addon if we're running from it
                # This prevents crashes. Blender will handle the overwrite.
                # Only disable if it's installed under a different name
                if found_addon_name and found_addon_name != "UVV":
                    print(f"UVV: Found existing addon as '{found_addon_name}', will disable it")
                    try:
                        if found_addon_name in bpy.context.preferences.addons:
                            print(f"UVV: Disabling current addon: {found_addon_name}")
                            bpy.ops.preferences.addon_disable(module=found_addon_name)
                    except Exception as e:
                        print(f"UVV: Warning: Could not disable addon {found_addon_name}: {e}")
                        # Continue anyway - installation should still work
                
                # Install the new version
                # Note: addon_install expects the filepath to be a string
                print(f"UVV: Installing from: {zip_path}")
                try:
                    bpy.ops.preferences.addon_install(filepath=zip_path, overwrite=True)
                    print("UVV: Installation successful")
                except Exception as e:
                    print(f"UVV: Error during installation: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
                
                # Re-enable the addon (it will be installed as "UVV" from the zip)
                # Use a timer to re-enable after a short delay to avoid conflicts
                print(f"UVV: Scheduling addon re-enable...")
                
                def re_enable_addon():
                    try:
                        if addon_module_name in bpy.context.preferences.addons:
                            if not bpy.context.preferences.addons[addon_module_name].enabled:
                                bpy.ops.preferences.addon_enable(module=addon_module_name)
                                print(f"UVV: Addon re-enabled successfully")
                        return None  # One-shot timer
                    except Exception as e:
                        print(f"UVV: Warning: Could not re-enable addon: {e}")
                        return None
                
                # Register a timer to re-enable after 0.5 seconds
                bpy.app.timers.register(re_enable_addon, first_interval=0.5)
                
                self.report({'INFO'}, f"UVV: Successfully installed version {version}! Please restart Blender for changes to take effect.")
                
            except Exception as e:
                self.report({'ERROR'}, f"UVV: Failed to install addon: {e}")
                import traceback
                traceback.print_exc()
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {'CANCELLED'}
            
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Clear update info after successful install
            settings.latest_version_available = ""
            settings.update_download_url = ""
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"UVV: Unexpected error during update: {e}")
            import traceback
            traceback.print_exc()
            # Try to cleanup temp directory
            try:
                if 'temp_dir' in locals():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            return {'CANCELLED'}


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


class UVV_OT_ShowVersionInfo(Operator):
    """Show UVV Version Information"""
    bl_idname = "uv.uvv_show_version_info"
    bl_label = "Version Info"
    bl_description = "Show UVV version information and installation details"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import os
        import sys
        
        # Get version from __init__.py
        from .. import __version__
        
        # Get the addon's file path
        addon_file = __file__
        addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(addon_file)))
        
        # Try to find the addon in preferences
        addon_info = []
        for addon_name, addon_module in bpy.context.preferences.addons.items():
            try:
                if hasattr(addon_module, 'module') and addon_module.module:
                    if hasattr(addon_module.module, 'bl_info'):
                        bl_info = addon_module.module.bl_info
                        if bl_info.get('name', '').startswith('🌀 UVV'):
                            addon_info.append({
                                'name': addon_name,
                                'enabled': addon_module.enabled,
                                'file': getattr(addon_module, 'module_file', 'Unknown'),
                                'version': bl_info.get('version', 'Unknown')
                            })
            except:
                continue
        
        # Print detailed info
        print("=" * 60)
        print("UVV: VERSION INFORMATION")
        print("=" * 60)
        print(f"Current Version (from __init__.py): {__version__}")
        print(f"Addon Directory: {addon_dir}")
        print(f"Addon File: {addon_file}")
        print("")
        
        if addon_info:
            print("Installed Addon(s):")
            for info in addon_info:
                print(f"  - Name: {info['name']}")
                print(f"    Enabled: {info['enabled']}")
                print(f"    File: {info['file']}")
                print(f"    Version (from bl_info): {info['version']}")
                print("")
        else:
            print("Warning: UVV addon not found in preferences!")
            print("")
        
        # Check for updates
        settings = context.scene.uvv_settings
        if settings.latest_version_available:
            print(f"Latest Available Version: {settings.latest_version_available}")
            print(f"Download URL: {settings.update_download_url}")
        else:
            print("No update available (or not checked yet)")
        
        print("=" * 60)
        
        # Show in UI
        version_msg = f"UVV Version: {__version__}"
        if addon_info:
            installed_version = addon_info[0]['version']
            version_msg += f" | Installed: {installed_version}"
        if settings.latest_version_available:
            version_msg += f" | Latest: {settings.latest_version_available}"
        
        self.report({'INFO'}, version_msg)
        self.report({'INFO'}, f"Check console for detailed information")
        
        return {'FINISHED'}


classes = [
    UVV_OT_ToggleUVSync,
    UVV_OT_IsolateIslands,
    UVV_OT_OpenDocumentation,
    UVV_OT_OpenChangelog,
    UVV_OT_ShowVersionInfo,
    UVV_OT_CheckForUpdates,
    UVV_OT_InstallUpdate,
    UVV_OT_DebugVersionCheck,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)