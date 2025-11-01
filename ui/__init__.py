# UVV UI package

from . import menus
from . import trimsheet_panel
from . import viewport_3d_panel
from . import pie_menu


def register():
    import bpy
    menus.register()
    trimsheet_panel.register()
    viewport_3d_panel.register()
    pie_menu.register()


def unregister():
    import bpy
    pie_menu.unregister()
    viewport_3d_panel.unregister()
    trimsheet_panel.unregister()
    menus.unregister()