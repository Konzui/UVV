

""" UVV Checker - UV Flow Style (Material Node Injection Only) """

import bpy
from typing import List


# Node names for checker system
UVV_MIX_SHADER_NAME = 'UVV_Checker_Mix'
UVV_CHECKER_TEXTURE_NAME = 'UVV_Checker_Texture'
UVV_ATTRIBUTE_NODE_NAME = 'UVV_Checker_UVMap'


def enable_shading(context, objects: List[bpy.types.Object]) -> None:
    """
    Enable textured shading for selected objects (UV Flow style).
    Sets display_type to TEXTURED and switches viewport to TEXTURE mode.
    """
    for obj in context.scene.objects:
        if obj.display_type in ['WIRE', 'BOUNDS']:
            pass
        elif obj in objects and obj.type == 'MESH':
            # Save previous display type
            if not obj.get('uvv_prev_display_type'):
                obj['uvv_prev_display_type'] = obj.display_type
            obj.display_type = 'TEXTURED'
            obj['uvv_checker_enabled'] = True
        elif (obj not in objects and
              not obj.get('uvv_checker_enabled') and
              obj.visible_get() and
              obj.type == 'MESH'):
            # Set other objects to SOLID
            if not obj.get('uvv_prev_display_type'):
                obj['uvv_prev_display_type'] = obj.display_type
            if (hasattr(context.space_data, 'shading') and
                context.space_data.shading.color_type != 'TEXTURE'):
                obj.display_type = 'SOLID'

    # Switch viewport to show materials (TEXTURE mode or MATERIAL mode)
    if hasattr(context.space_data, 'shading'):
        shading = context.space_data.shading.type
        is_wire = shading == 'WIREFRAME'
        color = context.space_data.shading.color_type

        # Save current settings
        if color != 'TEXTURE' and color != 'MATERIAL':
            context.scene['uvv_prev_color_type'] = color
        
        # Ensure we can see materials - use MATERIAL mode if available, otherwise TEXTURE
        if shading == 'WIREFRAME':
            context.space_data.shading.type = 'SOLID'
        
        # Force viewport to show materials - use MATERIAL mode if available, otherwise TEXTURE
        if hasattr(context.space_data.shading, 'color_type'):
            # Check if MATERIAL mode is available (Blender 3.0+)
            material_available = False
            try:
                for item in context.space_data.shading.bl_rna.properties['color_type'].enum_items:
                    if item.identifier == 'MATERIAL':
                        material_available = True
                        break
            except:
                pass
            
            if material_available:
                context.space_data.shading.color_type = 'MATERIAL'
            else:
                context.space_data.shading.color_type = 'TEXTURE'
        
        # Restore wireframe if it was wireframe
        if is_wire:
            context.space_data.shading.type = 'WIREFRAME'


def disable_shading(context, objects: List[bpy.types.Object]) -> None:
    """
    Disable textured shading and restore previous display settings (UV Flow style).
    """
    # Revert selected objects
    for obj in objects:
        if (obj.get('uvv_checker_enabled') and
            'uvv_prev_display_type' in obj.keys()):
            obj.display_type = obj.pop('uvv_prev_display_type')

    # Revert background objects only if no textured objects still exist
    other_tex_objs = [obj for obj in context.scene.objects if (
        obj not in objects and
        obj.visible_get() and
        obj.get('uvv_checker_enabled')
    )]

    if not other_tex_objs:
        for obj in context.scene.objects:
            if obj not in objects and 'uvv_prev_display_type' in obj.keys():
                obj.display_type = obj.pop('uvv_prev_display_type')

        if context.space_data and hasattr(context.space_data, 'shading'):
            if 'uvv_prev_color_type' in context.scene.keys():
                context.space_data.shading.color_type = context.scene.pop('uvv_prev_color_type')


def setup_image(context) -> bpy.types.Image:
    """
    Get or load the checker texture image.
    """
    from .checker import get_uvv_checker_image
    return get_uvv_checker_image(context)


def setup_slots(context, obj: bpy.types.Object) -> List[bpy.types.MaterialSlot]:
    """
    Ensure object has at least one material slot with a valid material.
    """
    if not len(obj.material_slots):
        obj.data.materials.append(bpy.data.materials.new("Material"))
    if not obj.material_slots[0].material:
        obj.material_slots[0].material = bpy.data.materials.new('Material')
    return [x for x in obj.material_slots if x.material]


def setup_nodes(context, obj: bpy.types.Object, slot: bpy.types.MaterialSlot, tex: bpy.types.Image) -> None:
    """
    Set up material nodes for UV checker display (UV Flow style).
    Creates a Mix Shader that blends the original shader with checker texture.
    """
    slot.material.use_nodes = True
    nodes = slot.material.node_tree.nodes
    links = slot.material.node_tree.links

    # Save active node
    if slot.material.node_tree.nodes.active:
        slot.material['uvv_prev_active'] = slot.material.node_tree.nodes.active.name

    # Find or create Material Output node
    output_nodes = [node for node in nodes if node.type == 'OUTPUT_MATERIAL']
    if not output_nodes:
        output_node = nodes.new('ShaderNodeOutputMaterial')
    else:
        for node in output_nodes:
            if node.is_active_output:
                output_node = node
                break

    # Create or get Mix Shader node
    if mix := nodes.get(UVV_MIX_SHADER_NAME, None):
        pass
    else:
        mix = nodes.new('ShaderNodeMixShader')
        mix.name = UVV_MIX_SHADER_NAME
        mix.label = UVV_MIX_SHADER_NAME
        mix.inputs['Fac'].default_value = 0.9
        mix.location = [output_node.location[0], output_node.location[1] + 150]

        # Connect existing shader to mix input
        if output_node.inputs and output_node.inputs[0].links and output_node.inputs[0].links[0].from_node != mix:
            links.new(output_node.inputs[0].links[0].from_socket, mix.inputs[1])

        # Connect mix to output
        links.new(mix.outputs[0], output_node.inputs[0])

    # Create or get Checker Texture node
    if checker_node := nodes.get(UVV_CHECKER_TEXTURE_NAME, None):
        image_tex = checker_node
    else:
        image_tex = nodes.new('ShaderNodeTexImage')
        image_tex.name = UVV_CHECKER_TEXTURE_NAME
        image_tex.label = UVV_CHECKER_TEXTURE_NAME
        image_tex.hide = True
        nodes.active = image_tex
        image_tex.location = [output_node.location[0], output_node.location[1] + 200]
        links.new(image_tex.outputs[0], mix.inputs[2])

    image_tex.image = tex

    # Create or get UV Map Attribute node
    if attribute_node := nodes.get(UVV_ATTRIBUTE_NODE_NAME, None):
        map_node = attribute_node
    else:
        map_node = nodes.new('ShaderNodeAttribute')
        map_node.name = UVV_ATTRIBUTE_NODE_NAME
        map_node.label = UVV_ATTRIBUTE_NODE_NAME
        map_node.hide = True
        map_node.location = [output_node.location[0], output_node.location[1] + 250]
        links.new(map_node.outputs['Vector'], image_tex.inputs[0])

    # Set UV map to active UV layer
    if hasattr(obj.data, 'uv_layers') and obj.data.uv_layers.active:
        map_node.attribute_name = obj.data.uv_layers.active.name


def remove_nodes(context, obj: bpy.types.Object, slot: bpy.types.MaterialSlot) -> None:
    """
    Remove UV checker nodes from the material (UV Flow style).
    """
    if obj.get('uvv_checker_enabled') and slot.material.use_nodes:
        nodes = slot.material.node_tree.nodes
        links = slot.material.node_tree.links

        # Remove Mix Shader node and reconnect original shader
        if mix_node := nodes.get(UVV_MIX_SHADER_NAME, None):
            if mix_node.inputs[1].links and mix_node.outputs[0].links:
                links.new(mix_node.inputs[1].links[0].from_socket, mix_node.outputs[0].links[0].to_socket)
            nodes.remove(mix_node)
            del mix_node

        # Remove Checker Texture node
        if checker_node := nodes.get(UVV_CHECKER_TEXTURE_NAME, None):
            if nodes.active == checker_node and slot.material.get('uvv_prev_active'):
                nodes.active = nodes[slot.material.pop('uvv_prev_active')]
            nodes.remove(checker_node)
            del checker_node

        # Remove Attribute node
        if attribute_node := nodes.get(UVV_ATTRIBUTE_NODE_NAME, None):
            nodes.remove(attribute_node)
            del attribute_node


def enable_checker_material(context, objects: List[bpy.types.Object]) -> None:
    """
    Enable UV checker material on specified objects (UV Flow style).
    Respects checker_show_in_3d_view setting.
    """
    from ..properties import get_uvv_settings
    settings = get_uvv_settings()

    enable_shading(context, objects)
    tex = setup_image(context)

    # Only add checker nodes if "Show in 3D View" is enabled
    if settings.checker_show_in_3d_view:
        for obj in objects:
            slots = setup_slots(context, obj)
            for slot in slots:
                setup_nodes(context, obj, slot, tex)


def disable_checker_material(context, objects: List[bpy.types.Object]) -> None:
    """
    Disable UV checker material on specified objects (UV Flow style).
    """
    disable_shading(context, objects)

    for obj in objects:
        slots = [x for x in obj.material_slots if x.material]
        for slot in slots:
            remove_nodes(context, obj, slot)

        if obj.get('uvv_checker_enabled'):
            obj.pop('uvv_checker_enabled')


def refresh_checker(context) -> None:
    """
    Refresh UV checker display - enable for EDIT mode objects, disable for non-EDIT mode objects (UV Flow style).
    This is the key function that makes it Edit Mode only!

    This function is designed to be called repeatedly (from msgbus callbacks or timers).
    It dynamically adds/removes checker nodes based on each object's current mode.
    """
    # Find all objects that should have checker (in EDIT mode)
    edit_mode_objects = [obj for obj in context.view_layer.objects
                         if obj.mode == 'EDIT' and obj.type == 'MESH']

    # Find all objects that currently have checker enabled
    checked_objects = [obj for obj in context.view_layer.objects
                      if obj.get('uvv_checker_enabled')]

    # Objects that are in EDIT mode but don't have checker yet → ADD checker
    objects_to_enable = [obj for obj in edit_mode_objects if not obj.get('uvv_checker_enabled')]
    if objects_to_enable:
        enable_checker_material(context, objects_to_enable)

    # Objects that have checker but are NOT in EDIT mode anymore → REMOVE checker
    objects_to_disable = [obj for obj in checked_objects if obj.mode != 'EDIT']
    if objects_to_disable:
        disable_checker_material(context, objects_to_disable)


def has_checker_enabled(context) -> bool:
    """Check if any object has checker enabled"""
    for obj in context.view_layer.objects:
        if obj.get('uvv_checker_enabled'):
            return True
    return False
