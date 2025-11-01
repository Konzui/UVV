
""" Init UVV Checker """

from bpy.utils import register_class, unregister_class
import bpy
import bpy.utils.previews

from .checker import register as register_checker
from .checker import unregister as unregister_checker

from .files import register as register_files
from .files import unregister as unregister_files

from .darken_image import register as register_darken_image
from .darken_image import unregister as unregister_darken_image

from .display_modes import register as register_display_modes
from .display_modes import unregister as unregister_display_modes

from .gizmo_draw import register as register_gizmo_draw
from .gizmo_draw import unregister as unregister_gizmo_draw

from .texel_calculator import register as register_texel_calculator
from .texel_calculator import unregister as unregister_texel_calculator

from .cleanup import register as register_cleanup
from .cleanup import unregister as unregister_cleanup


addon_keymaps = []


def register():
    """ Register classes """
    register_files()
    register_checker()
    register_darken_image()
    register_display_modes()
    register_texel_calculator()
    register_gizmo_draw()
    register_cleanup()


def unregister():
    """ Unregister classes """
    unregister_cleanup()
    unregister_gizmo_draw()
    unregister_texel_calculator()   
    unregister_display_modes()
    unregister_darken_image()
    unregister_checker()
    unregister_files()  # This now handles preview cleanup


if __name__ == "__main__":
    pass
