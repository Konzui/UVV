"""Pack operators for UVV addon - UNIV 1:1 Copy"""

import bpy
import bmesh
from bpy.props import BoolProperty
from ..properties import get_uvv_settings
from .. import utils
from ..types import UMeshes
from ..checker.td_utils import TdContext, TdUtils


class UVV_OT_Pack(bpy.types.Operator):
    """Pack selected islands - UNIV 1:1 Copy"""
    bl_idname = 'uv.uvv_pack'
    bl_label = 'Pack'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = f"Pack selected islands\n\n" \
        f"Has [P] keymap, but it conflicts with the 'Pin' operator"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and (obj := context.active_object) and obj.type == 'MESH'

    def execute(self, context):
        settings = get_uvv_settings()
        if settings.use_uvpm:
            if hasattr(context.scene, 'uvpm3_props'):
                return self.pack_uvpm()
            else:
                settings.use_uvpm = False
                self.report({'WARNING'}, 'UVPackmaster not found')
                return {'CANCELLED'}
        else:
            return self.pack_native()

    @staticmethod
    def pack_uvpm():
        # TODO: Add Info about unselected and hidden faces
        # TODO: Use UniV orient (instead Pre-Rotation) and remove AXIS_ALIGNED method
        # TODO: Use UniV normalize
        # TODO: Add for Exact Overlap Mode threshold
        # TODO: Add scale checker for packed meshes

        settings = get_uvv_settings()
        uvpm_scene_props = bpy.context.scene.uvpm3_props

        # Resolve main props container used by UVPM
        uvpm_main_props = uvpm_scene_props.default_main_props if hasattr(uvpm_scene_props, 'default_main_props') else uvpm_scene_props

        # Map Scale/Normalize
        # Normalize islands == normalize_scale in UVPM
        try:
            uvpm_main_props.normalize_scale = bool(settings.normalize_islands)
        except Exception:
            pass

        # Map rotation settings
        try:
            uvpm_main_props.rotation_enable = bool(settings.rotate)
            # Pre-rotation disable roughly corresponds to allowing free ANY rotation
            if settings.rotate and settings.rotate_method == 'ANY':
                uvpm_main_props.pre_rotation_disable = True
            else:
                uvpm_main_props.pre_rotation_disable = False

            # Rotation step: CARDINAL -> 90, AXIS_ALIGNED -> 0, ANY -> leave step as is
            if settings.rotate_method == 'CARDINAL':
                uvpm_main_props.rotation_step = 90
            elif settings.rotate_method == 'AXIS_ALIGNED':
                uvpm_main_props.rotation_step = 0
        except Exception:
            pass

        # Map padding as pixel margin
        try:
            uvpm_main_props.pixel_margin_enable = True
            uvpm_main_props.pixel_margin = int(settings.padding)
            # Use active image size if available, otherwise UI size
            img_size = utils.get_active_image_size()
            if img_size and len(img_size) >= 2:
                uvpm_main_props.pixel_margin_tex_size = int(max(img_size[0], img_size[1]))
                uvpm_main_props.tex_ratio = (img_size[0] != img_size[1])
            else:
                uvpm_main_props.pixel_margin_tex_size = int(max(int(settings.size_x), int(settings.size_y)))
                uvpm_main_props.tex_ratio = (int(settings.size_x) != int(settings.size_y))
        except Exception:
            pass

        # Optional: small precision bump as in prior logic
        try:
            if int(uvpm_main_props.precision) == 500:
                uvpm_main_props.precision = 800
        except Exception:
            pass

        # Handle stacking integration with UVPM (UVPackmaster-style implementation)
        # IMPORTANT: Always set enable state based on our settings
        stacking_enabled = getattr(settings, 'pack_enable_stacking', False)
        
        # CRITICAL: Store flipping state before stack group setup
        # uvpackmaster3 may disable flipping internally when stack groups are enabled
        # We need to preserve and restore it after stack group processing
        flip_was_enabled = getattr(uvpm_main_props, 'flipping_enable', False)
        
        uvpm_main_props.numbered_groups_descriptors.stack_group.enable = stacking_enabled

        if stacking_enabled and settings.pack_use_stack_groups:
            try:
                import bmesh
                context = bpy.context
                vcolor_layer_name = '__uvpm3_v3_stack_group'

                from ..utils.stack_utils import StackSystem
                stack_system = StackSystem(context)
                scene = context.scene

                # Process each mesh object
                for obj in context.objects_in_mode_unique_data:
                    if obj.type != 'MESH':
                        continue

                    # Get FRESH BMesh for this object
                    bm = bmesh.from_edit_mesh(obj.data)
                    bm.faces.ensure_lookup_table()

                    # Get or create the UVPM stack group attribute layer (DON'T remove existing)
                    if vcolor_layer_name not in bm.faces.layers.int:
                        vcolor_layer = bm.faces.layers.int.new(vcolor_layer_name)
                    else:
                        vcolor_layer = bm.faces.layers.int[vcolor_layer_name]

                    # CRITICAL: Initialize all faces to 0 (no stacking)
                    # This is the key - islands default to "don't stack" unless explicitly assigned
                    for face in bm.faces:
                        face[vcolor_layer] = 0

                    # Assign manual stack groups to UVPM attribute layer
                    # Only islands in stack groups will get non-zero values
                    # Only check stack groups for this specific object
                    for uvv_group in obj.uvv_stack_groups:
                        group_islands = stack_system.get_group_islands(uvv_group.group_id, obj=obj)

                        # Calculate UVPM group ID (must be >= 1, since 0 = no stack)
                        # Add 1 to our group_id to ensure we never use 0
                        uvpm_group_id = uvv_group.group_id + 1

                        for island in group_islands:
                            # IMPORTANT: Use face_indices instead of stale face references
                            # The island.faces contains BMesh faces from StackSystem's BMesh instance
                            # We need to use the current bm instance with face indices
                            for face_idx in island.face_indices:
                                bm.faces[face_idx][vcolor_layer] = uvpm_group_id

                    # Update the mesh
                    bmesh.update_edit_mesh(obj.data)

            except Exception as e:
                # Ignore mapping issues; proceed to pack
                import traceback
                traceback.print_exc()
                pass
        
        # CRITICAL: Restore flipping_enable after stack group setup
        # This workaround ensures flipping works even when stack groups are enabled
        # (uvpackmaster3 may internally disable flipping during similarity alignment)
        if stacking_enabled and settings.pack_use_stack_groups:
            try:
                # Explicitly restore flipping if it was enabled before
                # This forces uvpackmaster3 to respect the flipping setting
                uvpm_main_props.flipping_enable = flip_was_enabled
            except Exception:
                pass

        # Finally, invoke the UVPackmaster pack
        try:
            return bpy.ops.uvpackmaster3.pack('INVOKE_REGION_WIN', mode_id="pack.single_tile", pack_op_type='0')
        except Exception:
            return {'CANCELLED'}

    def pack_native(self):
        umeshes = UMeshes.calc(verify_uv=False)
        umeshes.fix_context()

        settings = get_uvv_settings()
        args = {
            'udim_source': settings.udim_source,
            'rotate': settings.rotate,
            'margin': settings.padding / 2 / min(int(settings.size_x), int(settings.size_y))}
        if bpy.app.version >= (3, 5, 0):
            args['margin_method'] = 'FRACTION'
        is_360v = bpy.app.version >= (3, 6, 0)
        if is_360v:
            args['scale'] = settings.scale
            args['rotate_method'] = settings.rotate_method
            args['pin'] = settings.pin
            args['merge_overlap'] = settings.merge_overlap
            args['pin_method'] = settings.pin_method
            args['shape_method'] = settings.shape_method

        import platform
        if is_360v and settings.shape_method != 'AABB' and platform.system() == 'Windows':
            import threading
            threading.Thread(target=self.press_enter_key).start()
            return bpy.ops.uv.pack_islands('INVOKE_DEFAULT', **args)  # noqa
        else:
            return bpy.ops.uv.pack_islands('EXEC_DEFAULT', **args)  # noqa

    @staticmethod
    def press_enter_key():
        import ctypes
        VK_RETURN = 0x0D  # Enter  # noqa
        KEYDOWN = 0x0000  # Press  # noqa
        KEYUP = 0x0002  # Release  # noqa
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYDOWN, 0)
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYUP, 0)


class UVV_OT_GetUVCoverage(bpy.types.Operator):
    """Calculate UV coverage percentage"""
    bl_idname = "uv.uvv_get_uv_coverage"
    bl_label = "Get UV Coverage"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object is not None and
                context.active_object.type == 'MESH')

    def execute(self, context):
        settings = get_uvv_settings()

        try:
            coverage = self.calculate_uv_coverage(context, settings.uv_coverage_mode)
            settings.uv_coverage = coverage

            # Calculate average texel density
            avg_td = self.calculate_average_texel_density(context)
            settings.average_texel_density = avg_td

            empty_space = max(0.0, 100.0 - coverage)
            self.report({'INFO'}, f"UV Coverage: {coverage:.2f}%, Empty Space: {empty_space:.2f}%")

        except Exception as e:
            self.report({'ERROR'}, f"Coverage calculation failed: {str(e)}")
            settings.uv_coverage = 0.0
            settings.average_texel_density = 0.0
            return {'CANCELLED'}

        return {'FINISHED'}

    def calculate_uv_coverage(self, context, mode):
        """Calculate UV coverage based on selected mode"""
        # Get all selected mesh objects
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not mesh_objects:
            mesh_objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' else []

        if not mesh_objects:
            return 0.0

        # Collect all faces from all objects
        all_faces_data = []
        
        for obj in mesh_objects:
            # Get bmesh
            if obj.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(obj.data)
            else:
                bm = bmesh.new()
                bm.from_mesh(obj.data)

            # Get UV layer
            if not bm.loops.layers.uv:
                if obj.mode != 'EDIT':
                    bm.free()
                continue

            uv_layer = bm.loops.layers.uv.active

            # Collect faces - prefer selected faces if any are selected, otherwise use all visible faces
            selected_faces = [f for f in bm.faces if f.select and not f.hide]
            if selected_faces:
                faces_to_process = selected_faces
            else:
                # No selection, use all visible faces
                faces_to_process = [f for f in bm.faces if not f.hide]

            # Store face UV data for later processing
            for face in faces_to_process:
                uv_coords = [loop[uv_layer].uv for loop in face.loops]
                if len(uv_coords) >= 3:
                    all_faces_data.append(uv_coords)

            # Clean up if we created a new bmesh
            if obj.mode != 'EDIT':
                bm.free()

        if not all_faces_data:
            return 0.0

        # Calculate actual coverage using grid-based sampling
        coverage = self.calculate_actual_coverage(all_faces_data)
        return min(coverage, 100.0)

    def calculate_actual_coverage(self, faces_uv_data):
        """Calculate the actual percentage of UV space covered using optimized grid sampling"""
        # Use adaptive grid resolution based on number of faces
        # Lower resolution = faster but less accurate
        num_faces = len(faces_uv_data)
        if num_faces < 10:
            grid_resolution = 200  # 200x200 = 40,000 points
        elif num_faces < 50:
            grid_resolution = 150  # 150x150 = 22,500 points
        else:
            grid_resolution = 100  # 100x100 = 10,000 points for complex meshes
        
        # Use a 2D boolean array for faster lookups (faster than set for dense coverage)
        # Initialize as False (not covered)
        grid = [[False] * grid_resolution for _ in range(grid_resolution)]
        
        # Pre-calculate bounding boxes for all faces to optimize
        face_bboxes = []
        for uv_coords in faces_uv_data:
            if len(uv_coords) < 3:
                continue
            
            min_u = max(0.0, min(coord.x for coord in uv_coords))
            max_u = min(1.0, max(coord.x for coord in uv_coords))
            min_v = max(0.0, min(coord.y for coord in uv_coords))
            max_v = min(1.0, max(coord.y for coord in uv_coords))
            
            # Skip faces completely outside UV space
            if min_u >= 1.0 or max_u <= 0.0 or min_v >= 1.0 or max_v <= 0.0:
                continue
            
            face_bboxes.append((uv_coords, min_u, max_u, min_v, max_v))
        
        # Process each face with optimized bounding box checks
        for uv_coords, min_u, max_u, min_v, max_v in face_bboxes:
            # Convert to grid coordinates
            min_u_grid = max(0, int(min_u * grid_resolution))
            max_u_grid = min(grid_resolution, int(max_u * grid_resolution) + 1)
            min_v_grid = max(0, int(min_v * grid_resolution))
            max_v_grid = min(grid_resolution, int(max_v * grid_resolution) + 1)
            
            # Only check cells in the bounding box
            for v_grid in range(min_v_grid, max_v_grid):
                # Pre-calculate v coordinate once per row
                v = (v_grid + 0.5) / grid_resolution
                
                for u_grid in range(min_u_grid, max_u_grid):
                    # Skip if already marked as covered (optimization)
                    if grid[v_grid][u_grid]:
                        continue
                    
                    # Convert grid cell center to UV coordinates
                    u = (u_grid + 0.5) / grid_resolution
                    
                    # Check if this point is inside the face
                    if self.point_in_polygon(u, v, uv_coords):
                        grid[v_grid][u_grid] = True
        
        # Count covered cells
        covered_count = sum(sum(row) for row in grid)
        total_cells = grid_resolution * grid_resolution
        coverage_percent = (covered_count / total_cells) * 100.0
        
        return coverage_percent

    def point_in_polygon(self, u, v, uv_coords):
        """Check if a point (u, v) is inside a polygon using optimized ray casting"""
        num_verts = len(uv_coords)
        if num_verts < 3:
            return False
        
        # Fast path for triangles (most common case)
        if num_verts == 3:
            v0 = uv_coords[0]
            v1 = uv_coords[1]
            v2 = uv_coords[2]
            
            # Barycentric coordinates check (faster for triangles)
            denom = (v1.y - v2.y) * (v0.x - v2.x) + (v2.x - v1.x) * (v0.y - v2.y)
            if abs(denom) < 1e-10:
                return False  # Degenerate triangle
            
            a = ((v1.y - v2.y) * (u - v2.x) + (v2.x - v1.x) * (v - v2.y)) / denom
            b = ((v2.y - v0.y) * (u - v2.x) + (v0.x - v2.x) * (v - v2.y)) / denom
            c = 1 - a - b
            
            return a >= 0 and b >= 0 and c >= 0
        
        # Ray casting for polygons with more than 3 vertices
        inside = False
        j = num_verts - 1
        
        for i in range(num_verts):
            ui, vi = uv_coords[i].x, uv_coords[i].y
            uj, vj = uv_coords[j].x, uv_coords[j].y
            
            # Check if ray crosses edge (skip horizontal edges)
            if (vi != vj) and ((vi > v) != (vj > v)):
                # Calculate intersection point
                t = (v - vi) / (vj - vi)
                intersection_u = ui + t * (uj - ui)
                if u < intersection_u:
                    inside = not inside
            
            j = i
        
        return inside

    def calculate_average_texel_density(self, context):
        """Calculate average texel density across all UV islands"""
        settings = get_uvv_settings()
        
        # Get all selected mesh objects
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not mesh_objects:
            mesh_objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' else []

        if not mesh_objects:
            return 0.0

        try:
            # Create TD context
            td_context = TdContext(context)
            td_context.td_calc_precision = settings.td_calc_precision
            td_context.selected_only = False  # Calculate for all visible faces
            
            # Get TD data for all objects
            td_storage = TdUtils.get_td_data_with_precision(
                context, 
                mesh_objects, 
                td_context, 
                td_influence='ISLAND'  # Calculate per island
            )

            if not td_storage or td_storage.is_empty():
                return 0.0

            # Calculate average TD (TD values are already in px/cm from the calculation)
            td_values = [island.td for island in td_storage.islands if island.td > 0.0]
            
            if not td_values:
                return 0.0

            avg_td_cm = sum(td_values) / len(td_values)

            # Convert to the selected unit
            # TD calculation returns px/cm, so we need to convert based on td_unit
            unit = settings.td_unit
            if unit == 'px/cm':
                # Already in px/cm, no conversion needed
                return avg_td_cm
            elif unit == 'px/m':
                # Convert from px/cm to px/m: multiply by 100
                return avg_td_cm * 100.0
            elif unit == 'px/in':
                # Convert from px/cm to px/in: multiply by 2.54
                return avg_td_cm * 2.54
            else:
                # Default to px/cm
                return avg_td_cm

        except Exception as e:
            self.report({'WARNING'}, f"Texel density calculation failed: {str(e)}")
            return 0.0


class UVV_OT_OpenPackSettings(bpy.types.Operator):
    """Open Pack Settings in a popout window"""
    bl_idname = 'uv.uvv_open_pack_settings'
    bl_label = 'Pack Settings'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        """Allow the operator to be called from anywhere"""
        return True

    def invoke(self, context, event):
        # Reset close flag in window manager
        wm = context.window_manager
        if not hasattr(wm, 'uvv_pack_settings_should_close'):
            bpy.types.WindowManager.uvv_pack_settings_should_close = bpy.props.BoolProperty(default=False)
        wm.uvv_pack_settings_should_close = False
        return wm.invoke_popup(self, width=450)

    def execute(self, context):
        """Execute method - not used for popup but required by Blender"""
        # Check if we should close
        wm = context.window_manager
        if hasattr(wm, 'uvv_pack_settings_should_close') and wm.uvv_pack_settings_should_close:
            wm.uvv_pack_settings_should_close = False
            return {'CANCELLED'}
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        # === TITLEBAR ===
        header = layout.row(align=True)
        header.scale_y = 1.3
        header.emboss = 'NONE'
        
        # Title
        header.label(text="Pack Settings", icon='PREFERENCES')
        
        layout.separator()

        col = layout.column(align=True)

        # === PRESETS SECTION ===
        box = col.box()

        presets_row = box.row(align=True)
        presets = context.scene.uvv_pack_presets
        index = context.scene.uvv_pack_presets_index

        # Add new preset button (left side)
        presets_row.operator("uv.uvv_add_pack_preset", text='', icon='ADD')

        # Preset name input showing current preset name
        if presets and 0 <= index < len(presets):
            current_preset = presets[index]
            # Show current preset name in the input field
            name_field = presets_row.row(align=True)
            name_field.prop(current_preset, 'name', text='')
        else:
            presets_row.label(text="No Preset")

        # Preset dropdown menu (icon only)
        presets_row.menu("UVV_MT_PackPresetMenu", text='', icon='DOWNARROW_HLT')

        # Save button
        presets_row.operator("uv.uvv_save_pack_preset", text='', icon='FILE_TICK')

        # Delete button
        presets_row.operator("uv.uvv_delete_pack_preset", text='', icon='TRASH')

        # Reset presets button (all the way to the right, icon only)
        presets_row.operator("uv.uvv_reset_pack_presets", text='', icon='FILE_REFRESH')

        col.separator()

        # UVPackmaster toggle
        uvpm_available = hasattr(context.scene, 'uvpm3_props')
        if uvpm_available:
            col.prop(settings, 'use_uvpm')
            col.separator()
        
        # Show pack options based on mode
        if settings.use_uvpm:
            if uvpm_available:
                # UVPM mode - show full UVPackmaster settings (UNIV 1:1 copy)
                self.draw_uvpm(col, settings)
            else:
                col.label(text='UVPackmaster not found')
        else:
            # Native Blender mode
            if bpy.app.version >= (3, 6, 0):
                # === Shape method (Exact/Fast) with border ===
                box = col.box()
                row = box.row(align=True)
                row.prop(settings, 'shape_method', expand=True)

                col.separator(factor=0.5)

                # === SCALE BOX ===
                box = col.box()
                box_col = box.column(align=True)
                box_col.prop(settings, 'scale', text='Scale', toggle=False)

                # Normalize (only visible when Scale is enabled)
                if settings.scale:
                    # Add indentation
                    split = box_col.split(factor=0.1, align=True)
                    split.label(text='')  # Empty space for indent
                    split.prop(settings, 'normalize_islands', text='Normalize', toggle=False)

                col.separator(factor=0.5)

                # === ROTATE BOX ===
                box = col.box()
                box_col = box.column(align=True)
                box_col.prop(settings, 'rotate', text='Rotate', toggle=False)

                # Rotation Method (only visible when Rotate is enabled)
                if settings.rotate:
                    # Add indentation using split with factor
                    split = box_col.split(factor=0.1, align=True)
                    split.label(text='')  # Empty space for indent
                    split.prop(settings, 'rotate_method', text='')

                col.separator(factor=0.5)

                # === LOCK GROUP ===
                box = col.box()
                box.label(text="Lock")
                box_col = box.column(align=True)

                # Lock checkboxes in same row
                row = box_col.row(align=True)
                row.prop(settings, 'pin', text='Pinned Islands', toggle=False)
                row.prop(settings, 'merge_overlap', text='Overlaps', toggle=False)

                col.separator(factor=0.5)

                # === MISC GROUP ===
                box = col.box()
                box.label(text="Misc")
                box_col = box.column(align=True)

                # Global Size row with lock
                row = box_col.row(align=True)
                row.label(text='Global Size')
                size_row = box_col.row(align=True)
                size_row.prop(settings, 'size_x', text='')
                size_row.prop(settings, 'lock_size', text='', icon='LOCKED' if settings.lock_size else 'UNLOCKED')
                size_row.prop(settings, 'size_y', text='')

                box_col.separator()

                # Padding
                box_col.prop(settings, 'padding', slider=True)

                box_col.separator()

                # Pack to - label and dropdown in separate rows
                box_col.label(text='Pack to')
                box_col.prop(settings, 'udim_source', text='')

            else:
                # Blender < 3.6
                col.prop(settings, 'rotate', toggle=True)

        col.separator()

    def draw_uvpm(self, layout, settings):
        """Draw UVPackmaster settings - matching native design"""
        uvpm_settings = bpy.context.scene.uvpm3_props

        if hasattr(uvpm_settings, 'default_main_props'):
            uvpm_main_props = uvpm_settings.default_main_props
        else:
            uvpm_main_props = uvpm_settings

        # === SCALE BOX ===
        box = layout.box()
        box_col = box.column(align=True)
        box_col.prop(settings, 'scale', text='Scale', toggle=False)

        # Child settings under Scale (only visible when Scale is enabled)
        if settings.scale:
            # Mixed Scale
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'heuristic_allow_mixed_scales', text='Mixed Scale', toggle=False)

            # Normalize
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'normalize_scale', text='Normalize', toggle=False)

        layout.separator(factor=0.5)

        # === ROTATION BOX ===
        box = layout.box()
        box_col = box.column(align=True)
        box_col.prop(uvpm_main_props, 'rotation_enable', text='Rotate', toggle=False)

        # Rotation settings (only visible when Rotation is enabled)
        if uvpm_main_props.rotation_enable:
            # Add indentation for child settings
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'pre_rotation_disable', text='Pre-Rotation Disable', toggle=False)

            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'rotation_step', text='Rotation Step')

        layout.separator(factor=0.5)

        # === FLIP BOX ===
        box = layout.box()
        box.prop(uvpm_main_props, 'flipping_enable', text='Flip', toggle=False)

        layout.separator(factor=0.5)

        # === STACK BOX ===
        box = layout.box()
        box_col = box.column(align=True)
        box_col.prop(settings, 'pack_enable_stacking', text='Stack', toggle=False)

        # Stack settings (only visible when enabled)
        if settings.pack_enable_stacking:
            # Use Stack Groups option (always enabled when stacking is on)
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(settings, 'pack_use_stack_groups', text='Use Stack Groups', toggle=False)

        layout.separator(factor=0.5)

        # === HEURISTIC SEARCH ===
        box = layout.box()
        box_col = box.column(align=True)
        box_col.prop(uvpm_main_props, 'heuristic_enable', text='Heuristic Search', toggle=False)

        # Heuristic settings (only visible when enabled)
        if uvpm_main_props.heuristic_enable:
            # Add indentation for child settings
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'heuristic_search_time', text='Search Time')

            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'heuristic_max_wait_time', text='Max Wait Time')

            # Advanced Heuristic (if available)
            if hasattr(uvpm_main_props, 'advanced_heuristic'):
                split = box_col.split(factor=0.1, align=True)
                split.label(text='')  # Empty space for indent
                split.prop(uvpm_main_props, 'advanced_heuristic', text='Advanced Heuristic', toggle=False)

        layout.separator(factor=0.5)

        # === LOCK GROUP ===
        box = layout.box()
        box.label(text="Lock")
        box_col = box.column(align=True)

        # Lock checkboxes in same row
        row = box_col.row(align=True)
        row.prop(uvpm_main_props, 'lock_overlapping_enable', text='Overlaps', toggle=False)
        row.prop(uvpm_main_props.numbered_groups_descriptors.lock_group, 'enable', text='Groups', toggle=False)

        # Lock Overlaps mode (shown below when enabled)
        if uvpm_main_props.lock_overlapping_enable:
            # Add indentation for lock mode
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'lock_overlapping_mode', text='')

        layout.separator(factor=0.5)

        # === MISC GROUP ===
        box = layout.box()
        box.label(text="Misc")
        box_col = box.column(align=True)

        # Global Size row with lock
        row = box_col.row(align=True)
        row.label(text='Global Size')
        size_row = box_col.row(align=True)
        size_row.prop(settings, 'size_x', text='')
        size_row.prop(settings, 'lock_size', text='', icon='LOCKED' if settings.lock_size else 'UNLOCKED')
        size_row.prop(settings, 'size_y', text='')

        box_col.separator()

        # Padding
        box_col.prop(settings, 'padding', slider=True)

        box_col.separator()

        # Pack to - label and dropdown in separate rows
        box_col.label(text='Pack to')
        box_col.prop(settings, 'udim_source', text='')


class UVV_OT_ClosePackSettings(bpy.types.Operator):
    """Close Pack Settings window"""
    bl_idname = 'uv.uvv_close_pack_settings'
    bl_label = 'Close Pack Settings'
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        # Simply return FINISHED - don't do anything that could close Blender
        # The popup can be closed with ESC or clicking outside
        # We avoid using bpy.ops.wm.window_close() as it closes the main window
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # For popups created with invoke_popup, the safest way to close is
        # to let the user press ESC or click outside
        # We can't safely close it programmatically without risking closing Blender
        return {'FINISHED'}


classes = [
    UVV_OT_Pack,
    UVV_OT_GetUVCoverage,
    UVV_OT_OpenPackSettings,
    UVV_OT_ClosePackSettings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)