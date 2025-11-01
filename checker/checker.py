

""" UVV Checker Texture System """

import bpy
from json import dumps

from .get_prefs import get_prefs, DEF_OVERRIDE_IMAGE_NAME
from .checker_labels import UVVCheckerLabels as label
from .files import load_checker_image, update_files_info


UVV_IMAGE_NODE_NAME = "UVV_Texture_node"
UVV_IMAGE_NAME = "uvv-checker@4x.png"
UVV_GENERATED_IMAGE_NAME = "BlenderChecker"
UVV_GLOBAL_OVERRIDER_NAME = "UVV Checker"
UVV_GLOBAL_OVERRIDER_NAME_OLD = "UVV_Checker"
UVV_OVERRIDER_NAME = "UVV_Override"
UVV_GENERIC_MAT_NAME = "UVV_Generic_Material"
UVV_NODE_COLOR = (0.701, 0.017, 0.009)
UVV_TILER_NODE_NAME = "UVV_Tiler_node"
UVV_OFFSETTER_NODE_NAME = "UVV_Offsetter_node"


MES_NO_INP_CHANNELS = 'UVV Checker node group has no input channels. Need to reset the Checker'
MES_NO_OUT_CHANNELS = 'UVV Checker node group has no output channels. Need to reset the Checker'


class InpSocket:
    name: str = 'MainShader'
    in_out: str = 'INPUT'
    socket_type: str = 'NodeSocketShader'


class OutSocket:
    name: str = 'MixedShader'
    in_out: str = 'OUTPUT'
    socket_type: str = 'NodeSocketColor'


class VecAdd:
    inp_vec1 = None
    inp_vec2 = None
    out = None

    def create(self, node_group):
        add_node = node_group.nodes.new(type="ShaderNodeVectorMath")
        self.inp_vec1 = add_node.inputs[0]
        self.inp_vec2 = add_node.inputs[1]
        self.out = add_node.outputs[0]
        add_node.location = (-191.2, -2.82)


class VecCombine:
    inp = None
    out = None

    def create(self, node_group):
        comb_node = node_group.nodes.new(type="ShaderNodeCombineXYZ")
        self.inp = comb_node.inputs[1]
        self.out = comb_node.outputs[0]
        comb_node.location = (-419.8, -216.74)


class InpValue:
    value = None
    out = None

    def create(self, node_group):
        val_node = node_group.nodes.new(type="ShaderNodeValue")
        val_node.name = UVV_OFFSETTER_NODE_NAME
        self.out = val_node.outputs[0]
        val_node.location = (-646.6902, -304.1786)


class CheckerOffsetter:
    add_node = None
    combine_node = None
    offset_value_node = None
    offset_value = 0.0
    inp = None
    out = None

    def init(self, node_group):
        self.add_node = VecAdd()
        self.add_node.create(node_group)
        self.combine_node = VecCombine()
        self.combine_node.create(node_group)
        self.offset_value_node = InpValue()
        self.offset_value_node.create(node_group)
        self.inp = self.add_node.inp_vec1
        self.out = self.add_node.out

        # Create Links
        node_group.links.new(self.offset_value_node.out, self.combine_node.inp)
        node_group.links.new(self.combine_node.out, self.add_node.inp_vec2)


def remove_uvv_generic_mats():
    """Remove all UVV Generic Materials from bpy.data"""
    gen_mats = [m for m in bpy.data.materials if UVV_GENERIC_MAT_NAME in m.name]
    for mat in gen_mats:
        bpy.data.materials.remove(mat)


def uvv_generic_mat():
    """ Return a UVV Generic material or create one and return """
    generic_material = bpy.data.materials.get(UVV_GENERIC_MAT_NAME, None)
    if not generic_material:
        generic_material = bpy.data.materials.new(name=UVV_GENERIC_MAT_NAME)
        generic_material.use_nodes = True
        generic_material.use_fake_user = True
    return generic_material


def generate_procedural_texture(pattern_type, resolution, image_name):
    """Generate procedural UV grid texture using Blender's built-in generators"""
    # Check if image already exists
    existing_image = bpy.data.images.get(image_name)
    
    if existing_image:
        # If it's a generated image with matching settings, reuse it
        if hasattr(existing_image, 'generated_type'):
            if (existing_image.generated_type == pattern_type and 
                existing_image.generated_width == resolution[0] and 
                existing_image.generated_height == resolution[1]):
                return existing_image
        
        # Otherwise, remove the existing image to create a fresh one
        # Use try-except to handle cases where removal is not allowed
        try:
            bpy.data.images.remove(existing_image)
        except Exception as e:
            print(f"UVV: Could not remove existing image {image_name}: {e}")
            # If we can't remove it, try to modify it instead
            try:
                existing_image.generated_type = pattern_type
                existing_image.generated_width = resolution[0]
                existing_image.generated_height = resolution[1]
                return existing_image
            except Exception as e2:
                print(f"UVV: Could not modify existing image {image_name}: {e2}")
                # If all else fails, return the existing image as-is
                return existing_image
    
    # Create new procedural texture
    try:
        tex = bpy.data.images.new(image_name, resolution[0], resolution[1])
        tex.generated_type = pattern_type
        return tex
    except Exception as e:
        print(f"UVV: Could not create new procedural texture {image_name}: {e}")
        # Fallback: try to get any existing image with similar name
        fallback_image = bpy.data.images.get("UVV UV_GRID 1024x1024")
        if fallback_image:
            return fallback_image
        # Last resort: return None
        return None


def load_arrow_grid_texture():
    """Load arrow grid texture from addon's images folder"""
    import os
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()
    
    # Construct path to arrow_checker.webp in images folder
    addon_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    arrow_path = os.path.join(addon_path, "images", "arrow_checker.webp")
    
    if os.path.exists(arrow_path):
        try:
            image = bpy.data.images.load(arrow_path, check_existing=True)
            return image
        except Exception as e:
            print(f"UVV: Failed to load arrow grid texture: {e}")
            return None
    else:
        print(f"UVV: Arrow grid texture not found at {arrow_path}")
        return None


def validate_checker_state(context):
    """
    Comprehensive state validation for the UV checker system.
    Returns a dictionary with the actual state of all checker components.
    """
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()
    
    state = {
        'has_materials_with_checker': False,
        'has_objects_in_edit_mode': False,
        'has_uv_editor_image': False,
        'has_3d_view_checker': False,
        'is_consistently_enabled': False,
        'needs_restoration': False,
        'mismatched_components': []
    }
    
    # Check for materials with checker nodes
    materials_with_checker = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.get('uvv_checker_enabled'):
            for slot in obj.material_slots:
                if slot.material and slot.material.use_nodes:
                    nodes = slot.material.node_tree.nodes
                    from .uvflow_style_checker import UVV_CHECKER_TEXTURE_NAME, UVV_MIX_SHADER_NAME, UVV_ATTRIBUTE_NODE_NAME
                    if (nodes.get(UVV_CHECKER_TEXTURE_NAME) and 
                        nodes.get(UVV_MIX_SHADER_NAME) and 
                        nodes.get(UVV_ATTRIBUTE_NODE_NAME)):
                        materials_with_checker.append(slot.material)
    
    state['has_materials_with_checker'] = len(materials_with_checker) > 0
    
    # Check for objects in edit mode (for reference, but not required for checker to be active)
    edit_mode_objects = [obj for obj in bpy.data.objects if obj.mode == 'EDIT' and obj.type == 'MESH']
    state['has_objects_in_edit_mode'] = len(edit_mode_objects) > 0
    
    # Check UV Editor state
    uv_editor_has_image = False
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR' and area.spaces.active.image:
                uv_editor_has_image = True
                break
    state['has_uv_editor_image'] = uv_editor_has_image
    
    # Check 3D view state (based on visibility setting)
    if settings.checker_show_in_3d_view:
        state['has_3d_view_checker'] = state['has_materials_with_checker']
    else:
        state['has_3d_view_checker'] = not state['has_materials_with_checker']
    
    # Determine if state is consistent
    expected_uv_editor = settings.checker_show_in_uv_editor and state['has_materials_with_checker']
    expected_3d_view = settings.checker_show_in_3d_view and state['has_materials_with_checker']
    
    # Checker is consistently enabled if it has materials with checker nodes
    # and the UV editor/3D view states match the expected states
    state['is_consistently_enabled'] = (
        state['has_materials_with_checker'] and
        (expected_uv_editor == state['has_uv_editor_image']) and
        (expected_3d_view == state['has_3d_view_checker'])
    )
    
    # Identify mismatched components
    if state['has_materials_with_checker'] != state['has_uv_editor_image']:
        state['mismatched_components'].append('uv_editor')
    if state['has_materials_with_checker'] != state['has_3d_view_checker']:
        state['mismatched_components'].append('3d_view')
    
    # Check if restoration is needed
    state['needs_restoration'] = (
        len(state['mismatched_components']) > 0 or
        not state['is_consistently_enabled']
    )
    
    return state


def sync_checker_state(context, force_sync=False):
    """
    Synchronize the actual checker state with the UI state.
    Fixes any mismatches between what should be enabled and what actually is.
    """
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()
    
    # Check if we're in a context where data modification is allowed
    # Skip sync during UI drawing or other restricted contexts
    try:
        # Test if we can modify data by trying to access a simple property
        test_obj = bpy.data.objects
        if not test_obj:
            return False
    except Exception:
        # If we can't even access bpy.data, we're in a restricted context
        return False
    
    state = validate_checker_state(context)
    
    if not state['needs_restoration'] and not force_sync:
        return True
    
    # Get current checker image
    current_image = get_uvv_checker_image(context)
    if not current_image:
        return False
    
    # Fix UV Editor state
    if 'uv_editor' in state['mismatched_components']:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    if settings.checker_show_in_uv_editor:
                        area.spaces.active.image = current_image
                    else:
                        area.spaces.active.image = None
    
    # Fix 3D View state
    if '3d_view' in state['mismatched_components']:
        if settings.checker_show_in_3d_view:
            # Restore checker nodes
            uvv_checker_image_update(context, current_image)
        else:
            # Remove checker nodes
            settings.hide_checker_from_3d_view(context)
    
    return True


def get_checker_state_for_ui(context):
    """
    Get the checker state for UI display.
    This checks if the checker system is enabled, regardless of current mode.
    """
    from .checker_mode_handler import is_checker_auto_mode_active
    
    # Check if auto mode is active (this indicates the checker system is enabled)
    return is_checker_auto_mode_active()


def get_uvv_checker_image(context):
    """ Return UVV Checker image or create one and Return """
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()

    # Handle custom image override first
    if settings.use_custom_image and settings.override_image_name != DEF_OVERRIDE_IMAGE_NAME:
        image = bpy.data.images.get(settings.override_image_name, None)
        if image is not None:
            return image

    # Route based on pattern type
    if settings.checker_pattern_type in ['UV_GRID', 'COLOR_GRID']:
        # Generate procedural texture
        pattern_type = 'UV_GRID' if settings.checker_pattern_type == 'UV_GRID' else 'COLOR_GRID'
        resolution = tuple(settings.checker_custom_resolution)
        image_name = f"UVV {settings.checker_pattern_type} {resolution[0]}x{resolution[1]}"
        return generate_procedural_texture(pattern_type, resolution, image_name)
    
    elif settings.checker_pattern_type == 'ARROW_GRID':
        # Load arrow grid texture
        return load_arrow_grid_texture()
    
    # Fallback to UV_GRID if unknown pattern type
    resolution = tuple(settings.checker_custom_resolution)
    image_name = f"UVV UV_GRID {resolution[0]}x{resolution[1]}"
    return generate_procedural_texture('UV_GRID', resolution, image_name)


def uvv_checker_image_update(context, _image):
    """Update checker image in node tree AND all UV editors (supports both modes)"""
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()

    interpolation = {True: 'Linear', False: 'Closest'}

    # Update based on current checker method
    if settings.checker_method == 'MODIFIER':
        # Update UV Flow style checker (update all checker texture nodes)
        from .uvflow_style_checker import UVV_CHECKER_TEXTURE_NAME

        for obj in bpy.data.objects:
            if obj.get('uvv_checker_enabled') and obj.type == 'MESH':
                for slot in obj.material_slots:
                    if slot.material and slot.material.use_nodes:
                        nodes = slot.material.node_tree.nodes
                        if checker_node := nodes.get(UVV_CHECKER_TEXTURE_NAME, None):
                            checker_node.image = _image
                            checker_node.interpolation = interpolation[settings.tex_checker_interpolation]
    else:
        # Update material-based checker (legacy)
        _overrider = None
        if bpy.data.node_groups.items():
            _overrider = bpy.data.node_groups.get(UVV_GLOBAL_OVERRIDER_NAME, None)
        if _overrider:
            if hasattr(_overrider, "nodes"):
                image_node = _overrider.nodes.get(UVV_IMAGE_NODE_NAME)
                if image_node:
                    image_node.image = _image
                    image_node.interpolation = interpolation[settings.tex_checker_interpolation]

    # Update all IMAGE_EDITOR areas to show the new checker image (only if enabled)
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                if settings.checker_show_in_uv_editor:
                    area.spaces.active.image = _image
                else:
                    # Clear the image from UV Editor when disabled
                    area.spaces.active.image = None


def uvv_checker_image_ensure(context):
    """
    Ensure Checker (any) image exist in UVV IMAGE NODE.
    """
    _overrider = None
    if bpy.data.node_groups.items():
        _overrider = bpy.data.node_groups.get(UVV_GLOBAL_OVERRIDER_NAME, None)
    if _overrider:
        if hasattr(_overrider, "nodes"):
            image_node = _overrider.nodes.get(UVV_IMAGE_NODE_NAME)
            if image_node:
                if not image_node.image:
                    print(f'UVV Checker: image_node.image is {image_node.image}. Error In "uvv_checker_image_ensure"')
                else:
                    image_node.image = get_uvv_checker_image(context)
                return image_node.image
    return None


def enshure_material_slots(context, _obj):
    """ Return material slots or create single material slot if empty """
    return _obj.material_slots or create_material_slot(context, _obj)


def create_material_slot(context, _obj):
    """ Create Material Slot and UVV Generic material inside slot. Return new slot """
    context.view_layer.objects.active = _obj
    bpy.ops.object.material_slot_add()
    return _obj.material_slots


def enshure_material(_slot):
    """ If slot material is empty - insert in given slot
    UVV Generic material and switch to tree mode """
    if not _slot.material:
        _slot.material = uvv_generic_mat().copy()


def enshure_user_mats_consistency(context, _objs):
    """ Refine and repair user materials from selected objects """
    for _obj in _objs:
        for _slot in enshure_material_slots(context, _obj):
            enshure_material(_slot)


def get_materials_from_objects(context, objs):
    """ Return materials from given objects set """
    _materials = []
    for _obj in objs:
        for _slot in enshure_material_slots(context, _obj):
            _materials.append(_slot.material)
    return _materials


def version_since_4_0_0():
    """Check if Blender version is 4.0.0 or higher"""
    return bpy.app.version >= (4, 0, 0)


def create_uvv_global_overrider_node_tree(context, _overrider, create_in_out=True):
    """ Create node tree for UVV Global Overrider """
    # Create group inputs
    group_inputs = _overrider.nodes.new('NodeGroupInput')
    group_inputs.location = (-200, 0)

    # Create group outputs
    group_outputs = _overrider.nodes.new('NodeGroupOutput')
    group_outputs.location = (400, 0)

    if create_in_out:
        if version_since_4_0_0():
            if hasattr(_overrider, 'interface'):

                if _overrider.interface.items_tree.get(InpSocket.name, None) is None:
                    _overrider.interface.new_socket(
                        InpSocket.name,
                        in_out=InpSocket.in_out,
                        socket_type=InpSocket.socket_type)

                if _overrider.interface.items_tree.get(OutSocket.name, None) is None:
                    _overrider.interface.new_socket(
                        OutSocket.name,
                        in_out=OutSocket.in_out,
                        socket_type=OutSocket.socket_type)
            else:
                return False
        else:
            if not len(_overrider.inputs):
                _overrider.inputs.new('NodeSocketShader', InpSocket.name)
            else:
                if _overrider.inputs.get(InpSocket.name, None) is None:
                    _overrider.inputs.new('NodeSocketShader', InpSocket.name)
            if not len(_overrider.outputs):
                _overrider.outputs.new('NodeSocketShader', OutSocket.name)
            else:
                if _overrider.outputs.get(OutSocket.name, None) is None:
                    _overrider.outputs.new('NodeSocketShader', OutSocket.name)

    # Create image node
    image_node = _overrider.nodes.new(type='ShaderNodeTexImage')
    image_node.name = UVV_IMAGE_NODE_NAME
    image_node.image = get_uvv_checker_image(context)

    # Create Tiler
    tiler = _overrider.nodes.new(type="ShaderNodeMapping")
    tiler.vector_type = "VECTOR"
    tiler.name = UVV_TILER_NODE_NAME
    uv_source = _overrider.nodes.new(type="ShaderNodeTexCoord")

    # Create Offsetter
    offsetter = CheckerOffsetter()
    offsetter.init(_overrider)

    # Link outputs
    _overrider.links.new(uv_source.outputs['UV'], offsetter.inp)
    _overrider.links.new(offsetter.out, tiler.inputs['Vector'])
    _overrider.links.new(image_node.outputs[0], group_outputs.inputs[OutSocket.name])
    _overrider.links.new(tiler.outputs[0], image_node.inputs['Vector'])

    # Set locations
    tiler.location = (0.0, 0.0)
    image_node.location = (260.28, 2.87)
    uv_source.location = (-420.75, 58.79)
    offsetter.location = (-630.76, -320.93)
    group_outputs.location = (585.25, 146.0)
    group_inputs.location = (-818.57, 149.64)

    return True


def UVV_Global_Overrider(context):
    """ Create and return UVV Global Overrider """
    # Create a global overrider node group
    global_overrider = bpy.data.node_groups.new(UVV_GLOBAL_OVERRIDER_NAME, 'ShaderNodeTree')
    if create_uvv_global_overrider_node_tree(context, global_overrider) is False:
        return False
    global_overrider.use_fake_user = True
    return global_overrider


def disable_overrider(context, _materials):
    """ Disable overrider """
    for _material in _materials:
        overriders = get_overrider(_material)
        for overrider in overriders:
            node_before_overrider = None
            node_after_overrider = None

            if hasattr(overrider, "inputs"):
                if len(overrider.inputs):
                    inp_channel = overrider.inputs.get(InpSocket.name)
                    if inp_channel is not None and inp_channel.links:
                        node_before_overrider = inp_channel.links[0].from_node
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_INP_CHANNELS

            if hasattr(overrider, "outputs"):
                if len(overrider.outputs):
                    out_channel = overrider.outputs.get(OutSocket.name)
                    if out_channel is not None and out_channel.links:
                        node_after_overrider = out_channel.links[0].to_node
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_OUT_CHANNELS

            _links = _material.node_tree.links
            # Remove link from Overrider node to User output material node
            if node_before_overrider:
                _links.remove(node_before_overrider.outputs[0].links[0])
            # Create link from shader (prev node) to User output material node
            if node_before_overrider and node_after_overrider:
                _links.new(node_before_overrider.outputs[0], node_after_overrider.inputs[0])
            if overrider:
                _material.node_tree.nodes.remove(overrider)
                if node_after_overrider:
                    node_after_overrider.socket_value_update(context)


def get_materials_with_overrider(_materials):
    """ Return all the materials contained overrider from given set of the materials """
    _materials_with_overrider = []
    for material in _materials:
        if hasattr(material, "node_tree"):
            if hasattr(material.node_tree, "nodes"):
                for node in material.node_tree.nodes:
                    if hasattr(node, "node_tree") and node.node_tree is not None:
                        if node.node_tree.name == UVV_GLOBAL_OVERRIDER_NAME \
                                or node.node_tree.name == UVV_GLOBAL_OVERRIDER_NAME_OLD:
                            _materials_with_overrider.append(material)
    return _materials_with_overrider


def has_materials_with_override(context: bpy.types.Context):
    """Check if checker is active (supports UV Flow auto mode and legacy material modes)"""
    from ..properties import get_uvv_settings

    try:
        settings = get_uvv_settings()
        checker_method = settings.checker_method
    except:
        # Fallback if settings not available
        checker_method = 'MATERIAL'

    if checker_method == 'MODIFIER':
        # Check for UV Flow style checker (auto mode with msgbus subscription)
        from .checker_mode_handler import is_checker_auto_mode_active
        return is_checker_auto_mode_active()
    else:
        # Check for material-based checker (legacy)
        for obj in context.selected_objects:
            if obj.type == 'MESH' and len(obj.data.polygons) != 0:
                for slot in obj.material_slots:
                    material = slot.material
                    if hasattr(material, "node_tree"):
                        if hasattr(material.node_tree, "nodes"):
                            for node in material.node_tree.nodes:
                                if hasattr(node, "node_tree") and node.node_tree is not None:
                                    if node.node_tree.name == UVV_GLOBAL_OVERRIDER_NAME \
                                            or node.node_tree.name == UVV_GLOBAL_OVERRIDER_NAME_OLD:
                                        return True
        return False


def get_overrider(_material):
    """ Return overriders from given material """
    overriders = []
    if hasattr(_material, "node_tree"):
        if hasattr(_material.node_tree, "nodes"):
            for _node in _material.node_tree.nodes:
                if hasattr(_node, "node_tree") and _node.node_tree is not None:
                    if _node.node_tree.name == UVV_GLOBAL_OVERRIDER_NAME \
                            or _node.node_tree.name == UVV_GLOBAL_OVERRIDER_NAME_OLD:
                        overriders.append(_node)
    return overriders


def implement_uvv_overrider(context, _obj, _GlobalOverrider):
    """ UVV Overrider Implementation """
    # Check material slots. If NOT - Create one and standard material.
    material_slots = enshure_material_slots(context, _obj)

    for slot in material_slots:
        enshure_material(slot)
        slot.material.use_nodes = True
        mat_nodes = slot.material.node_tree.nodes

        # Check if UVV Overrider exist in Current material nodes
        uvv_checker = mat_nodes.get(UVV_OVERRIDER_NAME)
        if uvv_checker:
            return

        # Implement UVV Overrider in to user material
        links = slot.material.node_tree.links

        # Define Material Output Node
        user_material_output_nodes = [node for node in mat_nodes if node.bl_rna.name == "Material Output"]
        if not user_material_output_nodes:
            mat_nodes.new("ShaderNodeOutputMaterial")
            user_material_output_nodes = [node for node in mat_nodes if node.bl_rna.name == "Material Output"]
        for count, mat_out_node in enumerate(user_material_output_nodes):
            uvv_checker = mat_nodes.new(type="ShaderNodeGroup")
            uvv_checker.node_tree = _GlobalOverrider
            uvv_checker.name = UVV_OVERRIDER_NAME
            uvv_checker.location = (200, 200)
            mat_nodes.active = uvv_checker
            uvv_checker.use_custom_color = True
            uvv_checker.color = UVV_NODE_COLOR

            user_mat_out_node_inputs = mat_out_node.inputs
            out_location = mat_out_node.location
            uvv_checker.location = (out_location.x - 200, out_location.y)

            # Define UVV Overrider Input and Output Channels
            uvv_overrider_input = uvv_checker.inputs.get(InpSocket.name, None)
            uvv_overrider_output = uvv_checker.outputs.get(OutSocket.name, None)

            prev_user_link = None
            if user_mat_out_node_inputs["Surface"].links:
                prev_user_link = user_mat_out_node_inputs["Surface"].links[0].from_node

            if prev_user_link and prev_user_link.name != UVV_OVERRIDER_NAME:
                if uvv_overrider_output is not None:
                    links.new(uvv_overrider_output, user_mat_out_node_inputs[0])
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_OUT_CHANNELS
                    return False
                if uvv_overrider_input is not None:
                    prev_user_link = links.new(uvv_overrider_input, prev_user_link.outputs[0])
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_INP_CHANNELS
                    return False
            else:
                if uvv_overrider_output is not None:
                    links.new(uvv_overrider_output, user_mat_out_node_inputs[0])
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_OUT_CHANNELS
                    return False


def repair_uvv_generic_mat():
    """ Repair UVV Generic material """
    mat = uvv_generic_mat()
    _links = mat.node_tree.links
    pr_bsdf_node = mat.node_tree.nodes.get("Principled BSDF")
    if not pr_bsdf_node:
        pr_bsdf_node = mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
    pr_bsdf_node_output = pr_bsdf_node.outputs[0]

    mat_output = mat.node_tree.nodes.get("Material Output")
    if not mat_output:
        mat_output = mat.node_tree.nodes.new(type="ShaderNodeOutputMaterial")
    mat_output_input = mat_output.inputs[0]

    _links.new(pr_bsdf_node_output, mat_output_input)


def repair_uvv_overrider(context):
    """ Repair UVV Global overrider to default state or create new if no exist in data blocks """
    _overrider = None
    if bpy.data.node_groups.items():
        _overrider = bpy.data.node_groups.get(UVV_GLOBAL_OVERRIDER_NAME, None)
    if _overrider:
        _overrider.nodes.clear()
        if create_uvv_global_overrider_node_tree(context, _overrider, create_in_out=True) is False:
            return False
    else:
        _overrider = UVV_Global_Overrider(context)


def remove_uvv_overrider(context):
    """ Remove UVV Overrider from all Materials in scene """
    disable_overrider(context, bpy.data.materials)


def disable_checker_in_uv_layout(context):
    screen = context.screen
    for area in screen.areas:
        if area.type == 'IMAGE_EDITOR':
            area.spaces.active.image = None


def _switch(area, style, switch):
    """Internal function to switch shading color type"""
    for space in area.spaces:
        if space.type == 'VIEW_3D':
            if space.shading.color_type == "VERTEX" and style == "VERTEX" and switch:
                style = "MATERIAL"
            if space.shading.type != 'WIREFRAME':
                space.shading.color_type = style
            return True
        return False


def switch_shading_style(context, style, switch):
    """Switch viewport shading color type (MATERIAL, TEXTURE, VERTEX, SINGLE)"""
    if context.area.type == 'VIEW_3D':
        return _switch(context.area, style, switch)
    else:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                return _switch(area, style, switch)


def get_current_shading_style(context):
    """Get current viewport shading color type"""
    if context.area.type == 'IMAGE_EDITOR':
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        return space.shading.color_type
    elif context.area.type == 'VIEW_3D':
        for space in context.area.spaces:
            if space.type == 'VIEW_3D':
                return space.shading.color_type
    else:
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()
        return settings.prev_color_type if settings else None
    return None


def resort_by_type_mesh_in_edit_mode_and_sel(context):
    """Get mesh objects from selection"""
    objs = []
    for obj in context.selected_objects:
        if obj.type == 'MESH':
            objs.append(obj)
    return objs


class CheckerMessenger:
    state: bool = True
    message: str = ''

    @classmethod
    def clear(cls):
        cls.state = True
        cls.message = ''


class UVVChecker_OT_CheckerOn(bpy.types.Operator):
    bl_idname = "view3d.uvv_checker_on"
    bl_label = 'Checker On'
    bl_description = 'Add checker texture to the selected mesh'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if bpy.ops.view3d.uvv_checker_toggle.poll():
            bpy.ops.view3d.uvv_checker_toggle(action='ON')
        return {'FINISHED'}


class UVVChecker_OT_CheckerOff(bpy.types.Operator):
    bl_idname = "view3d.uvv_checker_off"
    bl_label = 'Checker Off'
    bl_description = 'Remove checker texture from the selected mesh'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if bpy.ops.view3d.uvv_checker_toggle.poll():
            bpy.ops.view3d.uvv_checker_toggle(action='OFF')
        return {'FINISHED'}


class UVVChecker_OT_CheckerToggle(bpy.types.Operator):
    """ UVV Checker Processor """
    bl_idname = "view3d.uvv_checker_toggle"
    bl_label = label.OT_CHECKER_TOGGLE_LABEL
    bl_description = label.OT_CHECKER_TOGGLE_DESC
    bl_options = {'REGISTER', 'UNDO'}

    checked: bpy.props.BoolProperty(
        name='Checked',
        options={'HIDDEN', 'SKIP_SAVE'},
        default=False
    )
    action: bpy.props.EnumProperty(
        name='Action',
        description='Action',
        items=[
            ("ON", "On", "Turn on checker"),
            ("OFF", "Off", "Turn off checker"),
            ("TOGGLE", "Toggle", "Toggle checker")
            ],
        default='TOGGLE',
        options={'HIDDEN', 'SKIP_SAVE'},
        )

    LITERAL_PREV_IMAGE = 'uvv_checker_prev_image'
    LITERAL_TOGGLE = 'uvv_checker_toggle'

    @classmethod
    def draw_toggled(cls, layout: bpy.types.UILayout, context: bpy.types.Context):
        # Use comprehensive state detection
        b_is_checked = get_checker_state_for_ui(context)
        layout.operator(
            cls.bl_idname,
            depress=b_is_checked,
            icon='TEXTURE').action = 'TOGGLE'

    @classmethod
    def poll(cls, context):
        return context.area.type in {'VIEW_3D', 'IMAGE_EDITOR'}

    def execute(self, context):
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()

        CheckerMessenger.clear()

        # HYBRID APPROACH: Choose between material override and modifier based on user preference
        checker_method = settings.checker_method

        if checker_method == 'MODIFIER':
            # Use modifier-based approach
            return self.execute_modifier_mode(context, settings)
        else:
            # Use legacy material override approach
            return self.execute_material_mode(context, settings)

    def execute_modifier_mode(self, context, settings):
        """Execute checker using UV Flow style (material nodes with auto mode handler)"""
        from .checker_mode_handler import (
            is_checker_auto_mode_active,
            enable_checker_auto_mode,
            disable_checker_auto_mode
        )

        # Check if auto mode is currently active
        is_active = is_checker_auto_mode_active()

        if is_active:
            # Turn Off Checker - Disable auto mode
            if self.action in {'OFF', 'TOGGLE'}:

                # Disable auto mode (this will remove all checkers and unsubscribe from mode changes)
                disable_checker_auto_mode(context)

                # Restore UV editor image based on visibility settings
                if settings.checker_show_in_uv_editor:
                    if context.space_data.type == 'IMAGE_EDITOR':
                        was_image_name = bpy.app.driver_namespace.get(
                            UVVChecker_OT_CheckerToggle.LITERAL_PREV_IMAGE, '')
                        if was_image_name:
                            p_image = bpy.data.images.get(was_image_name, None)
                            if p_image:
                                context.space_data.image = p_image
                else:
                    # Clear UV Editor when disabled
                    if context.space_data.type == 'IMAGE_EDITOR':
                        context.space_data.image = None
        else:
            # Turn On Checker - Enable auto mode
            if self.action in {'ON', 'TOGGLE'}:
                # Get selected mesh objects
                selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']

                if len(selected_meshes) == 0:
                    self.report({'WARNING'}, "No mesh objects selected")
                    return {'CANCELLED'}

                # Check if any selected objects are in Edit Mode
                objects_in_edit_mode = [obj for obj in selected_meshes if obj.mode == 'EDIT']

                # If no objects in Edit Mode, switch selected objects to Edit Mode
                if len(objects_in_edit_mode) == 0:
                    # Switch to Edit Mode for selected objects
                    if context.object and context.object.type == 'MESH':
                        bpy.ops.object.mode_set(mode='EDIT')
                        self.report({'INFO'}, "Switched to Edit Mode and enabled UV Checker")
                    else:
                        self.report({'WARNING'}, "Cannot enter Edit Mode")
                        return {'CANCELLED'}

                # Save UV editor image
                if context.space_data.type == 'IMAGE_EDITOR':
                    was_image = context.space_data.image
                    bpy.app.driver_namespace[UVVChecker_OT_CheckerToggle.LITERAL_PREV_IMAGE] = was_image.name if was_image else ''

                # Enable auto mode (this will add checkers to Edit Mode objects and subscribe to mode changes)
                enable_checker_auto_mode(context)

                # Update UV editor (only if show in UV Editor is enabled)
                p_image = uvv_checker_image_ensure(context)
                if p_image is not None:
                    if settings.checker_show_in_uv_editor:
                        if context.space_data.type == 'IMAGE_EDITOR':
                            context.space_data.image = p_image
                    else:
                        # Clear UV Editor when disabled
                        if context.space_data.type == 'IMAGE_EDITOR':
                            context.space_data.image = None
                
                # Update 3D view (only if show in 3D View is enabled)
                if settings.checker_show_in_3d_view:
                    # The checker nodes are already added by enable_checker_auto_mode
                    # Just ensure the image is updated
                    p_image = uvv_checker_image_ensure(context)
                    if p_image is not None:
                        uvv_checker_image_update(context, p_image)
                else:
                    # Hide from 3D view by removing checker nodes
                    settings.hide_checker_from_3d_view(context)


        # Redraw viewports
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'VIEW_3D', 'IMAGE_EDITOR'}:
                    area.tag_redraw()

        return {'FINISHED'}

    def execute_material_mode(self, context, settings):
        """Execute checker using legacy material override approach"""
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if len(objs) == 0:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        for obj in objs:
            if len(obj.data.uv_layers) == 0:
                obj.data.uv_layers.new()
            obj.material_slots.update()
            obj.update_from_editmode()
            if obj.display_type != 'TEXTURED':
                self.report({'WARNING'}, f"UVV: {obj.name} viewport display mode is {obj.display_type}")

        # Get or create Global Overrider
        GlobalOverrider = bpy.data.node_groups.get(UVV_GLOBAL_OVERRIDER_NAME) or UVV_Global_Overrider(context)
        if GlobalOverrider is False:
            self.report({'WARNING'}, 'UVV: Checker nodes are damaged. Please perform "Reset Checker"')
            return {'CANCELLED'}
        enshure_user_mats_consistency(context, objs)
        materials_with_overrider = get_materials_with_overrider(get_materials_from_objects(context, objs))

        bpy.app.driver_namespace[UVVChecker_OT_CheckerToggle.LITERAL_TOGGLE] = False

        if materials_with_overrider:  # Case checker exist in currently selected objects - Turn Off Checker
            if self.action in {'OFF', 'TOGGLE'}:

                disable_overrider(context, materials_with_overrider)
                prev_color_type = settings.prev_color_type
                switch_shading_style(context, prev_color_type if prev_color_type != '' else 'TEXTURE', switch=False)

                # Restore UV editor image based on visibility settings
                if settings.checker_show_in_uv_editor:
                    if context.space_data.type == 'IMAGE_EDITOR':
                        was_image_name = bpy.app.driver_namespace.get(
                            UVVChecker_OT_CheckerToggle.LITERAL_PREV_IMAGE, '')
                        if was_image_name:
                            p_image = bpy.data.images.get(was_image_name, None)
                            if p_image:
                                context.space_data.image = p_image
                else:
                    # Clear UV Editor when disabled
                    if context.space_data.type == 'IMAGE_EDITOR':
                        context.space_data.image = None

        else:  # Else - Turn On Checker
            if self.action in {'ON', 'TOGGLE'}:
                if context.space_data.type == 'IMAGE_EDITOR':
                    was_image = context.space_data.image
                    bpy.app.driver_namespace[UVVChecker_OT_CheckerToggle.LITERAL_PREV_IMAGE] = was_image.name if was_image else ''

                p_prev_type = get_current_shading_style(context)
                if p_prev_type is not None:
                    settings.prev_color_type = p_prev_type
                repair_uvv_generic_mat()
                for obj in objs:
                    implement_uvv_overrider(context, obj, GlobalOverrider)
                p_image = uvv_checker_image_ensure(context)
                if p_image is not None:

                    bpy.app.driver_namespace[UVVChecker_OT_CheckerToggle.LITERAL_TOGGLE] = True

                    # Update UV editor based on visibility setting
                    if settings.checker_show_in_uv_editor:
                        if context.space_data.type == 'IMAGE_EDITOR':
                            context.space_data.image = p_image
                    else:
                        # Clear UV Editor when disabled
                        if context.space_data.type == 'IMAGE_EDITOR':
                            context.space_data.image = None
                    
                    # Update 3D view (only if show in 3D View is enabled)
                    if settings.checker_show_in_3d_view:
                        uvv_checker_image_update(context, p_image)
                    else:
                        # Hide from 3D view by removing checker nodes
                        settings.hide_checker_from_3d_view(context)
                switch_shading_style(context, "TEXTURE", switch=False)


        context = bpy.context

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'VIEW_3D', 'IMAGE_EDITOR'}:
                    area.tag_redraw()

        if CheckerMessenger.state is False:
            self.report({'WARNING'}, CheckerMessenger.message)
            return {'CANCELLED'}

        return {'FINISHED'}


class UVVChecker_OT_Reset(bpy.types.Operator):
    """ UVV Checker Reset """
    bl_idname = "view3d.uvv_checker_reset"
    bl_label = label.OT_CHECKER_RESET_LABEL
    bl_description = label.OT_CHECKER_RESET_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..properties import get_uvv_settings
        from .get_prefs import DEF_OVERRIDE_IMAGE_NAME
        settings = get_uvv_settings()

        print('UVV: >> Checker Resetting')

        settings.use_custom_image = False
        settings.override_image_name = DEF_OVERRIDE_IMAGE_NAME

        repair_uvv_overrider(context)

        settings.tex_checker_interpolation = True
        settings.tex_checker_tiling = (1.0, 1.0)
        settings.tex_checker_offset = 0.0

        settings.chk_rez_filter = False

        return {'FINISHED'}


class UVVChecker_OT_Remove(bpy.types.Operator):
    """ UVV Checker Remove """
    bl_idname = "view3d.uvv_checker_remove"
    bl_label = label.OT_CHECKER_REMOVE_LABEL
    bl_description = label.OT_CHECKER_REMOVE_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        remove_uvv_overrider(context)
        disable_checker_in_uv_layout(context)
        remove_uvv_generic_mats()
        return {'FINISHED'}


class UVV_OT_ResetResolution(bpy.types.Operator):
    """Reset resolution to default value"""
    bl_idname = "uv.uvv_reset_resolution"
    bl_label = "Reset Resolution"
    bl_description = "Reset resolution to default value (1024x1024)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()
        settings.checker_custom_resolution = (1024, 1024)
        return {'FINISHED'}


class UVV_OT_DoubleResolution(bpy.types.Operator):
    """Double the current resolution"""
    bl_idname = "uv.uvv_double_resolution"
    bl_label = "Double Resolution"
    bl_description = "Double the current resolution values"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()
        current_res = settings.checker_custom_resolution
        new_res = (min(current_res[0] * 2, 7680), min(current_res[1] * 2, 7680))
        settings.checker_custom_resolution = new_res
        return {'FINISHED'}


class UVV_OT_HalfResolution(bpy.types.Operator):
    """Half the current resolution"""
    bl_idname = "uv.uvv_half_resolution"
    bl_label = "Half Resolution"
    bl_description = "Half the current resolution values"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()
        current_res = settings.checker_custom_resolution
        new_res = (max(current_res[0] // 2, 64), max(current_res[1] // 2, 64))
        settings.checker_custom_resolution = new_res
        return {'FINISHED'}


class UVVChecker_OT_OpenEditor(bpy.types.Operator):
    """ UVV Checker Open Editor """
    bl_idname = "view3d.uvv_checker_open_editor"
    bl_label = label.OT_CHECKER_OPEN_EDITOR_LABEL
    bl_description = label.OT_CHECKER_OPEN_EDITOR_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.selected_objects:
            return True

    def execute(self, context):
        try:
            obj = context.selected_objects[0]
            material = obj.material_slots[0].material
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
            area = context.window_manager.windows[-1].screen.areas[0]
            area.type = 'NODE_EDITOR'
            area.ui_type = 'ShaderNodeTree'

            area.spaces.active.node_tree = material.node_tree
            overrider = material.node_tree.nodes[UVV_OVERRIDER_NAME]
            area.spaces.active.node_tree.nodes.active = overrider
            bpy.ops.node.group_edit()
        except Exception:
            print("Seems like problem with Shader editor opening...")

        return {'FINISHED'}


class UVVChecker_OT_ResetPath(bpy.types.Operator):
    bl_idname = "ops.uvv_checker_reset_path"
    bl_label = label.OT_RESET_PATH_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = label.OT_RESET_PATH_DESC

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text=label.MESS_RESET_PATH)
        layout.separator()

    def execute(self, context):
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()
        # Reset to default path
        from .get_prefs import get_path
        import os
        settings.checker_assets_path = os.path.join(get_path(), "images")
        # Update main dict
        settings.files_dict = dumps(update_files_info(settings.checker_assets_path))
        settings.sizes_y_index = 0
        settings.checker_images_index = 0
        return {'FINISHED'}


classes = [
    UVVChecker_OT_CheckerToggle,
    UVVChecker_OT_Reset,
    UVVChecker_OT_Remove,
    UVVChecker_OT_OpenEditor,
    UVVChecker_OT_ResetPath,
    UVVChecker_OT_CheckerOn,
    UVVChecker_OT_CheckerOff,
    UVV_OT_ResetResolution,
    UVV_OT_DoubleResolution,
    UVV_OT_HalfResolution
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    pass
