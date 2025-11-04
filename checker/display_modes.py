

""" UVV Display Mode Operators """

import bpy
import bmesh
from mathutils import Vector


class DisplayItem:
    """Display item for checker display modes"""
    def __init__(self, modes=None, spaces=None, select_op_id='', display_text=''):
        self.modes = modes if modes is not None else set()
        self.spaces = spaces if spaces is not None else set()
        self.select_op_id = select_op_id
        self.display_text = display_text


def is_draw_active_in_ui(context: bpy.types.Context):
    """Check if drawing is active in UI based on overlay settings"""
    if not hasattr(context.scene, 'uvv_settings'):
        return False
    
    p_scene = context.scene
    
    # Check overlay settings - simplified version for UVV
    b_active = True
    if hasattr(context.space_data, 'overlay') and hasattr(context.space_data.overlay, 'show_overlays'):
        # Check if overlay sync is enabled and overlays are off
        if hasattr(p_scene.uvv_settings, 'use_draw_overlay_sync') and p_scene.uvv_settings.use_draw_overlay_sync:
            b_active = context.space_data.overlay.show_overlays
    
    if bpy.app.version >= (3, 3, 0):
        if hasattr(context.space_data, 'show_gizmo'):
            b_active = b_active and context.space_data.show_gizmo
    
    return b_active


def get_draw_mode_pair_by_context(context: bpy.types.Context):
    """Get the draw mode property name and value for current context"""
    if not hasattr(context.scene, 'uvv_settings'):
        return ('draw_mode_UV', 'NONE')
    
    b_is_UV = context.space_data.type == 'IMAGE_EDITOR'
    s_space = 'UV' if b_is_UV else '3D'
    attr_name = 'draw_mode_' + s_space
    
    settings = context.scene.uvv_settings
    if hasattr(settings, attr_name):
        p_mode = getattr(settings, attr_name)
    else:
        p_mode = 'NONE'
    
    return (attr_name, p_mode)


def draw_checker_display_items(layout: bpy.types.UILayout, context: bpy.types.Context, t_modes: dict):
    """Draw checker system display items - Zen UV pattern"""
    if not hasattr(context.scene, 'uvv_settings'):
        return
    
    p_scene = context.scene
    settings = p_scene.uvv_settings
    
    b_active = is_draw_active_in_ui(context)
    
    attr_name, p_mode = get_draw_mode_pair_by_context(context)
    s_space = attr_name.replace('draw_mode_', '')
    
    s_context_mode = context.mode
    
    col = layout.column(align=True)
    col.active = b_active
    
    b_is_uv = s_space == 'UV'
    
    for k, v in t_modes.items():
        if s_context_mode in v.modes and s_space in v.spaces:
            row = col.row(align=True)
            
            if b_is_uv:
                # NOTE: Special case for stretched
                if k == 'STRETCHED':
                    op = row.operator(
                        "wm.context_set_boolean",
                        text="Stretched",
                        icon='HIDE_OFF',
                        depress=context.space_data.uv_editor.show_stretch if hasattr(context.space_data, 'uv_editor') else False)
                    op.data_path = "space_data.uv_editor.show_stretch"
                    op.value = not (context.space_data.uv_editor.show_stretch if hasattr(context.space_data, 'uv_editor') else False)
                    
                    if v.select_op_id:
                        row.operator(v.select_op_id, text='', icon="RESTRICT_SELECT_OFF")
                    continue
            
            b_is_enabled = p_mode == k
            
            if v.display_text is None or v.display_text == '':
                # Try to get display text from enum property
                if hasattr(settings, attr_name):
                    try:
                        s_display_text = layout.enum_item_name(settings, attr_name, k)
                    except:
                        s_display_text = k.replace('_', ' ').title()
                else:
                    s_display_text = k.replace('_', ' ').title()
            else:
                s_display_text = v.display_text
            
            op = row.operator('wm.context_set_enum', text=s_display_text, depress=b_is_enabled, icon='HIDE_OFF')
            op.data_path = 'scene.uvv_settings.' + attr_name
            op.value = 'NONE' if b_is_enabled else k
            if v.select_op_id:
                row.operator(v.select_op_id, text='', icon="RESTRICT_SELECT_OFF")


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
