"""
UVV Preferences Operators
Handles opening addon preferences and hotkey settings
"""

import bpy
from bpy.types import Operator


class UVV_OT_OpenAddonHotkeys(Operator):
    """Open UVV addon preferences to configure hotkeys"""
    bl_idname = "uv.uvv_open_addon_hotkeys"
    bl_label = "Open UVV Hotkeys"
    bl_description = "Open UVV addon preferences to configure hotkeys"
    bl_options = {"REGISTER"}

    def execute(self, context):
        # Open preferences window
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        
        # Switch to Add-ons tab
        for area in context.screen.areas:
            if area.type == 'PREFERENCES':
                for space in area.spaces:
                    if space.type == 'PREFERENCES':
                        space.active_section = 'ADDONS'
                        break
                break
        
        # Try to find and focus on UVV addon
        try:
            # This will expand the UVV addon if it's found
            bpy.ops.preferences.addon_expand(module=__package__)
        except:
            # If the addon isn't found by package name, try alternative
            try:
                bpy.ops.preferences.addon_expand(module="UVV")
            except:
                pass
        
        self.report({'INFO'}, "Navigate to Add-ons > UVV to configure hotkeys")
        return {"FINISHED"}


classes = [
    UVV_OT_OpenAddonHotkeys,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
