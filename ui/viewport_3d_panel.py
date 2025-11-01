import bpy
from bpy.types import Panel
from ..properties import get_uvv_settings
from .. import __version__


class UVV_3DViewPanel(Panel):
    """Base panel class for UVV 3D viewport panels"""
    @classmethod
    def poll(cls, context):
        return True  # Always show panels, disable buttons when no mesh object
    
    @classmethod
    def has_valid_object(cls, context):
        """Check if there's a valid mesh object for UV operations"""
        return (context.active_object is not None and 
                context.active_object.type == 'MESH' and
                context.active_object.data is not None)


class UVV_PT_3D_sync(UVV_3DViewPanel):
    """UV Sync panel in 3D Viewport"""
    bl_label = f"🌀 UVV v{__version__}"
    bl_idname = "UVV_PT_3D_sync"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 0

    def draw_header_preset(self, context):
        """Draw buttons on the right side of the panel header"""
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()
        settings = get_uvv_settings()

        # Version availability button (dynamic based on actual version check)
        version_available = settings.latest_version_available

        if version_available:  # Only show if newer version is available
            op = layout.operator("uv.uvv_show_version_info", text="New Update Available")
            op.version = version_available

        # Settings button - automatically aligned to the right, using same icon as Pack/Auto Unwrap
        if icons_coll and "settings" in icons_coll:
            layout.popover(panel="UVV_PT_UVSyncSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            layout.popover(panel="UVV_PT_UVSyncSettings", text="", icon="PREFERENCES")

    def draw(self, context):
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # UV Sync and Isolate Part in same row
        col = layout.column(align=True)
        col.scale_y = 1.2

        row = col.row(align=True)

        # UV Sync toggle (as toggle button)
        tool_settings = context.tool_settings
        if hasattr(tool_settings, 'use_uv_select_sync'):
            sync_enabled = tool_settings.use_uv_select_sync
            row.operator("uv.uvv_toggle_uv_sync", text="UV Sync", icon='UV_SYNC_SELECT', depress=sync_enabled)
        else:
            row.operator("uv.uvv_toggle_uv_sync", text="UV Sync", icon='UV_SYNC_SELECT')

        # Isolate Part button
        if icons_coll and "isolate_islands" in icons_coll:
            row.operator("uv.uvv_isolate_islands", text="Isolate Part", icon_value=icons_coll["isolate_islands"].icon_id)
        else:
            row.operator("uv.uvv_isolate_islands", text="Isolate Part", icon='RESTRICT_VIEW_OFF')


class UVV_PT_3D_unwrap(UVV_3DViewPanel):
    """Unwrap panel in 3D Viewport"""
    bl_label = "Unwrap"
    bl_idname = "UVV_PT_3D_unwrap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 1

    def draw(self, context):
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Unwrap section - no dark background
        col = layout.column(align=True)
        col.scale_y = 1.2

        # Auto Unwrap button with settings popover
        row = col.row(align=True)
        if icons_coll and "auto_unwrap" in icons_coll:
            row.operator("uv.uvv_auto_unwrap", text="Auto Unwrap", icon_value=icons_coll["auto_unwrap"].icon_id)
        else:
            row.operator("uv.uvv_auto_unwrap", text="Auto Unwrap", icon='UV_DATA')

        if icons_coll and "settings" in icons_coll:
            row.popover(panel="UVV_PT_AutoUnwrapSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            row.popover(panel="UVV_PT_AutoUnwrapSettings", text="", icon="PREFERENCES")

        # Triplanar UV button
        row = col.row(align=True)
        if icons_coll and "triplanar" in icons_coll:
            row.operator("uv.uvv_triplanar_mapping", text="Triplanar UV", icon_value=icons_coll["triplanar"].icon_id).type = "Triplanar_UV_Mapping"
        else:
            row.operator("uv.uvv_triplanar_mapping", text="Triplanar UV", icon='CUBE').type = "Triplanar_UV_Mapping"

        # Unwrap and Project Map buttons in same row
        unwrap_row = col.row(align=True)
        unwrap_row.enabled = context.mode == 'EDIT_MESH'
        if icons_coll and "unwrap" in icons_coll:
            unwrap_row.operator("mesh.uvv_unwrap_inplace", text="Unwrap", icon_value=icons_coll["unwrap"].icon_id)
        else:
            unwrap_row.operator("mesh.uvv_unwrap_inplace", text="Unwrap", icon='AUTOMERGE_ON')

        if icons_coll and "camera_unwrap" in icons_coll:
            unwrap_row.operator("uv.uvv_project_unwrap", text="Project Map", icon_value=icons_coll["camera_unwrap"].icon_id)
        else:
            unwrap_row.operator("uv.uvv_project_unwrap", text="Project Map", icon='UV_DATA')


class UVV_PT_3D_seams(UVV_3DViewPanel):
    """Seams panel in 3D Viewport"""
    bl_label = "Seams"
    bl_idname = "UVV_PT_3D_seams"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 2

    def draw_header_preset(self, context):
        """Draw settings button on the right side of the panel header"""
        layout = self.layout
        
        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()
        
        # Settings icon for seam settings - automatically aligned to the right, using same icon as other panels
        if icons_coll and "settings" in icons_coll:
            layout.popover("UVV_PT_SeamSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            layout.popover("UVV_PT_SeamSettings", text="", icon='PREFERENCES')

    def draw(self, context):
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        col = layout.column(align=True)
        col.scale_y = 1.2

        # Seam by Angle (separated on top)
        if icons_coll and "seam" in icons_coll:
            col.operator("uv.uvv_seam_by_angle", text="Seam by Angle", icon_value=icons_coll["seam"].icon_id)
        else:
            col.operator("uv.uvv_seam_by_angle", text="Seam by Angle", icon='EDGESEL')

        # Separator
        col.separator()

        # Weld, Stitch, and Split UV in same row
        row = col.row(align=True)

        # Left group: Weld and Stitch (grouped together)
        weld_stitch_group = row.row(align=True)
        if icons_coll and "match_stitch" in icons_coll:
            weld_stitch_group.operator("mesh.uvv_weld", text="Weld", icon_value=icons_coll["match_stitch"].icon_id)
        else:
            weld_stitch_group.operator("mesh.uvv_weld", text="Weld", icon='AUTOMERGE_ON')

        if icons_coll and "stitch" in icons_coll:
            weld_stitch_group.operator("mesh.uvv_stitch", text="Stitch", icon_value=icons_coll["stitch"].icon_id)
        else:
            weld_stitch_group.operator("mesh.uvv_stitch", text="Stitch", icon='SNAP_EDGE')

        # 4px gap (using separator with custom width)
        row.separator()
        row.separator()

        # Right side: Split UV
        if icons_coll and "split_uv" in icons_coll:
            row.operator("uv.uvv_split", text="Split", icon_value=icons_coll["split_uv"].icon_id)
        else:
            row.operator("uv.uvv_split", text="Split", icon='SCULPTMODE_HLT')


class UVV_PT_3D_constraints(UVV_3DViewPanel):
    """Constraints panel in 3D Viewport"""
    bl_label = "Constraints"
    bl_idname = "UVV_PT_3D_constraints"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 3

    def draw(self, context):
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        col = layout.column(align=True)
        col.scale_y = 1.2

        # Top row: All three constraint buttons in one row
        row = col.row(align=True)

        # Parallel Constraint button
        if icons_coll and "parallel_constraint" in icons_coll:
            row.operator("uv.uvv_parallel_constraint", text="Parallel", icon_value=icons_coll["parallel_constraint"].icon_id)
        else:
            row.operator("uv.uvv_parallel_constraint", text="Parallel", icon='DRIVER_DISTANCE')

        # Horizontal Constraint button
        if icons_coll and "horizontal_constraint" in icons_coll:
            row.operator("uv.uvv_add_horizontal_constraint", text="Horizontal", icon_value=icons_coll["horizontal_constraint"].icon_id)
        else:
            row.operator("uv.uvv_add_horizontal_constraint", text="Horizontal", icon='TRIA_RIGHT')

        # Vertical Constraint button
        if icons_coll and "vertical_constraint" in icons_coll:
            row.operator("uv.uvv_add_vertical_constraint", text="Vertical", icon_value=icons_coll["vertical_constraint"].icon_id)
        else:
            row.operator("uv.uvv_add_vertical_constraint", text="Vertical", icon='TRIA_UP')

        # Collapsible constraint list section
        settings = get_uvv_settings()
        obj = context.active_object

        # Filter constraints by active object
        obj_constraints = []
        if obj:
            for idx, constraint in enumerate(context.scene.uvv_constraints):
                if constraint.object_name == obj.name:
                    obj_constraints.append((idx, constraint))

        # Only show collapsible section if there are constraints
        if len(obj_constraints) > 0:
            # Collapsible header with dark background
            box = layout.box()
            row = box.row()
            row.alignment = 'LEFT'

            # Collapsible arrow and label with object name
            icon = 'DOWNARROW_HLT' if settings.show_constraints_list else 'RIGHTARROW'

            if obj:
                label_text = f"{obj.name} ({len(obj_constraints)})"
            else:
                label_text = f"No Object Selected"

            row.prop(settings, 'show_constraints_list',
                    text="",
                    icon=icon, emboss=False, toggle=True)

            # Mesh icon from outliner (after arrow, before object name)
            row.label(text="", icon='OUTLINER_OB_MESH')

            # Object name with constraint count
            row.label(text=label_text)

            # Show constraint list only when expanded and there are constraints
            if settings.show_constraints_list and len(obj_constraints) > 0:
                for idx, constraint in obj_constraints:
                    row = box.row(align=True)

                    # Enabled checkbox
                    op = row.operator("uv.uvv_toggle_constraint_enabled", text="",
                                    icon='CHECKBOX_HLT' if constraint.enabled else 'CHECKBOX_DEHLT',
                                    emboss=False)
                    op.constraint_index = idx

                    # Context indicator icon (UV or 3D)
                    context_icon = 'UV' if constraint.context_type == 'UV' else 'MESH_DATA'
                    row.label(text="", icon=context_icon)

                    # Constraint type icon - use custom icons when available
                    if constraint.constraint_type == 'HORIZONTAL':
                        if icons_coll and "horizontal_constraint" in icons_coll:
                            row.label(text=constraint.name, icon_value=icons_coll["horizontal_constraint"].icon_id)
                        else:
                            row.label(text=constraint.name, icon='TRIA_RIGHT')
                    elif constraint.constraint_type == 'VERTICAL':
                        if icons_coll and "vertical_constraint" in icons_coll:
                            row.label(text=constraint.name, icon_value=icons_coll["vertical_constraint"].icon_id)
                        else:
                            row.label(text=constraint.name, icon='TRIA_UP')
                    else:  # PARALLEL
                        if icons_coll and "parallel_constraint" in icons_coll:
                            row.label(text=constraint.name, icon_value=icons_coll["parallel_constraint"].icon_id)
                        else:
                            row.label(text=constraint.name, icon='DRIVER_DISTANCE')

                    # Select button
                    op = row.operator("uv.uvv_select_constraint_edges", text="", icon='RESTRICT_SELECT_OFF')
                    op.constraint_index = idx

                    # Delete button
                    op = row.operator("uv.uvv_delete_constraint", text="", icon='X')
                    op.constraint_index = idx


class UVV_PT_3D_visualize(UVV_3DViewPanel):
    """Visualize panel in 3D Viewport"""
    bl_label = "Visualize"
    bl_idname = "UVV_PT_3D_visualize"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 4  # Below constraints (order 3)

    def get_pattern_icon_id(self, pattern_type, icons_coll):
        """Get the appropriate icon ID for the pattern type"""
        if not icons_coll:
            return None
            
        icon_mapping = {
            'UV_GRID': 'uv_checker_thumbnail_blendergrid',
            'COLOR_GRID': 'uv_checker_thumbnail_blendercolorgrid', 
            'ARROW_GRID': 'uv_checker_thumbnail_arrowgrid'
        }
        
        icon_name = icon_mapping.get(pattern_type, 'uv_checker_thumbnail')
        if icon_name in icons_coll:
            return icons_coll[icon_name].icon_id
        return None

    def draw(self, context):
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Get settings
        from ..properties import get_uvv_settings
        settings = get_uvv_settings()

        # Main toolbar box with dark background (matching Trimsheet style)
        box = layout.box()
        box.scale_y = 1.2
        row = box.row(align=True)

        # Use comprehensive state detection instead of simple material check
        from ..checker.checker import get_checker_state_for_ui
        b_is_checked = get_checker_state_for_ui(context)

        # Don't auto-sync during draw - it modifies data which is not allowed
        # sync_checker_state(context)

        # LEFT SIDE: UV Checker button
        if icons_coll and "texture" in icons_coll:
            row.operator(
                "view3d.uvv_checker_toggle",
                text="UV Checker",
                icon_value=icons_coll["texture"].icon_id,
                depress=b_is_checked
            )
        else:
            row.operator(
                "view3d.uvv_checker_toggle",
                text="UV Checker",
                icon='TEXTURE',
                depress=b_is_checked
            )

        # MIDDLE: Pattern type dropdown (replaces old file selection dropdown)
        if settings.use_custom_image:
            if icons_coll and "uv_checker_thumbnail" in icons_coll:
                row.prop(settings, 'override_image_name', text='', icon_value=icons_coll["uv_checker_thumbnail"].icon_id)
            else:
                row.prop(settings, 'override_image_name', text='', icon='IMAGE_DATA')
        else:
            # Pattern type dropdown with pattern-specific icon
            pattern_icon_id = self.get_pattern_icon_id(settings.checker_pattern_type, icons_coll)
            if pattern_icon_id:
                row.prop(settings, "checker_pattern_type", text='', icon_value=pattern_icon_id)
            else:
                row.prop(settings, "checker_pattern_type", text='', icon='IMAGE_DATA')

        # RIGHT SIDE: Settings button - opens popover with checker settings
        if icons_coll and "settings" in icons_coll:
            row.popover(panel="UVV_PT_3D_CheckerSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            row.popover(panel="UVV_PT_3D_CheckerSettings", text="", icon="PREFERENCES")

        # Additional settings below the toolbar
        col = layout.column(align=True)
        
        # Filtration System
        if settings.chk_rez_filter and not settings.use_custom_image:
            self.draw_filtration_sys(context, col, settings)

        if settings.use_custom_image:
            row = col.row(align=True)
            row.operator("wm.uvv_get_checker_override_image", icon="IMPORT", text='')

        # Display mode buttons (always visible, disabled when not in Edit Mode)
        self.draw_display_buttons(context, col)

    def draw_display_buttons(self, context, layout):
        """Draw UV debug dropdown menu (Default, Stretched, Flipped)"""
        col = layout.column(align=True)
        col.separator()

        # Debug UVs title (above dropdown)
        col.label(text="Debug UVs")

        # Debug UVs dropdown (below title) - same height as UV Checker button
        row = col.row(align=True)
        row.scale_y = 1.2  # Same scale as UV Checker toolbar
        
        # Check if we're in Edit Mode (for 3D viewport, check if in Edit Mode)
        is_edit_mode = context.mode == 'EDIT_MESH'
        row.enabled = is_edit_mode

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()
        
        # Get current debug mode
        settings = context.scene.uvv_settings
        
        # Dropdown with icon inside
        if icons_coll and "debug_uvs" in icons_coll:
            row.prop(settings, "debug_uv_mode", text="", icon_value=icons_coll["debug_uvs"].icon_id)
        else:
            row.prop(settings, "debug_uv_mode", text="", icon='UV')

    def draw_filtration_sys(self, context, layout, settings):
        """Draw resolution filtration system"""
        col = layout.column(align=True)

        row = col.row(align=True)
        col_inner = row.column(align=True)
        row.prop(settings, "sizes_x", text="", index=0)
        col_inner = row.column(align=True)
        if settings.lock_axes:
            lock_icon = "LOCKED"
        else:
            lock_icon = "UNLOCKED"
        col_inner.prop(settings, "lock_axes", icon=lock_icon, icon_only=True)
        col_inner = row.column(align=True)
        col_inner.enabled = not settings.lock_axes
        col_inner.prop(settings, "sizes_y", text="", index=0)
        row.prop(settings, "chk_orient_filter", icon="EVENT_O", icon_only=True)


class UVV_PT_3D_CheckerSettings(Panel):
    """3D Viewport Checker settings popover panel"""
    bl_label = "Checker Settings"
    bl_idname = "UVV_PT_3D_CheckerSettings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_options = {"INSTANCED"}

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        col = layout.column(align=True)

        # Custom Resolution (for procedural patterns)
        if settings.checker_pattern_type in ['UV_GRID', 'COLOR_GRID']:
            col.separator()
            col.label(text="Custom Resolution:")
            box = col.box()
            box_col = box.column(align=True)
            
            # Uniform scale toggle
            box_col.prop(settings, 'checker_uniform_scale', text="Uniform Scale")
            
            # Resolution inputs
            if settings.checker_uniform_scale:
                # Single input for uniform scaling
                box_col.prop(settings, 'checker_custom_resolution', text="Resolution", index=0)
            else:
                # Separate X and Y inputs
                box_col.prop(settings, 'checker_custom_resolution', text="Resolution")
            
            # Resolution control buttons
            button_row = box_col.row(align=True)
            
            # Reset button (with 4px separator)
            reset_op = button_row.operator("uv.uvv_reset_resolution", text="Reset", icon='LOOP_BACK')
            
            # 4px separator
            button_row.separator(factor=0.1)
            
            # Double and Half buttons (grouped together)
            math_buttons = button_row.row(align=True)
            math_buttons.operator("uv.uvv_double_resolution", text="Double", icon='TRIA_UP')
            math_buttons.operator("uv.uvv_half_resolution", text="Half", icon='TRIA_DOWN')

        # Visibility toggles section
        col.separator()
        col.label(text="Checker Visibility:")
        box = col.box()
        
        # UV Editor visibility toggle
        box.prop(settings, 'checker_show_in_uv_editor', text="Show in UV Editor")
        
        # 3D View visibility toggle
        box.prop(settings, 'checker_show_in_3d_view', text="Show in 3D View")


classes = [
    UVV_PT_3D_sync,
    UVV_PT_3D_unwrap,
    UVV_PT_3D_seams,
    UVV_PT_3D_constraints,
    UVV_PT_3D_visualize,
    UVV_PT_3D_CheckerSettings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
