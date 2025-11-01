"""Pack operators for UVV addon - UNIV 1:1 Copy"""

import bpy
import bmesh
from bpy.props import BoolProperty
from ..properties import get_uvv_settings
from .. import utils
from ..types import UMeshes


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
                    for uvv_group in scene.uvv_stack_groups:
                        group_islands = stack_system.get_group_islands(uvv_group.group_id)

                        # Calculate UVPM group ID (must be >= 1, since 0 = no stack)
                        # Add 1 to our group_id to ensure we never use 0
                        uvpm_group_id = uvv_group.group_id + 1

                        for island in group_islands:
                            # Check if this island belongs to this object
                            if island.obj != obj:
                                continue

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

            empty_space = max(0.0, 100.0 - coverage)
            self.report({'INFO'}, f"UV Coverage: {coverage:.2f}%, Empty Space: {empty_space:.2f}%")

        except Exception as e:
            self.report({'ERROR'}, f"Coverage calculation failed: {str(e)}")
            settings.uv_coverage = 0.0
            return {'CANCELLED'}

        return {'FINISHED'}

    def calculate_uv_coverage(self, context, mode):
        """Calculate UV coverage based on selected mode"""
        total_coverage = 0.0

        # Get all selected mesh objects
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not mesh_objects:
            mesh_objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' else []

        if not mesh_objects:
            return 0.0

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

            if mode == 'GENERIC':
                # Calculate coverage for all faces
                coverage = self.calculate_face_coverage(bm.faces, uv_layer)
                total_coverage += coverage

            elif mode == 'SELECTED':
                # Calculate coverage for selected faces only
                selected_faces = [f for f in bm.faces if f.select]
                if selected_faces:
                    coverage = self.calculate_face_coverage(selected_faces, uv_layer)
                    total_coverage += coverage

            elif mode == 'EXCLUDE_STACKED':
                # Calculate coverage excluding stacked islands
                # For now, we'll use the same as GENERIC
                # A full implementation would detect and exclude stacked islands
                coverage = self.calculate_face_coverage(bm.faces, uv_layer)
                total_coverage += coverage

            # Clean up if we created a new bmesh
            if obj.mode != 'EDIT':
                bm.free()

        # Coverage is already a percentage from calculate_face_coverage
        return min(total_coverage, 100.0)

    def calculate_face_coverage(self, faces, uv_layer):
        """Calculate the UV area coverage for a set of faces"""
        total_uv_area = 0.0

        for face in faces:
            if face.hide:
                continue

            # Get UV coordinates for this face
            uv_coords = [loop[uv_layer].uv for loop in face.loops]

            if len(uv_coords) < 3:
                continue

            # Calculate area using triangulation
            # For each triangle in the face (using fan triangulation from first vertex)
            face_area = 0.0
            for i in range(1, len(uv_coords) - 1):
                v0 = uv_coords[0]
                v1 = uv_coords[i]
                v2 = uv_coords[i + 1]

                # Triangle area = 0.5 * |cross product|
                # For 2D: area = 0.5 * |x1(y2-y3) + x2(y3-y1) + x3(y1-y2)|
                area = abs(
                    v0.x * (v1.y - v2.y) +
                    v1.x * (v2.y - v0.y) +
                    v2.x * (v0.y - v1.y)
                ) * 0.5

                face_area += area

            total_uv_area += face_area

        # Convert to percentage (UV space is 0-1, so area of 1.0 = 100%)
        coverage_percent = total_uv_area * 100.0

        return coverage_percent


classes = [
    UVV_OT_Pack,
    UVV_OT_GetUVCoverage,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)