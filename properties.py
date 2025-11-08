import bpy
import os
import sys
import uuid
from json import loads, dumps
from bpy.props import FloatProperty, IntProperty, BoolProperty, StringProperty, EnumProperty, FloatVectorProperty, IntVectorProperty, CollectionProperty
from bpy.types import PropertyGroup, AddonPreferences


def update_trim_bounds(self, context):
    """Update callback when trim bounds change"""

    # If this is a circle/ellipse, sync center and radii from bounding box
    if hasattr(self, 'shape_type') and self.shape_type == 'CIRCLE':
        # Calculate center and radii from bounding box (don't trigger infinite loop)
        new_center_x = (self.left + self.right) / 2
        new_center_y = (self.bottom + self.top) / 2
        new_radius_x = (self.right - self.left) / 2
        new_radius_y = (self.top - self.bottom) / 2

        # Use direct assignment to avoid triggering update callbacks
        self['center_x'] = new_center_x
        self['center_y'] = new_center_y
        self['radius_x'] = new_radius_x
        self['radius_y'] = new_radius_y

    # Auto-set fit method to COVER if trim is full width/height
    tolerance = 0.001
    is_full_width = abs(self.left - 0.0) < tolerance and abs(self.right - 1.0) < tolerance
    is_full_height = abs(self.bottom - 0.0) < tolerance and abs(self.top - 1.0) < tolerance

    if is_full_width or is_full_height:
        self.fit_method = 'COVER'


def update_pack_texture_size_x(self, context):
    """Update texture height when width changes and aspect is locked"""
    if self.pack_lock_texture_size:
        self.pack_texture_size_y = self.pack_texture_size_x


def update_pack_texture_size_y(self, context):
    """Update texture width when height changes and aspect is locked"""
    if self.pack_lock_texture_size:
        self.pack_texture_size_x = self.pack_texture_size_y


def update_size_x(self, context):
    """Update callback when size_x changes"""
    settings = context.scene.uvv_settings
    if settings.lock_size and settings.size_y != settings.size_x:
        settings.size_y = settings.size_x


def update_size_y(self, context):
    """Update callback when size_y changes"""
    settings = context.scene.uvv_settings
    if settings.lock_size and settings.size_x != settings.size_y:
        settings.size_x = settings.size_y


def update_lock_size(self, context):
    """Update callback when lock_size changes"""
    settings = context.scene.uvv_settings
    if settings.lock_size and settings.size_y != settings.size_x:
        settings.size_y = settings.size_x


class UVV_PackPreset(PropertyGroup):
    """Pack Islands preset with settings"""

    name: StringProperty(
        name="Preset Name",
        description="Name of this pack preset",
        default="New Preset"
    )

    # Pack settings
    use_uvpm: BoolProperty(name='Use UVPackmaster', default=False)

    shape_method: EnumProperty(
        name='Shape Method',
        default='CONCAVE',
        items=[
            ('CONCAVE', 'Exact', 'Uses exact geometry'),
            ('AABB', 'Fast', 'Uses bounding boxes')
        ]
    )

    scale: BoolProperty(name='Scale', default=True, description="Scale islands to fill unit square")
    rotate: BoolProperty(name='Rotate', default=True, description="Rotate islands to improve layout")
    normalize_islands: BoolProperty(name='Normalize Islands', default=False, description="Equalize texel density")

    rotate_method: EnumProperty(
        name='Rotation Method',
        default='CARDINAL',
        items=[
            ('ANY', 'Any', "Any angle is allowed for rotation"),
            ('AXIS_ALIGNED', 'Orient', "Rotated to a minimal rectangle, either vertical or horizontal"),
            ('CARDINAL', 'Step 90', "Only 90 degree rotations are allowed")
        ]
    )

    pin: BoolProperty(name='Lock Pinned Islands', default=False, description="Constrain islands containing any pinned UV's")

    pin_method: EnumProperty(
        name='Lock Method',
        default='LOCKED',
        items=[
            ('LOCKED', 'All', "Pinned islands are locked in place"),
            ('ROTATION_SCALE', 'Rotation and Scale', "Pinned islands will translate only"),
            ('ROTATION', 'Rotation', "Pinned islands won't rotate"),
            ('SCALE', 'Scale', "Pinned islands won't rescale")
        ]
    )

    merge_overlap: BoolProperty(name='Lock Overlaps', default=False)

    udim_source: EnumProperty(
        name='Pack to',
        default='CLOSEST_UDIM',
        items=[
            ('CLOSEST_UDIM', 'Closest UDIM', "Pack islands to closest UDIM"),
            ('ACTIVE_UDIM', 'Active UDIM', "Pack islands to active UDIM image tile or UDIM grid tile where 2D cursor is located"),
            ('ORIGINAL_AABB', 'Original BBox', "Pack to starting bounding box of islands")
        ]
    )

    padding: IntProperty(
        name='Padding',
        default=4,
        min=0,
        max=256,
        description="Padding between islands in pixels"
    )

    # Stacking options
    pack_enable_stacking: BoolProperty(
        name='Stack',
        description='Enable island stacking during packing',
        default=False
    )

    pack_use_stack_groups: BoolProperty(
        name='Use Stack Groups',
        description='Only stack islands that belong to manual stack groups',
        default=True
    )


class UVV_TDPreset(PropertyGroup):
    """Texel Density Preset (ZenUV compatibility)"""

    value: FloatProperty(
        name="TD Value",
        description="Texel density value for this preset",
        default=512.0,
        min=1.0,
        max=10000.0,
        precision=1,
        step=10
    )

    display_color: FloatVectorProperty(
        name="Display Color",
        description="Color for this preset in TD visualization",
        subtype='COLOR',
        size=3,
        default=(0.0, 1.0, 0.0),
        min=0.0,
        max=1.0
    )


def update_circle_radius_x(self, context):
    """Update callback when ellipse radius_x changes - update bounding box"""
    if self.shape_type == 'CIRCLE':
        # Update bounding box to match ellipse
        self['left'] = max(0.0, self.center_x - self.radius_x)
        self['right'] = min(1.0, self.center_x + self.radius_x)


def update_circle_radius_y(self, context):
    """Update callback when ellipse radius_y changes - update bounding box"""
    if self.shape_type == 'CIRCLE':
        # Update bounding box to match ellipse
        self['bottom'] = max(0.0, self.center_y - self.radius_y)
        self['top'] = min(1.0, self.center_y + self.radius_y)


def update_circle_center(self, context):
    """Update callback when circle center changes - update bounding box"""
    if self.shape_type == 'CIRCLE':
        # Update bounding box to match ellipse
        self['left'] = max(0.0, self.center_x - self.radius_x)
        self['right'] = min(1.0, self.center_x + self.radius_x)
        self['bottom'] = max(0.0, self.center_y - self.radius_y)
        self['top'] = min(1.0, self.center_y + self.radius_y)


class UVV_TrimRect(PropertyGroup):
    """Trimsheet rectangle/circle definition"""

    def get_uuid(self):
        """Get UUID, create if doesn't exist"""
        p_uuid = self.get('uuid', None)
        if p_uuid is None:
            self['uuid'] = str(uuid.uuid4())
            return self['uuid']
        return p_uuid

    def set_uuid(self, value):
        """Set UUID"""
        self['uuid'] = value

    uuid: StringProperty(
        name='UUID',
        description='Unique identifier for this trim',
        get=get_uuid,
        set=set_uuid,
        options=set()
    )

    name: StringProperty(
        name="Name",
        description="Name of this trim",
        default="Trim"
    )

    # Shape type (rectangle or circle)
    shape_type: EnumProperty(
        name="Shape Type",
        description="Shape of this trim",
        items=[
            ('RECTANGLE', "Rectangle", "Rectangular trim shape"),
            ('CIRCLE', "Circle", "Circular trim shape"),
        ],
        default='RECTANGLE'
    )

    # Rectangle bounds in UV space (0-1)
    # NOTE: For circles, these represent the bounding box
    left: FloatProperty(
        name="Left",
        description="Left edge of trim rectangle (or circle bounding box)",
        default=0.0,
        update=update_trim_bounds
    )

    bottom: FloatProperty(
        name="Bottom",
        description="Bottom edge of trim rectangle (or circle bounding box)",
        default=0.0,
        update=update_trim_bounds
    )

    right: FloatProperty(
        name="Right",
        description="Right edge of trim rectangle (or circle bounding box)",
        default=1.0,
        update=update_trim_bounds
    )

    top: FloatProperty(
        name="Top",
        description="Top edge of trim rectangle (or circle bounding box)",
        default=1.0,
        update=update_trim_bounds
    )

    # Circle/Ellipse-specific properties
    center_x: FloatProperty(
        name="Center X",
        description="X coordinate of ellipse center in UV space",
        default=0.5,
        update=update_circle_center
    )

    center_y: FloatProperty(
        name="Center Y",
        description="Y coordinate of ellipse center in UV space",
        default=0.5,
        update=update_circle_center
    )

    radius_x: FloatProperty(
        name="Radius X",
        description="Horizontal radius of ellipse in UV space",
        default=0.2,
        min=0.001,
        update=update_circle_radius_x
    )

    radius_y: FloatProperty(
        name="Radius Y",
        description="Vertical radius of ellipse in UV space",
        default=0.2,
        min=0.001,
        update=update_circle_radius_y
    )

    # Visual properties
    color: FloatVectorProperty(
        name="Color",
        description="Fill color for this trim",
        subtype='COLOR',
        size=3,
        default=(0.0, 0.5, 0.0),
        min=0.0,
        max=1.0
    )

    selected: BoolProperty(
        name="Selected",
        description="Whether this trim is selected",
        default=False
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Whether this trim is enabled/visible",
        default=True
    )

    locked: BoolProperty(
        name="Locked",
        description="Whether this trim is locked",
        default=False
    )

    tag: StringProperty(
        name="Tag",
        description="Tag for organizing and filtering trims (e.g., 'wood', 'metal', 'floor'). Type to create new tags",
        default="",
        maxlen=64
    )

    # Fit options (CSS object-fit inspired)
    fit_mode: EnumProperty(
        name="Fit Mode",
        description="How to fit UVs into the trim",
        items=[
            ('FILL', "Fill", "Stretch to fill trim bounds (ignores aspect ratio)"),
            ('CONTAIN', "Contain", "Fit inside trim bounds (maintains aspect, may letterbox)"),
            ('COVER', "Cover", "Fill trim bounds completely (maintains aspect, may crop)"),
            ('FIT_WIDTH', "Fit Width", "Match trim width, allow vertical overflow/underflow"),
            ('FIT_HEIGHT', "Fit Height", "Match trim height, allow horizontal overflow/underflow"),
            ('NONE', "None", "Don't scale, only position"),
        ],
        default='CONTAIN'
    )

    fit_alignment: EnumProperty(
        name="Alignment",
        description="How to align UVs within the trim",
        items=[
            ('CENTER', "Center", "Center in trim"),
            ('TOP_LEFT', "Top Left", "Align to top-left corner"),
            ('TOP_CENTER', "Top Center", "Align to top edge, centered horizontally"),
            ('TOP_RIGHT', "Top Right", "Align to top-right corner"),
            ('CENTER_LEFT', "Center Left", "Align to left edge, centered vertically"),
            ('CENTER_RIGHT', "Center Right", "Align to right edge, centered vertically"),
            ('BOTTOM_LEFT', "Bottom Left", "Align to bottom-left corner"),
            ('BOTTOM_CENTER', "Bottom Center", "Align to bottom edge, centered horizontally"),
            ('BOTTOM_RIGHT', "Bottom Right", "Align to bottom-right corner"),
        ],
        default='CENTER'
    )

    fit_padding: FloatProperty(
        name="Padding",
        description="Internal padding as percentage of trim size",
        default=0.0,
        min=0.0,
        max=0.5,  # 50% max to prevent negative space
        subtype='PERCENTAGE'
    )

    fit_auto_rotate: BoolProperty(
        name="Auto Rotate",
        description="Try 0° and 90° rotation, pick best fit",
        default=False
    )

    # UI state
    show_details: BoolProperty(
        name="Show Details",
        description="Show trim details section (name, color, transforms)",
        default=False
    )

    show_bounds: BoolProperty(
        name="Show Bounds",
        description="Show bounds properties",
        default=False
    )

    show_fit_options: BoolProperty(
        name="Show Fit Options",
        description="Show fit options properties",
        default=False
    )

    def get_width(self):
        """Get width of rectangle (or ellipse width)"""
        if self.shape_type == 'CIRCLE':
            return self.radius_x * 2
        return abs(self.right - self.left)

    def get_height(self):
        """Get height of rectangle (or ellipse height)"""
        if self.shape_type == 'CIRCLE':
            return self.radius_y * 2
        return abs(self.top - self.bottom)

    def get_center(self):
        """Get center point of trim"""
        if self.shape_type == 'CIRCLE':
            return (self.center_x, self.center_y)
        return ((self.left + self.right) / 2, (self.bottom + self.top) / 2)

    def set_rect(self, left, top, right, bottom):
        """Set all rectangle bounds at once"""
        self.left = min(left, right)
        self.right = max(left, right)
        self.top = max(top, bottom)
        self.bottom = min(top, bottom)

    def is_circular(self):
        """Check if this trim is circular/elliptical"""
        return self.shape_type == 'CIRCLE'

    def get_circle_data(self):
        """Get ellipse data (center_x, center_y, radius_x, radius_y)"""
        if self.shape_type == 'CIRCLE':
            return (self.center_x, self.center_y, self.radius_x, self.radius_y)
        return None

    def set_circle(self, center_x, center_y, radius_x, radius_y=None):
        """Set ellipse properties and update bounding box

        Args:
            center_x: Center X coordinate
            center_y: Center Y coordinate
            radius_x: Horizontal radius
            radius_y: Vertical radius (if None, uses radius_x for perfect circle)
        """
        self.shape_type = 'CIRCLE'
        self.center_x = center_x
        self.center_y = center_y
        self.radius_x = radius_x
        self.radius_y = radius_y if radius_y is not None else radius_x
        # Update bounding box
        self['left'] = max(0.0, center_x - self.radius_x)
        self['right'] = min(1.0, center_x + self.radius_x)
        self['bottom'] = max(0.0, center_y - self.radius_y)
        self['top'] = min(1.0, center_y + self.radius_y)


class UVV_Settings(PropertyGroup):
    """UVV addon settings stored in scene"""

    texel_density: FloatProperty(
        name="Texel Density",
        description="The number of texture pixels (texels) per unit surface area in 3D space",
        default=512.0,
        min=1.0,
        max=10000.0,
        precision=1,
        step=10
    )

    texture_size_x: IntProperty(
        name="Texture Width",
        description="Texture width for calculations",
        default=1024,
        min=1,
        max=8192
    )

    texture_size_y: IntProperty(
        name="Texture Height",
        description="Texture height for calculations",
        default=1024,
        min=1,
        max=8192
    )

    # === Transform Properties ===

    rotation_angle: FloatProperty(
        name="Rotation Angle",
        description="Rotation angle in degrees",
        default=90.0,
        min=-360.0,
        max=360.0,
        precision=1,
        step=10
    )

    split_uv_offset: FloatProperty(
        name="Split UV Offset",
        description="Distance to offset UV edges when splitting (rip region)",
        default=0.01,
        min=0.0001,
        max=1.0,
        precision=4,
        step=0.01
    )

    show_annotations: BoolProperty(
        name="Show Annotations",
        description="Show debugging annotations for UV operations",
        default=False
    )

    # === Trimsheet Overlay Properties ===

    show_trim_overlays: BoolProperty(
        name="Show Trim Overlays",
        description="Toggle visibility of trimsheet overlays in UV editor",
        default=True
    )

    show_trim_overlay_settings: BoolProperty(
        name="Show Overlay Settings",
        description="Show/hide overlay settings dropdown",
        default=False
    )

    trim_overlay_opacity: FloatProperty(
        name="Overlay Opacity",
        description="Opacity of trimsheet overlays",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR'
    )

    trim_unrestricted_placement: BoolProperty(
        name="Unrestricted Placement",
        description="Allow trims to be placed outside the 0-1 UV space (keeps snapping to 0-1 grid intact)",
        default=True
    )

    def update_trim_edit_mode(self, context):
        """Update callback when trim edit mode changes"""
        # Redraw UV editor
        if context.area:
            context.area.tag_redraw()

    trim_edit_mode: BoolProperty(
        name="Trim Edit Mode",
        description="Enable transform controls for trim editing (Figma-style)",
        default=False,
        update=update_trim_edit_mode
    )

    # === UV Checker Properties ===

    # Basic checker settings
    prev_color_type: StringProperty(
        name="Color Type",
        default='MATERIAL'
    )

    # Hidden property to remember user's darken preference when checker is disabled
    darken_user_preference: BoolProperty(
        name="Darken User Preference",
        description="Internal property to remember user's darken preference",
        default=True,  # Darken enabled by default
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def update_checker_visibility(self, context):
        """Update checker visibility when toggles change"""
        # Refresh the checker display based on current settings
        from .checker.checker import uvv_checker_image_update
        from .checker.checker import get_uvv_checker_image
        
        # Get current checker image
        current_image = get_uvv_checker_image(context)
        if current_image:
            # Update UV Editor display
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        if self.checker_show_in_uv_editor:
                            area.spaces.active.image = current_image
                        else:
                            # Clear the image from UV Editor when disabled
                            area.spaces.active.image = None
            
            # Update 3D View display by refreshing materials
            if self.checker_show_in_3d_view:
                uvv_checker_image_update(context, current_image)
            else:
                # Hide from 3D view by removing checker nodes
                self.hide_checker_from_3d_view(context)

    def hide_checker_from_3d_view(self, context):
        """Hide checker from 3D view by removing nodes"""
        from .checker.uvflow_style_checker import UVV_CHECKER_TEXTURE_NAME, UVV_MIX_SHADER_NAME, UVV_ATTRIBUTE_NODE_NAME
        
        for obj in bpy.data.objects:
            if obj.get('uvv_checker_enabled') and obj.type == 'MESH':
                for slot in obj.material_slots:
                    if slot.material and slot.material.use_nodes:
                        nodes = slot.material.node_tree.nodes
                        links = slot.material.node_tree.links
                        
                        # Remove checker nodes
                        if checker_node := nodes.get(UVV_CHECKER_TEXTURE_NAME, None):
                            nodes.remove(checker_node)
                        if mix_node := nodes.get(UVV_MIX_SHADER_NAME, None):
                            nodes.remove(mix_node)
                        if attr_node := nodes.get(UVV_ATTRIBUTE_NODE_NAME, None):
                            nodes.remove(attr_node)

    # Checker visibility toggles for UV Editor and 3D View
    checker_show_in_uv_editor: BoolProperty(
        name="Show in UV Editor",
        description="Show checker texture in UV Editor",
        default=False,
        update=update_checker_visibility
    )

    checker_show_in_3d_view: BoolProperty(
        name="Show in 3D View",
        description="Show checker texture in 3D Viewport",
        default=True,
        update=update_checker_visibility
    )

    # Checker method (hybrid approach)
    checker_method: EnumProperty(
        name="Checker Method",
        description="Method for applying UV checker visualization",
        items=[
            ('MATERIAL', "Material Override", "Fast node-based material override (may leave artifacts in file without addon)"),
            ('MODIFIER', "Modifier", "Geometry Nodes modifier (clean files, easily removable without addon)"),
        ],
        default='MODIFIER'
    )

    # Persistent checker auto mode state (survives Blender restart)
    checker_auto_mode_enabled: BoolProperty(
        name="Checker Auto Mode Enabled",
        description="Whether checker auto mode is currently active (persists across sessions)",
        default=False,
    )

    # Show checker settings dropdown
    show_checker_settings: BoolProperty(
        name="Show Checker Settings",
        description="Show/hide checker settings dropdown",
        default=False
    )

    use_custom_image: BoolProperty(
        name="Use Custom Image",
        description="Use custom image as UVV texture checker image",
        default=False
    )

    override_image_name: StringProperty(
        name='Image',
        default='No Image',
    )

    def update_debug_uv_mode(self, context):
        """Update debug UV mode when changed - sync with draw_mode_UV for backward compatibility"""
        try:
            if self.debug_uv_mode == 'STRETCHED':
                # Sync with draw_mode_UV
                if context.space_data.type == 'IMAGE_EDITOR':
                    self.draw_mode_UV = 'STRETCHED'
                else:
                    self.draw_mode_3D = 'STRETCHED'
                # Disable texel density overlay
                self.uvv_texel_overlay_active = False
                # Enable stretched UV display
                if hasattr(context.space_data, 'uv_editor'):
                    context.space_data.uv_editor.show_stretch = True

            elif self.debug_uv_mode == 'FLIPPED':
                # Sync with draw_mode_UV
                if context.space_data.type == 'IMAGE_EDITOR':
                    self.draw_mode_UV = 'FLIPPED'
                else:
                    self.draw_mode_3D = 'FLIPPED'
                # Disable texel density overlay
                self.uvv_texel_overlay_active = False
                # Select flipped UV faces
                if hasattr(context.space_data, 'uv_editor'):
                    context.space_data.uv_editor.show_stretch = False
                # Execute the flipped selection operator
                bpy.ops.uv.uvv_select_flipped()

            elif self.debug_uv_mode == 'TEXEL_DENSITY':
                # Sync with draw_mode_UV (Zen UV pattern)
                if context.space_data.type == 'IMAGE_EDITOR':
                    self.draw_mode_UV = 'TEXEL_DENSITY'
                else:
                    self.draw_mode_3D = 'TEXEL_DENSITY'
                # Disable stretched UV display
                if hasattr(context.space_data, 'uv_editor'):
                    context.space_data.uv_editor.show_stretch = False

                # Enable texel density visualization (will be set by update_draw_mode_UV)
                # Trigger gizmo rebuild (Zen UV pattern)
                from .checker.gizmo_draw import update_all_gizmos
                update_all_gizmos(context)

                # Redraw all relevant areas
                for window in context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type in {'IMAGE_EDITOR', 'VIEW_3D'}:
                            area.tag_redraw()

            else:  # DEFAULT
                # Sync with draw_mode_UV
                if context.space_data.type == 'IMAGE_EDITOR':
                    self.draw_mode_UV = 'NONE'
                else:
                    self.draw_mode_3D = 'NONE'
                # Disable texel density overlay
                self.uvv_texel_overlay_active = False
                # Disable stretched UV display
                if hasattr(context.space_data, 'uv_editor'):
                    context.space_data.uv_editor.show_stretch = False

                # Redraw all relevant areas
                for window in context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type in {'IMAGE_EDITOR', 'VIEW_3D'}:
                            area.tag_redraw()

        except Exception as e:
            print(f"Error updating debug UV mode: {e}")
            import traceback
            traceback.print_exc()

    debug_uv_mode: EnumProperty(
        name="Debug UV Mode",
        description="Select UV debug visualization mode",
        items=[
            ('DEFAULT', "Default", "No debug visualization"),
            ('STRETCHED', "Stretched", "Show stretched UVs"),
            ('FLIPPED', "Flipped", "Select flipped UV faces"),
            ('TEXEL_DENSITY', "Texel Density", "Show texel density visualization with color gradient"),
        ],
        default='DEFAULT',
        update=update_debug_uv_mode
    )

    # Display mode properties (Zen UV pattern)
    def update_draw_mode_UV(self, context):
        """Update draw mode for UV editor - sync with overlay active state"""
        if self.draw_mode_UV == 'TEXEL_DENSITY':
            self.uvv_texel_overlay_active = True
            from .checker.gizmo_draw import update_all_gizmos
            update_all_gizmos(context)
        elif self.draw_mode_UV == 'NONE':
            self.uvv_texel_overlay_active = False
        # Redraw UV editor
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

    def update_draw_mode_3D(self, context):
        """Update draw mode for 3D viewport"""
        # Redraw 3D viewport
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    draw_mode_UV: EnumProperty(
        name='Draw Mode UV',
        description='UV editor display mode',
        items=[
            ('NONE', 'None', 'All UV draws disabled'),
            ('TEXEL_DENSITY', 'Texel Density', 'Display texel density'),
            ('STRETCHED', 'Stretched', 'Display stretched UVs'),
            ('FLIPPED', 'Flipped', 'Display flipped faces'),
        ],
        default='NONE',
        update=update_draw_mode_UV,
        options={'SKIP_SAVE'}
    )

    draw_mode_3D: EnumProperty(
        name='Draw Mode 3D',
        description='3D viewport display mode',
        items=[
            ('NONE', 'None', 'All 3D draws disabled'),
            ('TEXEL_DENSITY', 'Texel Density', 'Display texel density'),
            ('STRETCHED', 'Stretched', 'Display stretched UVs'),
            ('FLIPPED', 'Flipped', 'Display flipped faces'),
        ],
        default='NONE',
        update=update_draw_mode_3D,
        options={'SKIP_SAVE'}
    )

    def update_draw_sub_TD(self, context):
        """Update TD display submode - trigger gizmo update"""
        if self.draw_mode_UV == 'TEXEL_DENSITY' or self.draw_mode_3D == 'TEXEL_DENSITY':
            from .checker.gizmo_draw import update_all_gizmos
            update_all_gizmos(context)

    draw_sub_TD_UV: EnumProperty(
        name='Draw TD Mode UV',
        description='Texel density draw mode in UV editor (gradient and/or viewport)',
        items=[
            ('ALL', 'All', 'Draw texel density gradient scale and mesh in the viewport'),
            ('GRADIENT', 'Gradient', 'Draw texel density gradient scale'),
            ('VIEWPORT', 'Viewport', 'Draw texel density mesh in the viewport'),
        ],
        default='ALL',
        update=update_draw_sub_TD
    )

    draw_sub_TD_3D: EnumProperty(
        name='Draw TD Mode 3D',
        description='Texel density draw mode in 3D viewport (gradient and/or viewport)',
        items=[
            ('ALL', 'All', 'Draw texel density gradient scale and mesh in the viewport'),
            ('GRADIENT', 'Gradient', 'Draw texel density gradient scale'),
            ('VIEWPORT', 'Viewport', 'Draw texel density mesh in the viewport'),
        ],
        default='ALL',
        update=update_draw_sub_TD
    )

    # Texel density influence mode (FACE vs ISLAND calculation)
    def update_td_influence(self, context):
        """Update TD influence mode - trigger rebuild"""
        if self.draw_mode_UV == 'TEXEL_DENSITY' or self.draw_mode_3D == 'TEXEL_DENSITY':
            from .checker.gizmo_draw import update_all_gizmos
            update_all_gizmos(context, force=True)

    # EXACT ZenUV property name
    influence: EnumProperty(
        name="TD Influence",
        description="Calculation mode: For each Face or for each Island",
        items=[
            ("FACE", "Face", "Calculate texel density for each Face", 'UV_FACESEL', 0),
            ("ISLAND", "Island", "Calculate texel density for each Island", 'UV_ISLANDSEL', 1),
        ],
        default='ISLAND',
        update=update_td_influence
    )

    # Overlay sync property
    use_draw_overlay_sync: BoolProperty(
        name='Overlay Sync',
        description='Draw is synchronized with overlay on-off setting',
        default=False
    )

    # Checker file management
    def get_path(self):
        """Get the path of Addon"""
        return os.path.dirname(os.path.realpath(__file__))

    def get_files_dict(self, context):
        """Get files dictionary"""
        try:
            if self.files_dict == "":
                from .checker.files import update_files_info
                self.files_dict = dumps(update_files_info(self.checker_assets_path))
            files_dict = loads(self.files_dict)
            return files_dict
        except Exception:
            print("Warning!", sys.exc_info()[0], "occurred.")
            from .checker.files import update_files_info
            self.files_dict = dumps(update_files_info(self.checker_assets_path))
            return None

    def get_x_res_list(self, context):
        """ Get resolutions list for files from files_dict """
        files_dict = self.get_files_dict(context)
        if files_dict:
            values_x = []
            for image in files_dict:
                value = files_dict[image]["res_x"]
                if value not in values_x:
                    values_x.append(value)
            values_x.sort()
            resolutions_x = []
            for identifier, value in enumerate(values_x):
                resolutions_x.append((str(value), str(value), "", identifier))
            return resolutions_x
        return [('None', 'None', '', 0), ]

    def get_y_res_list(self, context):
        """ Fills resolutions_y depend on current value of SizeX """
        files_dict = self.get_files_dict(context)
        if files_dict:
            res_x = self.sizes_x
            if res_x and res_x.isdigit():
                res_x = int(res_x)
                # If axes locked - return same value as Resolution X
                if self.lock_axes:
                    return [(str(res_x), str(res_x), "", 0)]
                identifier = 0
                values_y = []
                resolutions_y = []
                for image in files_dict:
                    value = files_dict[image]["res_y"]
                    if files_dict[image]["res_x"] == res_x and value not in values_y:
                        values_y.append(value)
                        resolutions_y.append((str(value), str(value), "", identifier))
                        identifier += 1
                if resolutions_y:
                    return resolutions_y
        return [('None', 'None', '', 0), ]

    def checker_image_items(self, context):
        """Get checker image items for dropdown"""
        # This function is no longer used since we removed FILE_BASED option
        # Return empty list to avoid errors
        return [('None', 'None', '', 0), ]

    def dynamic_update_function(self, context: bpy.types.Context):
        """Dynamic update when checker settings change"""
        try:
            from .checker.checker import get_materials_with_overrider
            if self.dynamic_update and get_materials_with_overrider(bpy.data.materials):
                self.checker_presets_update_function(context)
        except Exception as e:
            print("CHECKER DYN UPDATE:", e)

    def update_x_res(self, context: bpy.types.Context):
        """Update when X resolution changes"""
        self.sizes_y_index = 0
        self.checker_images_index = 0
        self.dynamic_update_function(context)

    def update_orient_switch(self, context: bpy.types.Context):
        """Update when orientation filter changes"""
        if self.chk_orient_filter:
            self.sizes_x_index = 1
            self.sizes_y_index = 0
        self.checker_images_index = 0
        self.dynamic_update_function(context)

    def update_y_res(self, context):
        """Update when Y resolution changes"""
        self.checker_images_index = 0
        self.dynamic_update_function(context)

    def dynamic_update_function_overall(self, context):
        """Overall dynamic update"""
        from .checker.checker import get_materials_with_overrider
        self.sizes_y_index = 0
        self.checker_images_index = 0
        if self.dynamic_update:
            materials_with_overrider = get_materials_with_overrider(bpy.data.materials)
            if materials_with_overrider:
                self.checker_presets_update_function(context)

    def checker_presets_update_function(self, context):
        """Update checker presets"""
        try:
            from .checker.checker import get_uvv_checker_image, uvv_checker_image_update
            from .checker.files import load_checker_image
            image = get_uvv_checker_image(context)
            if image:
                uvv_checker_image_update(context, image)
            else:
                image = load_checker_image(context, self.checker_images)
                if image:
                    uvv_checker_image_update(context, image)
        except Exception as e:
            print("CHECKER PRESETS UPDATE:", e)

    def update_checker_assets_path(self, context):
        """Update when checker assets path changes"""
        from .checker.files import update_files_info
        self.files_dict = dumps(update_files_info(self.checker_assets_path))

    checker_assets_path: StringProperty(
        name="Checker Library",
        subtype='DIR_PATH',
        default="",
        update=update_checker_assets_path
    )

    files_dict: StringProperty(
        name="UVV Checker Files Dict",
        default=""
    )

    dynamic_update: BoolProperty(
        name="Auto Sync Checker",
        description="Automatically sync selected Checker Texture with Viewport",
        default=True
    )

    lock_axes: BoolProperty(
        name="Lock",
        description="Lock aspect ratio",
        default=True,
        update=update_x_res
    )

    chk_rez_filter: BoolProperty(
        name="Resolution Filter",
        description="Filter by resolution",
        default=False,
        update=update_x_res
    )

    chk_orient_filter: BoolProperty(
        name="Orient Filter",
        description="Orient Checker Filter",
        default=False,
        update=update_orient_switch
    )

    sizes_x: EnumProperty(
        name='X Resolution',
        description="X resolution",
        items=get_x_res_list,
        update=update_x_res
    )

    sizes_y: EnumProperty(
        name='Y Resolution',
        description="Y resolution",
        items=get_y_res_list,
        update=update_y_res
    )

    sizes_x_index: IntProperty(default=0)
    sizes_y_index: IntProperty(default=0)
    checker_images_index: IntProperty(default=0)

    checker_images: EnumProperty(
        name='Checker Images',
        items=checker_image_items,
        update=checker_presets_update_function
    )

    # Pattern type selection (UVFlow-style patterns)
    checker_pattern_type: EnumProperty(
        name='Pattern Type',
        description='Type of UV checker pattern to use',
        items=[
            ('UV_GRID', 'Blender Grid', 'Blender\'s procedural grey UV grid'),
            ('COLOR_GRID', 'Blender Color Grid', 'Blender\'s procedural colorful UV grid'),
            ('ARROW_GRID', 'Arrow Grid', 'Arrow pattern grid for orientation checking')
        ],
        default='UV_GRID',
        update=checker_presets_update_function
    )

    def update_uniform_scale(self, context):
        """Update function for uniform scale toggle"""
        if self.checker_uniform_scale:
            # When enabling uniform scale, sync Y to X
            current_x = self.checker_custom_resolution[0]
            self.checker_custom_resolution = (current_x, current_x)
        self.checker_presets_update_function(context)

    # Uniform scale toggle for resolution
    checker_uniform_scale: BoolProperty(
        name='Uniform Scale',
        description='Keep resolution proportional (X and Y will scale together)',
        default=True,
        update=update_uniform_scale
    )

    def update_uniform_resolution(self, context):
        """Update Y resolution to match X when uniform scale is enabled"""
        if self.checker_uniform_scale:
            # Only update Y to match X, don't modify the property that triggered this
            current_x = self.checker_custom_resolution[0]
            # Use direct property assignment to avoid triggering update again
            self["checker_custom_resolution"] = (current_x, current_x)
        self.checker_presets_update_function(context)

    # Custom resolution for procedural patterns
    checker_custom_resolution: IntVectorProperty(
        name='Custom Resolution',
        description='Custom resolution for procedural patterns',
        default=(1024, 1024),
        size=2,
        min=64,
        max=7680,
        update=update_uniform_resolution
    )

    # Texture checker interpolation and tiling
    tex_checker_interpolation: BoolProperty(
        name="Interpolation",
        description="Texture Checker Interpolation",
        default=True
    )

    tex_checker_tiling: FloatVectorProperty(
        name="Tiling",
        description="Checker texture tiling",
        default=(1.0, 1.0),
        size=2,
        min=0.001,
        max=100.0
    )

    tex_checker_offset: FloatProperty(
        name="Offset",
        description="Checker texture offset",
        default=0.0,
        min=-10.0,
        max=10.0
    )

    # Texel Density Overlay
    uvv_texel_overlay_active: BoolProperty(
        name="Texel Density Overlay",
        description="Show custom texel density visualization overlay",
        default=False
    )

    uvv_texel_data_cache: StringProperty(
        name="Texel Data Cache",
        description="Cached texel density data for gizmo rendering",
        default=""
    )

    # Texel Density Display Mode
    texel_density_display_mode: EnumProperty(
        name="TD Display Mode",
        description="What to display when texel density mode is active",
        items=[
            ('VIEWPORT', "Viewport Only", "Show only colored overlay in viewport"),
            ('GRADIENT', "Gradient Only", "Show only gradient bar in UI"),
            ('ALL', "All", "Show both viewport overlay and gradient bar")
        ],
        default='ALL'
    )

    # Texel Density Gradient Bar Properties
    td_gradient_width: IntProperty(
        name='TD Gradient Width',
        description='Width of texel density gradient bar in pixels',
        min=50,
        max=2000,
        default=300
    )

    td_gradient_height: IntProperty(
        name='TD Gradient Height',
        description='Height of texel density gradient bar in pixels',
        min=10,
        max=500,
        default=15
    )

    td_gradient_alpha: FloatProperty(
        name='TD Color Alpha',
        description='Texel density overlay color alpha',
        default=0.6,
        min=0.01,
        max=1.0,
        subtype='FACTOR'
    )

    # Texel Density Color Scheme Properties (Zen UV pattern)
    # EXACT ZenUV property name
    color_scheme_name: EnumProperty(
        name="Color Scheme",
        description="Color scheme for texel density visualization",
        items=[
            ('FULL_SPEC', "Full Spectrum", "Blue (high) to Red (low) full spectrum"),
            ('REVERSED_SPEC', "Reversed Spectrum", "Red (high) to Blue (low) reversed spectrum"),
            ('USER_THREE', "User 3-Color", "User-defined 3-color scheme (under/equal/over)"),
            ('USER_LINEAR', "User Linear", "Linear interpolation between user under/over colors"),
            ('MONO', "Monochrome", "Grayscale from black to white"),
        ],
        default='FULL_SPEC'
    )

    # EXACT ZenUV property names (no td_ prefix for color processor compatibility)
    display_method: EnumProperty(
        name="Display Method",
        description="Texel density display method",
        items=[
            ('SPECTRUM', "Spectrum", "Show full color spectrum based on TD range"),
            ('BALANCED', "Balanced", "Show 3-color balanced view (under/equal/over target TD)"),
            ('PRESETS', "Presets", "Show colors based on TD presets"),
        ],
        default='SPECTRUM'
    )

    # User-defined colors for 3-color scheme
    td_color_under: FloatVectorProperty(
        name="Under Color",
        description="Color for texel density below target",
        subtype='COLOR',
        size=3,
        default=(0.0, 0.0, 1.0),  # Blue
        min=0.0,
        max=1.0
    )

    td_color_equal: FloatVectorProperty(
        name="Equal Color",
        description="Color for texel density equal to target",
        subtype='COLOR',
        size=3,
        default=(0.0, 1.0, 0.0),  # Green
        min=0.0,
        max=1.0
    )

    td_color_over: FloatVectorProperty(
        name="Over Color",
        description="Color for texel density above target",
        subtype='COLOR',
        size=3,
        default=(1.0, 0.0, 0.0),  # Red
        min=0.0,
        max=1.0
    )

    # TD Range properties - EXACT ZenUV property name
    is_range_manual: BoolProperty(
        name="Manual Range",
        description="Manually set TD range instead of auto-calculating from mesh",
        default=False
    )

    td_range_min: FloatProperty(
        name="Range Min",
        description="Minimum TD value for color mapping",
        default=0.0,
        min=0.0,
        max=10000.0
    )

    td_range_max: FloatProperty(
        name="Range Max",
        description="Maximum TD value for color mapping",
        default=1000.0,
        min=0.0,
        max=10000.0
    )

    # Additional TD properties for ZenUV compatibility
    draw_auto_update: BoolProperty(
        name="Auto Update",
        description="Automatically update TD visualization when geometry changes. Disable for better performance during complex operations",
        default=True
    )

    use_presets_only: BoolProperty(
        name="Use Presets Only",
        description="In presets mode, show only faces matching TD presets (others shown in black)",
        default=False
    )

    values_filter: FloatProperty(
        name="Values Filter",
        description="Density of value labels on gradient widget (higher = fewer labels)",
        default=10.0,
        min=1.0,
        max=100.0
    )

    # BALANCED mode properties
    balanced_checker: FloatProperty(
        name="Balanced Base TD",
        description="Target texel density for BALANCED mode (middle/equal color)",
        default=512.0,
        min=1.0,
        max=10000.0,
        precision=1,
        step=10
    )

    # TD Units system
    td_unit: EnumProperty(
        name="TD Unit",
        description="Units for texel density display",
        items=[
            ('px/cm', "px/cm", "Pixels per centimeter"),
            ('px/m', "px/m", "Pixels per meter"),
            ('px/in', "px/in", "Pixels per inch"),
        ],
        default='px/cm'
    )

    # TD Calculation precision (for performance on large meshes)
    td_calc_precision: IntProperty(
        name="TD Calculation Precision",
        description="Calculate using N% of faces (100 = all faces, lower = faster but less accurate)",
        default=100,
        min=1,
        max=100,
        subtype='PERCENTAGE'
    )

    # === Pack Properties (UNIV 1:1 Copy) ===

    # Global size with lock feature
    size_x: EnumProperty(
        name='X',
        default='2048',
        items=[
            ('64', '64', ''),
            ('128', '128', ''),
            ('256', '256', ''),
            ('512', '512', ''),
            ('1024', '1024', ''),
            ('2048', '2048', ''),
            ('4096', '4096', ''),
            ('8192', '8192', ''),
        ],
        update=update_size_x
    )

    size_y: EnumProperty(
        name='Y',
        default='2048',
        items=[
            ('64', '64', ''),
            ('128', '128', ''),
            ('256', '256', ''),
            ('512', '512', ''),
            ('1024', '1024', ''),
            ('2048', '2048', ''),
            ('4096', '4096', ''),
            ('8192', '8192', ''),
        ],
        update=update_size_y
    )

    lock_size: BoolProperty(
        name='Lock Size',
        default=True,
        update=update_lock_size
    )

    # Pack Settings (matching UNIV exactly)
    use_uvpm: BoolProperty(name='Use UVPackmaster', default=False)

    def update_pack_enable_stacking(self, context):
        """Auto-enable stack groups when stacking is enabled"""
        if self.pack_enable_stacking:
            self.pack_use_stack_groups = True

    # Stacking options
    pack_enable_stacking: BoolProperty(
        name='Stack',
        description='Enable island stacking during packing',
        default=False,
        update=update_pack_enable_stacking
    )

    pack_use_stack_groups: BoolProperty(
        name='Use Stack Groups',
        description='Only stack islands that belong to manual stack groups',
        default=True
    )

    shape_method: EnumProperty(
        name='Shape Method',
        default='CONCAVE',
        items=[
            ('CONCAVE', 'Exact', 'Uses exact geometry'),
            ('AABB', 'Fast', 'Uses bounding boxes')
        ]
    )

    scale: BoolProperty(
        name='Scale',
        default=True,
        description="Scale islands to fill unit square"
    )

    rotate: BoolProperty(
        name='Rotate',
        default=True,
        description="Rotate islands to improve layout"
    )

    rotate_method: EnumProperty(
        name='Rotation Method',
        default='CARDINAL',
        items=[
            ('ANY', 'Any', "Any angle is allowed for rotation"),
            ('AXIS_ALIGNED', 'Orient', "Rotated to a minimal rectangle, either vertical or horizontal"),
            ('CARDINAL', 'Step 90', "Only 90 degree rotations are allowed")
        ]
    )

    pin: BoolProperty(
        name='Lock Pinned Islands',
        default=False,
        description="Constrain islands containing any pinned UV's"
    )

    pin_method: EnumProperty(
        name='Lock Method',
        default='LOCKED',
        items=[
            ('LOCKED', 'All', "Pinned islands are locked in place"),
            ('ROTATION_SCALE', 'Rotation and Scale', "Pinned islands will translate only"),
            ('ROTATION', 'Rotation', "Pinned islands won't rotate"),
            ('SCALE', 'Scale', "Pinned islands won't rescale")
        ]
    )

    merge_overlap: BoolProperty(name='Lock Overlaps', default=False)

    normalize_islands: BoolProperty(
        name='Normalize Islands',
        default=False,
        description="Equalize texel density across all UV islands before packing (native packer only)"
    )

    udim_source: EnumProperty(
        name='Pack to',
        default='CLOSEST_UDIM',
        items=[
            ('CLOSEST_UDIM', 'Closest UDIM', "Pack islands to closest UDIM"),
            ('ACTIVE_UDIM', 'Active UDIM', "Pack islands to active UDIM image tile or UDIM grid tile where 2D cursor is located"),
            ('ORIGINAL_AABB', 'Original BBox', "Pack to starting bounding box of islands")
        ]
    )

    padding: IntProperty(
        name='Padding',
        default=8,
        min=0,
        soft_min=2,
        soft_max=32,
        max=64,
        step=2,
        subtype='PIXEL',
        description="Space between islands in pixels.\n\n"
                    "Formula for converting the current Padding implementation to Margin:\n"
                    "Margin = Padding / 2 / Texture Size\n\n"
                    "Optimal value for UV padding:\n"
                    "256 = 1  px\n"
                    "512 = 2-3 px\n"
                    "1024 = 4-5 px\n"
                    "2048 = 8-10 px\n"
                    "4096 = 16-20 px\n"
                    "8192 = 32-40 px\t"
    )

    # UV Coverage Properties
    uv_coverage: FloatProperty(
        name="UV Coverage",
        description="Percentage of UV space covered by islands",
        default=0.0,
        min=0.0,
        max=100.0
    )

    average_texel_density: FloatProperty(
        name="Average Texel Density",
        description="Average texel density across all UV islands",
        default=0.0,
        min=0.0,
        max=100000.0
    )

    uv_coverage_mode: EnumProperty(
        name="UV Coverage Mode",
        description="Mode for UV coverage calculation",
        items=[
            ('AUTO', "Auto", "Automatically calculate UV coverage"),
            ('MANUAL', "Manual", "Manually set UV coverage"),
        ],
        default='AUTO'
    )

    # === Parallel Constraint Properties ===

    parallel_edge1_object: StringProperty(
        name="Parallel Edge 1 Object",
        description="Object name containing the first parallel constraint edge",
        default=""
    )

    parallel_edge1_data: StringProperty(
        name="Parallel Edge 1 Data",
        description="JSON data for first parallel constraint edge (indices and UV coords)",
        default=""
    )

    parallel_edge2_object: StringProperty(
        name="Parallel Edge 2 Object",
        description="Object name containing the second parallel constraint edge",
        default=""
    )

    parallel_edge2_data: StringProperty(
        name="Parallel Edge 2 Data",
        description="JSON data for second parallel constraint edge (indices and UV coords)",
        default=""
    )

    parallel_constraint_stored: BoolProperty(
        name="Parallel Constraint Stored",
        description="Flag indicating if parallel constraint edges are stored",
        default=False
    )

    # === Stack Properties ===

    stack_match_rotation: BoolProperty(
        name="Match Rotation",
        description="Rotate islands to match master orientation when stacking",
        default=True
    )

    stack_rotation_mode: EnumProperty(
        name="Rotation Mode",
        description="How to match rotation when stacking islands",
        items=[
            ('NONE', "None", "No rotation - keep original orientation"),
            ('SNAP_90', "Snap 90°", "Snap to nearest 90° rotation based on edge orientation"),
            ('OPTIMAL', "Optimal Angles", "Try all 90° angles, pick best bounding box match"),
            ('OPTIMAL_MATCH', "Optimal Match", "Test both no-rotation and 90° snapping, pick closest match"),
        ],
        default='OPTIMAL_MATCH'
    )

    stack_match_scale: BoolProperty(
        name="Match Scale",
        description="Scale islands to match master size when stacking",
        default=True
    )

    stack_scale_mode: EnumProperty(
        name="Scale Mode",
        description="How to scale islands when stacking",
        items=[
            ('UNIFORM', "Uniform", "Scale uniformly (average of X and Y, maintains aspect ratio)"),
            ('BOUNDS', "Bounds", "Match exact bounding box (non-uniform, may distort)"),
            ('NONE', "None", "Keep original scale (position only)")
        ],
        default='UNIFORM'
    )

    stack_auto_group: BoolProperty(
        name="Auto-Assign to Groups",
        description="Automatically assign newly detected similar islands to groups",
        default=False
    )

    show_stack_groups_list: BoolProperty(
        name="Show Stack Groups List",
        description="Show/hide the stack groups list in the UI",
        default=False
    )

    show_materials_list: BoolProperty(
        name="Show Materials List",
        description="Show/hide the materials list in the trimsheet panel",
        default=True
    )

    show_trims_list: BoolProperty(
        name="Show Trims List",
        description="Show/hide the trims list in the trimsheet panel",
        default=True
    )

    stack_min_group_size: IntProperty(
        name="Minimum Group Size",
        description="Minimum number of islands required in a stack group (groups below this will be removed during batch cleanup)",
        default=2,
        min=1,
        max=100
    )

    # === Similarity Detection Properties ===

    stack_simi_mode: EnumProperty(
        name="Similarity Mode",
        description="Method used to detect similar islands",
        items=[
            ('BORDER_SHAPE', "Border Shape", "Compares island border/perimeter shapes (fast, default)"),
            ('VERTEX_POSITION', "Vertex Position", "Matches vertices by their position (more accurate)"),
            ('TOPOLOGY', "Topology", "Requires identical topology and vertex positions (most accurate, slower)"),
        ],
        default='BORDER_SHAPE'
    )

    stack_simi_precision: IntProperty(
        name="Precision",
        description="Accuracy level for similarity detection (higher = more precise but slower)",
        default=500,
        min=10,
        max=10000
    )

    stack_simi_threshold: FloatProperty(
        name="Threshold",
        description="Similarity tolerance (lower = stricter matching)",
        default=0.1,
        min=0.01,
        max=1.0,
        precision=2,
        step=0.01
    )

    stack_simi_check_holes: BoolProperty(
        name="Check Holes",
        description="Consider inner hole shapes when detecting similarity (slower but more accurate)",
        default=False
    )

    stack_simi_adjust_scale: BoolProperty(
        name="Adjust Scale",
        description="Normalize island scales before comparing similarity",
        default=True
    )

    stack_simi_non_uniform_tolerance: FloatProperty(
        name="Non-Uniform Scaling Tolerance",
        description="Tolerance for non-uniform scaling differences (0.0 = strict, 1.0 = loose)",
        default=0.1,
        min=0.0,
        max=1.0,
        precision=2,
        step=0.01
    )

    stack_simi_flipping_enable: BoolProperty(
        name="Allow Flipping",
        description="Allow horizontal/vertical flipping when matching islands",
        default=True
    )

    # === Stack Overlay Properties ===

    def update_stack_overlay_enabled(self, context):
        """Update callback when stack overlay enabled state changes"""
        from .utils.stack_overlay import update_stack_overlay_state
        update_stack_overlay_state(self, context)

    stack_overlay_enabled: BoolProperty(
        name="Show Stack Overlays",
        description="Display colored overlays for stack groups in UV Editor",
        default=True,
        update=update_stack_overlay_enabled
    )

    def update_stack_overlay_opacity(self, context):
        """Update callback when overlay opacity changes"""
        from .utils.stack_overlay import refresh_overlay
        refresh_overlay()
    
    stack_overlay_opacity: FloatProperty(
        name="Overlay Opacity",
        description="Opacity of stack group overlays",
        default=0.3,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        update=update_stack_overlay_opacity
    )

    def update_stack_overlay_mode(self, context):
        """Update callback when overlay mode changes"""
        from .utils.stack_overlay import refresh_overlay
        refresh_overlay()
    
    stack_overlay_mode: EnumProperty(
        name="Overlay Mode",
        description="How to display stack overlays",
        items=[
            ('FILL', 'Fill', 'Solid fill with group color'),
            ('BORDER', 'Border', 'Only island borders'),
            ('BOTH', 'Both', 'Fill and border')
        ],
        default='FILL',
        update=update_stack_overlay_mode
    )

    stack_overlay_show_fill: BoolProperty(
        name="Show Fill",
        description="Draw filled overlay for stack groups",
        default=False,
        update=update_stack_overlay_mode
    )

    stack_overlay_show_border: BoolProperty(
        name="Show Border",
        description="Draw border outline for stack groups",
        default=False,
        update=update_stack_overlay_mode
    )

    stack_overlay_show_labels: BoolProperty(
        name="Show Group Labels",
        description="Display group names on islands",
        default=False
    )

    stack_overlay_highlight_on_click: BoolProperty(
        name="Flash Highlight",
        description="Show flash border with the group's color when clicking on a group (fades over time)",
        default=True
    )

    stack_overlay_flash_duration: FloatProperty(
        name="Flash Speed",
        description="Duration of the flash animation in seconds (lower = faster)",
        default=1.0,
        min=0.1,
        max=5.0,
        step=0.1,
        precision=2,
        subtype='TIME'
    )

    stack_overlay_show_permanent_border: BoolProperty(
        name="Selection Border",
        description="Show permanent white border around islands in the selected group",
        default=False
    )

    stack_overlay_flash_border_width: FloatProperty(
        name="Flash Border Width",
        description="Maximum thickness of the flash border (shrinks to minimum during animation)",
        default=4.0,
        min=2.0,
        max=20.0,
        step=10,
        precision=1,
        subtype='PIXEL'
    )

    # === UI State Properties ===

    show_constraints_list: BoolProperty(
        name="Show Constraints List",
        description="Show/hide the constraints list in the UI",
        default=True
    )

    # === Auto Unwrap Properties ===

    auto_unwrap_enabled: BoolProperty(
        name="Enable Auto Unwrap",
        description="Automatically unwrap UVs after weld, stitch, or split operations",
        default=False
    )

    # === Version Check Properties ===

    latest_version_available: StringProperty(
        name="Latest Version Available",
        description="Latest version available for download (empty if up-to-date)",
        default=""
    )

    version_check_in_progress: BoolProperty(
        name="Version Check In Progress",
        description="Flag to prevent multiple simultaneous version checks",
        default=False
    )

    update_download_url: StringProperty(
        name="Update Download URL",
        description="Direct download URL for the latest version zip file",
        default=""
    )


class UVV_Constraint(PropertyGroup):
    """Single UV constraint (horizontal, vertical, or parallel)"""

    constraint_type: EnumProperty(
        name="Type",
        description="Type of constraint",
        items=[
            ('HORIZONTAL', "Horizontal", "Edges constrained to be horizontal"),
            ('VERTICAL', "Vertical", "Edges constrained to be vertical"),
            ('PARALLEL', "Parallel", "Two edges constrained to be parallel"),
        ],
        default='HORIZONTAL'
    )

    context_type: EnumProperty(
        name="Context",
        description="Which viewport context this constraint was created in",
        items=[
            ('UV', "UV", "Created in UV editor from UV selection"),
            ('3D', "3D", "Created in 3D viewport from mesh selection"),
        ],
        default='UV'
    )

    name: StringProperty(
        name="Name",
        description="Name of this constraint",
        default="Constraint"
    )

    # Object and edge data storage
    object_name: StringProperty(
        name="Object",
        description="Object containing the constrained edges",
        default=""
    )

    edge_indices: StringProperty(
        name="Edge Indices",
        description="JSON list of edge indices for this constraint",
        default="[]"
    )

    # For parallel constraints (second edge)
    object_name2: StringProperty(
        name="Object 2",
        description="Second object for parallel constraint",
        default=""
    )

    edge_indices2: StringProperty(
        name="Edge Indices 2",
        description="JSON list of edge indices for second parallel edge",
        default="[]"
    )

    enabled: BoolProperty(
        name="Enabled",
        description="Whether this constraint is active",
        default=True
    )


class UVV_StackGroup(PropertyGroup):
    """Represents a manual stack group for organizing UV islands"""

    name: StringProperty(
        name="Name",
        description="Name of this stack group",
        default="Group 1"
    )

    group_id: IntProperty(
        name="Group ID",
        description="Unique identifier for this stack group",
        default=0,
        min=0
    )

    color: FloatVectorProperty(
        name="Color",
        description="Color for UI visualization",
        subtype='COLOR',
        size=3,
        default=(0.5, 0.5, 0.5),
        min=0.0,
        max=1.0
    )

    islands_data: StringProperty(
        name="Islands Data",
        description="JSON storage of island identifiers (object_name, face_indices)",
        default="[]"
    )

    # Cached island count for UI performance
    cached_island_count: IntProperty(
        name="Cached Island Count",
        description="Cached count of islands in this group",
        default=0,
        min=0
    )


def get_uvv_settings():
    """Get UVV settings from current scene"""
    return bpy.context.scene.uvv_settings


def univ_settings():
    """Get UVV settings - compatibility function for UniV-style code"""
    return get_uvv_settings()


class UVV_AddonPreferences(AddonPreferences):
    """UVV addon preferences for keymap settings"""
    bl_idname = __package__

    # Pie menu keymap settings
    pie_menu_enabled: BoolProperty(
        name="Enable Pie Menu",
        description="Enable the UVV pie menu (ALT+SHIFT+X)",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="UVV Pie Menu Settings:")
        layout.prop(self, "pie_menu_enabled")
        
        if self.pie_menu_enabled:
            layout.label(text="Hotkey: ALT+SHIFT+X", icon='INFO')
            layout.label(text="Works in 3D View and UV Editor (Edit Mesh mode)")


classes = [
    UVV_PackPreset,
    UVV_TDPreset,
    UVV_TrimRect,
    UVV_Constraint,
    UVV_StackGroup,
    UVV_Settings,
    UVV_AddonPreferences,
]


def trim_index_update(self, context):
    """Update callback when trim selection changes"""
    # Ensure modal is running when trim is selected
    try:
        # Check reload flag first to prevent crashes during/after reload
        try:
            import sys
            # Check ALL modules - if ANY has reloading=True, we're reloading
            for mod in sys.modules.values():
                if mod and hasattr(mod, 'UVV_OT_trimsheet_tool_modal') and hasattr(mod, '_uvv_trimsheet_reloading'):
                    if getattr(mod, '_uvv_trimsheet_reloading', False):
                        return  # Don't try to start modal if reloading
        except:
            pass  # If check fails, continue (safer than blocking during normal operation)
        
        # Try to import and start modal - handle import errors gracefully
        try:
            # Try relative import first (standard case)
            from .operators.trimsheet_tool_modal import start_trimsheet_modal_if_needed
        except ImportError:
            # Fallback: try absolute import (handles reload cases)
            try:
                from operators.trimsheet_tool_modal import start_trimsheet_modal_if_needed
            except ImportError:
                # Module not available - likely during reload, just return
                return
        
        if context:
            start_trimsheet_modal_if_needed(context)
    except Exception as e:
        # Silently ignore errors - they're likely due to reload
        pass


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.uvv_settings = bpy.props.PointerProperty(type=UVV_Settings)

    # Register trimsheet collection on Material datablock (each material has its own trims)
    bpy.types.Material.uvv_trims = CollectionProperty(type=UVV_TrimRect)
    bpy.types.Material.uvv_trims_index = IntProperty(
        name="Active Trim Index",
        default=-1,
        min=-1,
        update=trim_index_update
    )

    # Register constraints collection on Scene (constraints are per-scene)
    bpy.types.Scene.uvv_constraints = CollectionProperty(type=UVV_Constraint)
    bpy.types.Scene.uvv_constraints_index = IntProperty(name="Active Constraint Index", default=-1, min=-1)

    # Register pack presets collection on Scene (presets are per-scene)
    bpy.types.Scene.uvv_pack_presets = CollectionProperty(type=UVV_PackPreset)
    bpy.types.Scene.uvv_pack_presets_index = IntProperty(name="Active Pack Preset Index", default=0, min=-1)

    # Register TD presets collection on Scene (ZenUV compatibility: zen_tdpr_list equivalent)
    bpy.types.Scene.uvv_td_presets = CollectionProperty(type=UVV_TDPreset)
    bpy.types.Scene.uvv_td_presets_index = IntProperty(name="Active TD Preset Index", default=-1, min=-1)

    # Register stack groups collection on Object (stack groups are per-object)
    bpy.types.Object.uvv_stack_groups = CollectionProperty(type=UVV_StackGroup)
    bpy.types.Object.uvv_stack_groups_index = IntProperty(name="Active Stack Group Index", default=-1, min=-1)

    # Initialize checker assets path to default
    def init_checker_path():
        """Initialize checker assets path on first load"""
        if bpy.context.scene and hasattr(bpy.context.scene, 'uvv_settings'):
            settings = bpy.context.scene.uvv_settings
            if settings.checker_assets_path == "":
                addon_path = os.path.dirname(os.path.realpath(__file__))
                settings.checker_assets_path = os.path.join(addon_path, "images")

    def restore_checker_state():
        """Restore checker state on addon startup/scene load"""
        try:
            from .checker.checker import sync_checker_state, validate_checker_state
            from .checker.checker_mode_handler import enable_checker_auto_mode, disable_checker_auto_mode
            if bpy.context.scene and hasattr(bpy.context.scene, 'uvv_settings'):
                settings = bpy.context.scene.uvv_settings
                
                # Check if checker auto mode should be enabled based on persisted state
                if settings.checker_auto_mode_enabled:
                    # Re-enable checker auto mode (this will restore msgbus subscription and checkers)
                    enable_checker_auto_mode(bpy.context)
                else:
                    # Ensure everything is cleaned up if auto mode is disabled
                    disable_checker_auto_mode(bpy.context)
                
                # Validate and sync checker state
                state = validate_checker_state(bpy.context)
                if state['needs_restoration']:
                    sync_checker_state(bpy.context, force_sync=True)
        except Exception as e:
            print(f"UVV: Error restoring checker state: {e}")

    def init_pack_presets():
        """Initialize default pack presets on first load - updates default presets, preserves custom ones"""
        if bpy.context.scene and hasattr(bpy.context.scene, 'uvv_pack_presets'):
            presets = bpy.context.scene.uvv_pack_presets

            # Define default presets with their properties
            default_presets = {
                "Fast": {
                    "use_uvpm": False,
                    "shape_method": 'AABB',
                    "scale": True,
                    "rotate": True,
                    "normalize_islands": False,
                    "rotate_method": 'CARDINAL',
                    "pin": False,
                    "merge_overlap": False,
                    "udim_source": 'CLOSEST_UDIM',
                    "padding": 4
                },
                "Accurate": {
                    "use_uvpm": False,
                    "shape_method": 'CONCAVE',
                    "scale": True,
                    "rotate": True,
                    "normalize_islands": True,
                    "rotate_method": 'CARDINAL',
                    "pin": False,
                    "merge_overlap": False,
                    "udim_source": 'CLOSEST_UDIM',
                    "padding": 4
                },
                "UVPM Fast": {
                    "use_uvpm": True,
                    "shape_method": 'AABB',
                    "scale": True,
                    "rotate": True,
                    "normalize_islands": True,
                    "rotate_method": 'CARDINAL',
                    "pin": False,
                    "merge_overlap": False,
                    "udim_source": 'CLOSEST_UDIM',
                    "padding": 4,
                    "pack_enable_stacking": True,
                    "pack_use_stack_groups": True
                },
                "UVPM Accurate": {
                    "use_uvpm": True,
                    "shape_method": 'CONCAVE',
                    "scale": True,
                    "rotate": True,
                    "normalize_islands": True,
                    "rotate_method": 'ANY',
                    "pin": False,
                    "merge_overlap": False,
                    "udim_source": 'CLOSEST_UDIM',
                    "padding": 4,
                    "pack_enable_stacking": True,
                    "pack_use_stack_groups": True
                }
            }

            # Remove old "UVMaster" presets (migrated to "UVPM")
            old_preset_names = ["UVMaster Fast", "UVMaster Accurate"]
            indices_to_remove = []
            for i, preset in enumerate(presets):
                if preset.name in old_preset_names:
                    indices_to_remove.append(i)
            
            # Remove in reverse order to avoid index shifting issues
            for i in reversed(indices_to_remove):
                presets.remove(i)
                # Adjust active index if needed
                if bpy.context.scene.uvv_pack_presets_index >= i:
                    if bpy.context.scene.uvv_pack_presets_index > 0:
                        bpy.context.scene.uvv_pack_presets_index -= 1
                    else:
                        bpy.context.scene.uvv_pack_presets_index = 0

            # Track which default presets we've found/created
            found_defaults = set()

            # Update existing default presets or create missing ones
            for preset_name, preset_props in default_presets.items():
                # Look for existing preset with this name
                found = False
                for preset in presets:
                    if preset.name == preset_name:
                        # Update existing preset with default values
                        for prop_name, prop_value in preset_props.items():
                            setattr(preset, prop_name, prop_value)
                        found = True
                        found_defaults.add(preset_name)
                        break
                
                # If not found, create it
                if not found:
                    preset = presets.add()
                    preset.name = preset_name
                    for prop_name, prop_value in preset_props.items():
                        setattr(preset, prop_name, prop_value)
                    found_defaults.add(preset_name)

            # Check if UVPM is installed and auto-select UVPM Fast preset
            if hasattr(bpy.context.scene, 'uvpm3_props'):
                # Find UVPM Fast preset index
                for i, p in enumerate(presets):
                    if p.name == "UVPM Fast":
                        bpy.context.scene.uvv_pack_presets_index = i
                        break
                else:
                    # Fallback to first preset if UVPM Fast not found
                    if len(presets) > 0:
                        bpy.context.scene.uvv_pack_presets_index = 0
            else:
                # Set active index to first preset if UVPM not installed
                if len(presets) > 0:
                    bpy.context.scene.uvv_pack_presets_index = 0

    bpy.app.timers.register(init_checker_path, first_interval=0.1)
    bpy.app.timers.register(restore_checker_state, first_interval=0.2)
    bpy.app.timers.register(init_pack_presets, first_interval=0.3)


def unregister():
    # Remove pack preset properties (check if they exist first)
    if hasattr(bpy.types.Scene, 'uvv_pack_presets'):
        del bpy.types.Scene.uvv_pack_presets
    if hasattr(bpy.types.Scene, 'uvv_pack_presets_index'):
        del bpy.types.Scene.uvv_pack_presets_index

    # Remove TD preset properties (check if they exist first)
    if hasattr(bpy.types.Scene, 'uvv_td_presets'):
        del bpy.types.Scene.uvv_td_presets
    if hasattr(bpy.types.Scene, 'uvv_td_presets_index'):
        del bpy.types.Scene.uvv_td_presets_index

    # Remove constraint properties (check if they exist first)
    if hasattr(bpy.types.Scene, 'uvv_constraints'):
        del bpy.types.Scene.uvv_constraints
    if hasattr(bpy.types.Scene, 'uvv_constraints_index'):
        del bpy.types.Scene.uvv_constraints_index

    # Remove stack groups properties (check if they exist first)
    if hasattr(bpy.types.Scene, 'uvv_stack_groups'):
        del bpy.types.Scene.uvv_stack_groups
    if hasattr(bpy.types.Scene, 'uvv_stack_groups_index'):
        del bpy.types.Scene.uvv_stack_groups_index

    # Remove trimsheet properties (check if they exist first)
    if hasattr(bpy.types.Material, 'uvv_trims'):
        del bpy.types.Material.uvv_trims
    if hasattr(bpy.types.Material, 'uvv_trims_index'):
        del bpy.types.Material.uvv_trims_index

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # Remove main settings property (check if it exists first)
    if hasattr(bpy.types.Scene, 'uvv_settings'):
        del bpy.types.Scene.uvv_settings