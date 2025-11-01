

""" UVV Modifier-Based Checker System (UV Flow style - display_type + auto mode) """

import bpy


UVV_CHECKER_MODIFIER_NAME = "UVV_Checker_Display"
UVV_CHECKER_MATERIAL_NAME = "UVV_Checker_Material"
UVV_CHECKER_GEONODES_NAME = "UVV_Checker_Override"


def get_or_create_checker_material(context):
    """Get or create the checker material for modifier-based system"""
    from .checker import get_uvv_checker_image

    # Check if material already exists
    mat = bpy.data.materials.get(UVV_CHECKER_MATERIAL_NAME)

    if mat is None:
        # Create new material
        mat = bpy.data.materials.new(name=UVV_CHECKER_MATERIAL_NAME)
        mat.use_nodes = True
        mat.use_fake_user = True

        # Clear default nodes
        mat.node_tree.nodes.clear()

        # Create new node setup
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Create nodes
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        output_node.location = (300, 0)

        emission_node = nodes.new(type='ShaderNodeEmission')
        emission_node.location = (0, 0)

        image_node = nodes.new(type='ShaderNodeTexImage')
        image_node.location = (-300, 0)
        image_node.image = get_uvv_checker_image(context)

        uv_map_node = nodes.new(type='ShaderNodeUVMap')
        uv_map_node.location = (-500, 0)

        # Link nodes
        links.new(uv_map_node.outputs['UV'], image_node.inputs['Vector'])
        links.new(image_node.outputs['Color'], emission_node.inputs['Color'])
        links.new(emission_node.outputs['Emission'], output_node.inputs['Surface'])

    # Update image if it changed
    else:
        image_node = None
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE':
                image_node = node
                break

        if image_node:
            image_node.image = get_uvv_checker_image(context)

    return mat


def get_or_create_geonodes_group():
    """Get or create the geometry nodes group for material override"""
    # Check if node group already exists
    node_group = bpy.data.node_groups.get(UVV_CHECKER_GEONODES_NAME)

    if node_group is None:
        # Create new geometry node group
        node_group = bpy.data.node_groups.new(name=UVV_CHECKER_GEONODES_NAME, type='GeometryNodeTree')
        node_group.use_fake_user = True

        # Create interface sockets (Blender 4.0+ API)
        if hasattr(node_group, 'interface'):
            # Input
            node_group.interface.new_socket(
                'Geometry',
                in_out='INPUT',
                socket_type='NodeSocketGeometry'
            )
            # Output
            node_group.interface.new_socket(
                'Geometry',
                in_out='OUTPUT',
                socket_type='NodeSocketGeometry'
            )
        else:
            # Fallback for older Blender versions
            node_group.inputs.new('NodeSocketGeometry', 'Geometry')
            node_group.outputs.new('NodeSocketGeometry', 'Geometry')

        # Create nodes
        nodes = node_group.nodes
        links = node_group.links

        # Group Input
        group_input = nodes.new('NodeGroupInput')
        group_input.location = (-400, 0)

        # Set Material node
        set_material_node = nodes.new('GeometryNodeSetMaterial')
        set_material_node.location = (-100, 0)
        # Material will be assigned per-modifier instance

        # Group Output
        group_output = nodes.new('NodeGroupOutput')
        group_output.location = (200, 0)

        # Link nodes
        links.new(group_input.outputs['Geometry'], set_material_node.inputs['Geometry'])
        links.new(set_material_node.outputs['Geometry'], group_output.inputs['Geometry'])

    return node_group


def has_checker_modifier(obj):
    """Check if object has the checker modifier"""
    if obj.type != 'MESH':
        return False

    for mod in obj.modifiers:
        if mod.name == UVV_CHECKER_MODIFIER_NAME:
            return True

    return False


def add_checker_modifier(context, obj):
    """Add checker modifier to object"""
    from .checker import get_uvv_checker_image

    if obj.type != 'MESH':
        return None

    # Ensure UV layer exists
    if len(obj.data.uv_layers) == 0:
        obj.data.uv_layers.new()

    # Check if modifier already exists
    if has_checker_modifier(obj):
        return obj.modifiers[UVV_CHECKER_MODIFIER_NAME]

    # Get or create material and node group
    checker_material = get_or_create_checker_material(context)
    node_group = get_or_create_geonodes_group()

    # Add modifier
    modifier = obj.modifiers.new(name=UVV_CHECKER_MODIFIER_NAME, type='NODES')
    modifier.node_group = node_group
    modifier.show_render = False  # Viewport only
    modifier.show_viewport = True  # Always show when object display allows
    modifier.show_in_editmode = True
    modifier.show_on_cage = True

    # Set object display type to TEXTURED (UV Flow style)
    # Save previous display type
    if not obj.get('uvv_prev_display_type'):
        obj['uvv_prev_display_type'] = obj.display_type
    obj.display_type = 'TEXTURED'

    # Mark as checker enabled
    obj['uvv_checker_enabled'] = True

    # Set the material on the Set Material node
    # We need to access the modifier's node inputs
    if hasattr(modifier, 'node_group') and modifier.node_group:
        # Find the Set Material node and set its material input
        for node in modifier.node_group.nodes:
            if node.type == 'SET_MATERIAL':
                # Set material via the modifier interface
                # In Blender 3.0+, we need to set it through the modifier's inputs
                try:
                    # Try to set via modifier identifier
                    if hasattr(modifier, '__setitem__'):
                        modifier["Input_2_attribute_name"] = ""
                        modifier["Input_2_use_attribute"] = 0

                    # Directly set on node (this works in most cases)
                    node.inputs['Material'].default_value = checker_material
                except:
                    pass
                break

    return modifier


def remove_checker_modifier(obj):
    """Remove checker modifier from object and restore display type"""
    if obj.type != 'MESH':
        return False

    removed = False
    for mod in obj.modifiers:
        if mod.name == UVV_CHECKER_MODIFIER_NAME:
            obj.modifiers.remove(mod)
            removed = True
            break

    # Restore previous display type
    if obj.get('uvv_prev_display_type'):
        obj.display_type = obj.pop('uvv_prev_display_type')

    # Remove checker enabled flag
    if obj.get('uvv_checker_enabled'):
        obj.pop('uvv_checker_enabled')

    return removed


def enable_checker_modifier_mode(context):
    """Enable checker using modifier approach (UV Flow style - only for EDIT mode objects)"""
    from .checker import uvv_checker_image_ensure
    from ..properties import get_uvv_settings

    settings = get_uvv_settings()

    # UV Flow style: Only get objects that are in EDIT mode
    objs = [obj for obj in context.view_layer.objects if obj.mode == 'EDIT' and obj.type == 'MESH']

    if len(objs) == 0:
        return False, "There are no objects in Edit Mode"

    # Save viewport state
    if context.space_data.type == 'IMAGE_EDITOR':
        was_image = context.space_data.image
        from .checker import UVVChecker_OT_CheckerToggle
        bpy.app.driver_namespace[UVVChecker_OT_CheckerToggle.LITERAL_PREV_IMAGE] = was_image.name if was_image else ''

    # Save shading mode
    if hasattr(context.space_data, 'shading'):
        if context.space_data.shading.color_type != 'TEXTURE':
            context.scene['uvv_prev_color_type'] = context.space_data.shading.color_type
            context.space_data.shading.color_type = 'TEXTURE'

    # Add modifiers to EDIT mode objects only
    for obj in objs:
        if not has_checker_modifier(obj):
            add_checker_modifier(context, obj)

    # Update UV editor
    p_image = uvv_checker_image_ensure(context)
    if p_image is not None:
        if context.space_data.type == 'IMAGE_EDITOR':
            context.space_data.image = p_image


    return True, ""


def disable_checker_modifier_mode(context):
    """Disable checker using modifier approach"""
    from ..properties import get_uvv_settings
    from .darken_image import UVV_OT_DarkenImage

    settings = get_uvv_settings()


    # Remove modifiers from all objects that have them
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and has_checker_modifier(obj):
            remove_checker_modifier(obj)

    # Restore viewport shading
    if hasattr(context.space_data, 'shading'):
        if 'uvv_prev_color_type' in context.scene.keys():
            context.space_data.shading.color_type = context.scene.pop('uvv_prev_color_type')

    # Restore UV editor image
    if context.space_data.type == 'IMAGE_EDITOR':
        from .checker import UVVChecker_OT_CheckerToggle
        was_image_name = bpy.app.driver_namespace.get(
            UVVChecker_OT_CheckerToggle.LITERAL_PREV_IMAGE, '')
        if was_image_name:
            p_image = bpy.data.images.get(was_image_name, None)
            if p_image:
                context.space_data.image = p_image

    return True, ""


def has_any_checker_modifiers(context):
    """Check if any selected object has checker modifier"""
    for obj in context.selected_objects:
        if obj.type == 'MESH' and has_checker_modifier(obj):
            return True
    return False


def update_checker_modifier_material(context):
    """Update the checker material when image changes"""
    # Update the checker material with new image
    checker_material = get_or_create_checker_material(context)

    # Force refresh all objects with the modifier
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and has_checker_modifier(obj):
            # Trigger update by toggling modifier visibility
            modifier = obj.modifiers.get(UVV_CHECKER_MODIFIER_NAME)
            if modifier:
                modifier.show_viewport = False
                modifier.show_viewport = True
