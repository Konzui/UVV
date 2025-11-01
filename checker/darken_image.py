

""" UVV Darken Image Operator """

import bpy


class UVV_OT_DarkenImage(bpy.types.Operator):
    bl_idname = "uv.uvv_darken_image"
    bl_label = 'Darken Image'
    bl_description = 'Darken active image in UV Editor'
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('NONE', 'None', ''),
            ('ON', 'On', ''),
            ('OFF', 'Off', '')
        ],
        default='NONE'
    )

    darkness: bpy.props.IntProperty(
        name='Darkness',
        min=1,
        max=100,
        default=50
    )

    @classmethod
    def getActiveImage(cls, context):
        """Get active image from UV editor"""
        if hasattr(context, 'space_data'):
            if context.space_data is not None and hasattr(context.space_data, 'image'):
                return context.space_data.image
        return None

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return cls.getActiveImage(context) is not None

    @classmethod
    def is_mode_on(cls, context: bpy.types.Context):
        """Check if darken mode is currently active"""
        p_scene = context.scene
        # Check global scene settings instead of per-image
        if p_scene.view_settings.use_curve_mapping:
            return True
        return False

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.mode = 'NONE'
        p_image = self.getActiveImage(context)
        if p_image is not None:
            if self.is_mode_on(context):
                self.mode = 'OFF'
            else:
                self.mode = 'ON'
            return self.execute(context)

        return {'CANCELLED'}

    def execute(self, context: bpy.types.Context):
        p_scene = context.scene

        if self.mode == 'ON':
            # Enable darken mode globally for all images
            # Apply to all images in the blend file
            for img in bpy.data.images:
                img.use_view_as_render = True

            p_scene.view_settings.use_curve_mapping = True

            # Set darkness level (lower = darker)
            p_white = max(self.darkness * 1, 0)
            p_scene.view_settings.curve_mapping.white_level = (p_white, p_white, p_white)
            p_scene.view_settings.curve_mapping.update()

            # Save user preference
            from ..properties import get_uvv_settings
            settings = get_uvv_settings()
            settings.darken_user_preference = True

        elif self.mode == 'OFF':
            # Disable darken mode globally for all images
            p_scene.view_settings.curve_mapping.white_level = (1.0, 1.0, 1.0)
            p_scene.view_settings.curve_mapping.update()

            # Disable for all images
            for img in bpy.data.images:
                img.use_view_as_render = False

            p_scene.view_settings.use_curve_mapping = False

            # Save user preference
            from ..properties import get_uvv_settings
            settings = get_uvv_settings()
            settings.darken_user_preference = False

        return {'FINISHED'}


classes = [
    UVV_OT_DarkenImage,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
