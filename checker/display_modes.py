

""" UVV Display Mode Operators """

import bpy
import bmesh
from mathutils import Vector


class UVV_OT_ToggleTexelDensity(bpy.types.Operator):
    bl_idname = "uv.uvv_toggle_texel_density"
    bl_label = 'Texel Density'
    bl_description = 'Toggle texel density visualization with custom colors'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    @classmethod
    def is_active(cls, context: bpy.types.Context):
        """Check if texel density overlay is currently active"""
        if hasattr(context.scene, 'uvv_settings'):
            return context.scene.uvv_settings.uvv_texel_overlay_active
        return False

    def execute(self, context: bpy.types.Context):
        from .gizmo_draw import update_all_gizmos

        settings = context.scene.uvv_settings

        # Toggle state
        is_active = settings.uvv_texel_overlay_active
        settings.uvv_texel_overlay_active = not is_active

        if settings.uvv_texel_overlay_active:
            # Enable overlay - trigger gizmo rebuild
            update_all_gizmos(context)
            self.report({'INFO'}, "Texel density overlay enabled")
        else:
            # Disable overlay
            self.report({'INFO'}, "Texel density overlay disabled")

        # Force redraw of UV editor
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

        return {'FINISHED'}


class UVV_OT_SelectFlipped(bpy.types.Operator):
    bl_idname = "uv.uvv_select_flipped"
    bl_label = 'Select Flipped'
    bl_description = 'Select UV islands that are flipped (mirrored)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context: bpy.types.Context):
        # Get selected mesh objects
        objs = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No mesh objects selected")
            return {'CANCELLED'}

        # Switch to face selection mode
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
        bpy.ops.mesh.select_all(action='DESELECT')

        flipped_count = 0

        for obj in objs:
            # Get bmesh from object
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                continue

            # Check each face for flipped UVs
            for face in bm.faces:
                if len(face.loops) < 3:
                    continue

                # Get UV coordinates
                uv_coords = [loop[uv_layer].uv for loop in face.loops]

                # Calculate the signed area of the UV polygon
                # Positive area = normal orientation, negative = flipped
                area = 0.0
                for i in range(len(uv_coords)):
                    j = (i + 1) % len(uv_coords)
                    area += uv_coords[i].x * uv_coords[j].y
                    area -= uv_coords[j].x * uv_coords[i].y

                # If area is negative, the UV face is flipped
                if area < 0:
                    face.select = True
                    flipped_count += 1

            # Update mesh
            bmesh.update_edit_mesh(obj.data)

        if flipped_count == 0:
            self.report({'INFO'}, "No flipped UV faces found")
        else:
            self.report({'INFO'}, f"Selected {flipped_count} flipped UV faces")

        return {'FINISHED'}


classes = [
    UVV_OT_ToggleTexelDensity,
    UVV_OT_SelectFlipped,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
