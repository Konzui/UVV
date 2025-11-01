"""Auto UV Unwrap using Ministry of Flat external unwrapper"""

import bpy
import bmesh
import os
import subprocess
import urllib.error
import urllib.request
import ssl
import uuid
from zipfile import ZipFile
from io import BytesIO
from collections import defaultdict
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty


class MinistryOfFlatData:
    """Constants for Ministry of Flat unwrapper"""
    URL_MINISTRY_OF_FLAT = 'https://www.quelsolaar.com/ministry_of_flat/'
    MINISTRY_OF_FLAT_TEXT = "www.ministryofflat.com"
    MINISTRY_OF_FLAT_AUTHOR = "Eskil Steenberg"
    DOWNLOAD_URL = "https://www.quelsolaar.com/MinistryOfFlat_Release.zip"


def get_unwrapper_directory():
    """Get directory where unwrapper executable is stored"""
    import bpy
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    unwrapper_dir = os.path.join(addon_dir, "external_tools", "auto_unwrap")
    return unwrapper_dir


def get_unwrapper_path():
    """Get full path to unwrapper executable"""
    unwrapper_dir = get_unwrapper_directory()
    return os.path.join(unwrapper_dir, "MinistryOfFlat_Release", "UnWrapConsole3.exe")


def internet_enabled():
    """Check if Blender has internet access enabled"""
    try:
        prefs = bpy.context.preferences
        return prefs.system.use_online_access
    except:
        return True  # Assume enabled if can't check


class UVV_OT_AutoUnwrapInstall(Operator):
    """Download and install Ministry of Flat Auto UV Unwrapper"""
    bl_idname = "uv.uvv_auto_unwrap_install"
    bl_label = "Download Auto UV Unwrapper"
    bl_description = f"Download and install auto UV unwrapper from {MinistryOfFlatData.URL_MINISTRY_OF_FLAT}"

    @classmethod
    def poll(cls, context):
        return internet_enabled()

    @classmethod
    def description(cls, context, properties):
        s_desc = cls.bl_description
        if not internet_enabled():
            s_desc += "\n* Offline - Allow Online Access in System->Network Preferences"
        return s_desc

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column(align=True)

        lines = [
            'You are about to download "UV Automated Unwrapper" from the Ministry of Flat.',
            'Please note that by pressing the "OK" button, you acknowledge that you have read and agree',
            'to the terms and conditions of the free license associated with this tool.',
            'We recommend reviewing these terms carefully to understand your rights and responsibilities.'
        ]

        for line in lines:
            row = col.row(align=True)
            row.separator(factor=2)
            row.label(text=line)

        col.separator()

        row = col.row(align=True)
        r_split = row.split(factor=0.5)
        r_split.separator()
        r_1 = r_split.row(align=True)
        r_1.alignment = 'CENTER'
        r_1.label(text=f"Author: {MinistryOfFlatData.MINISTRY_OF_FLAT_AUTHOR}")

        row = layout.row(align=True)
        row.label(text="To access the terms and conditions, please visit:")
        op = row.operator("wm.url_open", text=MinistryOfFlatData.MINISTRY_OF_FLAT_TEXT)
        op.url = MinistryOfFlatData.URL_MINISTRY_OF_FLAT

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=540)

    def execute(self, context):
        target_dir = get_unwrapper_directory()

        # Create directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)

        try:
            self.report({'INFO'}, "Downloading unwrapper...")
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(MinistryOfFlatData.DOWNLOAD_URL, context=ssl_context) as zipresp:
                with ZipFile(BytesIO(zipresp.read())) as zfile:
                    zfile.extractall(target_dir)

            self.report({'INFO'}, "Auto UV Unwrapper installed successfully")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to download unwrapper: {str(e)}")
            return {'CANCELLED'}


class UVV_OT_AutoUnwrap(Operator):
    """Automated UV unwrapper using Ministry of Flat algorithm"""
    bl_idname = "uv.uvv_auto_unwrap"
    bl_label = "Auto Unwrap"
    bl_description = f"Automated UV unwrapper based on utility written by {MinistryOfFlatData.MINISTRY_OF_FLAT_AUTHOR} ({MinistryOfFlatData.MINISTRY_OF_FLAT_TEXT})"
    bl_options = {'REGISTER', 'UNDO'}

    # Unwrap settings
    auto_detect_hard_edges: BoolProperty(
        name="Auto Detect Hard Edges",
        description="Try to separate all hard edges (useful for lightmapping and normal mapping)",
        default=False
    )

    use_normal: BoolProperty(
        name="Use Normal",
        description="Use the model's normals to help classify polygons",
        default=False
    )

    overlap_identical_parts: BoolProperty(
        name="Overlap Identical Parts",
        description="Overlap identical parts to share texture space",
        default=False
    )

    overlap_mirrored_parts: BoolProperty(
        name="Overlap Mirrored Parts",
        description="Overlap mirrored parts to share texture space",
        default=False
    )

    world_scale: BoolProperty(
        name="Scale UV to Worldspace",
        description="Scale UVs to match real world scale (may go beyond 0-1 range)",
        default=True
    )

    # Texel density
    use_texel_density: BoolProperty(
        name="Use Texel Density",
        description="Scale UVs to match texel density value",
        default=False
    )

    texel_density: FloatProperty(
        name="Texel Density",
        description="Target texel density",
        min=0.001,
        default=1024.0,
        precision=2
    )

    texture_size: EnumProperty(
        name="Texture Size",
        items=[
            ('512', "512", ""),
            ('1024', "1024", ""),
            ('2048', "2048", ""),
            ('4096', "4096", ""),
            ('8192', "8192", ""),
        ],
        default='2048'
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH' and
            context.active_object and
            context.active_object.type == 'MESH'
        )

    def invoke(self, context, event):
        # Check if unwrapper is installed
        unwrapper_path = get_unwrapper_path()
        if not os.path.exists(unwrapper_path):
            if not internet_enabled():
                self.report({'WARNING'}, 'OFFLINE - Allow Online Access in Blender Preferences to continue!')
                return {'CANCELLED'}
            return bpy.ops.uv.uvv_auto_unwrap_install('INVOKE_DEFAULT')

        return self.execute(context)

    @classmethod
    def do_draw(cls, op, layout, context):
        """Shared draw method for operator panel and popover"""
        layout.use_property_split = True
        layout.use_property_decorate = False

        # Texel density
        box = layout.box()
        box.label(text="Texel Density", icon='TEXTURE')
        col = box.column(align=True)
        col.prop(op, "use_texel_density")
        if op.use_texel_density:
            col.prop(op, "texel_density")
            col.prop(op, "texture_size")

        # Unwrap settings
        box = layout.box()
        box.label(text="Unwrap Settings", icon='UV')
        col = box.column(align=True)
        col.prop(op, "auto_detect_hard_edges")
        col.prop(op, "use_normal")
        col.prop(op, "overlap_identical_parts")
        col.prop(op, "overlap_mirrored_parts")
        col.prop(op, "world_scale")

    def draw(self, context):
        UVV_OT_AutoUnwrap.do_draw(self, self.layout, context)

    def build_command_args(self, input_file, output_file):
        """Build command line arguments for unwrapper"""
        args = [get_unwrapper_path(), input_file, output_file]

        if self.auto_detect_hard_edges:
            args.extend(["-SEPARATE", "TRUE"])

        if self.use_normal:
            args.extend(["-NORMALS", "TRUE"])

        if self.overlap_identical_parts:
            args.extend(["-OVERLAP", "TRUE"])

        if self.overlap_mirrored_parts:
            args.extend(["-MIRROR", "TRUE"])

        if self.world_scale:
            args.extend(["-WORLDSCALE", "TRUE"])

        if self.use_texel_density:
            args.extend(["-DENSITY", str(round(self.texel_density))])
            args.extend(["-RESOLUTION", self.texture_size])

        # Default settings for removed advanced options
        args.extend(["-STRETCH", "FALSE"])
        args.extend(["-PACKING", "TRUE"])
        args.extend(["-CUTDEBUG", "FALSE"])
        args.extend(["-SQUARE", "FALSE"])
        args.extend(["-WELD", "FALSE"])
        args.extend(["-QUAD", "TRUE"])
        args.extend(["-SILENT", "TRUE"])

        return args

    def execute(self, context):
        try:
            # Ensure we're in face select mode and UV sync
            if not context.scene.tool_settings.use_uv_select_sync:
                context.scene.tool_settings.use_uv_select_sync = True
            bpy.ops.mesh.select_mode(type="FACE", action="ENABLE")

            # Store selection and original objects
            selected_objects = [obj for obj in context.objects_in_mode_unique_data]
            if not selected_objects:
                self.report({'WARNING'}, "No objects selected")
                return {'CANCELLED'}

            active_obj_name = context.active_object.name if context.active_object else None

            # Get working directory
            work_dir = get_unwrapper_directory()
            os.makedirs(work_dir, exist_ok=True)

            # Store face data while in edit mode
            objects_data = []

            for obj in selected_objects:
                bm = bmesh.from_edit_mesh(obj.data)
                selected_faces = [f for f in bm.faces if f.select]

                if not selected_faces:
                    continue

                # Store face indices
                face_indices = [f.index for f in selected_faces]
                objects_data.append((obj, face_indices))

                # Create temporary object with selected faces
                temp_name = str(uuid.uuid4())
                temp_mesh = bpy.data.meshes.new(temp_name)
                temp_obj = bpy.data.objects.new(temp_name, temp_mesh)
                context.collection.objects.link(temp_obj)

                temp_bm = bmesh.new()
                vert_map = {}

                # Copy selected faces
                for face in selected_faces:
                    new_verts = []
                    for vert in face.verts:
                        if vert not in vert_map:
                            new_vert = temp_bm.verts.new(vert.co)
                            vert_map[vert] = new_vert
                            new_vert.normal = vert.normal[:]
                        new_verts.append(vert_map[vert])

                    new_face = temp_bm.faces.new(new_verts)
                    new_face.normal = face.normal[:]
                    new_face.smooth = face.smooth

                # Handle seams
                temp_bm.edges.ensure_lookup_table()
                edges = [e for e in temp_bm.edges if e.seam]

                if edges:
                    bmesh.ops.split_edges(temp_bm, edges=edges)

                temp_bm.to_mesh(temp_mesh)
                temp_mesh.update()
                temp_bm.free()

            if not objects_data:
                self.report({'WARNING'}, "No faces selected")
                return {'CANCELLED'}

            # Switch to object mode for export
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')

            # Select only temp objects for export
            temp_objs_to_export = [obj for obj in context.collection.objects if obj.name.count('-') == 4 and len(obj.name) == 36]
            for temp_obj in temp_objs_to_export:
                temp_obj.select_set(True)

            input_file = os.path.join(work_dir, "_TEMP.obj")
            output_file = os.path.join(work_dir, "_TEMP_UNWRAPPED.obj")

            result = bpy.ops.wm.obj_export(
                filepath=input_file,
                export_selected_objects=True,
                export_materials=False,
                export_uv=False,
                export_normals=True,
                export_smooth_groups=True
            )

            if 'FINISHED' not in result:
                self.report({'ERROR'}, "Export failed")
                return {'CANCELLED'}

            # Run unwrapper
            args = self.build_command_args(input_file, output_file)
            subprocess.call(args, cwd=work_dir)

            # Import result
            if not os.path.exists(output_file):
                self.report({'ERROR'}, "Unwrap failed - no output file")
                return {'CANCELLED'}

            all_objs_before = set(bpy.data.objects)
            result = bpy.ops.wm.obj_import(filepath=output_file)

            if 'FINISHED' not in result:
                self.report({'ERROR'}, "Import failed")
                return {'CANCELLED'}

            imported_objs = list(set(bpy.data.objects) - all_objs_before)

            # Calculate normalization factor if needed (when not using texel density)
            uv_scale_factor = 1.0
            if not self.use_texel_density and self.world_scale:
                # Find max UV coordinate to normalize to 0-1 range
                max_uv = 0.0
                for imported_obj in imported_objs:
                    uv_layer = imported_obj.data.uv_layers.active
                    if uv_layer:
                        for uv_data in uv_layer.data:
                            max_uv = max(max_uv, abs(uv_data.uv.x), abs(uv_data.uv.y))

                if max_uv > 0:
                    uv_scale_factor = 1.0 / max_uv

            # Transfer UVs back to original objects (still in object mode)
            for (orig_obj, face_indices), imported_obj in zip(objects_data, imported_objs):
                # Read UV data from imported object
                uv_layer_import = imported_obj.data.uv_layers.active
                if not uv_layer_import:
                    continue

                # Get UV data
                import_uvs = {}
                for poly_idx, poly in enumerate(imported_obj.data.polygons):
                    loop_uvs = []
                    for loop_idx in poly.loop_indices:
                        uv = uv_layer_import.data[loop_idx].uv.copy()
                        # Apply normalization if needed
                        uv.x *= uv_scale_factor
                        uv.y *= uv_scale_factor
                        loop_uvs.append(uv)
                    import_uvs[poly_idx] = loop_uvs

                # Create or get UV layer on original object
                if not orig_obj.data.uv_layers.active:
                    orig_obj.data.uv_layers.new()
                uv_layer_orig = orig_obj.data.uv_layers.active

                # Transfer UVs to original object
                for poly_idx, face_idx in enumerate(face_indices):
                    if poly_idx in import_uvs and face_idx < len(orig_obj.data.polygons):
                        orig_poly = orig_obj.data.polygons[face_idx]
                        import_loop_uvs = import_uvs[poly_idx]

                        for i, loop_idx in enumerate(orig_poly.loop_indices):
                            if i < len(import_loop_uvs):
                                uv_layer_orig.data[loop_idx].uv = import_uvs[poly_idx][i]

            # Cleanup temp and imported objects
            for temp_obj in temp_objs_to_export:
                if temp_obj.name in bpy.data.objects:
                    mesh = temp_obj.data
                    bpy.data.objects.remove(temp_obj)
                    if mesh and mesh.users == 0:
                        bpy.data.meshes.remove(mesh)

            for obj in imported_objs:
                if obj.name in bpy.data.objects:
                    mesh = obj.data
                    bpy.data.objects.remove(obj)
                    if mesh and mesh.users == 0:
                        bpy.data.meshes.remove(mesh)

            # Return to edit mode
            for obj in selected_objects:
                obj.select_set(True)

            if active_obj_name and active_obj_name in bpy.data.objects:
                context.view_layer.objects.active = bpy.data.objects[active_obj_name]

            bpy.ops.object.mode_set(mode='EDIT')

            # Remove temp files
            try:
                if os.path.exists(input_file):
                    os.remove(input_file)
                if os.path.exists(output_file):
                    os.remove(output_file)
            except:
                pass

            self.report({'INFO'}, "Auto unwrap completed successfully")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Auto unwrap failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class UVV_PT_AutoUnwrapSettings(bpy.types.Panel):
    """Popover panel for Auto Unwrap settings"""
    bl_label = "Auto Unwrap Settings"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "__POPUP__"
    bl_ui_units_x = 16

    def draw(self, context):
        layout = self.layout

        wm = context.window_manager
        op_last = wm.operator_properties_last("uv.uvv_auto_unwrap")
        if op_last:
            UVV_OT_AutoUnwrap.do_draw(op_last, layout, context)
        else:
            layout.label(text="Run Auto Unwrap first to see settings", icon='INFO')


classes = [
    UVV_OT_AutoUnwrapInstall,
    UVV_OT_AutoUnwrap,
    UVV_PT_AutoUnwrapSettings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
