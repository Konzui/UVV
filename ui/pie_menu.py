"""
UVV Pie Menu Implementation
Based on ZenUV's pie menu system
"""

import bpy
from bpy.types import Menu, Operator


class UVV_MT_PieMenu(Menu):
    """UVV Pie Menu with 8 UV tools"""
    bl_label = "UVV Tools"
    bl_idname = "UVV_MT_PieMenu"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # West (4) - Split
        if icons_coll and "split_uv" in icons_coll:
            pie.operator("uv.uvv_split", text="Split", icon_value=icons_coll["split_uv"].icon_id)
        else:
            pie.operator("uv.uvv_split", text="Split", icon='SCULPTMODE_HLT')

        # East (6) - Weld
        if icons_coll and "match_stitch" in icons_coll:
            pie.operator("mesh.uvv_weld", text="Weld", icon_value=icons_coll["match_stitch"].icon_id)
        else:
            pie.operator("mesh.uvv_weld", text="Weld", icon='AUTOMERGE_ON')

        # South (2) - Others (Secondary Menu)
        pie.operator("uv.uvv_open_secondary_pie", text="Others", icon='MENU_PANEL')

        # North (8) - Isolate Part
        if icons_coll and "isolate_islands" in icons_coll:
            pie.operator("uv.uvv_isolate_islands", text="Isolate Part", icon_value=icons_coll["isolate_islands"].icon_id)
        else:
            pie.operator("uv.uvv_isolate_islands", text="Isolate Part", icon='RESTRICT_VIEW_OFF')

        # NorthWest (7) - Unwrap
        if icons_coll and "unwrap" in icons_coll:
            pie.operator("mesh.uvv_unwrap_inplace", text="Unwrap", icon_value=icons_coll["unwrap"].icon_id)
        else:
            pie.operator("mesh.uvv_unwrap_inplace", text="Unwrap", icon='AUTOMERGE_ON')

        # NorthEast (9) - Project Map
        if icons_coll and "camera_unwrap" in icons_coll:
            pie.operator("uv.uvv_project_unwrap", text="Project Map", icon_value=icons_coll["camera_unwrap"].icon_id)
        else:
            pie.operator("uv.uvv_project_unwrap", text="Project Map", icon='UV_DATA')

        # SouthWest (1) - Relax
        if icons_coll and "relax" in icons_coll:
            pie.operator("uv.univ_relax", text="Relax", icon_value=icons_coll["relax"].icon_id)
        else:
            pie.operator("uv.univ_relax", text="Relax", icon='MESH_CIRCLE')

        # SouthEast (3) - Quadrify
        if icons_coll and "quadrify" in icons_coll:
            pie.operator("uv.uvv_quadrify", text="Quadrify", icon_value=icons_coll["quadrify"].icon_id)
        else:
            pie.operator("uv.uvv_quadrify", text="Quadrify", icon='IPO_LINEAR')


class UVV_MT_SecondaryPieMenu(Menu):
    """UVV Secondary Pie Menu with additional UV tools"""
    bl_label = "UVV Other Tools"
    bl_idname = "UVV_MT_SecondaryPieMenu"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # North (8) - Straighten
        if icons_coll and "straighten" in icons_coll:
            pie.operator("uv.uvv_straighten", text="Straighten", icon_value=icons_coll["straighten"].icon_id)
        else:
            pie.operator("uv.uvv_straighten", text="Straighten", icon='IPO_LINEAR')

        # South (2) - Pack Presets
        pie.operator("uv.uvv_open_pack_presets_pie", text="Pack Presets", icon='MENU_PANEL')

        # East (6) - Orient
        if icons_coll and "orient" in icons_coll:
            pie.operator("uv.uvv_orient", text="Orient", icon_value=icons_coll["orient"].icon_id)
        else:
            pie.operator("uv.uvv_orient", text="Orient", icon='ORIENTATION_GLOBAL')

        # West (4) - Parallel Constraint
        if icons_coll and "parallel_constraint" in icons_coll:
            pie.operator("uv.uvv_parallel_constraint", text="Parallel", icon_value=icons_coll["parallel_constraint"].icon_id)
        else:
            pie.operator("uv.uvv_parallel_constraint", text="Parallel", icon='DRIVER_DISTANCE')

        # Northeast (9) - Horizontal Constraint
        if icons_coll and "horizontal_constraint" in icons_coll:
            pie.operator("uv.uvv_add_horizontal_constraint", text="Horizontal", icon_value=icons_coll["horizontal_constraint"].icon_id)
        else:
            pie.operator("uv.uvv_add_horizontal_constraint", text="Horizontal", icon='TRIA_RIGHT')

        # Northwest (7) - Vertical Constraint
        if icons_coll and "vertical_constraint" in icons_coll:
            pie.operator("uv.uvv_add_vertical_constraint", text="Vertical", icon_value=icons_coll["vertical_constraint"].icon_id)
        else:
            pie.operator("uv.uvv_add_vertical_constraint", text="Vertical", icon='TRIA_UP')

        # Southwest (1) - Empty slot for better spacing
        pie.separator()

        # Southeast (3) - Empty slot for better spacing
        pie.separator()


class UVV_MT_PackPresetsPieMenu(Menu):
    """UVV Pack Presets Pie Menu with 4 packing presets"""
    bl_label = "UVV Pack Presets"
    bl_idname = "UVV_MT_PackPresetsPieMenu"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # North (8) - Fast Preset
        pie.operator("uv.uvv_apply_pack_preset_fast", text="Fast", icon='TIME')

        # South (2) - Accurate Preset
        pie.operator("uv.uvv_apply_pack_preset_accurate", text="Accurate", icon='PRECISION')

        # East (6) - UVMaster Fast Preset
        pie.operator("uv.uvv_apply_pack_preset_uvmaster_fast", text="UVMaster Fast", icon='UV_DATA')

        # West (4) - UVMaster Accurate Preset
        pie.operator("uv.uvv_apply_pack_preset_uvmaster_accurate", text="UVMaster Accurate", icon='UV_DATA')

        # Northeast (9) - Empty slot for better spacing
        pie.separator()

        # Northwest (7) - Empty slot for better spacing
        pie.separator()

        # Southwest (1) - Empty slot for better spacing
        pie.separator()

        # Southeast (3) - Empty slot for better spacing
        pie.separator()


class UVV_OT_PieMenu(Operator):
    """UVV Pie Menu Operator"""
    bl_idname = "uvv.pie_menu"
    bl_label = "UVV Pie Menu"
    bl_description = "Open UVV pie menu with UV tools"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        # Only active in Edit Mesh mode
        if context.mode != 'EDIT_MESH':
            return False
        
        # Check if we have an active object and it's a mesh
        if not context.active_object or context.active_object.type != 'MESH':
            return False
        
        # Check if we're in the right editor type
        if context.area:
            if context.area.type == 'VIEW_3D':
                return True
            elif context.area.type == 'IMAGE_EDITOR':
                # Only in UV mode for UV Editor
                if hasattr(context.space_data, 'ui_type'):
                    return context.space_data.ui_type == 'UV'
                return True
        
        return False

    def execute(self, context):
        # Debug: Print context information
        print(f"UVV Pie Menu: Called in {context.area.type if context.area else 'Unknown'} area")
        print(f"UVV Pie Menu: Mode: {context.mode}")
        print(f"UVV Pie Menu: Active object: {context.active_object.name if context.active_object else 'None'}")
        
        # Check if pie menu is enabled in preferences
        try:
            prefs = context.preferences.addons[__package__].preferences
            if not prefs.pie_menu_enabled:
                self.report({'INFO'}, "UVV Pie Menu is disabled in addon preferences")
                return {'CANCELLED'}
        except:
            # If preferences not found, continue anyway
            pass

        # Call the pie menu
        bpy.ops.wm.call_menu_pie(name="UVV_MT_PieMenu")
        return {"FINISHED"}


class UVV_OT_OpenSecondaryPie(Operator):
    """UVV Secondary Pie Menu Operator"""
    bl_idname = "uv.uvv_open_secondary_pie"
    bl_label = "UVV Other Tools"
    bl_description = "Open UVV secondary pie menu with additional UV tools"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        # Only active in Edit Mesh mode
        if context.mode != 'EDIT_MESH':
            return False
        
        # Check if we have an active object and it's a mesh
        if not context.active_object or context.active_object.type != 'MESH':
            return False
        
        # Check if we're in the right editor type
        if context.area:
            if context.area.type == 'VIEW_3D':
                return True
            elif context.area.type == 'IMAGE_EDITOR':
                # Only in UV mode for UV Editor
                if hasattr(context.space_data, 'ui_type'):
                    return context.space_data.ui_type == 'UV'
                return True
        
        return False

    def execute(self, context):
        # Debug: Print context information
        print(f"UVV Secondary Pie Menu: Called in {context.area.type if context.area else 'Unknown'} area")
        print(f"UVV Secondary Pie Menu: Mode: {context.mode}")
        print(f"UVV Secondary Pie Menu: Active object: {context.active_object.name if context.active_object else 'None'}")
        
        # Check if pie menu is enabled in preferences
        try:
            prefs = context.preferences.addons[__package__].preferences
            if not prefs.pie_menu_enabled:
                self.report({'INFO'}, "UVV Pie Menu is disabled in addon preferences")
                return {'CANCELLED'}
        except:
            # If preferences not found, continue anyway
            pass

        # Call the secondary pie menu
        bpy.ops.wm.call_menu_pie(name="UVV_MT_SecondaryPieMenu")
        return {"FINISHED"}


class UVV_OT_OpenPackPresetsPie(Operator):
    """UVV Pack Presets Pie Menu Operator"""
    bl_idname = "uv.uvv_open_pack_presets_pie"
    bl_label = "UVV Pack Presets"
    bl_description = "Open UVV pack presets pie menu with packing presets"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        # Only active in Edit Mesh mode
        if context.mode != 'EDIT_MESH':
            return False
        
        # Check if we have an active object and it's a mesh
        if not context.active_object or context.active_object.type != 'MESH':
            return False
        
        # Check if we're in the right editor type
        if context.area:
            if context.area.type == 'VIEW_3D':
                return True
            elif context.area.type == 'IMAGE_EDITOR':
                # Only in UV mode for UV Editor
                if hasattr(context.space_data, 'ui_type'):
                    return context.space_data.ui_type == 'UV'
                return True
        
        return False

    def execute(self, context):
        # Debug: Print context information
        print(f"UVV Pack Presets Pie Menu: Called in {context.area.type if context.area else 'Unknown'} area")
        print(f"UVV Pack Presets Pie Menu: Mode: {context.mode}")
        print(f"UVV Pack Presets Pie Menu: Active object: {context.active_object.name if context.active_object else 'None'}")
        
        # Check if pie menu is enabled in preferences
        try:
            prefs = context.preferences.addons[__package__].preferences
            if not prefs.pie_menu_enabled:
                self.report({'INFO'}, "UVV Pie Menu is disabled in addon preferences")
                return {'CANCELLED'}
        except:
            # If preferences not found, continue anyway
            pass

        # Call the pack presets pie menu
        bpy.ops.wm.call_menu_pie(name="UVV_MT_PackPresetsPieMenu")
        return {"FINISHED"}


classes = [
    UVV_MT_PieMenu,
    UVV_MT_SecondaryPieMenu,
    UVV_MT_PackPresetsPieMenu,
    UVV_OT_PieMenu,
    UVV_OT_OpenSecondaryPie,
    UVV_OT_OpenPackPresetsPie,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
