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

            # Name (editable)
            row = layout.row(align=True)
            row.prop(trim, "name", text="", emboss=False)

            # Fit UV to trim button - larger width
            row = layout.row(align=True)
            row.scale_x = 1.2

            # Get icon collection
            from .. import get_icons_set
            icons_coll = get_icons_set()

            if icons_coll and "trim_set" in icons_coll:
                op = row.operator("uv.uvv_trim_fit_selection", text="", icon_value=icons_coll["trim_set"].icon_id, emboss=False)
            else:
                op = row.operator("uv.uvv_trim_fit_selection", text="", icon='UV', emboss=False)
            op.trim_index = index

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="")


class UVV_PT_trimsheet(Panel):
    """Trimsheet panel in UV editor sidebar"""
    bl_label = "Trimsheet"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "🌀 UVV"
    bl_order = 11  # Last in the sequence

    @classmethod
    def poll(cls, context):
        return context.area.spaces.active.mode == "UV"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        # Check if we have a valid object
        if not obj or obj.type != 'MESH':
            # Keep panel visible without early return
            col = layout.column(align=True)
            col.scale_y = 1.2
            col.label(text="Select a mesh object to use trimsheet tools", icon='INFO')
            col.separator()

        # Material selector dropdown (always show, even if there are no materials)
        # Do not hide UI when there are no materials

        box = layout.box()
        row = box.row(align=True)
        row.template_list(
            "MATERIAL_UL_matslots", "",
            obj, "material_slots",
            obj, "active_material_index",
            rows=2
        )

        material = obj.active_material

        layout.separator()

        # Get icon collection
        from .. import get_icons_set
        icons_coll = get_icons_set()

        # Trimsheet toolbar (dark background box with button groups)
        scene = context.scene
        trim_plane_active = scene.get('uvv_trim_plane_data', {}).get('active', False)
        has_trims = bool(material and hasattr(material, 'uvv_trims') and len(material.uvv_trims) > 0)
        settings = context.scene.uvv_settings

        if trim_plane_active:
            # Show apply/cancel buttons when in plane editing mode
            col = layout.column(align=True)
            col.scale_y = 1.3
            col.operator("uv.uvv_trim_from_plane_apply", text="Apply to Trim Set", icon='CHECKMARK')
            col.operator("uv.uvv_trim_from_plane_cancel", text="Cancel", icon='X')
        else:
            # Main toolbar box with dark background (matching Texel Density style)
            box = layout.box()
            box.scale_y = 1.2
            row = box.row(align=True)

            # LEFT SIDE: Creation tools
            if not has_trims:
                # 3D button - fixed width (no scaling)
                if icons_coll and "3d_plane" in icons_coll:
                    row.operator("uv.uvv_trim_from_plane_start", text="3D", icon_value=icons_coll["3d_plane"].icon_id)
                else:
                    row.operator("uv.uvv_trim_from_plane_start", text="3D", icon='MESH_PLANE')
            else:
                # Edit toggle button - fixed width (no scaling)
                if icons_coll and "edit_trim_plane" in icons_coll:
                    row.operator("uv.uvv_trim_edit_toggle", text="Edit", icon_value=icons_coll["edit_trim_plane"].icon_id, depress=settings.trim_edit_mode)
                else:
                    row.operator("uv.uvv_trim_edit_toggle", text="Edit", icon='GREASEPENCIL', depress=settings.trim_edit_mode)

            # Rectangle trim - 50% wider than height
            button_row = row.row(align=True)
            button_row.scale_x = 1.5  # 50% wider than height
            if icons_coll and "trim_rect" in icons_coll:
                button_row.operator("uv.uvv_trim_create", text="", icon_value=icons_coll["trim_rect"].icon_id)
            else:
                button_row.operator("uv.uvv_trim_create", text="", icon='MESH_PLANE')

            # Circle trim - 50% wider than height
            button_row = row.row(align=True)
            button_row.scale_x = 1.5  # 50% wider than height
            if icons_coll and "trim_circle" in icons_coll:
                button_row.operator("uv.uvv_trim_create_circle", text="", icon_value=icons_coll["trim_circle"].icon_id)
            else:
                button_row.operator("uv.uvv_trim_create_circle", text="", icon='MESH_CIRCLE')

            # Dropdown menu - default width
            row.menu("UVV_MT_trim_options", text="", icon='DOWNARROW_HLT')

            # Flexible spacer to push Import/Export to the right
            row.separator()

            # RIGHT SIDE: Import/Export (pushed to the right edge)
            # Import button - 50% wider than height
            button_row = row.row(align=True)
            button_row.scale_x = 1.5  # 50% wider than height
            if icons_coll and "import" in icons_coll:
                button_row.operator("uv.uvv_trim_import_svg", text="", icon_value=icons_coll["import"].icon_id)
            else:
                button_row.operator("uv.uvv_trim_import_svg", text="", icon='IMPORT')

            # Export button - 50% wider than height
            button_row = row.row(align=True)
            button_row.scale_x = 1.5  # 50% wider than height
            if icons_coll and "export" in icons_coll:
                button_row.operator("uv.uvv_trim_export_svg", text="", icon_value=icons_coll["export"].icon_id)
            else:
                button_row.operator("uv.uvv_trim_export_svg", text="", icon='EXPORT')

        # Overlay controls with Fit to Trim, Auto Fit, and styled Overlays button
        settings = context.scene.uvv_settings
        row = layout.row(align=True)
        row.scale_y = 1.2  # Same scale as toolbar buttons

        # LEFT SIDE: Fit to Trim and Auto Fit buttons - in separate container to preserve text
        button_row = row.row(align=True)

        # Fit button (calls trim_fit_selection with active trim)
        if material and hasattr(material, 'uvv_trims') and len(material.uvv_trims) > 0:
            if icons_coll and "trim_set" in icons_coll:
                op = button_row.operator("uv.uvv_trim_fit_selection", text="Fit", icon_value=icons_coll["trim_set"].icon_id)
            else:
                op = button_row.operator("uv.uvv_trim_fit_selection", text="Fit", icon='UV')
            op.trim_index = material.uvv_trims_index
        else:
            # Disabled button when no trims
            disabled_row = button_row.row(align=True)
            disabled_row.enabled = False
            if icons_coll and "trim_set" in icons_coll:
                disabled_row.operator("uv.uvv_trim_fit_selection", text="Fit", icon_value=icons_coll["trim_set"].icon_id)
            else:
                disabled_row.operator("uv.uvv_trim_fit_selection", text="Fit", icon='UV')

        # Auto Fit button (formerly Smart Pack)
        if icons_coll and "smart_pack_trim" in icons_coll:
            button_row.operator("uv.uvv_trim_smart_pack", text="Auto Fit", icon_value=icons_coll["smart_pack_trim"].icon_id)
        else:
            button_row.operator("uv.uvv_trim_smart_pack", text="Auto Fit", icon='PACKAGE')

        # Flexible spacer to push Overlays to the right
        row.separator()

        # RIGHT SIDE: Overlays button with dropdown - grouped in separate container
        right_group = row.row(align=True)
        
        # Overlays toggle button - 50% wider than height
        button_row = right_group.row(align=True)
        button_row.scale_x = 1.5  # 50% wider than height like other icon buttons
        overlay_icon = 'HIDE_OFF' if settings.show_trim_overlays else 'HIDE_ON'
        if icons_coll and "overlay_trim" in icons_coll:
            button_row.prop(settings, "show_trim_overlays", text="", icon_value=icons_coll["overlay_trim"].icon_id, toggle=True)
        else:
            button_row.prop(settings, "show_trim_overlays", text="", icon=overlay_icon, toggle=True)

        # Overlays dropdown menu - default width
        right_group.menu("UVV_MT_overlay_options", text="", icon='DOWNARROW_HLT')

        # Trim list
        row = layout.row()
        if material and hasattr(material, 'uvv_trims'):
            row.template_list(
                "UVV_UL_trims_list", "",
                material, "uvv_trims",
                material, "uvv_trims_index",
                rows=1
            )
        else:
            # Keep layout structure but disable when no material
            row.enabled = False
            row.template_list(
                "UVV_UL_trims_list", "",
                context.scene, "uvv_pack_presets",  # harmless placeholder collection
                context.scene, "uvv_pack_presets_index",
                rows=1
            )

        # List controls
        col = row.column(align=True)
        col.enabled = bool(material and hasattr(material, 'uvv_trims'))
        col.operator("uv.uvv_trim_add", icon='ADD', text="")
        col.operator("uv.uvv_trim_remove", icon='REMOVE', text="")
        col.separator()
        col.operator("uv.uvv_trim_duplicate", icon='DUPLICATE', text="")
        col.separator()
        col.operator("uv.uvv_trim_move", icon='TRIA_UP', text="").direction = 'UP'
        col.operator("uv.uvv_trim_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

        # Active trim section - Collapsible
        if material and hasattr(material, 'uvv_trims') and material.uvv_trims_index >= 0 and material.uvv_trims_index < len(material.uvv_trims):
            trim = material.uvv_trims[material.uvv_trims_index]

            # Collapsible header for trim details
            layout.separator()
            row = layout.row(align=True)
            icon = 'DOWNARROW_HLT' if trim.show_details else 'RIGHTARROW'
            row.prop(trim, "show_details", text=f"{trim.name} Details", icon=icon, emboss=False)

            # Show details when expanded
            if trim.show_details:
                box = layout.box()

                # Compact name and color row
                header_row = box.row(align=True)
                header_row.scale_y = 0.9
                header_row.label(text="Name:")
                header_row.prop(trim, "name", text="")
                # Small color swatch
                color_col = header_row.row(align=True)
                color_col.scale_x = 0.5
                color_col.prop(trim, "color", text="")

                # Horizontal separator line
                box.separator(factor=0.5)

                # Tag section with existing tags dropdown
                tag_row = box.row(align=True)
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
                box.separator(factor=0.5)

                # Collapsible Transforms section (bounds only)
                box.separator(factor=0.3)
                row = box.row(align=True)
                icon = 'DOWNARROW_HLT' if trim.show_bounds else 'RIGHTARROW'
                row.alignment = 'LEFT'
                row.prop(trim, "show_bounds", text="Transforms", icon=icon, emboss=False)
                sub = row.row()
                sub.alignment = 'RIGHT'
                sub.label(text=f"Size: {trim.get_width():.3f} × {trim.get_height():.3f}")

                if trim.show_bounds:
                    # Bounds (no label)
                    bounds_col = box.column(align=True)
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
    UVV_PT_trimsheet,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
