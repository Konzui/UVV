import bpy
from bpy.types import Panel, Menu, UIList
from ..properties import get_uvv_settings
from .. import __version__


class UVV_UL_stack_groups_list(UIList):
    """UIList for displaying stack groups"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Draw a single stack group item"""
        group = item

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Color indicator
            row = layout.row(align=True)
            row.scale_x = 0.5
            row.prop(group, 'color', text='', icon='LAYER_ACTIVE')

            # Group name (editable) - like trimsheet
            row = layout.row(align=True)
            row.prop(group, 'name', text='', emboss=False)

            # Island count (separate row for better layout)
            row = layout.row(align=True)
            island_count = group.cached_island_count
            count_text = f"({island_count} island{'s' if island_count != 1 else ''})"
            row.label(text=count_text)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="")


class UVVPanel(Panel):
    """Base panel class for UVV panels"""
    @classmethod
    def poll(cls, context):
        return context.area.spaces.active.mode == "UV"
    
    @classmethod
    def has_valid_object(cls, context):
        """Check if there's a valid mesh object for UV operations"""
        return (context.active_object is not None and 
                context.active_object.type == 'MESH' and
                context.active_object.data is not None)


class UVV_PT_UVSyncSettings(Panel):
    """UV Sync Settings popover panel"""
    bl_label = "UV Sync Settings"
    bl_idname = "UVV_PT_UVSyncSettings"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'
    bl_options = {"INSTANCED"}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("uv.uvv_open_documentation", text="Documentation", icon='HELP')
        col.operator("uv.uvv_open_changelog", text="Changelog", icon='TEXT')
        col.operator("uv.uvv_open_addon_hotkeys", text="Hotkeys", icon='KEYINGSET')
        
        # Check for Updates button
        settings = get_uvv_settings()
        if settings.version_check_in_progress:
            col.operator("uv.uvv_check_for_updates", text="Checking...", icon='TIME')
        else:
            col.operator("uv.uvv_check_for_updates", text="Check for Updates", icon='FILE_REFRESH')
        
        # Debug button (for troubleshooting)
        col.operator("uv.uvv_debug_version_check", text="Debug Version Check", icon='CONSOLE')


class UVV_PT_sync(UVVPanel):
    """UV Sync panel"""
    bl_label = f"🌀 UVV v{__version__}"
    bl_idname = "UVV_PT_sync"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 1

    def draw_header_preset(self, context):
        """Draw buttons on the right side of the panel header"""
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()
        settings = get_uvv_settings()
        settings = get_uvv_settings()
        settings = get_uvv_settings()
        settings = get_uvv_settings()
        settings = get_uvv_settings()

        # Version availability button (dynamic based on actual version check)
        settings = get_uvv_settings()
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
        layout.operator_context = 'INVOKE_DEFAULT'
        settings = get_uvv_settings()

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # UV Sync and Isolate Island row
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

        # Isolate Island button
        if icons_coll and "isolate_islands" in icons_coll:
            row.operator("uv.uvv_isolate_islands", text="Isolate Island", icon_value=icons_coll["isolate_islands"].icon_id)
        else:
            row.operator("uv.uvv_isolate_islands", text="Isolate Island", icon='RESTRICT_VIEW_OFF')


class UVV_PT_unwrap(UVVPanel):
    """Unwrap panel"""
    bl_label = "Unwrap"
    bl_idname = "UVV_PT_unwrap"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        settings = get_uvv_settings()

        # Check if we have a valid object
        has_valid_obj = self.has_valid_object(context)

        # Show helpful message if no object
        if not has_valid_obj:
            col = layout.column(align=True)
            col.scale_y = 1.2
            col.label(text="Select a mesh object to use UV tools", icon='INFO')
            col.separator()

            # Disable all buttons by creating a disabled column
            disabled_col = col.column(align=True)
            disabled_col.enabled = False
            self._draw_disabled_content(context, disabled_col)
            return

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

        # Unwrap and Project Map buttons in same row
        unwrap_row = col.row(align=True)
        unwrap_row.enabled = context.mode == 'EDIT_MESH'
        if icons_coll and "unwrap" in icons_coll:
            unwrap_row.operator("uv.uvv_unwrap_inplace", text="Unwrap", icon_value=icons_coll["unwrap"].icon_id)
        else:
            unwrap_row.operator("uv.uvv_unwrap_inplace", text="Unwrap", icon='UV_DATA')

        if icons_coll and "camera_unwrap" in icons_coll:
            unwrap_row.operator("uv.uvv_project_unwrap", text="Project Map", icon_value=icons_coll["camera_unwrap"].icon_id)
        else:
            unwrap_row.operator("uv.uvv_project_unwrap", text="Project Map", icon='UV_DATA')

    def _draw_disabled_content(self, context, layout):
        """Draw disabled content when no valid object is selected"""
        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Unwrap section - no dark background
        col = layout.column(align=True)
        col.scale_y = 1.2

        # Auto Unwrap button with settings popover (disabled)
        row = col.row(align=True)
        if icons_coll and "auto_unwrap" in icons_coll:
            row.operator("uv.uvv_auto_unwrap", text="Auto Unwrap", icon_value=icons_coll["auto_unwrap"].icon_id)
        else:
            row.operator("uv.uvv_auto_unwrap", text="Auto Unwrap", icon='UV_DATA')

        if icons_coll and "settings" in icons_coll:
            row.popover(panel="UVV_PT_AutoUnwrapSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            row.popover(panel="UVV_PT_AutoUnwrapSettings", text="", icon="PREFERENCE")

        # Unwrap and Project Map buttons in same row (disabled)
        unwrap_row = col.row(align=True)
        if icons_coll and "unwrap" in icons_coll:
            unwrap_row.operator("uv.uvv_unwrap_inplace", text="Unwrap", icon_value=icons_coll["unwrap"].icon_id)
        else:
            unwrap_row.operator("uv.uvv_unwrap_inplace", text="Unwrap", icon='UV_DATA')

        if icons_coll and "camera_unwrap" in icons_coll:
            unwrap_row.operator("uv.uvv_project_unwrap", text="Project Map", icon_value=icons_coll["camera_unwrap"].icon_id)
        else:
            unwrap_row.operator("uv.uvv_project_unwrap", text="Project Map", icon='UV_DATA')


class UVV_PT_seams(UVVPanel):
    """Seams panel"""
    bl_label = "Seams"
    bl_idname = "UVV_PT_seams"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 4

    def draw(self, context):
        layout = self.layout

        # Check if we have a valid object
        has_valid_obj = self.has_valid_object(context)
        
        # Show helpful message if no object
        if not has_valid_obj:
            col = layout.column(align=True)
            col.scale_y = 1.2
            col.label(text="Select a mesh object to use seam tools", icon='INFO')
            col.separator()
            
            # Disable all buttons by creating a disabled column
            disabled_col = col.column(align=True)
            disabled_col.enabled = False
            self._draw_disabled_seams_content(context, disabled_col)
            return

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        col = layout.column(align=True)
        col.scale_y = 1.2

        # Weld, Stitch, and Split UV in same row
        row = col.row(align=True)

        # Left group: Weld and Stitch (grouped together)
        weld_stitch_group = row.row(align=True)
        if icons_coll and "match_stitch" in icons_coll:
            weld_stitch_group.operator("uv.uvv_weld", text="Weld", icon_value=icons_coll["match_stitch"].icon_id)
        else:
            weld_stitch_group.operator("uv.uvv_weld", text="Weld", icon='AUTOMERGE_ON')

        if icons_coll and "stitch" in icons_coll:
            weld_stitch_group.operator("uv.uvv_stitch", text="Stitch", icon_value=icons_coll["stitch"].icon_id)
        else:
            weld_stitch_group.operator("uv.uvv_stitch", text="Stitch", icon='SNAP_EDGE')

        # 4px gap (using separator with custom width)
        row.separator()
        row.separator()

        # Right side: Split UV
        if icons_coll and "split_uv" in icons_coll:
            row.operator("uv.uvv_split", text="Split", icon_value=icons_coll["split_uv"].icon_id)
        else:
            row.operator("uv.uvv_split", text="Split", icon='SCULPTMODE_HLT')

    def _draw_disabled_seams_content(self, context, layout):
        """Draw disabled seams content when no valid object is selected"""
        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        col = layout.column(align=True)
        col.scale_y = 1.2

        # Weld, Stitch, and Split UV in same row (disabled)
        row = col.row(align=True)

        # Left group: Weld and Stitch (grouped together) (disabled)
        weld_stitch_group = row.row(align=True)
        if icons_coll and "match_stitch" in icons_coll:
            weld_stitch_group.operator("uv.uvv_weld", text="Weld", icon_value=icons_coll["match_stitch"].icon_id)
        else:
            weld_stitch_group.operator("uv.uvv_weld", text="Weld", icon='AUTOMERGE_ON')

        if icons_coll and "stitch" in icons_coll:
            weld_stitch_group.operator("uv.uvv_stitch", text="Stitch", icon_value=icons_coll["stitch"].icon_id)
        else:
            weld_stitch_group.operator("uv.uvv_stitch", text="Stitch", icon='SNAP_EDGE')

        # 4px gap (using separator with custom width)
        row.separator()
        row.separator()

        # Right side: Split UV (disabled)
        if icons_coll and "split_uv" in icons_coll:
            row.operator("uv.uvv_split", text="Split", icon_value=icons_coll["split_uv"].icon_id)
        else:
            row.operator("uv.uvv_split", text="Split", icon='SCULPTMODE_HLT')


class UVV_PT_constraints(UVVPanel):
    """Constraints panel"""
    bl_label = "Constraints"
    bl_idname = "UVV_PT_constraints"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 5

    def draw(self, context):
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Settings used across this panel
        settings = get_uvv_settings()

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

        # Only show dark background if there are constraints
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

            # Show constraint list only when expanded
            if settings.show_constraints_list:
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


class UVV_PT_modify(UVVPanel):
    """Modify panel"""
    bl_label = "Modify"
    bl_idname = "UVV_PT_modify"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 6

    def draw(self, context):
        layout = self.layout

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        col = layout.column(align=True)
        col.scale_y = 1.2

        # Row 1: Normalize with directional arrows (Orient-style layout)
        row = col.row(align=True)
        if icons_coll and "normalize" in icons_coll:
            row.operator("uv.uvv_normalize", text="Normalize", icon_value=icons_coll["normalize"].icon_id).axis = 'XY'
        else:
            row.operator("uv.uvv_normalize", text="Normalize", icon='FULLSCREEN_ENTER').axis = 'XY'

        sub = row.row(align=True)
        sub.scale_x = 1.2
        if icons_coll and "arrow_right" in icons_coll:
            sub.operator("uv.uvv_normalize", text='', icon_value=icons_coll["arrow_right"].icon_id).axis = 'X'
        else:
            sub.operator("uv.uvv_normalize", text='', icon='TRIA_RIGHT').axis = 'X'

        if icons_coll and "arrow_top" in icons_coll:
            sub.operator("uv.uvv_normalize", text='', icon_value=icons_coll["arrow_top"].icon_id).axis = 'Y'
        else:
            sub.operator("uv.uvv_normalize", text='', icon='TRIA_UP').axis = 'Y'

        # Row 2: Relax, Quadrify, Straighten
        row = col.row(align=True)
        if icons_coll and "relax" in icons_coll:
            row.operator("uv.univ_relax", text="Relax", icon_value=icons_coll["relax"].icon_id)
        else:
            row.operator("uv.univ_relax", text="Relax", icon='MESH_CIRCLE')

        if icons_coll and "quadrify" in icons_coll:
            row.operator("uv.uvv_quadrify", icon_value=icons_coll["quadrify"].icon_id)
        else:
            row.operator("uv.uvv_quadrify", icon='IPO_LINEAR')

        if icons_coll and "straighten" in icons_coll:
            row.operator("uv.uvv_straighten", text="Straighten", icon_value=icons_coll["straighten"].icon_id)
        else:
            row.operator("uv.uvv_straighten", text="Straighten", icon='IPO_LINEAR')


class UVV_PT_stack(UVVPanel):
    """Stack panel"""
    bl_label = "Stack"
    bl_idname = "UVV_PT_stack"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 7

    def draw(self, context):
        layout = self.layout
        settings = context.scene.uvv_settings

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        col = layout.column(align=True)
        col.scale_y = 1.2

        # Top row: Create Group (icon only), Auto Group (with dropdown), Select
        # Use align=True with manual separators for controlled gaps
        row = col.row(align=True)

        # Create Group button (icon only - using add.png) - WIDER
        create_btn = row.row(align=True)
        create_btn.scale_x = 1.5
        if icons_coll and "add" in icons_coll:
            create_btn.operator("uv.uvv_create_stack_group", text="", icon_value=icons_coll["add"].icon_id)
        else:
            create_btn.operator("uv.uvv_create_stack_group", text="", icon='ADD')

        # Smaller gap (half of previous)
        row.separator(factor=0.25)

        # Auto Group button with dropdown menu (using auto_group.png)
        # EXACT COPY of texel density pattern - button and menu directly on row
        if icons_coll and "auto_group" in icons_coll:
            row.operator("uv.uvv_group_by_similarity", text="Auto Group", icon_value=icons_coll["auto_group"].icon_id)
        else:
            row.operator("uv.uvv_group_by_similarity", text="Auto Group", icon='GROUP_BONE')
        # Dropdown menu - same as texel density
        row.menu("UVV_MT_auto_group_settings", text="", icon='DOWNARROW_HLT')

        # Small gap
        row.separator(factor=0.5)

        # Select button (using select.png) - selects similar islands based on selection - SMALLER
        select_btn = row.row(align=True)
        select_btn.scale_x = 0.7
        if icons_coll and "select" in icons_coll:
            select_btn.operator("uv.uvv_select_similar", text="Select", icon_value=icons_coll["select"].icon_id)
        else:
            select_btn.operator("uv.uvv_select_similar", text="Select", icon='SELECT_SET')

        # Stack Groups section
        col.separator()
        box = layout.box()
        box_col = box.column(align=True)

        # Header row with collapsible arrow, label, and buttons
        header_row = box_col.row(align=True)
        header_row.alignment = 'LEFT'

        # Collapsible arrow
        icon = 'DOWNARROW_HLT' if settings.show_stack_groups_list else 'RIGHTARROW'
        header_row.prop(settings, 'show_stack_groups_list',
                      text="",
                      icon=icon, emboss=False, toggle=True)

        # "Stack Groups" label
        header_row.label(text="Stack Groups")

        # Spacer
        header_row.separator()

        # Settings button on the right
        buttons_row = header_row.row(align=True)
        buttons_row.alignment = 'RIGHT'

        # Settings button
        if icons_coll and "settings" in icons_coll:
            buttons_row.popover(panel="UVV_PT_StackSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            buttons_row.popover(panel="UVV_PT_StackSettings", text="", icon="PREFERENCES")

        # Show group list when expanded
        if settings.show_stack_groups_list:
            # Stack groups list (trimsheet style) - always show when expanded
            scene = context.scene
            stack_groups = scene.uvv_stack_groups

            row = box_col.row()
            row.template_list(
                "UVV_UL_stack_groups_list", "",
                scene, "uvv_stack_groups",
                scene, "uvv_stack_groups_index",
                rows=1
            )

            # List controls (trimsheet style) - simplified
            col_controls = row.column(align=True)

            # Get icon collection for arrow down icon
            from .. import get_icons_set
            icons_coll_controls = get_icons_set()

            # Assign to Stack Group button (using arrow_bot.png for arrow down)
            if icons_coll_controls and "arrow_bot" in icons_coll_controls:
                col_controls.operator("uv.uvv_assign_to_active_stack_group", icon_value=icons_coll_controls["arrow_bot"].icon_id, text="")
            else:
                col_controls.operator("uv.uvv_assign_to_active_stack_group", icon='TRIA_DOWN', text="")

            # Select active stack group button (using select.png icon)
            if icons_coll_controls and "select" in icons_coll_controls:
                col_controls.operator("uv.uvv_select_only_active_stack_group", icon_value=icons_coll_controls["select"].icon_id, text="")
            else:
                col_controls.operator("uv.uvv_select_only_active_stack_group", icon='RESTRICT_SELECT_OFF', text="")

            # Stack active stack group button (using stack.png icon)
            if icons_coll_controls and "stack" in icons_coll_controls:
                op = col_controls.operator("uv.uvv_stack_active_group", icon_value=icons_coll_controls["stack"].icon_id, text="")
            else:
                op = col_controls.operator("uv.uvv_stack_active_group", icon='SORTSIZE', text="")

            # Only show delete buttons when there are groups
            if len(stack_groups) > 0:
                col_controls.separator()
                col_controls.operator("uv.uvv_delete_active_stack_group", icon='REMOVE', text="")
                col_controls.operator("uv.uvv_remove_all_stack_groups", icon='TRASH', text="")


class UVV_PT_transform(UVVPanel):
    """Transform panel"""
    bl_label = "Transform"
    bl_idname = "UVV_PT_transform"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Row 1: Align buttons - Split into 2 groups (Left, Center H, Right) | gap | (Top, Center V, Bottom)
        col = layout.column(align=True)
        col.scale_y = 1.2
        row = col.row(align=True)
        row.scale_x = 3

        # Group 1: Left, Center H, Right
        if icons_coll and "align_left" in icons_coll:
            row.operator("uv.uvv_align_left", text="", icon_value=icons_coll["align_left"].icon_id)
        else:
            row.operator("uv.uvv_align_left", text="", icon='TRIA_LEFT')

        if icons_coll and "align_center_h" in icons_coll:
            row.operator("uv.uvv_align_center_horizontal", text="", icon_value=icons_coll["align_center_h"].icon_id)
        else:
            row.operator("uv.uvv_align_center_horizontal", text="", icon='PIVOT_MEDIAN')

        if icons_coll and "align_right" in icons_coll:
            row.operator("uv.uvv_align_right", text="", icon_value=icons_coll["align_right"].icon_id)
        else:
            row.operator("uv.uvv_align_right", text="", icon='TRIA_RIGHT')

        # Gap between groups
        row.separator(factor=0.25)

        # Group 2: Top, Center V, Bottom
        if icons_coll and "align_top" in icons_coll:
            row.operator("uv.uvv_align_top", text="", icon_value=icons_coll["align_top"].icon_id)
        else:
            row.operator("uv.uvv_align_top", text="", icon='TRIA_UP')

        if icons_coll and "align_center_v" in icons_coll:
            row.operator("uv.uvv_align_center_vertical", text="", icon_value=icons_coll["align_center_v"].icon_id)
        else:
            row.operator("uv.uvv_align_center_vertical", text="", icon='PIVOT_MEDIAN')

        if icons_coll and "align_bottom" in icons_coll:
            row.operator("uv.uvv_align_bottom", text="", icon_value=icons_coll["align_bottom"].icon_id)
        else:
            row.operator("uv.uvv_align_bottom", text="", icon='TRIA_DOWN')

        # Row 2: Rotation and Mirror - Split into 2 groups (Rotation angle, Rotate) | gap | (Flip H, Flip V)
        col = layout.column(align=True)
        col.scale_y = 1.2
        row = col.row(align=True)
        row.scale_x = 3

        # Group 1: Rotation angle input and Rotate button
        row.prop(settings, "rotation_angle", text="")

        if icons_coll and "rotate_transform" in icons_coll:
            row.operator("uv.uvv_rotate_90", text="", icon_value=icons_coll["rotate_transform"].icon_id)
        else:
            row.operator("uv.uvv_rotate_90", text="", icon='FILE_REFRESH')

        # Gap between groups (matching align row gap)
        row.separator(factor=0.25)

        # Group 2: Flip H and Flip V
        if icons_coll and "flip_h" in icons_coll:
            row.operator("uv.uvv_mirror_horizontal", text="", icon_value=icons_coll["flip_h"].icon_id)
        else:
            row.operator("uv.uvv_mirror_horizontal", text="", icon='MOD_MIRROR')

        if icons_coll and "flip_v" in icons_coll:
            row.operator("uv.uvv_mirror_vertical", text="", icon_value=icons_coll["flip_v"].icon_id)
        else:
            row.operator("uv.uvv_mirror_vertical", text="", icon='MOD_MIRROR')

        # Separator before orient
        layout.separator()

        # Row 4: Orient section - 3 buttons in a row (Orient, Horizontal, Vertical)
        col = layout.column(align=True)
        col.scale_y = 1.2
        row = col.row(align=True)
        if icons_coll and "orient" in icons_coll:
            row.operator('uv.uvv_orient', text="Orient", icon_value=icons_coll["orient"].icon_id).edge_dir = 'BOTH'
        else:
            row.operator('uv.uvv_orient', text="Orient", icon='ORIENTATION_NORMAL').edge_dir = 'BOTH'

        sub = row.row(align=True)
        sub.scale_x = 1.2
        if icons_coll and "arrow_right" in icons_coll:
            sub.operator('uv.uvv_orient', text='', icon_value=icons_coll["arrow_right"].icon_id).edge_dir = 'HORIZONTAL'
        else:
            sub.operator('uv.uvv_orient', text='', icon='TRIA_RIGHT').edge_dir = 'HORIZONTAL'

        if icons_coll and "arrow_top" in icons_coll:
            sub.operator('uv.uvv_orient', text='', icon_value=icons_coll["arrow_top"].icon_id).edge_dir = 'VERTICAL'
        else:
            sub.operator('uv.uvv_orient', text='', icon='TRIA_UP').edge_dir = 'VERTICAL'


class UVV_PT_pack(UVVPanel):
    """Pack panel"""
    bl_label = "Pack"
    bl_idname = "UVV_PT_pack"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 8

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Pack Islands button with icon based on active packer (Blender/UVPackmaster)
        col = layout.column(align=True)
        col.scale_y = 1.2
        row = col.row(align=True)

        # Use Blender or UVPackmaster icon based on settings
        if settings.use_uvpm:
            # UVPackmaster mode
            if icons_coll and "uvpackmaster" in icons_coll:
                row.operator("uv.uvv_pack", text="Pack Islands", icon_value=icons_coll["uvpackmaster"].icon_id)
            else:
                row.operator("uv.uvv_pack", text="Pack Islands", icon='PACKAGE')
        else:
            # Native Blender mode
            if icons_coll and "blender" in icons_coll:
                row.operator("uv.uvv_pack", text="Pack Islands", icon_value=icons_coll["blender"].icon_id)
            else:
                row.operator("uv.uvv_pack", text="Pack Islands", icon='BLENDER')

        # Settings popover
        if icons_coll and "settings" in icons_coll:
            row.popover(panel="UVV_PT_PackSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            row.popover(panel="UVV_PT_PackSettings", text="", icon="PREFERENCES")

        # Preset dropdown connected to button above
        presets = context.scene.uvv_pack_presets
        index = context.scene.uvv_pack_presets_index

        # Create a menu-style dropdown
        preset_row = col.row(align=True)
        preset_row.scale_y = 0.9

        if presets and len(presets) > 0 and 0 <= index < len(presets):
            # Show current preset name and open menu
            preset_row.menu("UVV_MT_PackPresetMenu", text=presets[index].name, icon='PRESET')
        else:
            preset_row.menu("UVV_MT_PackPresetMenu", text="Select Preset", icon='PRESET')

        # UV Coverage
        self.draw_uv_coverage(context, layout, settings)

    def draw_uv_coverage(self, context, layout, settings):
        """Draw UV coverage display"""
        col = layout.column(align=True)

        # UV Coverage and refresh button in same row
        row = col.row(align=True)
        coverage_value = round(settings.uv_coverage, 2)
        row.label(text=f"Fill: {coverage_value}%")
        row.operator("uv.uvv_get_uv_coverage", icon="FILE_REFRESH", text='')


class UVV_MT_PackPresetMenu(Menu):
    """Pack preset selection menu"""
    bl_label = "Pack Presets"
    bl_idname = "UVV_MT_PackPresetMenu"

    def draw(self, context):
        layout = self.layout
        presets = context.scene.uvv_pack_presets

        if not presets or len(presets) == 0:
            layout.label(text="No presets available", icon='INFO')
        else:
            for i, preset in enumerate(presets):
                op = layout.operator("uv.uvv_apply_pack_preset", text=preset.name)
                op.preset_index = i


class UVV_PT_PackSettings(Panel):
    """Pack settings popover panel"""
    bl_label = "Pack Settings"
    bl_idname = "UVV_PT_PackSettings"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        col = layout.column(align=True)

        # === PRESETS SECTION ===
        box = col.box()

        presets_row = box.row(align=True)
        presets = context.scene.uvv_pack_presets
        index = context.scene.uvv_pack_presets_index

        # Add new preset button (left side)
        presets_row.operator("uv.uvv_add_pack_preset", text='', icon='ADD')

        # Preset name input showing current preset name
        if presets and 0 <= index < len(presets):
            current_preset = presets[index]
            # Show current preset name in the input field
            name_field = presets_row.row(align=True)
            name_field.prop(current_preset, 'name', text='')
        else:
            presets_row.label(text="No Preset")

        # Preset dropdown menu (icon only)
        presets_row.menu("UVV_MT_PackPresetMenu", text='', icon='DOWNARROW_HLT')

        # Save button
        presets_row.operator("uv.uvv_save_pack_preset", text='', icon='FILE_TICK')

        # Delete button
        presets_row.operator("uv.uvv_delete_pack_preset", text='', icon='TRASH')

        # Reset presets button (all the way to the right, icon only)
        presets_row.operator("uv.uvv_reset_pack_presets", text='', icon='FILE_REFRESH')

        col.separator()

        # UVPackmaster toggle
        uvpm_available = hasattr(context.scene, 'uvpm3_props')
        if uvpm_available:
            col.prop(settings, 'use_uvpm')
            col.separator()
        
        # Show pack options based on mode
        if settings.use_uvpm:
            if uvpm_available:
                # UVPM mode - show full UVPackmaster settings (UNIV 1:1 copy)
                self.draw_uvpm(col, settings)
            else:
                col.label(text='UVPackmaster not found')
        else:
            # Native Blender mode
            if bpy.app.version >= (3, 6, 0):
                # === Shape method (Exact/Fast) with border ===
                box = col.box()
                row = box.row(align=True)
                row.prop(settings, 'shape_method', expand=True)

                col.separator(factor=0.5)

                # === SCALE BOX ===
                box = col.box()
                box_col = box.column(align=True)
                box_col.prop(settings, 'scale', text='Scale', toggle=False)

                # Normalize (only visible when Scale is enabled)
                if settings.scale:
                    # Add indentation
                    split = box_col.split(factor=0.1, align=True)
                    split.label(text='')  # Empty space for indent
                    split.prop(settings, 'normalize_islands', text='Normalize', toggle=False)

                col.separator(factor=0.5)

                # === ROTATE BOX ===
                box = col.box()
                box_col = box.column(align=True)
                box_col.prop(settings, 'rotate', text='Rotate', toggle=False)

                # Rotation Method (only visible when Rotate is enabled)
                if settings.rotate:
                    # Add indentation using split with factor
                    split = box_col.split(factor=0.1, align=True)
                    split.label(text='')  # Empty space for indent
                    split.prop(settings, 'rotate_method', text='')

                col.separator(factor=0.5)

                # === LOCK GROUP ===
                box = col.box()
                box.label(text="Lock")
                box_col = box.column(align=True)

                # Lock checkboxes in same row
                row = box_col.row(align=True)
                row.prop(settings, 'pin', text='Pinned Islands', toggle=False)
                row.prop(settings, 'merge_overlap', text='Overlaps', toggle=False)

                col.separator(factor=0.5)

                # === MISC GROUP ===
                box = col.box()
                box.label(text="Misc")
                box_col = box.column(align=True)

                # Global Size row with lock
                row = box_col.row(align=True)
                row.label(text='Global Size')
                size_row = box_col.row(align=True)
                size_row.prop(settings, 'size_x', text='')
                size_row.prop(settings, 'lock_size', text='', icon='LOCKED' if settings.lock_size else 'UNLOCKED')
                size_row.prop(settings, 'size_y', text='')

                box_col.separator()

                # Padding
                box_col.prop(settings, 'padding', slider=True)

                box_col.separator()

                # Pack to - label and dropdown in separate rows
                box_col.label(text='Pack to')
                box_col.prop(settings, 'udim_source', text='')

            else:
                # Blender < 3.6
                col.prop(settings, 'rotate', toggle=True)

        col.separator()

    def draw_uvpm(self, layout, settings):
        """Draw UVPackmaster settings - matching native design"""
        uvpm_settings = bpy.context.scene.uvpm3_props

        if hasattr(uvpm_settings, 'default_main_props'):
            uvpm_main_props = uvpm_settings.default_main_props
        else:
            uvpm_main_props = uvpm_settings

        # === SCALE BOX ===
        box = layout.box()
        box_col = box.column(align=True)
        box_col.prop(settings, 'scale', text='Scale', toggle=False)

        # Child settings under Scale (only visible when Scale is enabled)
        if settings.scale:
            # Mixed Scale
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'heuristic_allow_mixed_scales', text='Mixed Scale', toggle=False)

            # Normalize
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'normalize_scale', text='Normalize', toggle=False)

        layout.separator(factor=0.5)

        # === ROTATION BOX ===
        box = layout.box()
        box_col = box.column(align=True)
        box_col.prop(uvpm_main_props, 'rotation_enable', text='Rotate', toggle=False)

        # Rotation settings (only visible when Rotation is enabled)
        if uvpm_main_props.rotation_enable:
            # Add indentation for child settings
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'pre_rotation_disable', text='Pre-Rotation Disable', toggle=False)

            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'rotation_step', text='Rotation Step')

        layout.separator(factor=0.5)

        # === FLIP BOX ===
        box = layout.box()
        box.prop(uvpm_main_props, 'flipping_enable', text='Flip', toggle=False)

        layout.separator(factor=0.5)

        # === STACK BOX ===
        box = layout.box()
        box_col = box.column(align=True)
        box_col.prop(settings, 'pack_enable_stacking', text='Stack', toggle=False)

        # Stack settings (only visible when enabled)
        if settings.pack_enable_stacking:
            # Use Stack Groups option (always enabled when stacking is on)
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(settings, 'pack_use_stack_groups', text='Use Stack Groups', toggle=False)

        layout.separator(factor=0.5)

        # === HEURISTIC SEARCH ===
        box = layout.box()
        box_col = box.column(align=True)
        box_col.prop(uvpm_main_props, 'heuristic_enable', text='Heuristic Search', toggle=False)

        # Heuristic settings (only visible when enabled)
        if uvpm_main_props.heuristic_enable:
            # Add indentation for child settings
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'heuristic_search_time', text='Search Time')

            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'heuristic_max_wait_time', text='Max Wait Time')

            # Advanced Heuristic (if available)
            if hasattr(uvpm_main_props, 'advanced_heuristic'):
                split = box_col.split(factor=0.1, align=True)
                split.label(text='')  # Empty space for indent
                split.prop(uvpm_main_props, 'advanced_heuristic', text='Advanced Heuristic', toggle=False)

        layout.separator(factor=0.5)

        # === LOCK GROUP ===
        box = layout.box()
        box.label(text="Lock")
        box_col = box.column(align=True)

        # Lock checkboxes in same row
        row = box_col.row(align=True)
        row.prop(uvpm_main_props, 'lock_overlapping_enable', text='Overlaps', toggle=False)
        row.prop(uvpm_main_props.numbered_groups_descriptors.lock_group, 'enable', text='Groups', toggle=False)

        # Lock Overlaps mode (shown below when enabled)
        if uvpm_main_props.lock_overlapping_enable:
            # Add indentation for lock mode
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(uvpm_main_props, 'lock_overlapping_mode', text='')

        layout.separator(factor=0.5)

        # === MISC GROUP ===
        box = layout.box()
        box.label(text="Misc")
        box_col = box.column(align=True)

        # Global Size row with lock
        row = box_col.row(align=True)
        row.label(text='Global Size')
        size_row = box_col.row(align=True)
        size_row.prop(settings, 'size_x', text='')
        size_row.prop(settings, 'lock_size', text='', icon='LOCKED' if settings.lock_size else 'UNLOCKED')
        size_row.prop(settings, 'size_y', text='')

        box_col.separator()

        # Padding
        box_col.prop(settings, 'padding', slider=True)

        box_col.separator()

        # Pack to - label and dropdown in separate rows
        box_col.label(text='Pack to')
        box_col.prop(settings, 'udim_source', text='')


class UVV_PT_texel_density(UVVPanel):
    """Texel Density panel"""
    bl_label = "Texel Density"
    bl_idname = "UVV_PT_texel_density"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 9

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        # Texel Density section with dark background (matching Visualize style)
        box = layout.box()
        box.scale_y = 1.2

        # All texel density controls in one row
        row = box.row(align=True)

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Get button (left)
        if icons_coll and "td_get" in icons_coll:
            row.operator("uv.uvv_texel_density_get", text="Get TD", icon_value=icons_coll["td_get"].icon_id)
        else:
            row.operator("uv.uvv_texel_density_get", text="Get TD")

        # Input field and dropdown (middle)
        row.prop(settings, "texel_density", text="")
        row.menu("UVV_MT_TexelPresets", text="", icon='DOWNARROW_HLT')

        # Add 24px spacing
        row.separator(factor=2.0)

        # Set button (right)
        if icons_coll and "td_set" in icons_coll:
            row.operator("uv.uvv_texel_density_set", text="Set TD", icon_value=icons_coll["td_set"].icon_id)
        else:
            row.operator("uv.uvv_texel_density_set", text="Set TD")


class UVV_PT_visualize(UVVPanel):
    """Visualize panel for UV checker and display tools"""
    bl_label = "Visualize"
    bl_idname = "UVV_PT_visualize"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 10

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        # UV Checker section
        self.draw_checker_panel(context, layout, settings)

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

    def draw_checker_panel(self, context, layout, settings):
        """Draw the UV Checker panel section"""
        from ..checker.checker import UVVChecker_OT_CheckerToggle
        from .. import get_icons_set

        # Main toolbar box with dark background (matching Trimsheet style)
        box = layout.box()
        box.scale_y = 1.2
        row = box.row(align=True)

        # Use comprehensive state detection instead of simple material check
        from ..checker.checker import get_checker_state_for_ui
        b_is_checked = get_checker_state_for_ui(context)
        
        icons_coll = get_icons_set()

        # LEFT SIDE: UV Checker button
        if icons_coll and "texture" in icons_coll:
            row.operator(
                UVVChecker_OT_CheckerToggle.bl_idname,
                text="UV Checker",
                depress=b_is_checked,
                icon_value=icons_coll["texture"].icon_id).action = 'TOGGLE'
        else:
            row.operator(
                UVVChecker_OT_CheckerToggle.bl_idname,
                text="UV Checker",
                depress=b_is_checked,
                icon='TEXTURE').action = 'TOGGLE'

        # Pattern type dropdown (replaces old file selection dropdown)
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

        # Settings button - opens popover with checker settings
        if icons_coll and "settings" in icons_coll:
            row.popover(panel="UVV_PT_CheckerSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            row.popover(panel="UVV_PT_CheckerSettings", text="", icon="PREFERENCES")

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
        col.separator(factor=0.5)  # Smaller gap

        # Visualize title and dropdown in same row
        row = col.row(align=True)
        row.scale_y = 1.2  # Same scale as UV Checker toolbar

        # Check if we're in Edit Mode
        is_edit_mode = context.area.type == 'IMAGE_EDITOR' and context.mode == 'EDIT_MESH'

        # Visualize label (left)
        row.label(text="Visualize")

        # Dropdown (right) - disabled when not in Edit Mode
        dropdown_row = row.row(align=True)
        dropdown_row.enabled = is_edit_mode
        dropdown_row.scale_x = 1.5  # Make dropdown wider

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Get current debug mode
        settings = context.scene.uvv_settings

        # Dropdown with icon inside
        if icons_coll and "debug_uvs" in icons_coll:
            dropdown_row.prop(settings, "debug_uv_mode", text="", icon_value=icons_coll["debug_uvs"].icon_id)
        else:
            dropdown_row.prop(settings, "debug_uv_mode", text="", icon='UV')

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


class UVV_PT_CheckerSettings(Panel):
    """Checker settings popover panel"""
    bl_label = "Checker Settings"
    bl_idname = "UVV_PT_CheckerSettings"
    bl_space_type = 'IMAGE_EDITOR'
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
        box_col = box.column(align=True)
        box_col.prop(settings, 'checker_show_in_uv_editor', text="Show in UV Editor", toggle=True)
        box_col.prop(settings, 'checker_show_in_3d_view', text="Show in 3D View", toggle=True)


class UVV_MT_TexelPresets(Menu):
    """Texel Density Presets Menu"""
    bl_label = "Texel Density Presets"
    bl_idname = "UVV_MT_TexelPresets"

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        # Math operations on current value with results
        current_value = settings.texel_density
        multiply_result = current_value * 2.0
        divide_result = current_value / 2.0
        layout.operator("uv.uvv_texel_density_multiply", text=f"{current_value:.0f} × 2 = {multiply_result:.0f}", icon='TRIA_UP')
        layout.operator("uv.uvv_texel_density_divide", text=f"{current_value:.0f} / 2 = {divide_result:.0f}", icon='TRIA_DOWN')

        # Separator between math operations and presets
        layout.separator()

        # Texel density presets: 64, 128, 256, 512, 1024, 2048
        presets = [64.0, 128.0, 256.0, 512.0, 1024.0, 2048.0]

        for preset in presets:
            op = layout.operator("uv.uvv_set_texel_preset", text=f"{int(preset)}")
            op.preset_value = preset


class UVV_PT_SeamSettings(Panel):
    """Seam settings popover panel"""
    bl_label = "Seam Settings"
    bl_idname = "UVV_PT_SeamSettings"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'
    bl_options = {"INSTANCED"}

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()
        
        col = layout.column(align=True)
        col.prop(settings, "auto_unwrap_enabled", text="Auto Unwrap")
        
        # Add helpful description
        col.separator()
        col.label(text="Automatically unwrap UVs after", icon='INFO')
        col.label(text="weld, stitch, or split operations")
        col.label(text="Disable if performance is slow")


class UVV_PT_StackSettings(Panel):
    """Stack settings popover panel"""
    bl_label = "Stack Settings"
    bl_idname = "UVV_PT_StackSettings"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'
    bl_options = {"INSTANCED"}

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        col = layout.column(align=True)

        # === SIMILARITY DETECTION BOX === (MOVED TO TOP)
        box = col.box()
        box.label(text="Similarity Detection")
        box_col = box.column(align=True)

        # Similarity Mode (removed "Mode" label on left)
        box_col.prop(settings, 'stack_simi_mode', text='', expand=False)

        # Precision (only for non-vertex modes) - aligned with dropdown
        if settings.stack_simi_mode != 'VERTEX_POSITION':
            box_col.prop(settings, 'stack_simi_precision', text='Precision')

        # Threshold - aligned with dropdown
        box_col.prop(settings, 'stack_simi_threshold', text='Threshold', slider=True)

        # Check Holes (only for Border Shape mode) - aligned with dropdown
        if settings.stack_simi_mode == 'BORDER_SHAPE':
            box_col.prop(settings, 'stack_simi_check_holes', text='Check Holes', toggle=False)

        col.separator(factor=0.5)

        # === SCALE BOX === (MOVED UP - now includes Adjust Scale content)
        box = col.box()
        box_col = box.column(align=True)
        box_col.prop(settings, 'stack_match_scale', text='Match Scale', toggle=False)

        # Scale Mode (only visible when Match Scale is enabled)
        if settings.stack_match_scale:
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(settings, 'stack_scale_mode', text='')

        box_col.separator(factor=0.3)

        # Adjust Scale (moved from separate box)
        box_col.prop(settings, 'stack_simi_adjust_scale', text='Adjust Scale', toggle=False)

        # Non-Uniform Scaling Tolerance (only when Adjust Scale is enabled)
        if settings.stack_simi_adjust_scale:
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(settings, 'stack_simi_non_uniform_tolerance', text='Non-Uniform Tolerance', slider=True)

        col.separator(factor=0.5)

        # === ROTATION BOX ===
        box = col.box()
        box_col = box.column(align=True)
        box_col.prop(settings, 'stack_match_rotation', text='Match Rotation', toggle=False)

        # Rotation Mode (only visible when Match Rotation is enabled)
        if settings.stack_match_rotation:
            split = box_col.split(factor=0.1, align=True)
            split.label(text='')  # Empty space for indent
            split.prop(settings, 'stack_rotation_mode', text='')

        col.separator(factor=0.5)

        # === ALLOW FLIPPING BOX ===
        box = col.box()
        box_col = box.column(align=True)
        box_col.prop(settings, 'stack_simi_flipping_enable', text='Allow Flipping', toggle=False)

        col.separator()


class UVV_MT_auto_group_settings(Menu):
    """Auto Group Settings Menu"""
    bl_label = "Auto Group Settings"
    bl_idname = "UVV_MT_auto_group_settings"

    def draw(self, context):
        layout = self.layout
        settings = get_uvv_settings()

        # Only show the Minimum Group Size setting
        layout.prop(settings, 'stack_min_group_size', text="Minimum Group Size")


classes = [
    UVV_UL_stack_groups_list,
    UVV_PT_UVSyncSettings,
    UVV_PT_sync,
    UVV_PT_unwrap,
    UVV_PT_seams,
    UVV_PT_constraints,
    UVV_PT_modify,
    UVV_PT_stack,
    UVV_PT_transform,
    UVV_PT_pack,
    UVV_MT_PackPresetMenu,
    UVV_PT_PackSettings,
    UVV_PT_SeamSettings,
    UVV_PT_StackSettings,
    UVV_PT_texel_density,
    UVV_PT_visualize,
    UVV_PT_CheckerSettings,
    UVV_MT_TexelPresets,
    UVV_MT_auto_group_settings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)