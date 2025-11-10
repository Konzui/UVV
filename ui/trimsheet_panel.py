"""Trimsheet UI panel in UV editor"""

import bpy
from bpy.types import Panel, UIList, Menu


class UVV_MT_trim_options(Menu):
    """Menu for trim creation options"""
    bl_label = "Trim Options"
    bl_idname = "UVV_MT_trim_options"

    def draw(self, context):
        layout = self.layout

        # Get material to check if trims exist
        obj = context.active_object
        has_trims = False
        if obj and obj.active_material:
            material = obj.active_material
            has_trims = len(material.uvv_trims) > 0

        # Delete All Trims (always show, grayed out if no trims)
        row = layout.row()
        row.enabled = has_trims  # Gray out if no trims
        row.operator("uv.uvv_trim_clear_all", text="Delete All Trims", icon='TRASH')


class UVV_MT_overlay_options(Menu):
    """Menu for overlay settings"""
    bl_label = "Overlay Options"
    bl_idname = "UVV_MT_overlay_options"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.uvv_settings

        # Menu title
        layout.label(text="Overlays", icon='OVERLAY')
        layout.separator()

        # Trim Shape section
        layout.label(text="Trim Shape")
        layout.prop(settings, "trim_overlay_opacity", text="Opacity", slider=True)


class UVV_MT_tag_presets(Menu):
    """Menu for selecting existing tags"""
    bl_label = "Existing Tags"
    bl_idname = "UVV_MT_tag_presets"

    def draw(self, context):
        layout = self.layout

        obj = context.active_object
        if not obj or not obj.active_material:
            return

        material = obj.active_material
        if material.uvv_trims_index < 0 or material.uvv_trims_index >= len(material.uvv_trims):
            return

        # Get all unique tags
        existing_tags = sorted(set(
            t.tag.strip()
            for t in material.uvv_trims
            if t.tag and t.tag.strip()
        ))

        if not existing_tags:
            layout.label(text="No tags yet", icon='INFO')
            return

        layout.label(text="Select Tag:")
        layout.separator()

        # Create operator button for each tag
        for tag in existing_tags:
            op = layout.operator("uv.uvv_trim_set_tag", text=tag, icon='TAG')
            op.tag = tag
            op.trim_index = material.uvv_trims_index


class UVV_UL_trims_list(UIList):
    """UIList for displaying trims"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Draw a single trim item"""
        trim = item

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # If this is not a trim-like item (placeholder), draw nothing to avoid errors
            if not hasattr(trim, 'enabled') or not hasattr(trim, 'color') or not hasattr(trim, 'name'):
                layout.label(text="")
                return
            # Enabled toggle (eye icon) - moved to the left
            row = layout.row(align=True)
            row.scale_x = 0.8
            icon = 'HIDE_OFF' if trim.enabled else 'HIDE_ON'
            row.prop(trim, "enabled", text="", icon=icon, emboss=False)

            # Color swatch
            row = layout.row(align=True)
            row.scale_x = 0.5
            row.prop(trim, "color", text="")

            # Name - use operator button styled as label for double-click support
            # Single-click selects, double-click enters edit mode
            row = layout.row(align=True)
            op = row.operator("uv.uvv_trim_edit_from_list", text=trim.name, emboss=False, depress=False)
            op.trim_index = index

            # Lock/Unlock toggle button - larger width
            row = layout.row(align=True)
            row.scale_x = 1.2

            # Get icon collection
            from .. import get_icons_set
            icons_coll = get_icons_set()

            # Show lock icon when locked, unlocked icon when unlocked
            if icons_coll and "lock" in icons_coll and "unlocked" in icons_coll:
                icon_id = icons_coll["lock"].icon_id if trim.locked else icons_coll["unlocked"].icon_id
                row.prop(trim, "locked", text="", icon_value=icon_id, emboss=False)
            else:
                # Fallback to Blender icons if custom icons not available
                icon = 'LOCKED' if trim.locked else 'UNLOCKED'
                row.prop(trim, "locked", text="", icon=icon, emboss=False)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="")


class UVV_PT_TrimsheetSettings(Panel):
    """Trimsheet settings popover panel"""
    bl_label = "Trimsheet Settings"
    bl_idname = "UVV_PT_TrimsheetSettings"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'HEADER'
    bl_options = {"INSTANCED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.uvv_settings
        icons_coll = None
        try:
            from .. import get_icons_set
            icons_coll = get_icons_set()
        except:
            pass

        col = layout.column(align=True)

        # Import button
        if icons_coll and "import" in icons_coll:
            col.operator("uv.uvv_trim_import_svg", text="Import Trimsheet (.svg)", icon_value=icons_coll["import"].icon_id)
        else:
            col.operator("uv.uvv_trim_import_svg", text="Import Trimsheet (.svg)", icon='IMPORT')

        # Export button
        if icons_coll and "export" in icons_coll:
            col.operator("uv.uvv_trim_export_svg", text="Export Trimsheet (.svg)", icon_value=icons_coll["export"].icon_id)
        else:
            col.operator("uv.uvv_trim_export_svg", text="Export Trimsheet (.svg)", icon='EXPORT')

        # Separator
        layout.separator()

        # Unrestricted placement toggle
        col = layout.column(align=True)
        col.prop(settings, "trim_unrestricted_placement", text="Unrestricted Placement")


class UVV_PT_trimsheet(Panel):
    """Trimsheet panel in UV editor sidebar"""
    bl_label = "Trimsheet"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 11  # Last in the sequence
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.area.spaces.active.mode == "UV"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        settings = context.scene.uvv_settings

        # Check if we have a valid object (ensure it's always a boolean)
        has_valid_obj = bool(obj and obj.type == 'MESH')

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Trimsheet toolbar (dark background box with button groups)
        scene = context.scene
        trim_plane_active = scene.get('uvv_trim_plane_data', {}).get('active', False)
        material = obj.active_material if obj else None
        has_trims = bool(material and hasattr(material, 'uvv_trims') and len(material.uvv_trims) > 0)

        if trim_plane_active:
            # Show apply/cancel buttons when in plane editing mode
            col = layout.column(align=True)
            col.scale_y = 1.3
            col.enabled = has_valid_obj
            col.operator("uv.uvv_trim_from_plane_apply", text="Apply to Trim Set", icon='CHECKMARK')
            col.operator("uv.uvv_trim_from_plane_cancel", text="Cancel", icon='X')

        # Materials section - Simple material list (no collapsible header)
        # Only show separator and material list when we have a valid object
        if has_valid_obj:
            layout.separator(factor=0.25)

            # Show "Missing Material" notification if no material is assigned (ABOVE the material list)
            if not obj.active_material:
                missing_material_col = layout.column(align=True)
                missing_material_col.scale_y = 0.9
                missing_material_col.label(text="Missing Material", icon='ERROR')

            # Material selector list
            material_row = layout.row(align=True)
            material_row.template_list(
                "MATERIAL_UL_matslots", "",
                obj, "material_slots",
                obj, "active_material_index",
                rows=2
            )

        # Add Trim buttons row - ABOVE the collapsible section (like Stack Groups)
        # Smaller gap between Materials and Add buttons
        layout.separator(factor=0.1)

        # Add Trim buttons row
        add_row = layout.row(align=True)
        add_row.scale_y = 1.2
        add_row.enabled = has_valid_obj and context.mode == 'OBJECT'

        # Rectangle trim button with text
        if icons_coll and "add_trim" in icons_coll:
            add_row.operator("uv.uvv_trim_add", text="Add Trim", icon_value=icons_coll["add_trim"].icon_id)
        else:
            add_row.operator("uv.uvv_trim_add", text="Add Trim", icon='ADD')

        # Circle trim button with text
        if icons_coll and "add_trim_circle" in icons_coll:
            add_row.operator("uv.uvv_trim_add_circle", text="Add Circle", icon_value=icons_coll["add_trim_circle"].icon_id)
        else:
            add_row.operator("uv.uvv_trim_add_circle", text="Add Circle", icon='MESH_CIRCLE')

        # Trims section - Collapsible box (matching Stack Groups style)
        # Smaller gap between Add buttons and Trims collapsible
        layout.separator(factor=0.1)
        box = layout.box()
        box_col = box.column(align=True)

        # Header row with collapsible arrow, label, and buttons
        header_row = box_col.row(align=True)
        header_row.scale_y = 1.2
        header_row.enabled = has_valid_obj

        # Left side: Collapsible arrow and label
        left_side = header_row.row(align=True)

        # Collapsible arrow
        icon = 'DOWNARROW_HLT' if settings.show_trims_list else 'RIGHTARROW'
        left_side.prop(settings, 'show_trims_list',
                      text="",
                      icon=icon, emboss=False, toggle=True)

        # "Trims" label - also clickable to toggle
        left_side.prop(settings, 'show_trims_list',
                      text="Trims",
                      icon='NONE', emboss=False, toggle=True)

        # Flexible spacer to push buttons to the right
        header_row.separator()

        # Right side: Buttons grouped together
        buttons_row = header_row.row(align=True)

        # Show/Hide Overlays button (toggle)
        overlay_icon = 'HIDE_OFF' if settings.show_trim_overlays else 'HIDE_ON'
        if icons_coll and "overlay_trim" in icons_coll:
            buttons_row.prop(settings, "show_trim_overlays", text="", icon_value=icons_coll["overlay_trim"].icon_id, toggle=True)
        else:
            buttons_row.prop(settings, "show_trim_overlays", text="", icon=overlay_icon, toggle=True)

        # Overlay settings dropdown
        buttons_row.menu("UVV_MT_overlay_options", text="", icon='DOWNARROW_HLT')

        # Gap between overlay dropdown and settings button
        buttons_row.separator(factor=0.5)

        # Settings button (identical to stack menu)
        if icons_coll and "settings" in icons_coll:
            buttons_row.popover(panel="UVV_PT_TrimsheetSettings", text="", icon_value=icons_coll["settings"].icon_id)
        else:
            buttons_row.popover(panel="UVV_PT_TrimsheetSettings", text="", icon="PREFERENCES")

        # Show trims list when expanded
        if settings.show_trims_list:
            # Gap between header row and controls row
            box_col.separator(factor=0.8)

            # Controls row above the list
            controls_row = box_col.row(align=True)
            controls_row.scale_y = 1.2  # Match height with other buttons
            controls_row.scale_x = 3  # Scale proportionally like Transform panel
            controls_row.enabled = has_valid_obj

            has_trims = material and hasattr(material, 'uvv_trims') and len(material.uvv_trims) > 0

            # Note: Fit Per Island toggle is available in the operator panel after clicking Fit

            # Fit button - icon only
            if icons_coll and "fit_trim" in icons_coll:
                op = controls_row.operator("uv.uvv_trim_fit_selection", text="", icon_value=icons_coll["fit_trim"].icon_id)
            else:
                op = controls_row.operator("uv.uvv_trim_fit_selection", text="", icon='UV')
            if has_trims:
                op.trim_index = material.uvv_trims_index

            # Auto Fit button - full text, wider to accommodate text
            if icons_coll and "smart_pack_trim" in icons_coll:
                controls_row.operator("uv.uvv_trim_smart_pack", text="Auto Fit", icon_value=icons_coll["smart_pack_trim"].icon_id)
            else:
                controls_row.operator("uv.uvv_trim_smart_pack", text="Auto Fit", icon='PACKAGE')

            # Larger gap between Fit/Auto Fit group and Remove button
            controls_row.separator(factor=0.75)

            # Delete button - aligned to the right
            if icons_coll and "remove_trim" in icons_coll:
                controls_row.operator("uv.uvv_trim_remove", text="", icon_value=icons_coll["remove_trim"].icon_id)
            else:
                controls_row.operator("uv.uvv_trim_remove", text="", icon='REMOVE')

            # Gap between controls row and list
            box_col.separator(factor=0.8)

            # Trim list - full width, no side controls
            if material and hasattr(material, 'uvv_trims'):
                box_col.template_list(
                    "UVV_UL_trims_list", "",
                    material, "uvv_trims",
                    material, "uvv_trims_index",
                    rows=1
                )
            else:
                # Keep layout structure but disable when no material
                list_row = box_col.row()
                list_row.enabled = False
                list_row.template_list(
                    "UVV_UL_trims_list", "",
                    context.scene, "uvv_pack_presets",  # harmless placeholder collection
                    context.scene, "uvv_pack_presets_index",
                    rows=1
                )

            # Visual separation between list and controls
            box_col.separator(factor=0.5)

            # List controls below the list - WITH align=True (exactly like stack groups header)
            controls_below = box_col.row(align=True)
            controls_below.scale_y = 0.9  # Smaller buttons
            controls_below.scale_x = 2.0  # Smaller buttons
            controls_below.enabled = has_valid_obj and bool(material and hasattr(material, 'uvv_trims'))

            # Move buttons (up/down)
            controls_below.operator("uv.uvv_trim_move", icon='TRIA_UP', text="").direction = 'UP'
            controls_below.operator("uv.uvv_trim_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

            # Duplicate button
            controls_below.operator("uv.uvv_trim_duplicate", icon='DUPLICATE', text="")

            # Gap between left group and right group (larger gap)
            controls_below.separator(factor=0.5)

            # Delete all button (right-aligned)
            if icons_coll and "trash" in icons_coll:
                controls_below.operator("uv.uvv_trim_clear_all", icon_value=icons_coll["trash"].icon_id, text="")
            else:
                controls_below.operator("uv.uvv_trim_clear_all", icon='TRASH', text="")

        # Active trim section - Collapsible with dark background
        if material and hasattr(material, 'uvv_trims') and material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims):
            trim = material.uvv_trims[material.uvv_trims_index]

            # Wrap entire section in box for dark background
            layout.separator()
            details_box = layout.box()
            details_col = details_box.column(align=True)

            # Collapsible header for trim details
            row = details_col.row(align=True)
            icon = 'DOWNARROW_HLT' if trim.show_details else 'RIGHTARROW'
            row.prop(trim, "show_details", text=f"{trim.name} Details", icon=icon, emboss=False)

            # Show details when expanded
            if trim.show_details:

                # Compact name and color row
                header_row = details_col.row(align=True)
                header_row.scale_y = 0.9
                header_row.label(text="Name:")
                header_row.prop(trim, "name", text="")
                # Small color swatch
                color_col = header_row.row(align=True)
                color_col.scale_x = 0.5
                color_col.prop(trim, "color", text="")

                # Horizontal separator line
                details_col.separator(factor=0.25)

                # Tag section with existing tags dropdown
                tag_row = details_col.row(align=True)
                tag_row.scale_y = 0.9
                tag_row.label(text="Tag:")

                # Tag input field
                tag_row.prop(trim, "tag", text="", icon='TAG')

                # Get all unique tags from all trims in this material
                existing_tags = sorted(set(
                    t.tag.strip()
                    for t in material.uvv_trims
                    if t.tag and t.tag.strip()
                ))

                # Show dropdown menu with existing tags if any exist
                if existing_tags:
                    tag_row.menu("UVV_MT_tag_presets", text="")

                # Horizontal separator line
                details_col.separator(factor=0.25)

                # Collapsible Transforms section (bounds only)
                details_col.separator(factor=0.2)
                row = details_col.row(align=True)
                icon = 'DOWNARROW_HLT' if trim.show_bounds else 'RIGHTARROW'
                row.alignment = 'LEFT'
                row.prop(trim, "show_bounds", text="Transforms", icon=icon, emboss=False)
                sub = row.row()
                sub.alignment = 'RIGHT'
                sub.label(text=f"Size: {trim.get_width():.3f} × {trim.get_height():.3f}")

                if trim.show_bounds:
                    # Bounds (no label)
                    bounds_col = details_col.column(align=True)
                    bounds_col.scale_y = 0.9
                    split = bounds_col.split(factor=0.4)
                    split.label(text="Left:")
                    split.prop(trim, "left", text="")

                    split = bounds_col.split(factor=0.4)
                    split.label(text="Right:")
                    split.prop(trim, "right", text="")

                    split = bounds_col.split(factor=0.4)
                    split.label(text="Top:")
                    split.prop(trim, "top", text="")

                    split = bounds_col.split(factor=0.4)
                    split.label(text="Bottom:")
                    split.prop(trim, "bottom", text="")

            # Debug Tools section removed


classes = [
    UVV_MT_trim_options,
    UVV_MT_overlay_options,
    UVV_MT_tag_presets,
    UVV_UL_trims_list,
    UVV_PT_TrimsheetSettings,
    UVV_PT_trimsheet,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
