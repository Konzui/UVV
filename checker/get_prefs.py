
""" UVV Checker Constants """

import bpy
import os


DEF_OVERRIDE_IMAGE_NAME = 'No Image'


def get_prefs():
    """Get UVV addon preferences"""
    # UVV stores settings in scene properties, not addon preferences
    # This function returns the scene settings for compatibility
    return bpy.context.scene.uvv_settings if hasattr(bpy.context.scene, 'uvv_settings') else None


def get_path():
    """Get the path of Addon"""
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
