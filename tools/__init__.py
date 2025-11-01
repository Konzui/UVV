from . import seam_brush
from . import trimsheet_tool
from ..utils import trimsheet_draw


def register():
    seam_brush.register()
    trimsheet_tool.register()
    # Register trimsheet draw handler
    trimsheet_draw.register_draw_handler()


def register_tools():
    """Register workspace tools separately"""
    seam_brush.register_tool()
    trimsheet_tool.register_tool()


def unregister_tools():
    """Unregister workspace tools separately"""
    trimsheet_tool.unregister_tool()
    seam_brush.unregister_tool()


def unregister():
    # Unregister trimsheet draw handler
    trimsheet_draw.unregister_draw_handler()
    trimsheet_tool.unregister()
    seam_brush.unregister()