"""Stack operators for UV island stacking and selection"""

import bpy
import bmesh
from bpy.props import BoolProperty, EnumProperty, IntProperty
from ..properties import get_uvv_settings


def clear_selection(context):
    """Clear all UV/mesh selection"""
    sync_uv = context.scene.tool_settings.use_uv_select_sync

    for obj in context.objects_in_mode_unique_data:
        if obj.type != 'MESH':
            continue

        bm = bmesh.from_edit_mesh(obj.data)

        if sync_uv:
            for face in bm.faces:
                face.select = False
        else:
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                for face in bm.faces:
                    for loop in face.loops:
                        loop[uv_layer].select = False

        bmesh.update_edit_mesh(obj.data)


class UVV_OT_StackAll(bpy.types.Operator):
    """Stack all similar UV islands together using Blender's copy/paste (automatically matches rotation and scale)"""
    bl_idname = "uv.uvv_stack_all"
    bl_label = "Stack All"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            # Try UVPackmaster first if available
            try:
                if hasattr(bpy.ops, 'uvpackmaster3'):
                    # Use UVPackmaster's align_similar operator (same as UVPackmaster's stacking)
                    bpy.ops.uvpackmaster3.align_similar()
                    self.report({'INFO'}, "Stacked all similar islands using UVPackmaster")
                    return {'FINISHED'}
                else:
                    # Fallback to our implementation if UVPackmaster not available
                    self.report({'WARNING'}, "UVPackmaster not available, using fallback method")
            except Exception as e:
                self.report({'WARNING'}, f"UVPackmaster failed: {str(e)}, using fallback method")

            # Fallback: Use our implementation
            # Get all objects in edit mode
            objects = [obj for obj in context.objects_in_mode_unique_data if obj.type == 'MESH']

            # Store original selection state
            original_uv_selections = {}
            for obj in objects:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    original_uv_selections[obj] = {}
                    for face in bm.faces:
                        for loop in face.loops:
                            uv = loop[uv_layer]
                            original_uv_selections[obj][loop.index] = (uv.select, uv.select_edge)

            # Use Mio3's approach: copy/paste with Blender's built-in operators
            stack_system = StackSystem(context)
            scene = context.scene
            stacked_count = 0

            # Track which islands have been processed
            processed_islands = set()

            # First, process stack groups (prioritize manual groups)
            if len(scene.uvv_stack_groups) > 0:
                for stack_group in scene.uvv_stack_groups:
                    group_islands = stack_system.get_group_islands(stack_group.group_id)
                    if len(group_islands) < 2:
                        continue

                    # Use similarity detection to further group within the manual group
                    # Group by sim_index within this stack group
                    group_by_sim = {}
                    for island in group_islands:
                        sim_index = island.sim_index
                        if sim_index not in group_by_sim:
                            group_by_sim[sim_index] = []
                        group_by_sim[sim_index].append(island)

                    # Stack each similarity group
                    for sim_index, island_group in group_by_sim.items():
                        if len(island_group) < 2:
                            continue

                        master = stack_system.find_master(island_group)

                        # Select only the master island
                        clear_selection(context)
                        master.select(True)

                        # Copy master island UV data
                        bpy.ops.uv.copy()

                        # Select all replicas in this group
                        for island in island_group:
                            if island is not master:
                                island.select(True)
                                stacked_count += 1
                                processed_islands.add(id(island))

                        # Paste to stack all replicas onto master
                        bpy.ops.uv.paste()

            # Then, process ungrouped similar islands (automatic similarity)
            stack_system.group_by_similarity()

            for island_group in stack_system.stacks.values():
                if len(island_group) < 2:
                    continue

                # Skip islands that were already processed in groups
                unprocessed_group = [isl for isl in island_group if id(isl) not in processed_islands]
                if len(unprocessed_group) < 2:
                    continue

                master = stack_system.find_master(unprocessed_group)

                # Select only the master island
                clear_selection(context)
                master.select(True)

                # Copy master island UV data
                bpy.ops.uv.copy()

                # Select all replicas in this group
                for island in unprocessed_group:
                    if island is not master:
                        island.select(True)
                        stacked_count += 1

                # Paste to stack all replicas onto master
                bpy.ops.uv.paste()

            # Restore original selection
            for obj, selections in original_uv_selections.items():
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    for face in bm.faces:
                        for loop in face.loops:
                            if loop.index in selections:
                                select, select_edge = selections[loop.index]
                                loop[uv_layer].select = select
                                loop[uv_layer].select_edge = select_edge
                    bmesh.update_edit_mesh(obj.data)

            if stacked_count > 0:
                self.report({'INFO'}, f"Stacked {stacked_count} island(s) (fallback method)")
            else:
                self.report({'WARNING'}, "No similar islands found to stack")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Stack operation failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_StackSelected(bpy.types.Operator):
    """Stack selected similar UV islands using Blender's copy/paste (automatically matches rotation and scale)"""
    bl_idname = "uv.uvv_stack_selected"
    bl_label = "Stack Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            # Try UVPackmaster first if available
            try:
                if hasattr(bpy.ops, 'uvpackmaster3'):
                    # Use UVPackmaster's align_similar operator (same as UVPackmaster's stacking)
                    bpy.ops.uvpackmaster3.align_similar()
                    self.report({'INFO'}, "Stacked selected similar islands using UVPackmaster")
                    return {'FINISHED'}
                else:
                    # Fallback to our implementation if UVPackmaster not available
                    self.report({'WARNING'}, "UVPackmaster not available, using fallback method")
            except Exception as e:
                self.report({'WARNING'}, f"UVPackmaster failed: {str(e)}, using fallback method")

            # Fallback: Use our implementation
            # Get all objects in edit mode
            objects = [obj for obj in context.objects_in_mode_unique_data if obj.type == 'MESH']

            # Store original selection state
            original_uv_selections = {}
            for obj in objects:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    original_uv_selections[obj] = {}
                    for face in bm.faces:
                        for loop in face.loops:
                            uv = loop[uv_layer]
                            original_uv_selections[obj][loop.index] = (uv.select, uv.select_edge)

            # Use Mio3's approach: copy/paste with Blender's built-in operators
            stack_system = StackSystem(context)
            scene = context.scene
            selected_islands = stack_system.get_selected_islands()

            if not selected_islands:
                self.report({'WARNING'}, "No islands selected")
                return {'CANCELLED'}

            stacked_count = 0

            # Check if selected islands belong to groups
            selected_in_groups = {}  # group_id -> list of islands
            ungrouped_selected = []

            for island in selected_islands:
                found_group = False
                island_data = island.get_identifier_data()
                
                for stack_group in scene.uvv_stack_groups:
                    group_islands = stack_system.get_group_islands(stack_group.group_id)
                    # Check if this island is in the group by comparing identifiers
                    for group_island in group_islands:
                        group_island_data = group_island.get_identifier_data()
                        if (island_data.get('object_name') == group_island_data.get('object_name') and
                            island_data.get('face_indices') == group_island_data.get('face_indices')):
                            if stack_group.group_id not in selected_in_groups:
                                selected_in_groups[stack_group.group_id] = []
                            selected_in_groups[stack_group.group_id].append(island)
                            found_group = True
                            break
                    if found_group:
                        break
                        
                if not found_group:
                    ungrouped_selected.append(island)

            # Process groups first (only stack islands within same group)
            for group_id, group_selected_islands in selected_in_groups.items():
                if len(group_selected_islands) < 2:
                    continue

                # Group by similarity within this selection
                stack_system.group_by_similarity()
                by_sim_index = {}
                for island in group_selected_islands:
                    sim_index = island.sim_index
                    if sim_index not in by_sim_index:
                        by_sim_index[sim_index] = []
                    by_sim_index[sim_index].append(island)

                # Stack each similarity group
                for sim_index, island_group in by_sim_index.items():
                    if len(island_group) < 2:
                        continue

                    master = stack_system.find_master(island_group)

                    # Select only the master island
                    clear_selection(context)
                    master.select(True)

                    # Copy master island UV data
                    bpy.ops.uv.copy()

                    # Select all replicas in this group
                    for island in island_group:
                        if island is not master:
                            island.select(True)
                            stacked_count += 1

                    # Paste to stack all replicas onto master
                    bpy.ops.uv.paste()

            # Process ungrouped selected islands (similarity-based)
            if len(ungrouped_selected) >= 2:
                stack_system.group_by_similarity()
                selected_stacks = stack_system.get_selected_stacks()

                for island_group in selected_stacks.values():
                    # Filter to only include ungrouped selected islands
                    ungrouped_group = [isl for isl in island_group if isl in ungrouped_selected]
                    if len(ungrouped_group) < 2:
                        continue

                    master = stack_system.find_master(ungrouped_group)

                    # Select only the master island
                    clear_selection(context)
                    master.select(True)

                    # Copy master island UV data
                    bpy.ops.uv.copy()

                    # Select all replicas in this group
                    for island in ungrouped_group:
                        if island is not master:
                            island.select(True)
                            stacked_count += 1

                    # Paste to stack all replicas onto master
                    bpy.ops.uv.paste()

            # Restore original selection
            for obj, selections in original_uv_selections.items():
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    for face in bm.faces:
                        for loop in face.loops:
                            if loop.index in selections:
                                select, select_edge = selections[loop.index]
                                loop[uv_layer].select = select
                                loop[uv_layer].select_edge = select_edge
                    bmesh.update_edit_mesh(obj.data)

            if stacked_count > 0:
                self.report({'INFO'}, f"Stacked {stacked_count} selected island(s) (fallback method)")
            else:
                self.report({'WARNING'}, "No similar islands found in selection")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Stack operation failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_SelectPrimaries(bpy.types.Operator):
    """Select primary islands (base instances for stacking)"""
    bl_idname = "uv.uvv_select_primaries"
    bl_label = "Primaries"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            # Clear selection
            clear_selection(context)

            stack_system = StackSystem(context)
            selected_count = stack_system.select_primaries()

            if selected_count > 0:
                self.report({'INFO'}, f"Selected {selected_count} primary island(s)")
            else:
                self.report({'WARNING'}, "No stacks found")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Select operation failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_SelectReplicas(bpy.types.Operator):
    """Select replica islands (islands with same topology as primaries)"""
    bl_idname = "uv.uvv_select_replicas"
    bl_label = "Replicas"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            # Clear selection
            clear_selection(context)

            stack_system = StackSystem(context)
            selected_count = stack_system.select_replicas()

            if selected_count > 0:
                self.report({'INFO'}, f"Selected {selected_count} replica island(s)")
            else:
                self.report({'WARNING'}, "No replica islands found")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Select operation failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_SelectSingles(bpy.types.Operator):
    """Select unique islands (islands without similar copies)"""
    bl_idname = "uv.uvv_select_singles"
    bl_label = "Singles"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            # Clear selection
            clear_selection(context)

            stack_system = StackSystem(context)
            selected_count = stack_system.select_singles()

            if selected_count > 0:
                self.report({'INFO'}, f"Selected {selected_count} unique island(s)")
            else:
                self.report({'WARNING'}, "No unique islands found")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Select operation failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_SelectSimilar(bpy.types.Operator):
    """Select islands similar to the selected ones (same topology/similarity index)"""
    bl_idname = "uv.uvv_select_similar"
    bl_label = "Select Similar"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            stack_system = StackSystem(context)
            selected_islands = stack_system.get_selected_islands()

            if not selected_islands:
                self.report({'WARNING'}, "No islands selected")
                return {'CANCELLED'}

            # Clear selection first
            clear_selection(context)

            # Select similar islands based on first selected island
            target_island = selected_islands[0]
            selected_count = stack_system.select_similar(target_island)

            if selected_count > 0:
                self.report({'INFO'}, f"Selected {selected_count} similar island(s)")
            else:
                self.report({'WARNING'}, "No similar islands found")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Select operation failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_CreateStackGroup(bpy.types.Operator):
    """Create a new stack group and assign selected islands to it"""
    bl_idname = "uv.uvv_create_stack_group"
    bl_label = "Create Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            stack_system = StackSystem(context)
            selected_islands = stack_system.get_selected_islands()

            if not selected_islands:
                self.report({'WARNING'}, "No islands selected")
                return {'CANCELLED'}

            scene = context.scene

            # Find next available group ID (start from 1, never use 0)
            # 0 is reserved for "no stack group" in UVPackmaster
            existing_ids = [g.group_id for g in scene.uvv_stack_groups]
            next_id = 1
            if existing_ids:
                next_id = max(existing_ids) + 1

            # Create new group
            new_group = scene.uvv_stack_groups.add()
            new_group.name = f"Group {next_id}"
            new_group.group_id = next_id

            # Assign distinct color (simple rotation through hue)
            import colorsys
            hue = (next_id * 0.618034) % 1.0  # Golden ratio for color distribution
            rgb = colorsys.hsv_to_rgb(hue, 0.7, 0.9)
            new_group.color = rgb

            # Assign selected islands to group
            stack_system.assign_to_group(selected_islands, next_id)

            # Update cached count
            new_group.cached_island_count = len(selected_islands)

            scene.uvv_stack_groups_index = len(scene.uvv_stack_groups) - 1

            # Stack the newly created group immediately by calling the stack operator
            if len(selected_islands) >= 2:
                bpy.ops.uv.uvv_stack_group(group_id=next_id)
                self.report({'INFO'}, f"Created and stacked group '{new_group.name}' with {len(selected_islands)} island(s)")
            else:
                self.report({'INFO'}, f"Created stack group '{new_group.name}' with {len(selected_islands)} island(s) (need at least 2 to stack)")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to create group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_AssignToStackGroup(bpy.types.Operator):
    """Assign selected islands to an existing stack group"""
    bl_idname = "uv.uvv_assign_to_stack_group"
    bl_label = "Assign to Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_id: bpy.props.IntProperty(
        name="Group ID",
        description="ID of the stack group to assign islands to",
        default=-1
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            if self.group_id < 0:
                self.report({'ERROR'}, "Invalid group ID")
                return {'CANCELLED'}

            stack_system = StackSystem(context)
            selected_islands = stack_system.get_selected_islands()

            if not selected_islands:
                self.report({'WARNING'}, "No islands selected")
                return {'CANCELLED'}

            # Find group
            scene = context.scene
            stack_group = None
            for group in scene.uvv_stack_groups:
                if group.group_id == self.group_id:
                    stack_group = group
                    break

            if not stack_group:
                self.report({'ERROR'}, f"Group {self.group_id} not found")
                return {'CANCELLED'}

            # Assign islands
            if stack_system.assign_to_group(selected_islands, self.group_id):
                self.report({'INFO'}, f"Assigned {len(selected_islands)} island(s) to '{stack_group.name}'")
            else:
                self.report({'ERROR'}, "Failed to assign islands to group")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to assign to group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_SelectStackGroup(bpy.types.Operator):
    """Select all islands in a stack group"""
    bl_idname = "uv.uvv_select_stack_group"
    bl_label = "Select Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_id: bpy.props.IntProperty(
        name="Group ID",
        description="ID of the stack group to select",
        default=-1
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            if self.group_id < 0:
                self.report({'ERROR'}, "Invalid group ID")
                return {'CANCELLED'}

            stack_system = StackSystem(context)

            # Clear selection first
            clear_selection(context)

            # Select group islands
            selected_count = stack_system.select_group(self.group_id)

            if selected_count > 0:
                scene = context.scene
                group_name = "Unknown"
                for group in scene.uvv_stack_groups:
                    if group.group_id == self.group_id:
                        group_name = group.name
                        break
                self.report({'INFO'}, f"Selected {selected_count} island(s) from '{group_name}'")
            else:
                self.report({'WARNING'}, "No islands found in group")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to select group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_RemoveFromStackGroup(bpy.types.Operator):
    """Remove selected islands from their stack group"""
    bl_idname = "uv.uvv_remove_from_stack_group"
    bl_label = "Remove from Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_id: bpy.props.IntProperty(
        name="Group ID",
        description="ID of the stack group to remove islands from",
        default=-1
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            if self.group_id < 0:
                self.report({'ERROR'}, "Invalid group ID")
                return {'CANCELLED'}

            stack_system = StackSystem(context)
            selected_islands = stack_system.get_selected_islands()

            if not selected_islands:
                self.report({'WARNING'}, "No islands selected")
                return {'CANCELLED'}

            if stack_system.remove_from_group(selected_islands, self.group_id):
                scene = context.scene
                group_name = "Unknown"
                for group in scene.uvv_stack_groups:
                    if group.group_id == self.group_id:
                        group_name = group.name
                        break
                self.report({'INFO'}, f"Removed {len(selected_islands)} island(s) from '{group_name}'")
            else:
                self.report({'ERROR'}, "Failed to remove islands from group")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to remove from group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_DeleteStackGroup(bpy.types.Operator):
    """Delete a stack group"""
    bl_idname = "uv.uvv_delete_stack_group"
    bl_label = "Delete Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_id: bpy.props.IntProperty(
        name="Group ID",
        description="ID of the stack group to delete",
        default=-1
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        try:
            if self.group_id < 0:
                self.report({'ERROR'}, "Invalid group ID")
                return {'CANCELLED'}

            scene = context.scene

            # Find and remove group
            for i, group in enumerate(scene.uvv_stack_groups):
                if group.group_id == self.group_id:
                    group_name = group.name
                    scene.uvv_stack_groups.remove(i)
                    if scene.uvv_stack_groups_index >= len(scene.uvv_stack_groups):
                        scene.uvv_stack_groups_index = len(scene.uvv_stack_groups) - 1
                    self.report({'INFO'}, f"Deleted stack group '{group_name}'")
                    return {'FINISHED'}

            self.report({'ERROR'}, f"Group {self.group_id} not found")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to delete group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_StackGroup(bpy.types.Operator):
    """Stack all islands in the specified group"""
    bl_idname = "uv.uvv_stack_group"
    bl_label = "Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_id: IntProperty(
        name="Group ID",
        description="ID of the stack group to stack",
        default=0,
        min=0
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            stack_system = StackSystem(context)
            
            # Get islands in the specified group
            group_islands = stack_system.get_group_islands(self.group_id)
            
            if not group_islands:
                self.report({'WARNING'}, f"No islands found in group {self.group_id}")
                return {'CANCELLED'}

            if len(group_islands) < 2:
                self.report({'WARNING'}, f"Group {self.group_id} has only {len(group_islands)} island(s). Need at least 2 to stack.")
                return {'CANCELLED'}

            # Stack ONLY the islands in this group, not all similar islands
            # This allows users to have multiple groups with the same looking islands

            # Find the master island (least distorted)
            master = stack_system.find_master(group_islands)

            # Clear current selection
            clear_selection(context)

            # Select only the master island
            master.select(True)

            # Copy master island UV data
            bpy.ops.uv.copy()

            # Clear selection and select all replicas (everything except master)
            clear_selection(context)
            stacked_count = 0
            for island in group_islands:
                if island is not master:
                    island.select(True)
                    stacked_count += 1

            # Paste to stack all replicas on the master
            bpy.ops.uv.paste()

            # Update all meshes
            for obj in stack_system.context.objects_in_mode_unique_data:
                if obj.type == 'MESH':
                    bmesh.update_edit_mesh(obj.data)

            self.report({'INFO'}, f"Stacked {stacked_count} islands from group {self.group_id} (fallback method)")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to stack group: {str(e)}")
            return {'CANCELLED'}


class UVV_OT_StackAllGroups(bpy.types.Operator):
    """Stack all islands in all stack groups"""
    bl_idname = "uv.uvv_stack_all_groups"
    bl_label = "Stack All Groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            stack_system = StackSystem(context)
            scene = context.scene
            stack_groups = scene.uvv_stack_groups
            
            if not stack_groups:
                self.report({'WARNING'}, "No stack groups found")
                return {'CANCELLED'}

            total_stacked = 0
            groups_processed = 0

            # Use UVPackmaster's engine for stacking all groups
            try:
                # Check if UVPackmaster is available
                if hasattr(bpy.ops, 'uvpackmaster3'):
                    # Clear selection first
                    clear_selection(context)
                    
                    # Select all islands from all groups
                    all_group_islands = []
                    for group in stack_groups:
                        group_islands = stack_system.get_group_islands(group.group_id)
                        if len(group_islands) >= 2:
                            all_group_islands.extend(group_islands)
                            groups_processed += 1
                    
                    if all_group_islands:
                        # Select all islands from all groups
                        for island in all_group_islands:
                            island.select(True)
                        
                        # Use UVPackmaster's align_similar operator (same as UVPackmaster's stacking)
                        bpy.ops.uvpackmaster3.align_similar()
                        total_stacked = len(all_group_islands)
                        self.report({'INFO'}, f"Stacked {total_stacked} islands across {groups_processed} groups using UVPackmaster")
                        return {'FINISHED'}
                    else:
                        self.report({'WARNING'}, "No groups with 2+ islands found to stack")
                        return {'CANCELLED'}
                else:
                    # Fallback to our implementation if UVPackmaster not available
                    self.report({'WARNING'}, "UVPackmaster not available, using fallback method")
            except Exception as e:
                self.report({'WARNING'}, f"UVPackmaster failed: {str(e)}, using fallback method")

            # Fallback: Process each group individually
            for group in stack_groups:
                group_islands = stack_system.get_group_islands(group.group_id)
                
                if len(group_islands) < 2:
                    continue  # Skip groups with less than 2 islands

                groups_processed += 1
                
                # Clear current selection
                clear_selection(context)
                
                # Select all islands in the group
                for island in group_islands:
                    island.select(True)

                # Use Mio3's approach: copy/paste with Blender's built-in operators
                stack_system.group_by_similarity()
                selected_stacks = stack_system.get_selected_stacks()

                stacked_count = 0

                # Process each stack group
                for island_group in selected_stacks.values():
                    if len(island_group) < 2:
                        continue

                    master = stack_system.find_master(island_group)

                    # Select only the master island
                    clear_selection(context)
                    master.select(True)

                    # Copy master island UV data
                    bpy.ops.uv.copy()

                    # Select all replicas in this group
                    for island in island_group:
                        if island is not master:
                            island.select(True)
                            stacked_count += 1

                    # Paste to stack all replicas on the master
                    bpy.ops.uv.paste()

                total_stacked += stacked_count

            # Update all meshes
            for obj in stack_system.context.objects_in_mode_unique_data:
                if obj.type == 'MESH':
                    bmesh.update_edit_mesh(obj.data)

            if groups_processed > 0:
                self.report({'INFO'}, f"Stacked {total_stacked} islands across {groups_processed} groups")
            else:
                self.report({'WARNING'}, "No groups with 2+ islands found to stack")
            
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to stack all groups: {str(e)}")
            return {'CANCELLED'}


class UVV_OT_RefreshGroupCounts(bpy.types.Operator):
    """Refresh cached island counts for all stack groups"""
    bl_idname = "uv.uvv_refresh_group_counts"
    bl_label = "Refresh Group Counts"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            stack_system = StackSystem(context)
            stack_system.refresh_group_counts()
            self.report({'INFO'}, "Refreshed group counts")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to refresh counts: {str(e)}")
            return {'CANCELLED'}


class UVV_OT_GroupBySimilarity(bpy.types.Operator):
    """Group selected islands by similarity and create stack groups automatically"""
    bl_idname = "uv.uvv_group_by_similarity"
    bl_label = "Auto Group"
    bl_options = {'REGISTER', 'UNDO'}

    min_group_size: IntProperty(
        name="Minimum Group Size",
        description="Minimum number of islands required in a group (groups with fewer islands will be ignored)",
        default=2,
        min=1,
        max=100
    )

    # Track groups created by this operator instance for replacement
    _created_group_ids = []

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def invoke(self, context, event):
        # Show popup dialog asking for minimum group size
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        """Draw the popup dialog content"""
        layout = self.layout
        layout.prop(self, 'min_group_size', text="Minimum Group Size")

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            stack_system = StackSystem(context)
            selected_islands = stack_system.get_selected_islands()

            if not selected_islands:
                self.report({'WARNING'}, "No islands selected")
                return {'CANCELLED'}

            if len(selected_islands) < 2:
                self.report({'WARNING'}, "Need at least 2 islands to group by similarity")
                return {'CANCELLED'}

            scene = context.scene

            # Clear previously created similarity groups (only those created by this operator)
            if hasattr(self.__class__, '_created_group_ids') and self.__class__._created_group_ids:
                indices_to_remove = []
                for i, group in enumerate(scene.uvv_stack_groups):
                    if group.group_id in self.__class__._created_group_ids:
                        indices_to_remove.append(i)

                # Remove in reverse order to maintain correct indices
                for i in reversed(indices_to_remove):
                    scene.uvv_stack_groups.remove(i)
                    if scene.uvv_stack_groups_index >= len(scene.uvv_stack_groups):
                        scene.uvv_stack_groups_index = max(0, len(scene.uvv_stack_groups) - 1)

                # Clear the tracking list
                self.__class__._created_group_ids = []

            # Group islands by similarity
            stack_system.group_by_similarity()
            selected_stacks = stack_system.get_selected_stacks()

            if not selected_stacks:
                self.report({'WARNING'}, "No similar islands found to group")
                return {'CANCELLED'}

            groups_created = 0
            skipped_count = 0

            # Create a group for each similarity group (filter by min_group_size)
            for sim_index, island_group in selected_stacks.items():
                # Skip groups below minimum size
                if len(island_group) < self.min_group_size:
                    skipped_count += 1
                    continue

                # Find next available group ID (start from 1, never use 0)
                # 0 is reserved for "no stack group" in UVPackmaster
                existing_ids = [g.group_id for g in scene.uvv_stack_groups]
                next_id = 1
                if existing_ids:
                    next_id = max(existing_ids) + 1

                # Create new group
                new_group = scene.uvv_stack_groups.add()
                new_group.name = f"Similarity Group {groups_created + 1}"
                new_group.group_id = next_id

                # Assign distinct color (simple rotation through hue)
                import colorsys
                hue = (groups_created * 0.618034) % 1.0  # Golden ratio for color distribution
                rgb = colorsys.hsv_to_rgb(hue, 0.7, 0.9)
                new_group.color = rgb

                # Assign islands to group
                stack_system.assign_to_group(island_group, next_id)

                # Update cached count
                new_group.cached_island_count = len(island_group)

                # Track this group ID for future replacements
                self.__class__._created_group_ids.append(next_id)

                groups_created += 1

            # Force UI refresh so lists update immediately in 4.2+
            try:
                for window in context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type in {'IMAGE_EDITOR', 'VIEW_3D'}:
                            area.tag_redraw()
                bpy.context.view_layer.update()
                try:
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                except Exception:
                    pass
            except Exception:
                pass

            if groups_created > 0:
                if skipped_count > 0:
                    self.report({'INFO'}, f"Created {groups_created} similarity group(s) (skipped {skipped_count} group(s) below {self.min_group_size} islands)")
                else:
                    self.report({'INFO'}, f"Created {groups_created} similarity group(s) with {len(selected_islands)} island(s)")
            else:
                if skipped_count > 0:
                    self.report({'WARNING'}, f"No groups found with {self.min_group_size}+ islands (skipped {skipped_count} small group(s))")
                else:
                    self.report({'WARNING'}, "No similar islands found to group")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to group by similarity: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_DeleteActiveStackGroup(bpy.types.Operator):
    """Delete the active stack group"""
    bl_idname = "uv.uvv_delete_active_stack_group"
    bl_label = "Delete Active Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and 
                context.active_object and 
                context.active_object.type == 'MESH' and
                len(context.scene.uvv_stack_groups) > 0)

    def execute(self, context):
        try:
            scene = context.scene
            index = scene.uvv_stack_groups_index

            if 0 <= index < len(scene.uvv_stack_groups):
                group = scene.uvv_stack_groups[index]
                group_name = group.name
                scene.uvv_stack_groups.remove(index)
                
                # Adjust index if needed
                if scene.uvv_stack_groups_index >= len(scene.uvv_stack_groups):
                    scene.uvv_stack_groups_index = len(scene.uvv_stack_groups) - 1
                
                self.report({'INFO'}, f"Deleted stack group '{group_name}'")
            else:
                self.report({'ERROR'}, "No active group to delete")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to delete group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_BatchRemoveSmallStackGroups(bpy.types.Operator):
    """Remove all stack groups that have fewer islands than the minimum group size"""
    bl_idname = "uv.uvv_batch_remove_small_groups"
    bl_label = "Remove Small Groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem
        from ..properties import get_uvv_settings

        try:
            settings = get_uvv_settings()
            min_size = settings.stack_min_group_size
            
            if min_size < 1:
                self.report({'WARNING'}, "Minimum group size must be at least 1")
                return {'CANCELLED'}

            stack_system = StackSystem(context)
            scene = context.scene
            stack_groups = scene.uvv_stack_groups

            if not stack_groups:
                self.report({'INFO'}, "No stack groups to check")
                return {'FINISHED'}

            removed_count = 0
            removed_names = []

            # Collect groups to remove (iterate backwards to avoid index issues)
            groups_to_remove = []
            for i in range(len(stack_groups) - 1, -1, -1):
                group = stack_groups[i]
                island_count = group.cached_island_count
                
                if island_count < min_size:
                    groups_to_remove.append((i, group.name, island_count))

            # Remove groups
            for i, group_name, island_count in groups_to_remove:
                scene.uvv_stack_groups.remove(i)
                removed_count += 1
                removed_names.append(f"{group_name} ({island_count} island{'s' if island_count != 1 else ''})")
                
                # Adjust active index if needed
                if scene.uvv_stack_groups_index >= len(scene.uvv_stack_groups):
                    scene.uvv_stack_groups_index = max(0, len(scene.uvv_stack_groups) - 1)

            if removed_count > 0:
                self.report({'INFO'}, f"Removed {removed_count} group(s) below {min_size} islands: {', '.join(removed_names)}")
            else:
                self.report({'INFO'}, f"No groups found with fewer than {min_size} island(s)")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to remove groups: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_RemoveAllStackGroups(bpy.types.Operator):
    """Remove all stack groups"""
    bl_idname = "uv.uvv_remove_all_stack_groups"
    bl_label = "Remove All Groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object and
                context.active_object.type == 'MESH' and
                len(context.scene.uvv_stack_groups) > 0)

    def invoke(self, context, event):
        # Show confirmation dialog
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            scene = context.scene
            group_count = len(scene.uvv_stack_groups)

            if group_count == 0:
                self.report({'INFO'}, "No groups to remove")
                return {'FINISHED'}

            # Remove all groups
            scene.uvv_stack_groups.clear()
            scene.uvv_stack_groups_index = 0

            self.report({'INFO'}, f"Removed all {group_count} stack group(s)")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to remove groups: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_SelectOnlyActiveStackGroup(bpy.types.Operator):
    """Select all islands in the active stack group from the list"""
    bl_idname = "uv.uvv_select_only_active_stack_group"
    bl_label = "Select Active Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object and
                context.active_object.type == 'MESH' and
                len(context.scene.uvv_stack_groups) > 0)

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            scene = context.scene
            index = scene.uvv_stack_groups_index

            if index < 0 or index >= len(scene.uvv_stack_groups):
                self.report({'WARNING'}, "No active stack group")
                return {'CANCELLED'}

            active_group = scene.uvv_stack_groups[index]
            group_id = active_group.group_id

            # Clear selection first
            clear_selection(context)

            # Select the active group
            stack_system = StackSystem(context)
            selected_count = stack_system.select_group(group_id)

            if selected_count > 0:
                self.report({'INFO'}, f"Selected {selected_count} island(s) from '{active_group.name}'")
            else:
                self.report({'WARNING'}, f"No islands found in '{active_group.name}'")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to select group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_AssignToActiveStackGroup(bpy.types.Operator):
    """Assign selected islands to the active stack group"""
    bl_idname = "uv.uvv_assign_to_active_stack_group"
    bl_label = "Assign to Active Stack Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object and
                context.active_object.type == 'MESH' and
                len(context.scene.uvv_stack_groups) > 0)

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            scene = context.scene
            index = scene.uvv_stack_groups_index

            if index < 0 or index >= len(scene.uvv_stack_groups):
                self.report({'WARNING'}, "No active stack group")
                return {'CANCELLED'}

            active_group = scene.uvv_stack_groups[index]
            group_id = active_group.group_id

            stack_system = StackSystem(context)
            selected_islands = stack_system.get_selected_islands()

            if not selected_islands:
                self.report({'WARNING'}, "No islands selected")
                return {'CANCELLED'}

            # Assign islands
            if stack_system.assign_to_group(selected_islands, group_id):
                # Update cached count
                active_group.cached_island_count = len(stack_system.get_group_islands(group_id))
                self.report({'INFO'}, f"Assigned {len(selected_islands)} island(s) to '{active_group.name}'")
            else:
                self.report({'ERROR'}, "Failed to assign islands to group")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to assign to group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_StackActiveGroup(bpy.types.Operator):
    """Stack the active stack group from the list"""
    bl_idname = "uv.uvv_stack_active_group"
    bl_label = "Stack Active Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object and
                context.active_object.type == 'MESH' and
                len(context.scene.uvv_stack_groups) > 0)

    def execute(self, context):
        try:
            scene = context.scene
            index = scene.uvv_stack_groups_index

            if index < 0 or index >= len(scene.uvv_stack_groups):
                self.report({'WARNING'}, "No active stack group")
                return {'CANCELLED'}

            active_group = scene.uvv_stack_groups[index]
            group_id = active_group.group_id

            # Call the stack group operator
            bpy.ops.uv.uvv_stack_group(group_id=group_id)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to stack group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


classes = [
    UVV_OT_StackAll,
    UVV_OT_StackSelected,
    UVV_OT_SelectPrimaries,
    UVV_OT_SelectReplicas,
    UVV_OT_SelectSingles,
    UVV_OT_SelectSimilar,
    UVV_OT_CreateStackGroup,
    UVV_OT_AssignToStackGroup,
    UVV_OT_SelectStackGroup,
    UVV_OT_RemoveFromStackGroup,
    UVV_OT_DeleteStackGroup,
    UVV_OT_StackGroup,
    UVV_OT_StackAllGroups,
    UVV_OT_RefreshGroupCounts,
    UVV_OT_GroupBySimilarity,
    UVV_OT_DeleteActiveStackGroup,
    UVV_OT_BatchRemoveSmallStackGroups,
    UVV_OT_RemoveAllStackGroups,
    UVV_OT_SelectOnlyActiveStackGroup,
    UVV_OT_AssignToActiveStackGroup,
    UVV_OT_StackActiveGroup,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
