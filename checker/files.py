

""" UVV Checker Files Processor """

from struct import unpack
import os
from shutil import copy
from json import dumps
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty

from .checker_labels import UVVCheckerLabels as label
from .get_prefs import get_prefs


_checker_previews = None


def get_checker_previews():
    global _checker_previews
    if _checker_previews is None:
        import bpy.utils.previews
        _checker_previews = bpy.utils.previews.new()
    return _checker_previews


def load_checker_image(context, _image):
    """Load checker image from the images folder"""
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()

    image_file = os.path.join(settings.checker_assets_path, _image)
    current_image = bpy.data.images.get(_image)
    if current_image and not current_image.has_data:
        bpy.data.images.remove(current_image, do_unlink=True)
    if os.path.exists(image_file):
        try:
            p_image = bpy.data.images.load(image_file, check_existing=True)
            return p_image
        except Exception as e:
            print(e)
            print(f'UVV Checker: image is {_image}. Error In "load_checker_image"')
            return None
    else:
        if _image != "None":
            print("UVV Checker: file not exist ", image_file)
        return None


def get_image_size(fname):
    '''Determine the image type from signature and return its size.'''
    with open(fname, 'rb') as fhandle:
        head = fhandle.read(24)
        if len(head) < 24:
            return None

        # Check PNG signature
        if head[:8] == b'\x89PNG\r\n\x1a\n':
            width, height = unpack('>II', head[16:24])
            return width, height

        # Check JPEG signature (starts with 0xFFD8)
        elif head[0:2] == b'\xff\xd8':
            try:
                fhandle.seek(2)
                while True:
                    marker_start = fhandle.read(1)
                    while marker_start != b'\xff':
                        marker_start = fhandle.read(1)

                    marker = fhandle.read(1)
                    while marker == b'\xff':
                        marker = fhandle.read(1)

                    if marker in [b'\xc0', b'\xc1', b'\xc2', b'\xc3', b'\xc5', b'\xc6', b'\xc7', b'\xc9', b'\xca', b'\xcb', b'\xcd', b'\xce', b'\xcf']:
                        fhandle.read(3)  # skip length and precision
                        height, width = unpack('>HH', fhandle.read(4))
                        return width, height
                    else:
                        size_bytes = fhandle.read(2)
                        size = unpack('>H', size_bytes)[0]
                        fhandle.seek(size - 2, 1)
            except Exception:
                return None

        return None


def collect_image_names(path):
    """Read PNG and JPG files from directory for UVV Checker."""
    checker_images = []
    if os.path.exists(path):
        for _file in os.listdir(path):
            full_path = os.path.join(path, _file)
            if os.path.isfile(full_path):
                ext = os.path.splitext(_file)[1].lower()
                if ext in {".png", ".jpg", ".jpeg"}:
                    checker_images.append(_file)
    else:
        print("UVV: Folder ../images does not exist")
    return checker_images


def update_files_info(path):
    """ Update info of files from UVV Checker .images directory """
    files_dict = dict()
    files = collect_image_names(path)
    if files:
        p_previews = get_checker_previews()
        p_previews.clear()

        for _file in files:
            files_dict[_file] = dict()
            p_path = os.path.join(path, _file)
            files_dict[_file]["res_x"], files_dict[_file]["res_y"] = get_image_size(p_path)

            try:
                p_previews.load(_file, p_path, 'IMAGE')
            except Exception as e:
                print(str(e))

    return files_dict


class UVVChecker_OT_CollectImages(Operator):
    """ UVV Checker Collect files data """
    bl_idname = "view3d.uvv_checker_collect_images"
    bl_label = label.OT_COLLECT_IMAGES_LABEL
    bl_description = label.OT_COLLECT_IMAGES_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()
        path = settings.checker_assets_path
        settings.files_dict = dumps(update_files_info(path))
        return {'FINISHED'}


class UVVChecker_OT_AppendFile(Operator, ImportHelper):
    bl_idname = "view3d.uvv_checker_append_checker_file"
    bl_label = label.OT_APPEND_CHECKER_LABEL
    bl_description = label.OT_APPEND_CHECKER_DESC

    filter_glob: StringProperty(
        default='*.jpg;*.png',
        options={'HIDDEN'}
    )

    def execute(self, context):
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()
        path = settings.checker_assets_path
        # Copy User Image to
        copy(self.filepath, path)
        print("UVV Checker: File ", self.filepath)
        print("          Copied to: ", path)
        settings.files_dict = dumps(update_files_info(path))
        return {'FINISHED'}


class UVVChecker_OT_GetCheckerOverrideImage(bpy.types.Operator):
    bl_idname = 'wm.uvv_get_checker_override_image'
    bl_label = 'Get Override Image'
    bl_description = 'Get texture checker override image'
    bl_options = {'REGISTER'}

    def get_items(self, context: bpy.types.Context):
        p_items = []
        for k, v in bpy.data.images.items():
            p_items.append((k, k, ""))

        s_id = "UVVChecker_OT_GetCheckerOverrideImage_ITEMS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])

        if p_was_items != p_items:
            bpy.app.driver_namespace[s_id] = p_items

        return bpy.app.driver_namespace.get(s_id, [])

    image_name: bpy.props.EnumProperty(
        name='Image Name',
        description='Source image name, which will be used for checker image',
        items=get_items
    )

    def get_image_size(self):
        p_image = bpy.data.images.get(self.image_name, None)
        if p_image:
            return p_image.size
        return (0, 0)

    @classmethod
    def getActiveImage(cls, context):
        if hasattr(context, 'area') and context.area is not None and context.area.type != 'IMAGE_EDITOR':
            if context.active_object is not None:
                p_act_mat = context.active_object.active_material
                if p_act_mat is not None:
                    if p_act_mat.use_nodes:
                        # Priority for Base Color Texture
                        try:
                            principled = next(n for n in p_act_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                            base_color = principled.inputs['Base Color']
                            link = base_color.links[0]
                            link_node = link.from_node
                            return link_node.image
                        except Exception:
                            pass

        return None

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_image = self.getActiveImage(context)
        if p_image:
            try:
                self.image_name = p_image.name
            except Exception as e:
                print('UVV DETECT IMAGE:', e)

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        from .checker import uvv_checker_image_update, get_uvv_checker_image
        from ..properties import get_uvv_settings

        settings = get_uvv_settings()
        settings.override_image_name = self.image_name
        image = get_uvv_checker_image(context)
        if image is not None:
            uvv_checker_image_update(context, image)
            return {'FINISHED'}
        return {'CANCELLED'}


classes = [
    UVVChecker_OT_CollectImages,
    UVVChecker_OT_AppendFile,
    UVVChecker_OT_GetCheckerOverrideImage
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    global _checker_previews

    # Clean up preview collection
    if _checker_previews is not None:
        bpy.utils.previews.remove(_checker_previews)
        _checker_previews = None

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
