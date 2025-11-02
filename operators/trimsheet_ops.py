"""Trimsheet operators for add, remove, duplicate, etc."""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import IntProperty, EnumProperty, StringProperty, FloatProperty, BoolProperty
from mathutils import Vector
from ..utils import trimsheet_utils


class UVV_OT_trim_add(Operator):
    """Add a new trim to the active material"""
    bl_idname = "uv.uvv_trim_add"
    bl_label = "Add Trim"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object and context.active_object.active_material is not None)

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material")
            return {'CANCELLED'}

        # Add new trim with default centered rectangle
        material.uvv_trims.add()
        new_trim = material.uvv_trims[-1]

        # Set properties
        trim_count = len([t for t in material.uvv_trims if t.name.startswith("Trim")])
        new_trim.name = f"Trim.{trim_count:03d}"
        new_trim.color = trimsheet_utils.generate_trim_color(material.uvv_trims)
        new_trim.set_rect(0.25, 0.75, 0.75, 0.25)  # Centered rectangle

        # Select new trim
        trimsheet_utils.deselect_all_trims(material)
        new_trim.selected = True
        material.uvv_trims_index = len(material.uvv_trims) - 1

        context.area.tag_redraw()
        return {'FINISHED'}


class UVV_OT_trim_remove(Operator):
    """Remove the active trim"""
    bl_idname = "uv.uvv_trim_remove"
    bl_label = "Remove Trim"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        material = trimsheet_utils.get_active_material(context)
        return material and hasattr(material, 'uvv_trims') and len(material.uvv_trims) > 0

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            return {'CANCELLED'}

        idx = material.uvv_trims_index
        if 0 <= idx < len(material.uvv_trims):
            material.uvv_trims.remove(idx)
            # Adjust index
            material.uvv_trims_index = min(idx, len(material.uvv_trims) - 1)
            context.area.tag_redraw()
            return {'FINISHED'}

        return {'CANCELLED'}


class UVV_OT_trim_duplicate(Operator):
    """Duplicate the active trim"""
    bl_idname = "uv.uvv_trim_duplicate"
    bl_label = "Duplicate Trim"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        material = trimsheet_utils.get_active_material(context)
        return material and hasattr(material, 'uvv_trims') and material.uvv_trims_index >= 0

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            return {'CANCELLED'}

        source_idx = material.uvv_trims_index
        if 0 <= source_idx < len(material.uvv_trims):
            source = material.uvv_trims[source_idx]

            # Add new trim
            material.uvv_trims.add()
            new_trim = material.uvv_trims[-1]

            # Copy properties
            new_trim.name = source.name + ".001"
            new_trim.color = source.color
            # Offset slightly so it's visible
            offset = 0.05
            new_trim.set_rect(
                source.left + offset,
                source.top + offset,
                source.right + offset,
                source.bottom + offset
            )

            # Select new trim
            trimsheet_utils.deselect_all_trims(material)
            new_trim.selected = True
            material.uvv_trims_index = len(material.uvv_trims) - 1

            context.area.tag_redraw()
            return {'FINISHED'}

        return {'CANCELLED'}


class UVV_OT_trim_select(Operator):
    """Select a trim by index"""
    bl_idname = "uv.uvv_trim_select"
    bl_label = "Select Trim"
    bl_options = {'INTERNAL'}

    index: IntProperty(default=-1)

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if material and trimsheet_utils.select_trim(material, self.index):
            context.area.tag_redraw()
            return {'FINISHED'}
        return {'CANCELLED'}


class UVV_OT_trim_move(Operator):
    """Move trim up or down in the list"""
    bl_idname = "uv.uvv_trim_move"
    bl_label = "Move Trim"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=[
            ('UP', "Up", ""),
            ('DOWN', "Down", ""),
        ]
    )

    @classmethod
    def poll(cls, context):
        material = trimsheet_utils.get_active_material(context)
        return material and hasattr(material, 'uvv_trims') and len(material.uvv_trims) > 1

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            return {'CANCELLED'}

        idx = material.uvv_trims_index
        new_idx = idx

        if self.direction == 'UP' and idx > 0:
            new_idx = idx - 1
            material.uvv_trims.move(idx, new_idx)
        elif self.direction == 'DOWN' and idx < len(material.uvv_trims) - 1:
            new_idx = idx + 1
            material.uvv_trims.move(idx, new_idx)

        material.uvv_trims_index = new_idx
        context.area.tag_redraw()
        return {'FINISHED'}


class UVV_OT_trim_fit_selection(Operator):
    """Fit selected UV islands to trim bounds"""
    bl_idname = "uv.uvv_trim_fit_selection"
    bl_label = "Fit UVs to Trim"
    bl_options = {'REGISTER', 'UNDO'}

    trim_index: IntProperty(default=-1)

    # Fit options (shown in operator panel)
    fit_mode: EnumProperty(
        name="Fit Mode",
        description="How to fit UVs into the trim",
        items=[
            ('FILL', "Fill", "Advanced fill with horizontal/vertical controls"),
            ('CONTAIN', "Contain", "Fit inside trim bounds (maintains aspect, may letterbox)"),
            ('NONE', "None", "Don't scale, only position"),
        ],
        default='CONTAIN'
    )

    fit_alignment: EnumProperty(
        name="Alignment",
        description="How to align UVs within the trim",
        items=[
            ('CENTER', "●", "Center in trim"),
            ('TOP_LEFT', "↖", "Align to top-left corner"),
            ('TOP_CENTER', "↑", "Align to top edge, centered horizontally"),
            ('TOP_RIGHT', "↗", "Align to top-right corner"),
            ('CENTER_LEFT', "←", "Align to left edge, centered vertically"),
            ('CENTER_RIGHT', "→", "Align to right edge, centered vertically"),
            ('BOTTOM_LEFT', "↙", "Align to bottom-left corner"),
            ('BOTTOM_CENTER', "↓", "Align to bottom edge, centered horizontally"),
            ('BOTTOM_RIGHT', "↘", "Align to bottom-right corner"),
        ],
        default='CENTER'
    )

    fit_padding: bpy.props.FloatProperty(
        name="Padding",
        description="Internal padding as percentage of trim size",
        default=0.0,
        min=0.0,
        max=0.5,
        subtype='PERCENTAGE'
    )

    fit_auto_rotate: bpy.props.BoolProperty(
        name="Auto Rotate",
        description="Try 0° and 90° rotation, pick best fit",
        default=False
    )

    # Advanced fill mode controls (only shown when fit_mode == 'FILL')
    fit_horizontal_mode: EnumProperty(
        name="Horizontal",
        description="How to scale horizontally in Fill mode",
        items=[
            ('FILL', "Fill", "Fill to trim width"),
            ('CONTAIN', "Contain", "Contain within trim width (maintain aspect)"),
            ('CUSTOM', "Custom", "Custom scale percentage"),
        ],
        default='FILL'
    )

    fit_vertical_mode: EnumProperty(
        name="Vertical",
        description="How to scale vertically in Fill mode",
        items=[
            ('FILL', "Fill", "Fill to trim height"),
            ('CONTAIN', "Contain", "Contain within trim height (maintain aspect)"),
            ('CUSTOM', "Custom", "Custom scale percentage"),
        ],
        default='FILL'
    )

    fit_horizontal_custom: bpy.props.FloatProperty(
        name="Horizontal Scale",
        description="Custom horizontal scale as percentage of trim width",
        default=100.0,
        subtype='PERCENTAGE'
    )

    fit_vertical_custom: bpy.props.FloatProperty(
        name="Vertical Scale",
        description="Custom vertical scale as percentage of trim height",
        default=100.0,
        subtype='PERCENTAGE'
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object and
                context.active_object.active_material is not None)

    def draw(self, context):
        """Draw operator properties in the panel"""
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # Fit Mode
        layout.prop(self, "fit_mode", text="Mode")

        # Advanced Fill mode controls (only show when mode is FILL)
        if self.fit_mode == 'FILL':
            layout.separator()
            box = layout.box()
            box.label(text="Fill Options:")

            # Horizontal mode
            box.prop(self, "fit_horizontal_mode", text="Horizontal")
            if self.fit_horizontal_mode == 'CUSTOM':
                box.prop(self, "fit_horizontal_custom", text="Width %", slider=True)

            # Vertical mode
            box.prop(self, "fit_vertical_mode", text="Vertical")
            if self.fit_vertical_mode == 'CUSTOM':
                box.prop(self, "fit_vertical_custom", text="Height %", slider=True)

        # Alignment
        layout.separator()

        # Create a sub-layout without property split for alignment grid
        align_layout = layout.column(align=True)
        align_layout.use_property_split = False
        align_layout.label(text="Alignment:")

        # 3x3 grid for alignment with Unicode arrows
        row = align_layout.row(align=True)
        row.prop_enum(self, "fit_alignment", 'TOP_LEFT')
        row.prop_enum(self, "fit_alignment", 'TOP_CENTER')
        row.prop_enum(self, "fit_alignment", 'TOP_RIGHT')

        row = align_layout.row(align=True)
        row.prop_enum(self, "fit_alignment", 'CENTER_LEFT')
        row.prop_enum(self, "fit_alignment", 'CENTER')
        row.prop_enum(self, "fit_alignment", 'CENTER_RIGHT')

        row = align_layout.row(align=True)
        row.prop_enum(self, "fit_alignment", 'BOTTOM_LEFT')
        row.prop_enum(self, "fit_alignment", 'BOTTOM_CENTER')
        row.prop_enum(self, "fit_alignment", 'BOTTOM_RIGHT')

        # Padding and Auto Rotate
        layout.separator()
        layout.prop(self, "fit_padding", slider=True)
        layout.prop(self, "fit_auto_rotate")

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material or not hasattr(material, 'uvv_trims'):
            self.report({'WARNING'}, "No active material with trims")
            return {'CANCELLED'}

        if self.trim_index < 0 or self.trim_index >= len(material.uvv_trims):
            self.report({'WARNING'}, "Invalid trim index")
            return {'CANCELLED'}

        trim = material.uvv_trims[self.trim_index]

        # Get active object
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No active mesh object")
            return {'CANCELLED'}

        # Get mesh data
        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)

        uv_layer = bm.loops.layers.uv.active
        if not uv_layer:
            self.report({'WARNING'}, "No active UV layer")
            return {'CANCELLED'}

        # Handle UV sync mode properly
        use_uv_select_sync = context.tool_settings.use_uv_select_sync
        
        if use_uv_select_sync:
            # In UV sync mode, temporarily disable sync and use UVIslandManager with mesh_link_uv=True
            context.tool_settings.use_uv_select_sync = False
            
            try:
                from ..utils.uv_classes import UVIslandManager
                island_manager = UVIslandManager([obj], mesh_link_uv=True)
                
                if not island_manager.islands:
                    self.report({'WARNING'}, "No UV islands found")
                    return {'CANCELLED'}
                
                # Get all UVs from all islands
                selected_uvs = []
                for island in island_manager.islands:
                    for face in island.faces:
                        for loop in face.loops:
                            selected_uvs.append(loop[uv_layer])
                
            finally:
                # Restore UV sync state
                context.tool_settings.use_uv_select_sync = True
        else:
            # In non-sync mode, use direct UV selection
            selected_uvs = []
            for face in bm.faces:
                for loop in face.loops:
                    if loop[uv_layer].select:
                        selected_uvs.append(loop[uv_layer])

        if len(selected_uvs) == 0:
            self.report({'WARNING'}, "No UVs selected")
            return {'CANCELLED'}

        # Calculate current bounds of selected UVs
        min_u = min(uv.uv.x for uv in selected_uvs)
        max_u = max(uv.uv.x for uv in selected_uvs)
        min_v = min(uv.uv.y for uv in selected_uvs)
        max_v = max(uv.uv.y for uv in selected_uvs)

        current_width = max_u - min_u
        current_height = max_v - min_v

        if current_width < 0.0001 or current_height < 0.0001:
            self.report({'WARNING'}, "Selected UVs have no area")
            return {'CANCELLED'}

        # Calculate trim bounds
        trim_width = trim.right - trim.left
        trim_height = trim.top - trim.bottom

        # Calculate centers
        current_center_x = (min_u + max_u) / 2.0
        current_center_y = (min_v + max_v) / 2.0
        trim_center_x = (trim.left + trim.right) / 2.0
        trim_center_y = (trim.bottom + trim.top) / 2.0

        # Apply padding to trim bounds
        padding_x = trim_width * self.fit_padding
        padding_y = trim_height * self.fit_padding
        effective_trim_width = trim_width - (2 * padding_x)
        effective_trim_height = trim_height - (2 * padding_y)
        effective_trim_left = trim.left + padding_x
        effective_trim_right = trim.right - padding_x
        effective_trim_bottom = trim.bottom + padding_y
        effective_trim_top = trim.top - padding_y

        # Auto-rotate if enabled
        rotation_angle = 0.0
        if self.fit_auto_rotate:
            # Check if rotating 90 degrees gives better fit
            aspect_uv = current_width / current_height
            aspect_trim = effective_trim_width / effective_trim_height
            aspect_uv_rotated = current_height / current_width

            # If rotated aspect ratio is closer to trim aspect ratio, rotate
            if abs(aspect_uv_rotated - aspect_trim) < abs(aspect_uv - aspect_trim):
                rotation_angle = 1.5708  # 90 degrees in radians
                current_width, current_height = current_height, current_width

        # Calculate scale factors based on fit mode
        scale_x = 1.0
        scale_y = 1.0

        if self.fit_mode == 'FILL':
            # Advanced fill mode with separate horizontal and vertical controls

            # Calculate horizontal scale
            if self.fit_horizontal_mode == 'FILL':
                scale_x = effective_trim_width / current_width
            elif self.fit_horizontal_mode == 'CONTAIN':
                # Maintain aspect ratio based on height
                scale = min(effective_trim_width / current_width, effective_trim_height / current_height)
                scale_x = scale
            elif self.fit_horizontal_mode == 'CUSTOM':
                # Convert percentage (0-200) to scale factor (0-2)
                scale_x = (effective_trim_width * (self.fit_horizontal_custom / 100.0)) / current_width

            # Calculate vertical scale
            if self.fit_vertical_mode == 'FILL':
                scale_y = effective_trim_height / current_height
            elif self.fit_vertical_mode == 'CONTAIN':
                # Maintain aspect ratio based on width
                scale = min(effective_trim_width / current_width, effective_trim_height / current_height)
                scale_y = scale
            elif self.fit_vertical_mode == 'CUSTOM':
                # Convert percentage (0-200) to scale factor (0-2)
                scale_y = (effective_trim_height * (self.fit_vertical_custom / 100.0)) / current_height

        elif self.fit_mode == 'CONTAIN':
            # Scale to fit inside trim bounds (maintain aspect ratio)
            scale = min(effective_trim_width / current_width, effective_trim_height / current_height)
            scale_x = scale
            scale_y = scale

        elif self.fit_mode == 'NONE':
            # No scaling, only positioning
            scale_x = 1.0
            scale_y = 1.0

        # Calculate scaled dimensions
        scaled_width = current_width * scale_x
        scaled_height = current_height * scale_y

        # Calculate alignment offset based on fit_alignment
        align_offset_x = 0.0
        align_offset_y = 0.0

        # Horizontal alignment
        if self.fit_alignment in ['TOP_LEFT', 'CENTER_LEFT', 'BOTTOM_LEFT']:
            # Align to left edge
            align_offset_x = effective_trim_left + (scaled_width / 2) - trim_center_x
        elif self.fit_alignment in ['TOP_RIGHT', 'CENTER_RIGHT', 'BOTTOM_RIGHT']:
            # Align to right edge
            align_offset_x = effective_trim_right - (scaled_width / 2) - trim_center_x
        # else: CENTER (default, no offset needed)

        # Vertical alignment
        if self.fit_alignment in ['TOP_LEFT', 'TOP_CENTER', 'TOP_RIGHT']:
            # Align to top edge
            align_offset_y = effective_trim_top - (scaled_height / 2) - trim_center_y
        elif self.fit_alignment in ['BOTTOM_LEFT', 'BOTTOM_CENTER', 'BOTTOM_RIGHT']:
            # Align to bottom edge
            align_offset_y = effective_trim_bottom + (scaled_height / 2) - trim_center_y
        # else: CENTER (default, no offset needed)

        # Transform all selected UVs
        import math
        for uv in selected_uvs:
            # Translate to origin (current center)
            x = uv.uv.x - current_center_x
            y = uv.uv.y - current_center_y

            # Rotate if needed
            if rotation_angle != 0.0:
                cos_a = math.cos(rotation_angle)
                sin_a = math.sin(rotation_angle)
                new_x = x * cos_a - y * sin_a
                new_y = x * sin_a + y * cos_a
                x = new_x
                y = new_y

            # Scale
            x *= scale_x
            y *= scale_y

            # Move to trim center + alignment offset
            uv.uv.x = trim_center_x + x + align_offset_x
            uv.uv.y = trim_center_y + y + align_offset_y

        # Update mesh
        bmesh.update_edit_mesh(mesh)

        # Tagging system removed

        self.report({'INFO'}, f"Fitted UVs to trim '{trim.name}'")
        return {'FINISHED'}


class UVV_OT_trim_set_tag(Operator):
    """Set tag for the active trim"""
    bl_idname = "uv.uvv_trim_set_tag"
    bl_label = "Set Tag"
    bl_options = {'REGISTER', 'UNDO'}

    tag: StringProperty(
        name="Tag",
        description="Tag to apply",
        default=""
    )

    trim_index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material is not None

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index < 0 or self.trim_index >= len(material.uvv_trims):
            return {'CANCELLED'}

        trim = material.uvv_trims[self.trim_index]
        trim.tag = self.tag

        return {'FINISHED'}


class UVV_OT_trim_set_alignment(Operator):
    """Set trim fit alignment"""
    bl_idname = "uv.uvv_trim_set_alignment"
    bl_label = "Set Alignment"
    bl_options = {'REGISTER', 'UNDO'}

    alignment: EnumProperty(
        items=[
            ('CENTER', "Center", ""),
            ('TOP_LEFT', "Top Left", ""),
            ('TOP_CENTER', "Top Center", ""),
            ('TOP_RIGHT', "Top Right", ""),
            ('CENTER_LEFT', "Center Left", ""),
            ('CENTER_RIGHT', "Center Right", ""),
            ('BOTTOM_LEFT', "Bottom Left", ""),
            ('BOTTOM_CENTER', "Bottom Center", ""),
            ('BOTTOM_RIGHT', "Bottom Right", ""),
        ]
    )

    trim_index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material is not None

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material or self.trim_index < 0 or self.trim_index >= len(material.uvv_trims):
            return {'CANCELLED'}

        trim = material.uvv_trims[self.trim_index]
        trim.fit_alignment = self.alignment

        return {'FINISHED'}


class UVV_OT_trim_clear_all(Operator):
    """Clear all trims from the active material"""
    bl_idname = "uv.uvv_trim_clear_all"
    bl_label = "Clear All Trims"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object and context.active_object.active_material is not None)

    def invoke(self, context, event):
        """Show confirmation dialog"""
        material = trimsheet_utils.get_active_material(context)
        if not material or len(material.uvv_trims) == 0:
            self.report({'WARNING'}, "No trims to clear")
            return {'CANCELLED'}

        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material")
            return {'CANCELLED'}

        trim_count = len(material.uvv_trims)
        if trim_count == 0:
            self.report({'WARNING'}, "No trims to clear")
            return {'CANCELLED'}

        # Clear all trims
        material.uvv_trims.clear()
        material.uvv_trims_index = -1

        self.report({'INFO'}, f"Cleared {trim_count} trim(s)")
        context.area.tag_redraw()
        return {'FINISHED'}


class UVV_OT_trim_export_svg(Operator):
    """Export trims as SVG file"""
    bl_idname = "uv.uvv_trim_export_svg"
    bl_label = "Export Trims (SVG)"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="trimsheet.svg")
    filter_glob: bpy.props.StringProperty(default="*.svg", options={'HIDDEN'})
    filename_ext: bpy.props.StringProperty(default=".svg", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        material = context.active_object.active_material if context.active_object else None
        return material and len(material.uvv_trims) > 0

    def invoke(self, context, event):
        # Set default filename if not set
        if not self.filepath or self.filepath == "":
            self.filepath = "trimsheet.svg"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material")
            return {'CANCELLED'}

        if len(material.uvv_trims) == 0:
            self.report({'WARNING'}, "No trims to export")
            return {'CANCELLED'}

        # Ensure .svg extension
        filepath = self.filepath
        if not filepath.lower().endswith('.svg'):
            filepath += '.svg'

        # Create SVG content
        svg_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        svg_content += '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1 1">\n'

        for trim in material.uvv_trims:
            if trim.enabled:
                # Convert UV coordinates to SVG coordinates (flip Y axis)
                x = trim.left
                y = 1.0 - trim.top  # Flip Y
                width = trim.right - trim.left
                height = trim.top - trim.bottom

                # Convert color to hex
                r = int(trim.color[0] * 255)
                g = int(trim.color[1] * 255)
                b = int(trim.color[2] * 255)
                color = f"#{r:02x}{g:02x}{b:02x}"

                svg_content += f'  <rect id="{trim.name}" x="{x}" y="{y}" width="{width}" height="{height}" fill="{color}" fill-opacity="0.5" stroke="{color}" stroke-width="0.002"/>\n'

        svg_content += '</svg>\n'

        # Write to file
        try:
            with open(filepath, 'w') as f:
                f.write(svg_content)
            self.report({'INFO'}, f"Exported {len(material.uvv_trims)} trim(s) to {filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_trim_import_svg(Operator):
    """Import trims from SVG file"""
    bl_idname = "uv.uvv_trim_import_svg"
    bl_label = "Import Trims (SVG)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.svg", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.active_material is not None

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material")
            return {'CANCELLED'}

        # Read SVG file
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(self.filepath)
            root = tree.getroot()

            # Parse SVG namespace
            ns = {'svg': 'http://www.w3.org/2000/svg'}

            imported_count = 0
            for rect in root.findall('.//svg:rect', ns):
                # Get attributes
                x = float(rect.get('x', 0))
                y = float(rect.get('y', 0))
                width = float(rect.get('width', 0.1))
                height = float(rect.get('height', 0.1))
                name = rect.get('id', f'Trim.{len(material.uvv_trims):03d}')

                # Parse color
                fill = rect.get('fill', '#ffffff')
                if fill.startswith('#'):
                    r = int(fill[1:3], 16) / 255.0
                    g = int(fill[3:5], 16) / 255.0
                    b = int(fill[5:7], 16) / 255.0
                    color = (r, g, b)  # Only 3 components for Blender color
                else:
                    color = (1.0, 1.0, 1.0)  # Only 3 components

                # Create trim (flip Y axis back)
                new_trim = material.uvv_trims.add()
                new_trim.name = name
                new_trim.left = x
                new_trim.right = x + width
                new_trim.bottom = 1.0 - y - height  # Flip Y back
                new_trim.top = 1.0 - y  # Flip Y back
                new_trim.color = color

                imported_count += 1

            self.report({'INFO'}, f"Imported {imported_count} trim(s) from {self.filepath}")
            context.area.tag_redraw()

        except Exception as e:
            self.report({'ERROR'}, f"Failed to import: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_trim_create_circle(Operator):
    """Create a circular trim (placeholder for future implementation)"""
    bl_idname = "uv.uvv_trim_create_circle"
    bl_label = "Create Circular Trim"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object and context.active_object.active_material is not None)

    def execute(self, context):
        self.report({'INFO'}, "Circular trim creation coming soon!")
        return {'FINISHED'}


class UVV_OT_trim_edit_from_list(Operator):
    """Select trim and enter edit mode on double-click from UI list"""
    bl_idname = "uv.uvv_trim_edit_from_list"
    bl_label = "Edit Trim from List"
    bl_options = {'REGISTER', 'UNDO'}

    trim_index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def invoke(self, context, event):
        """Handle double-click detection - only execute on double-click"""
        import time
        
        # Use class-level storage for click tracking (similar to stack groups)
        if not hasattr(self.__class__, '_last_click_info'):
            self.__class__._last_click_info = {}
        
        current_time = time.time()
        is_double_click = False
        
        # Check if this is a double-click (same trim index, within 0.3 seconds)
        if self.trim_index in self.__class__._last_click_info:
            last_time, last_trim_index = self.__class__._last_click_info[self.trim_index]
            time_diff = current_time - last_time
            # Only treat as double-click if it's the same trim and within threshold
            if last_trim_index == self.trim_index and time_diff < 0.3:  # 300ms double-click threshold
                is_double_click = True
        
        # Update last click info
        self.__class__._last_click_info[self.trim_index] = (current_time, self.trim_index)
        
        # Only execute on double-click
        if is_double_click:
            # Reset click tracking to prevent triple-click from being detected as double-click
            if self.trim_index in self.__class__._last_click_info:
                del self.__class__._last_click_info[self.trim_index]
            return self.execute(context)
        
        # Single click - just select the trim (don't enter edit mode)
        material = trimsheet_utils.get_active_material(context)
        if material and 0 <= self.trim_index < len(material.uvv_trims):
            material.uvv_trims_index = self.trim_index
            settings = context.scene.uvv_settings
            settings.trim_edit_mode = False
            context.area.tag_redraw()
        return {'CANCELLED'}

    def execute(self, context):
        """Execute on double-click: select trim and enter edit mode"""
        material = trimsheet_utils.get_active_material(context)
        if not material:
            return {'CANCELLED'}
        
        if not (0 <= self.trim_index < len(material.uvv_trims)):
            return {'CANCELLED'}
        
        # Select the trim
        material.uvv_trims_index = self.trim_index
        
        # Enter edit mode
        settings = context.scene.uvv_settings
        settings.trim_edit_mode = True
        
        # Start the tool modal operator (safely)
        try:
            from . import trimsheet_tool_modal
            if not trimsheet_tool_modal.UVV_OT_trimsheet_tool_modal._is_running:
                # Use a timer to start the modal in a safe context
                def start_modal_safely():
                    # Check reload flag first to prevent crashes during/after reload
                    # Check ALL modules (both old and new after reload) - if ANY has reloading=True, abort
                    try:
                        import sys
                        for mod in sys.modules.values():
                            if mod and hasattr(mod, 'UVV_OT_trimsheet_tool_modal') and hasattr(mod, '_uvv_trimsheet_reloading'):
                                if getattr(mod, '_uvv_trimsheet_reloading', False):
                                    return None  # Found reloading flag, abort immediately
                    except:
                        # If check fails, assume reloading (safe default)
                        return None
                    
                    # Additional safety: verify operator is still registered
                    try:
                        if not hasattr(bpy.ops.uv, 'uvv_trimsheet_tool_modal'):
                            return None
                    except:
                        return None
                    
                    # Validate context and window_manager before attempting to invoke
                    try:
                        if not bpy.context:
                            return None
                        if not hasattr(bpy.context, 'window_manager') or not bpy.context.window_manager:
                            return None
                        # Validate window_manager is valid by accessing a property
                        _ = bpy.context.window_manager.windows
                    except:
                        return None  # Context invalid, abort
                    
                    try:
                        from . import trimsheet_tool_modal as ttm
                        if not ttm.UVV_OT_trimsheet_tool_modal._is_running and bpy.context and bpy.context.area:
                            # Final reload check before invoking
                            try:
                                import sys
                                for mod in sys.modules.values():
                                    if mod and hasattr(mod, 'UVV_OT_trimsheet_tool_modal') and hasattr(mod, '_uvv_trimsheet_reloading'):
                                        if getattr(mod, '_uvv_trimsheet_reloading', False):
                                            return None  # Found reloading flag, abort
                            except:
                                return None
                            bpy.ops.uv.uvv_trimsheet_tool_modal('INVOKE_DEFAULT')
                    except:
                        pass
                    return None  # One-shot timer
                
                bpy.app.timers.register(start_modal_safely, first_interval=0.1)
        except:
            pass
        
        context.area.tag_redraw()
        return {'FINISHED'}


class UVV_OT_trim_edit_toggle(Operator):
    """Toggle trim edit mode to enable gizmo controls"""
    bl_idname = "uv.uvv_trim_edit_toggle"
    bl_label = "Toggle Trim Edit"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        settings = context.scene.uvv_settings
        settings.trim_edit_mode = not settings.trim_edit_mode

        if settings.trim_edit_mode:
            self.report({'INFO'}, "Trim edit mode enabled")

            # Start the tool modal operator
            try:
                from . import trimsheet_tool_modal
                if not trimsheet_tool_modal.UVV_OT_trimsheet_tool_modal._is_running:
                    # Use a timer to start the modal in a safe context
                    def start_modal_safely():
                        # Check reload flag first to prevent crashes during/after reload
                        # Import fresh each time to get current module state
                        try:
                            import sys
                            current_module = sys.modules.get('operators.trimsheet_tool_modal')
                            if current_module and getattr(current_module, '_addon_reloading', False):
                                return None
                        except:
                            return None  # If check fails, abort (safe default)
                        
                        # Additional safety: verify operator is still registered
                        try:
                            if not hasattr(bpy.ops.uv, 'uvv_trimsheet_tool_modal'):
                                return None
                        except:
                            return None
                        
                        # Validate context and window_manager before attempting to invoke
                        try:
                            if not bpy.context:
                                return None
                            if not hasattr(bpy.context, 'window_manager') or not bpy.context.window_manager:
                                return None
                            # Validate window_manager is valid by accessing a property
                            _ = bpy.context.window_manager.windows
                        except:
                            return None  # Context invalid, abort
                        
                        try:
                            from . import trimsheet_tool_modal as ttm
                            if not ttm.UVV_OT_trimsheet_tool_modal._is_running and bpy.context and bpy.context.area:
                                # Final reload check before invoking
                                current_module = sys.modules.get('operators.trimsheet_tool_modal')
                                if current_module and getattr(current_module, '_addon_reloading', False):
                                    return None
                                bpy.ops.uv.uvv_trimsheet_tool_modal('INVOKE_DEFAULT')
                        except:
                            pass
                        return None  # One-shot timer
                    
                    bpy.app.timers.register(start_modal_safely, first_interval=0.1)
            except:
                pass
        else:
            self.report({'INFO'}, "Trim edit mode disabled")

        context.area.tag_redraw()
        return {'FINISHED'}


class UVV_OT_trim_smart_pack(Operator):
    """Hotspot mapping - automatically assign UV islands to best-matching trim rectangles"""
    bl_idname = "uv.uvv_trim_smart_pack"
    bl_label = "Auto Fit"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Automatically assign UV islands to trim rectangles based on aspect ratio and area matching"
    
    # Priority settings
    priority: EnumProperty(
        name="Priority",
        description="Primary matching criterion",
        items=[
            ('ASPECT', "Aspect Ratio", "Match by aspect ratio first, then area"),
            ('AREA', "Area", "Match by area first, then aspect ratio"),
            ('WORLD_SIZE', "World Size", "Match by real-world dimensions (requires trim world size)"),
        ],
        default='ASPECT'
    )
    
    # Preprocessing settings
    orient: EnumProperty(
        name="Preprocessing",
        description="Island orientation before hotspotting",
        items=[
            ('AS_IS', "As Is", "No preprocessing"),
            ('WORLD', "World Orient", "Orient islands to world coordinates"),
            ('ORIENT', "Orient to Axis", "Auto-orient to nearest UV axis"),
        ],
        default='AS_IS'
    )
    
    # Area matching settings
    area_match: EnumProperty(
        name="Area Matching",
        description="How to match island area to trim area",
        items=[
            ('AS_IS', "As Is", "Natural 1:1 area matching"),
            ('MAX', "Maximize", "Push to larger trims (higher texel density)"),
            ('MIN', "Minimize", "Push to smaller trims (lower texel density)"),
            ('MANUAL', "Manual", "Use custom scale factor"),
        ],
        default='AS_IS'
    )
    
    manual_scale: FloatProperty(
        name="Scale Factor",
        description="Custom scale factor for area matching (1.0 = natural size)",
        default=1.0,
        min=0.01,
        max=100.0
    )
    
    # Transform settings
    allow_rotation: BoolProperty(
        name="Allow Rotation",
        description="Allow 90° rotation to improve aspect matching",
        default=True
    )
    
    # Fit Mode (CSS object-fit inspired)
    fit_mode: EnumProperty(
        name="Fit Mode",
        description="How to fit UVs into the trim",
        items=[
            ('FILL', "Fill", "Advanced fill with horizontal/vertical controls"),
            ('CONTAIN', "Contain", "Fit inside trim bounds (maintains aspect, may letterbox)"),
            ('COVER', "Cover", "Fill trim bounds completely (maintains aspect, may crop)"),
            ('FIT_WIDTH', "Fit Width", "Match trim width, allow vertical overflow/underflow"),
            ('FIT_HEIGHT', "Fit Height", "Match trim height, allow horizontal overflow/underflow"),
            ('NONE', "None", "Don't scale, only position"),
            ('FROM_TRIM', "From Trim", "Use individual trim settings"),
        ],
        default='CONTAIN'
    )
    
    # Advanced fill mode controls (only shown when fit_mode == 'FILL')
    fit_horizontal_mode: EnumProperty(
        name="Horizontal",
        description="How to scale horizontally in Fill mode",
        items=[
            ('FILL', "Fill", "Fill to trim width"),
            ('CONTAIN', "Contain", "Contain within trim width (maintain aspect)"),
            ('CUSTOM', "Custom", "Custom scale percentage"),
        ],
        default='FILL'
    )

    fit_vertical_mode: EnumProperty(
        name="Vertical",
        description="How to scale vertically in Fill mode",
        items=[
            ('FILL', "Fill", "Fill to trim height"),
            ('CONTAIN', "Contain", "Contain within trim height (maintain aspect)"),
            ('CUSTOM', "Custom", "Custom scale percentage"),
        ],
        default='FILL'
    )

    fit_horizontal_custom: FloatProperty(
        name="Horizontal Scale",
        description="Custom horizontal scale as percentage of trim width",
        default=100.0,
        subtype='PERCENTAGE'
    )

    fit_vertical_custom: FloatProperty(
        name="Vertical Scale",
        description="Custom vertical scale as percentage of trim height",
        default=100.0,
        subtype='PERCENTAGE'
    )
    
    inset_mode: EnumProperty(
        name="Inset Mode",
        description="How to determine padding/inset",
        items=[
            ('MANUAL', "Manual", "Use manual padding value"),
            ('FROM_TRIM', "From Trim", "Use individual trim settings"),
            ('COMBINED', "Combined", "Manual if trim inset is 0, otherwise use trim"),
        ],
        default='MANUAL'
    )
    
    padding: FloatProperty(
        name="Padding",
        description="Internal padding as percentage of trim size",
        default=0.0,
        min=0.0,
        max=0.5,
        subtype='PERCENTAGE'
    )
    
    alignment: EnumProperty(
        name="Alignment",
        description="How to align islands within trims",
        items=[
            ('CENTER', "●", "Center in trim"),
            ('TOP_LEFT', "↖", "Align to top-left corner"),
            ('TOP_CENTER', "↑", "Align to top edge, centered horizontally"),
            ('TOP_RIGHT', "↗", "Align to top-right corner"),
            ('CENTER_LEFT', "←", "Align to left edge, centered vertically"),
            ('CENTER_RIGHT', "→", "Align to right edge, centered vertically"),
            ('BOTTOM_LEFT', "↙", "Align to bottom-left corner"),
            ('BOTTOM_CENTER', "↓", "Align to bottom edge, centered horizontally"),
            ('BOTTOM_RIGHT', "↘", "Align to bottom-right corner"),
        ],
        default='CENTER'
    )
    
    # Variability settings
    allow_variability: BoolProperty(
        name="Allow Variability",
        description="Enable random variations for natural distribution",
        default=False
    )
    
    allow_rotation_variation: BoolProperty(
        name="Rotation Variation",
        description="Randomly add 180° rotation",
        default=False
    )
    
    allow_location_variation: BoolProperty(
        name="Location Variation",
        description="Randomly choose from equally suitable trims",
        default=False
    )
    
    allow_offset_variation: BoolProperty(
        name="Offset Variation",
        description="Randomly shift islands along trim axis",
        default=False
    )
    
    allow_flip_variation: BoolProperty(
        name="Flip Variation",
        description="Randomly mirror islands",
        default=False
    )
    
    loc_var_offset: FloatProperty(
        name="Variation Offset",
        description="Amount of random offset variation",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype='PERCENTAGE'
    )
    
    seed: IntProperty(
        name="Random Seed",
        description="Seed for reproducible random variations",
        default=132,
        min=0
    )
    
    # Advanced settings
    aspect_tolerance: FloatProperty(
        name="Aspect Tolerance",
        description="How strict aspect ratio matching should be",
        default=0.5,
        min=0.01,
        max=2.0,
        step=0.01
    )
    
    trims_mode: EnumProperty(
        name="Trim Selection",
        description="Which trims to use for matching",
        items=[
            ('ALL', "All Trims", "Use all available trims"),
            ('SELECTED', "Selected Trims", "Use only selected trims"),
        ],
        default='ALL'
    )
    
    detect_radial: BoolProperty(
        name="Detect Radial",
        description="Special handling for circular/square islands",
        default=False
    )
    
    select_radials: BoolProperty(
        name="Select Radials",
        description="Select radial islands after processing",
        default=False
    )
    
    # Aspect precision/corrector
    aspect_precision: FloatProperty(
        name="Aspect Precision",
        description="Fine-tune aspect ratio matching. Positive = wider trims, Negative = higher trims",
        default=0.0,
        min=-1.0,
        max=1.0,
        step=0.01,
        subtype='FACTOR'
    )
    
    # Tag-based filtering
    trim_category: StringProperty(
        name="Trim Category",
        description="Filter trims by category/tag (e.g., 'wood', 'metal'). Leave empty to use all trims",
        default="",
        maxlen=64
    )
    
    trim_tag: StringProperty(
        name="Trim Tag",
        description="Filter trims by specific tag. Leave empty to use all trims",
        default="",
        maxlen=64
    )

    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.active_material is not None and
                context.mode == 'EDIT_MESH')

    def execute(self, context):
        """Execute hotspot mapping"""
        # Get material and trims
        material = trimsheet_utils.get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material")
            return {'CANCELLED'}
        
        # Get trims based on mode
        if self.trims_mode == 'SELECTED':
            trims = [t for t in material.uvv_trims if t.selected]
            if not trims:
                self.report({'WARNING'}, "No selected trims")
                return {'CANCELLED'}
        else:
            trims = list(material.uvv_trims)
            if not trims:
                self.report({'WARNING'}, "No trims available")
                return {'CANCELLED'}
        
        # Import hotspot system
        from ..utils.hotspot_system import HspStorage
        
        # Initialize storage
        hsp_storage = HspStorage()
        hsp_storage.collect_trims(trims, self.detect_radial, self.trim_category, self.trim_tag)
        print(f"Collected {len(hsp_storage.trims)} regular trims and {len(hsp_storage.radial_trims)} radial trims")
        
        # Calculate area scalar
        scalar = self._get_area_scalar()
        
        # Initialize random seed for variability
        if self.allow_variability:
            import random
            random.seed(self.seed)
        
        # Process each object
        total_islands_processed = 0
        total_islands_fitted = 0
        objects_processed = 0
        radial_islands_processed = []
        
        for obj in context.objects_in_mode_unique_data:
            if obj.type != 'MESH':
                continue
                
            # Get bmesh and UV layer
            try:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                if not uv_layer:
                    # Try to get the first UV layer if active is None
                    if bm.loops.layers.uv:
                        uv_layer = bm.loops.layers.uv[0]
                        print(f"Using first UV layer for object {obj.name}")
                    else:
                        print(f"No UV layer found for object {obj.name}")
                        continue
                
                # Collect islands
                hsp_storage.collect_islands(context, bm, uv_layer, self.detect_radial)
                
                if not hsp_storage.islands_count:
                    print(f"No islands found for object {obj.name}")
                    continue
                
                objects_processed += 1
                
                # Apply preprocessing orientations
                if self.orient == 'WORLD':
                    self._world_orient_islands(context, obj, bm, hsp_storage.islands)
                    hsp_storage.update_islands(uv_layer)
                elif self.orient == 'ORIENT':
                    self._orient_to_near_axis(context, hsp_storage.islands, uv_layer)
                    hsp_storage.update_islands(uv_layer)
                
                # Process regular islands
                islands_to_process = list(hsp_storage.islands)
                print(f"Processing {len(islands_to_process)} regular islands")
                for island in islands_to_process:
                    total_islands_processed += 1
                    
                    # Skip islands with invalid bbox
                    if not island.bbox or island.bbox.area <= 0:
                        print(f"Skipping island with invalid bbox")
                        continue
                    
                    # Find best matching trim
                    suited_trims = self._find_best_trim(hsp_storage, island, scalar, context)
                    aspect_str = f"{island.aspect:.3f}" if island.aspect is not None else "None"
                    print(f"Found {len(suited_trims)} suitable trims for island with aspect {aspect_str}")
                    
                    if not suited_trims:
                        print(f"No suitable trim found for island")
                        continue
                    
                    # Choose trim (with variability)
                    if self.allow_location_variation and len(suited_trims) > 1:
                        import random
                        best_trim = random.choice(suited_trims)
                    else:
                        best_trim = suited_trims[0]
                    
                    # Calculate rotation angle with variations
                    rotation_angle = hsp_storage.calculate_rotation_angle(island, best_trim, self.allow_rotation)
                    
                    if self.allow_rotation_variation:
                        import random
                        rotation_angle += random.choice([0.0, pi])
                    
                    # Get trim-specific settings
                    padding = self._get_padding(best_trim)
                    
                    # Transform island to trim
                    if self._transform_island_to_trim(island, best_trim, rotation_angle, uv_layer, self.fit_mode, padding):
                        total_islands_fitted += 1
                        
                        # Apply flip variation if enabled
                        if self.allow_flip_variation:
                            self._apply_flip_variation(island, uv_layer)
                
                # Process radial islands separately
                if self.detect_radial and hsp_storage.radial_islands:
                    container = hsp_storage.radial_trims if hsp_storage.radial_trims else hsp_storage.trims
                    
                    for island in hsp_storage.radial_islands:
                        total_islands_processed += 1
                        radial_islands_processed.append((obj.name, island))
                        
                        # Use area-based matching for radial islands
                        suited_trims = hsp_storage.get_area_suited_trims(list(container), island, scalar, self.allow_rotation)
                        
                        if suited_trims:
                            if self.allow_location_variation and len(suited_trims) > 1:
                                import random
                                best_trim = random.choice(suited_trims)
                            else:
                                best_trim = suited_trims[0]
                            
                            # Calculate rotation with random variation for radials
                            rotation_angle = hsp_storage.calculate_rotation_angle(island, best_trim, self.allow_rotation)
                            if self.allow_rotation_variation:
                                import random
                                rotation_angle += random.choice(range(0, 360, 5)) * pi / 180  # Random 5-degree increments
                            
                            padding = self._get_padding(best_trim)
                            
                            if self._transform_island_to_trim(island, best_trim, rotation_angle, uv_layer, self.fit_mode, padding):
                                total_islands_fitted += 1
                                
                                if self.allow_flip_variation:
                                    self._apply_flip_variation(island, uv_layer)
                
                # Update mesh
                bmesh.update_edit_mesh(obj.data)
                
            except Exception as e:
                print(f"Error processing object {obj.name}: {e}")
                continue
        
        # Select radial islands if requested
        if self.select_radials and radial_islands_processed:
            self._select_radial_islands(context, radial_islands_processed)
        
        # Report results
        if objects_processed == 0:
            self.report({'WARNING'}, "No valid objects found to process")
        elif total_islands_processed == 0:
            self.report({'WARNING'}, "No islands found to process")
        else:
            success_rate = (total_islands_fitted / total_islands_processed) * 100
            self.report({'INFO'}, f"Auto Fit: {total_islands_fitted}/{total_islands_processed} islands fitted ({success_rate:.1f}% success rate)")
        
        return {'FINISHED'}
    
    def _get_area_scalar(self) -> float:
        """Get area scaling factor based on area_match setting"""
        if self.area_match == 'AS_IS':
            return 1.0
        elif self.area_match == 'MAX':
            return 50.0
        elif self.area_match == 'MIN':
            return 0.1
        else:  # MANUAL
            return self.manual_scale
    def _get_padding(self, trim):
        """Get padding setting for trim"""
        if self.inset_mode == 'MANUAL':
            return self.padding
        elif self.inset_mode == 'FROM_TRIM':
            # Check if trim has individual setting
            if hasattr(trim.trim, 'padding'):
                return trim.trim.padding
            elif hasattr(trim.trim, 'inset'):
                return trim.trim.inset
            return 0.0  # Default
        else:  # COMBINED
            # Use trim setting if available and non-zero, otherwise use manual
            if hasattr(trim.trim, 'padding') and trim.trim.padding > 0:
                return trim.trim.padding
            elif hasattr(trim.trim, 'inset') and trim.trim.inset > 0:
                return trim.trim.inset
            return self.padding
    
    def _world_orient_islands(self, context, obj, bm, islands):
        """Orient islands to world coordinates"""
        # This would require implementing world orientation logic
        # For now, just a placeholder
        print("World orientation not yet implemented")
    
    def _orient_to_near_axis(self, context, islands, uv_layer):
        """Orient islands to nearest UV axis"""
        # This would require implementing axis orientation logic
        # For now, just a placeholder
        print("Axis orientation not yet implemented")
    
    def _apply_flip_variation(self, island, uv_layer):
        """Apply random flip variation to island"""
        import random
        from mathutils import Vector
        
        # Get island center
        uv_points = [Vector(loop[uv_layer].uv) for loop in island.loops]
        center = sum(uv_points, Vector()) / len(uv_points)
        
        # Random flip scale
        flip_scale = random.choice([
            Vector((-1, 1)),   # Flip X
            Vector((1, -1)),   # Flip Y
            Vector((-1, -1)), # Flip both
            Vector((1, 1))    # No flip
        ])
        
        # Apply flip
        for loop in island.loops:
            uv = loop[uv_layer].uv
            # Translate to origin, scale, translate back
            uv.x = center.x + (uv.x - center.x) * flip_scale.x
            uv.y = center.y + (uv.y - center.y) * flip_scale.y
    
    def _select_radial_islands(self, context, radial_islands_processed):
        """Select radial islands after processing"""
        # Deselect all first
        bpy.ops.mesh.select_all(action='DESELECT')
        
        # Select radial islands
        for obj_name, island in radial_islands_processed:
            try:
                obj = context.scene.objects[obj_name]
                bm = bmesh.from_edit_mesh(obj.data)
                
                for face in island.faces:
                    face.select = True
                
                bmesh.update_edit_mesh(obj.data)
            except Exception as e:
                print(f"Error selecting radial islands for {obj_name}: {e}")
    
    def _find_best_trim(self, hsp_storage, island, scalar, context):
        """Find best matching trim based on priority"""
        if self.priority == 'ASPECT':
            return hsp_storage.get_trims_by_aspect_priority(island, scalar, self.allow_rotation, self.aspect_tolerance, self.aspect_precision)
        elif self.priority == 'AREA':
            return hsp_storage.get_trims_by_area_priority(island, scalar, self.allow_rotation, self.aspect_tolerance, self.aspect_precision)
        else:  # WORLD_SIZE
            return hsp_storage.get_trims_by_world_size_priority(context, island, scalar, self.allow_rotation, self.aspect_tolerance, self.aspect_precision)
    
    def _transform_island_to_trim(self, island, trim, rotation_angle, uv_layer, fit_mode='CONTAIN', padding=0.0):
        """Transform island to fit within trim bounds"""
        try:
            # Get island loops
            loops = island.loops
            if not loops:
                return False
            
            # Get trim bounds
            trim_left = trim.trim.left
            trim_bottom = trim.trim.bottom
            trim_right = trim.trim.right
            trim_top = trim.trim.top
            
            # Apply padding
            effective_left = trim_left + padding * (trim_right - trim_left)
            effective_bottom = trim_bottom + padding * (trim_top - trim_bottom)
            effective_right = trim_right - padding * (trim_right - trim_left)
            effective_top = trim_top - padding * (trim_top - trim_bottom)
            
            # Calculate current island bounds
            uv_points = [Vector(loop[uv_layer].uv) for loop in loops]
            from ..utils.hotspot_system import BoundingBox2d
            current_bbox = BoundingBox2d.from_points(uv_points)
            
            # Calculate scale factors
            current_width = current_bbox.width
            current_height = current_bbox.height
            
            if current_width == 0 or current_height == 0:
                return False
            
            effective_width = effective_right - effective_left
            effective_height = effective_top - effective_bottom
            
            # Calculate scale factors based on fit mode
            scale_x, scale_y = self._calculate_fit_scales(
                current_width, current_height, 
                effective_width, effective_height, 
                fit_mode, trim
            )
            
            # Calculate alignment offset
            align_offset_x = 0.0
            align_offset_y = 0.0
            
            scaled_width = current_width * scale_x
            scaled_height = current_height * scale_y
            
            trim_center_x = (trim_left + trim_right) / 2
            trim_center_y = (trim_bottom + trim_top) / 2
            
            # Apply alignment
            if self.alignment in ['TOP_LEFT', 'CENTER_LEFT', 'BOTTOM_LEFT']:
                align_offset_x = effective_left + scaled_width / 2 - trim_center_x
            elif self.alignment in ['TOP_RIGHT', 'CENTER_RIGHT', 'BOTTOM_RIGHT']:
                align_offset_x = effective_right - scaled_width / 2 - trim_center_x
            
            if self.alignment in ['TOP_LEFT', 'TOP_CENTER', 'TOP_RIGHT']:
                align_offset_y = effective_top - scaled_height / 2 - trim_center_y
            elif self.alignment in ['BOTTOM_LEFT', 'BOTTOM_CENTER', 'BOTTOM_RIGHT']:
                align_offset_y = effective_bottom + scaled_height / 2 - trim_center_y
            
            # Transform each loop
            import math
            for loop in loops:
                uv = loop[uv_layer].uv
                
                # Translate to origin
                x = uv.x - current_bbox.center.x
                y = uv.y - current_bbox.center.y
                
                # Rotate if needed
                if rotation_angle != 0.0:
                    cos_a = math.cos(rotation_angle)
                    sin_a = math.sin(rotation_angle)
                    new_x = x * cos_a - y * sin_a
                    new_y = x * sin_a + y * cos_a
                    x = new_x
                    y = new_y
                
                # Scale
                x *= scale_x
                y *= scale_y
                
                # Move to trim position
                uv.x = trim_center_x + x + align_offset_x
                uv.y = trim_center_y + y + align_offset_y
            
            return True
            
        except Exception as e:
            print(f"Error transforming island: {e}")
            return False
    
    def draw(self, context):
        """Draw operator properties in the panel"""
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        # Fit Mode
        layout.prop(self, "fit_mode", text="Mode")

        # Advanced Fill mode controls (only show when mode is FILL)
        if self.fit_mode == 'FILL':
            layout.separator()
            box = layout.box()
            box.label(text="Fill Options:")

            # Horizontal mode
            box.prop(self, "fit_horizontal_mode", text="Horizontal")
            if self.fit_horizontal_mode == 'CUSTOM':
                box.prop(self, "fit_horizontal_custom", text="Width %", slider=True)

            # Vertical mode
            box.prop(self, "fit_vertical_mode", text="Vertical")
            if self.fit_vertical_mode == 'CUSTOM':
                box.prop(self, "fit_vertical_custom", text="Height %", slider=True)

        # Alignment
        layout.separator()

        # Create a sub-layout without property split for alignment grid
        align_layout = layout.column(align=True)
        align_layout.use_property_split = False
        align_layout.label(text="Alignment:")

        # 3x3 grid for alignment with Unicode arrows
        row = align_layout.row(align=True)
        row.prop_enum(self, "alignment", 'TOP_LEFT')
        row.prop_enum(self, "alignment", 'TOP_CENTER')
        row.prop_enum(self, "alignment", 'TOP_RIGHT')

        row = align_layout.row(align=True)
        row.prop_enum(self, "alignment", 'CENTER_LEFT')
        row.prop_enum(self, "alignment", 'CENTER')
        row.prop_enum(self, "alignment", 'CENTER_RIGHT')

        row = align_layout.row(align=True)
        row.prop_enum(self, "alignment", 'BOTTOM_LEFT')
        row.prop_enum(self, "alignment", 'BOTTOM_CENTER')
        row.prop_enum(self, "alignment", 'BOTTOM_RIGHT')

        # Padding and Auto Rotate
        layout.separator()
        layout.prop(self, "padding", slider=True)
        layout.prop(self, "allow_rotation")
        
        # Matching Settings
        layout.separator()
        layout.label(text="Matching Settings:")
        box = layout.box()
        box.prop(self, 'priority')
        box.prop(self, 'area_match')
        
        # Show manual scale only when area_match is MANUAL
        if self.area_match == 'MANUAL':
            box.prop(self, 'manual_scale')
        
        box.prop(self, 'aspect_tolerance')
        
        # Advanced Options
        layout.separator()
        layout.label(text="Advanced Options:")
        box = layout.box()
        box.prop(self, 'fit_mode')
        
        # Advanced Fill mode controls (only show when mode is FILL)
        if self.fit_mode == 'FILL':
            box.separator()
            fill_box = box.box()
            fill_box.label(text="Fill Options:")
            
            # Horizontal mode
            fill_box.prop(self, 'fit_horizontal_mode', text="Horizontal")
            if self.fit_horizontal_mode == 'CUSTOM':
                fill_box.prop(self, 'fit_horizontal_custom', text="Width %", slider=True)
            
            # Vertical mode
            fill_box.prop(self, 'fit_vertical_mode', text="Vertical")
            if self.fit_vertical_mode == 'CUSTOM':
                fill_box.prop(self, 'fit_vertical_custom', text="Height %", slider=True)
        
        box.prop(self, 'inset_mode')
        
        # Show padding only when inset_mode is MANUAL or COMBINED
        if self.inset_mode in ['MANUAL', 'COMBINED']:
            box.prop(self, 'padding')
        
        # Alignment
        box.separator()
        
        # Create a sub-layout without property split for alignment grid
        align_layout = box.column(align=True)
        align_layout.use_property_split = False
        align_layout.label(text="Alignment:")
        
        # 3x3 grid for alignment with Unicode arrows
        row = align_layout.row(align=True)
        row.prop_enum(self, 'alignment', 'TOP_LEFT')
        row.prop_enum(self, 'alignment', 'TOP_CENTER')
        row.prop_enum(self, 'alignment', 'TOP_RIGHT')
        
        row = align_layout.row(align=True)
        row.prop_enum(self, 'alignment', 'CENTER_LEFT')
        row.prop_enum(self, 'alignment', 'CENTER')
        row.prop_enum(self, 'alignment', 'CENTER_RIGHT')
        
        row = align_layout.row(align=True)
        row.prop_enum(self, 'alignment', 'BOTTOM_LEFT')
        row.prop_enum(self, 'alignment', 'BOTTOM_CENTER')
        row.prop_enum(self, 'alignment', 'BOTTOM_RIGHT')
        
        # Variability Settings
        layout.label(text="Variability:")
        box = layout.box()
        box.prop(self, 'allow_variability')
        
        if self.allow_variability:
            box.prop(self, 'allow_rotation_variation')
            box.prop(self, 'allow_location_variation')
            box.prop(self, 'allow_offset_variation')
            
            if self.allow_offset_variation:
                box.prop(self, 'loc_var_offset')
            
            box.prop(self, 'allow_flip_variation')
            box.prop(self, 'seed')
        
        # Advanced Options
        layout.label(text="Advanced Options:")
        box = layout.box()
        box.prop(self, 'trims_mode')
        box.prop(self, 'detect_radial')
        
        if self.detect_radial:
            box.prop(self, 'select_radials')
    
    def _calculate_fit_scales(self, current_width, current_height, effective_width, effective_height, fit_mode, trim):
        """Calculate scale factors based on fit mode"""
        # Get trim-specific settings if FROM_TRIM
        if fit_mode == 'FROM_TRIM':
            if hasattr(trim.trim, 'fit_mode'):
                fit_mode = trim.trim.fit_mode
            else:
                fit_mode = 'CONTAIN'  # Default fallback
        
        if fit_mode == 'FILL':
            # Use advanced fill mode with horizontal/vertical controls
            scale_x = self._calculate_axis_scale(current_width, effective_width, self.fit_horizontal_mode, self.fit_horizontal_custom)
            scale_y = self._calculate_axis_scale(current_height, effective_height, self.fit_vertical_mode, self.fit_vertical_custom)
            
        elif fit_mode == 'CONTAIN':
            # Fit inside trim bounds (maintains aspect, may letterbox)
            scale_x = effective_width / current_width
            scale_y = effective_height / current_height
            scale = min(scale_x, scale_y)
            scale_x = scale
            scale_y = scale
            
        elif fit_mode == 'COVER':
            # Fill trim bounds completely (maintains aspect, may crop)
            scale_x = effective_width / current_width
            scale_y = effective_height / current_height
            scale = max(scale_x, scale_y)
            scale_x = scale
            scale_y = scale
            
        elif fit_mode == 'FIT_WIDTH':
            # Match trim width, allow vertical overflow/underflow
            scale_x = effective_width / current_width
            scale_y = scale_x  # Maintain aspect ratio
            
        elif fit_mode == 'FIT_HEIGHT':
            # Match trim height, allow horizontal overflow/underflow
            scale_y = effective_height / current_height
            scale_x = scale_y  # Maintain aspect ratio
            
        elif fit_mode == 'NONE':
            # Don't scale, only position
            scale_x = 1.0
            scale_y = 1.0
            
        else:
            # Default to CONTAIN
            scale_x = effective_width / current_width
            scale_y = effective_height / current_height
            scale = min(scale_x, scale_y)
            scale_x = scale
            scale_y = scale
        
        return scale_x, scale_y
    
    def _calculate_axis_scale(self, current_size, effective_size, mode, custom_value):
        """Calculate scale for a single axis based on mode"""
        if mode == 'FILL':
            return effective_size / current_size
        elif mode == 'CONTAIN':
            return effective_size / current_size  # Will be constrained by min() in caller
        elif mode == 'CUSTOM':
            return (custom_value / 100.0) * (effective_size / current_size)
        else:
            return effective_size / current_size
        
        # Tag Filtering
        layout.label(text="Tag Filtering:")
        box = layout.box()
        box.prop(self, 'trim_category')
        box.prop(self, 'trim_tag')
        
        # Aspect Corrector
        layout.label(text="Aspect Corrector:")
        box = layout.box()
        row = box.row()
        row.alert = True if self.aspect_precision != 0.0 else False
        row.label(text="Wider")
        rc = row.row(align=True)
        rc.alignment = 'LEFT'
        rc.prop(self, 'aspect_precision')
        row = row.row()
        row.alignment = 'RIGHT'
        row.label(text="Higher")


classes = [
    UVV_OT_trim_add,
    UVV_OT_trim_remove,
    UVV_OT_trim_duplicate,
    UVV_OT_trim_select,
    UVV_OT_trim_move,
    UVV_OT_trim_fit_selection,
    UVV_OT_trim_set_tag,
    UVV_OT_trim_set_alignment,
    UVV_OT_trim_clear_all,
    UVV_OT_trim_export_svg,
    UVV_OT_trim_import_svg,
    UVV_OT_trim_create_circle,
    UVV_OT_trim_edit_toggle,
    UVV_OT_trim_edit_from_list,
    UVV_OT_trim_smart_pack,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
