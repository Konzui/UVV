# UV Constraint operators
import bpy
import bmesh
import json
from bpy.types import Operator


class UVV_OT_AddHorizontalConstraint(Operator):
    """Add horizontal constraint to selected UV edges"""
    bl_idname = "uv.uvv_add_horizontal_constraint"
    bl_label = "Horizontal"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Allow in UV editor OR 3D viewport with edit mode
        is_uv_editor = context.area.type == 'IMAGE_EDITOR'
        is_3d_view = context.area.type == 'VIEW_3D'

        return ((is_uv_editor or is_3d_view) and
                context.mode == 'EDIT_MESH' and
                context.active_object is not None)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No active mesh object")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active

        if not uv_layer:
            self.report({'WARNING'}, "No active UV layer")
            return {'CANCELLED'}

        # Get selected edges (works in both UV editor and 3D viewport)
        selected_edges = []

        # In 3D viewport or UV sync mode, use mesh edge selection
        if context.area.type == 'VIEW_3D' or context.tool_settings.use_uv_select_sync:
            for edge in bm.edges:
                if edge.select and edge.index not in selected_edges:
                    selected_edges.append(edge.index)
        else:
            # In UV editor (non-sync mode), check UV edge selection
            for face in bm.faces:
                if not face.select:
                    continue
                for edge in face.edges:
                    # Check if edge has UV selection
                    has_uv_selection = any(
                        loop[uv_layer].select_edge
                        for loop in edge.link_loops
                    )
                    if has_uv_selection and edge.index not in selected_edges:
                        selected_edges.append(edge.index)

        if not selected_edges:
            self.report({'WARNING'}, "No edges selected")
            return {'CANCELLED'}

        # Detect context
        is_uv_context = context.area.type == 'IMAGE_EDITOR'

        # Create new constraint
        constraint = context.scene.uvv_constraints.add()
        constraint.constraint_type = 'HORIZONTAL'
        constraint.name = f"Horizontal ({len(selected_edges)} edges)"
        constraint.object_name = obj.name
        constraint.edge_indices = json.dumps(selected_edges)
        constraint.enabled = True
        constraint.context_type = 'UV' if is_uv_context else '3D'

        self.report({'INFO'}, f"Added horizontal constraint with {len(selected_edges)} edges")
        return {'FINISHED'}


class UVV_OT_AddVerticalConstraint(Operator):
    """Add vertical constraint to selected UV edges"""
    bl_idname = "uv.uvv_add_vertical_constraint"
    bl_label = "Vertical"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Allow in UV editor OR 3D viewport with edit mode
        is_uv_editor = context.area.type == 'IMAGE_EDITOR'
        is_3d_view = context.area.type == 'VIEW_3D'

        return ((is_uv_editor or is_3d_view) and
                context.mode == 'EDIT_MESH' and
                context.active_object is not None)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "No active mesh object")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active

        if not uv_layer:
            self.report({'WARNING'}, "No active UV layer")
            return {'CANCELLED'}

        # Get selected edges (works in both UV editor and 3D viewport)
        selected_edges = []

        # In 3D viewport or UV sync mode, use mesh edge selection
        if context.area.type == 'VIEW_3D' or context.tool_settings.use_uv_select_sync:
            for edge in bm.edges:
                if edge.select and edge.index not in selected_edges:
                    selected_edges.append(edge.index)
        else:
            # In UV editor (non-sync mode), check UV edge selection
            for face in bm.faces:
                if not face.select:
                    continue
                for edge in face.edges:
                    # Check if edge has UV selection
                    has_uv_selection = any(
                        loop[uv_layer].select_edge
                        for loop in edge.link_loops
                    )
                    if has_uv_selection and edge.index not in selected_edges:
                        selected_edges.append(edge.index)

        if not selected_edges:
            self.report({'WARNING'}, "No edges selected")
            return {'CANCELLED'}

        # Detect context
        is_uv_context = context.area.type == 'IMAGE_EDITOR'

        # Create new constraint
        constraint = context.scene.uvv_constraints.add()
        constraint.constraint_type = 'VERTICAL'
        constraint.name = f"Vertical ({len(selected_edges)} edges)"
        constraint.object_name = obj.name
        constraint.edge_indices = json.dumps(selected_edges)
        constraint.enabled = True
        constraint.context_type = 'UV' if is_uv_context else '3D'

        self.report({'INFO'}, f"Added vertical constraint with {len(selected_edges)} edges")
        return {'FINISHED'}


class UVV_OT_SelectConstraintEdges(Operator):
    """Select edges associated with this constraint"""
    bl_idname = "uv.uvv_select_constraint_edges"
    bl_label = "Select Edges"
    bl_options = {'REGISTER', 'UNDO'}

    constraint_index: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        if self.constraint_index < 0 or self.constraint_index >= len(context.scene.uvv_constraints):
            self.report({'WARNING'}, "Invalid constraint index")
            return {'CANCELLED'}

        constraint = context.scene.uvv_constraints[self.constraint_index]

        # Find the object
        obj = bpy.data.objects.get(constraint.object_name)
        if not obj:
            self.report({'WARNING'}, f"Object '{constraint.object_name}' not found")
            return {'CANCELLED'}

        # Make sure object is active
        if context.active_object != obj:
            context.view_layer.objects.active = obj

        # Get edge indices
        try:
            edge_indices = json.loads(constraint.edge_indices)
        except:
            self.report({'WARNING'}, "Failed to parse edge indices")
            return {'CANCELLED'}

        # Select the edges in the mesh
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.active

        # Deselect all first
        for face in bm.faces:
            face.select = False
            for loop in face.loops:
                loop[uv_layer].select = False
                loop[uv_layer].select_edge = False

        # Select constraint edges (first group)
        selected_count = 0
        for edge_idx in edge_indices:
            if edge_idx < len(bm.edges):
                edge = bm.edges[edge_idx]
                edge.select = True
                # Select in UV as well
                for loop in edge.link_loops:
                    loop[uv_layer].select_edge = True
                    loop[uv_layer].select = True
                selected_count += 1

        # If this is a parallel constraint, also select the second edge group
        if constraint.constraint_type == 'PARALLEL' and constraint.edge_indices2:
            try:
                edge_indices2 = json.loads(constraint.edge_indices2)
                for edge_idx in edge_indices2:
                    if edge_idx < len(bm.edges):
                        edge = bm.edges[edge_idx]
                        edge.select = True
                        # Select in UV as well
                        for loop in edge.link_loops:
                            loop[uv_layer].select_edge = True
                            loop[uv_layer].select = True
                        selected_count += 1
            except:
                pass  # If second group fails, at least first group is selected

        bmesh.update_edit_mesh(obj.data)

        self.report({'INFO'}, f"Selected {selected_count} edges")
        return {'FINISHED'}


class UVV_OT_DeleteConstraint(Operator):
    """Delete this constraint"""
    bl_idname = "uv.uvv_delete_constraint"
    bl_label = "Delete Constraint"
    bl_options = {'REGISTER', 'UNDO'}

    constraint_index: bpy.props.IntProperty()

    def execute(self, context):
        if self.constraint_index < 0 or self.constraint_index >= len(context.scene.uvv_constraints):
            self.report({'WARNING'}, "Invalid constraint index")
            return {'CANCELLED'}

        constraint = context.scene.uvv_constraints[self.constraint_index]
        constraint_name = constraint.name

        context.scene.uvv_constraints.remove(self.constraint_index)

        # Update active index if needed
        if context.scene.uvv_constraints_index >= len(context.scene.uvv_constraints):
            context.scene.uvv_constraints_index = len(context.scene.uvv_constraints) - 1

        self.report({'INFO'}, f"Deleted constraint '{constraint_name}'")
        return {'FINISHED'}


class UVV_OT_ToggleConstraintEnabled(Operator):
    """Toggle constraint enabled state"""
    bl_idname = "uv.uvv_toggle_constraint_enabled"
    bl_label = "Toggle Enabled"
    bl_options = {'REGISTER', 'UNDO'}

    constraint_index: bpy.props.IntProperty()

    def execute(self, context):
        if self.constraint_index < 0 or self.constraint_index >= len(context.scene.uvv_constraints):
            return {'CANCELLED'}

        constraint = context.scene.uvv_constraints[self.constraint_index]
        constraint.enabled = not constraint.enabled

        return {'FINISHED'}


classes = [
    UVV_OT_AddHorizontalConstraint,
    UVV_OT_AddVerticalConstraint,
    UVV_OT_SelectConstraintEdges,
    UVV_OT_DeleteConstraint,
    UVV_OT_ToggleConstraintEnabled,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
