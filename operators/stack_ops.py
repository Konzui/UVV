"""Stack operators for UV island stacking and selection"""

import bpy
import bmesh
import time
from bpy.props import BoolProperty, EnumProperty, IntProperty
from ..properties import get_uvv_settings

# Track last click time and group ID for double-click detection
# Key: group_id, Value: (timestamp, group_id)
_last_click_info = {}


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

            # First, process stack groups (prioritize manual groups) for each object
            for obj in objects:
                if len(obj.uvv_stack_groups) > 0:
                    for stack_group in obj.uvv_stack_groups:
                        group_islands = stack_system.get_group_islands(stack_group.group_id, obj=obj)
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

            # Get active object's stack groups
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            for island in selected_islands:
                found_group = False
                island_data = island.get_identifier_data()
                
                # Only check stack groups from the island's object
                island_obj = island.obj
                for stack_group in island_obj.uvv_stack_groups:
                    group_islands = stack_system.get_group_islands(stack_group.group_id, obj=island_obj)
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

            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}

            # Find next available group ID (start from 1, never use 0)
            # 0 is reserved for "no stack group" in UVPackmaster
            existing_ids = [g.group_id for g in obj.uvv_stack_groups]
            next_id = 1
            if existing_ids:
                next_id = max(existing_ids) + 1

            # Create new group on active object
            new_group = obj.uvv_stack_groups.add()
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

            obj.uvv_stack_groups_index = len(obj.uvv_stack_groups) - 1

            # Stack the newly created group immediately by calling the stack operator
            if len(selected_islands) >= 2:
                bpy.ops.uv.uvv_stack_group(group_id=next_id)
                self.report({'INFO'}, f"Created and stacked group '{new_group.name}' with {len(selected_islands)} island(s)")
            else:
                self.report({'INFO'}, f"Created stack group '{new_group.name}' with {len(selected_islands)} island(s) (need at least 2 to stack)")

            # Refresh overlay if enabled
            from ..utils.stack_overlay import refresh_overlay
            refresh_overlay()

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

            # Find group on active object
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            stack_group = None
            for group in obj.uvv_stack_groups:
                if group.group_id == self.group_id:
                    stack_group = group
                    break

            if not stack_group:
                self.report({'ERROR'}, f"Group {self.group_id} not found")
                return {'CANCELLED'}

            # Assign islands
            if stack_system.assign_to_group(selected_islands, self.group_id):
                self.report({'INFO'}, f"Assigned {len(selected_islands)} island(s) to '{stack_group.name}'")
                
                # Refresh overlay if enabled
                from ..utils.stack_overlay import refresh_overlay
                refresh_overlay()
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

    def invoke(self, context, event):
        """Handle double-click detection - only execute on double-click"""
        global _last_click_info
        
        current_time = time.time()
        is_double_click = False
        
        # Check if this is a double-click (same group, within 0.3 seconds)
        if self.group_id in _last_click_info:
            last_time, last_group_id = _last_click_info[self.group_id]
            time_diff = current_time - last_time
            # Only treat as double-click if it's the same group and within threshold
            if last_group_id == self.group_id and time_diff < 0.3:  # 300ms double-click threshold
                is_double_click = True
        
        # Update last click info
        _last_click_info[self.group_id] = (current_time, self.group_id)
        
        # Only execute on double-click
        if is_double_click:
            # Reset click tracking to prevent triple-click from being detected as double-click
            del _last_click_info[self.group_id]
            return self.execute(context)
        
        # Single click - do nothing (just update click tracking)
        return {'CANCELLED'}

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

            # Set the clicked group as active in the list
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            group_name = "Unknown"
            group_index = -1
            for idx, group in enumerate(obj.uvv_stack_groups):
                if group.group_id == self.group_id:
                    group_name = group.name
                    group_index = idx
                    break
            
            # Set this group as active in the list
            if group_index >= 0:
                obj.uvv_stack_groups_index = group_index

            if selected_count > 0:
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

            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            if stack_system.remove_from_group(selected_islands, self.group_id):
                group_name = "Unknown"
                for group in obj.uvv_stack_groups:
                    if group.group_id == self.group_id:
                        group_name = group.name
                        break
                self.report({'INFO'}, f"Removed {len(selected_islands)} island(s) from '{group_name}'")
                
                # Refresh overlay if enabled
                from ..utils.stack_overlay import refresh_overlay
                refresh_overlay()
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

            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}

            # Find and remove group
            for i, group in enumerate(obj.uvv_stack_groups):
                if group.group_id == self.group_id:
                    group_name = group.name
                    obj.uvv_stack_groups.remove(i)
                    if obj.uvv_stack_groups_index >= len(obj.uvv_stack_groups):
                        obj.uvv_stack_groups_index = len(obj.uvv_stack_groups) - 1
                    self.report({'INFO'}, f"Deleted stack group '{group_name}'")
                    
                    # Refresh overlay if enabled
                    from ..utils.stack_overlay import refresh_overlay
                    refresh_overlay()
                    
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
            
            # Collect all stack groups from all objects in mode
            all_stack_groups = []
            for obj in context.objects_in_mode_unique_data:
                if obj.type != 'MESH':
                    continue
                for group in obj.uvv_stack_groups:
                    all_stack_groups.append((obj, group))
            
            if not all_stack_groups:
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
                    for obj, group in all_stack_groups:
                        group_islands = stack_system.get_group_islands(group.group_id, obj=obj)
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
            for obj, group in all_stack_groups:
                group_islands = stack_system.get_group_islands(group.group_id, obj=obj)
                
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


def get_category_set(max_area, min_area):
    """Select which size categories to use based on the ratio between max and min areas
    
    Args:
        max_area: Maximum UV area
        min_area: Minimum UV area
    
    Returns:
        list: List of category names to use, ordered from smallest to largest
    """
    # Handle edge cases: single island or all same size
    if max_area <= min_area or max_area == 0 or min_area == 0:
        return ["Medium"]
    
    # Calculate ratio
    ratio = max_area / min_area
    
    # Select category set based on ratio thresholds
    if ratio < 5.0:
        # Ratio < 5x: Use Small, Medium, Large (3 categories)
        return ["Small", "Medium", "Large"]
    elif ratio < 10.0:
        # 5x ≤ ratio < 10x: Use Mini, Small, Medium, Large (4 categories)
        return ["Mini", "Small", "Medium", "Large"]
    else:
        # Ratio ≥ 10x: Use full range Tiny, Mini, Small, Medium, Large, Huge (6 categories)
        return ["Tiny", "Mini", "Small", "Medium", "Large", "Huge"]


def get_size_category(area, min_area, max_area, category_set):
    """Get size category based on percentile position within the selected category set
    
    Args:
        area: UV area of the island
        min_area: Minimum UV area across all islands
        max_area: Maximum UV area across all islands
        category_set: List of category names to use (ordered from smallest to largest)
    
    Returns:
        str: Size category name from the provided category set
    """
    # Handle edge cases: single island or all same size
    if max_area <= min_area or max_area == 0 or len(category_set) == 0:
        return category_set[0] if category_set else "Medium"
    
    # If only one category in set, use it
    if len(category_set) == 1:
        return category_set[0]
    
    # Calculate percentile position (0.0 to 1.0)
    if area <= min_area:
        percentile = 0.0
    elif area >= max_area:
        percentile = 1.0
    else:
        percentile = (area - min_area) / (max_area - min_area)
    
    # Map percentile to category based on number of categories
    # Divide the 0-1 range into equal segments for each category
    num_categories = len(category_set)
    
    # Special handling for exact boundaries
    if percentile == 0.0:
        category_index = 0
    elif percentile == 1.0:
        category_index = num_categories - 1
    else:
        # Map percentile to category index
        # Each category gets 1/num_categories of the range
        # e.g., for 3 categories: [0, 1/3), [1/3, 2/3), [2/3, 1]
        category_index = min(int(percentile * num_categories), num_categories - 1)
        # Ensure we don't assign max value to a middle category
        if percentile >= 1.0 - 1e-10:  # Very close to 1.0
            category_index = num_categories - 1
    
    return category_set[category_index]


def get_object_name_prefix(obj_name):
    """Get first and last letter of object name
    
    Args:
        obj_name: Name of the object
    
    Returns:
        str: First letter + last letter (e.g., "Cube" -> "Ce")
    """
    if not obj_name:
        return "XX"
    
    # Strip whitespace
    name = obj_name.strip()
    
    if len(name) == 0:
        return "XX"
    elif len(name) == 1:
        # Single character: use it twice
        return name + name
    else:
        # Multiple characters: first + last
        return name[0] + name[-1]


class UVV_OT_GroupBySimilarity(bpy.types.Operator):
    """Group selected islands by similarity and create stack groups automatically"""
    bl_idname = "uv.uvv_group_by_similarity"
    bl_label = "Auto Group"
    bl_options = {'REGISTER', 'UNDO'}

    # Track groups created by this operator instance for replacement
    _created_group_ids = []

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            settings = get_uvv_settings()
            min_group_size = settings.stack_min_group_size
            
            stack_system = StackSystem(context)
            selected_islands = stack_system.get_selected_islands()

            # If no islands are selected, automatically select all islands
            if not selected_islands:
                # Select all UV islands
                bpy.ops.uv.select_all(action='SELECT')
                # Refresh the stack system to get the newly selected islands
                stack_system = StackSystem(context)
                selected_islands = stack_system.get_selected_islands()
                
                if not selected_islands:
                    self.report({'WARNING'}, "No islands found to group")
                    return {'CANCELLED'}

            if len(selected_islands) < 2:
                self.report({'WARNING'}, "Need at least 2 islands to group by similarity")
                return {'CANCELLED'}

            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}

            # Clear previously created similarity groups (only those created by this operator)
            if hasattr(self.__class__, '_created_group_ids') and self.__class__._created_group_ids:
                indices_to_remove = []
                for i, group in enumerate(obj.uvv_stack_groups):
                    if group.group_id in self.__class__._created_group_ids:
                        indices_to_remove.append(i)

                # Remove in reverse order to maintain correct indices
                for i in reversed(indices_to_remove):
                    obj.uvv_stack_groups.remove(i)
                    if obj.uvv_stack_groups_index >= len(obj.uvv_stack_groups):
                        obj.uvv_stack_groups_index = max(0, len(obj.uvv_stack_groups) - 1)

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

            # Filter valid groups (above minimum size) and collect data for smart naming
            valid_groups = []
            uv_areas = []
            
            for sim_index, island_group in selected_stacks.items():
                # Skip groups below minimum size
                if len(island_group) < min_group_size:
                    skipped_count += 1
                    continue
                
                valid_groups.append((sim_index, island_group))
                
                # Calculate UV area for the first island in this group
                try:
                    first_island = island_group[0]
                    uv_area = first_island.calc_uv_area()
                    uv_areas.append(uv_area)
                except (AttributeError, ReferenceError, IndexError):
                    # Fallback: use bbox size as area approximation if calc_uv_area fails
                    try:
                        uv_area = first_island.bbox_size.x * first_island.bbox_size.y
                        uv_areas.append(uv_area)
                    except (AttributeError, ReferenceError):
                        uv_areas.append(0.0)
            
            # Determine min/max UV areas for size categorization
            min_area = min(uv_areas) if uv_areas else 0.0
            max_area = max(uv_areas) if uv_areas else 0.0
            
            # Get category set based on ratio between max and min
            category_set = get_category_set(max_area, min_area)
            
            # Initialize counters dynamically for each category in the selected set
            size_counters = {category: 0 for category in category_set}
            
            # Get object name prefix once
            obj_name_prefix = get_object_name_prefix(obj.name)

            # Create a group for each valid similarity group
            for idx, (sim_index, island_group) in enumerate(valid_groups):
                # Get UV area from stored values (calculated in first pass)
                uv_area = uv_areas[idx] if idx < len(uv_areas) else 0.0
                
                # Determine size category using the dynamic category set
                size_category = get_size_category(uv_area, min_area, max_area, category_set)
                
                # Increment counter for this size category
                size_counters[size_category] += 1
                counter_value = size_counters[size_category]
                
                # Generate smart name: "{FirstLastLetter} {SizeCategory} {Counter}"
                smart_name = f"{obj_name_prefix} {size_category} {counter_value}"

                # Find next available group ID (start from 1, never use 0)
                # 0 is reserved for "no stack group" in UVPackmaster
                existing_ids = [g.group_id for g in obj.uvv_stack_groups]
                next_id = 1
                if existing_ids:
                    next_id = max(existing_ids) + 1

                # Create new group on active object
                new_group = obj.uvv_stack_groups.add()
                new_group.name = smart_name
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
                    self.report({'INFO'}, f"Created {groups_created} similarity group(s) (skipped {skipped_count} group(s) below {min_group_size} islands)")
                else:
                    self.report({'INFO'}, f"Created {groups_created} similarity group(s) with {len(selected_islands)} island(s)")
            else:
                if skipped_count > 0:
                    self.report({'WARNING'}, f"No groups found with {min_group_size}+ islands (skipped {skipped_count} small group(s))")
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
                len(context.active_object.uvv_stack_groups) > 0)

    def execute(self, context):
        try:
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            index = obj.uvv_stack_groups_index

            if 0 <= index < len(obj.uvv_stack_groups):
                group = obj.uvv_stack_groups[index]
                group_name = group.name
                obj.uvv_stack_groups.remove(index)
                
                # Adjust index if needed
                if obj.uvv_stack_groups_index >= len(obj.uvv_stack_groups):
                    obj.uvv_stack_groups_index = len(obj.uvv_stack_groups) - 1
                
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
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            stack_groups = obj.uvv_stack_groups

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
                obj.uvv_stack_groups.remove(i)
                removed_count += 1
                removed_names.append(f"{group_name} ({island_count} island{'s' if island_count != 1 else ''})")
                
                # Adjust active index if needed
                if obj.uvv_stack_groups_index >= len(obj.uvv_stack_groups):
                    obj.uvv_stack_groups_index = max(0, len(obj.uvv_stack_groups) - 1)

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
                len(context.active_object.uvv_stack_groups) > 0)

    def invoke(self, context, event):
        # Show confirmation dialog
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            group_count = len(obj.uvv_stack_groups)

            if group_count == 0:
                self.report({'INFO'}, "No groups to remove")
                return {'FINISHED'}

            # Remove all groups
            obj.uvv_stack_groups.clear()
            obj.uvv_stack_groups_index = 0

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
    bl_description = (
        "Select all islands in the active stack group\n"
        "\n"
        "TIP: You can also double-click on the island amount\n"
        "in the stack groups list to select them"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and
                context.active_object and
                context.active_object.type == 'MESH' and
                len(context.active_object.uvv_stack_groups) > 0)

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            index = obj.uvv_stack_groups_index

            if index < 0 or index >= len(obj.uvv_stack_groups):
                self.report({'WARNING'}, "No active stack group")
                return {'CANCELLED'}

            active_group = obj.uvv_stack_groups[index]
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
                len(context.active_object.uvv_stack_groups) > 0)

    def execute(self, context):
        from ..utils.stack_utils import StackSystem

        try:
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            index = obj.uvv_stack_groups_index

            if index < 0 or index >= len(obj.uvv_stack_groups):
                self.report({'WARNING'}, "No active stack group")
                return {'CANCELLED'}

            active_group = obj.uvv_stack_groups[index]
            group_id = active_group.group_id

            stack_system = StackSystem(context)
            selected_islands = stack_system.get_selected_islands()

            if not selected_islands:
                self.report({'WARNING'}, "No islands selected")
                return {'CANCELLED'}

            # Assign islands
            if stack_system.assign_to_group(selected_islands, group_id):
                # Update cached count
                active_group.cached_island_count = len(stack_system.get_group_islands(group_id, obj=obj))
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
                len(context.active_object.uvv_stack_groups) > 0)

    def execute(self, context):
        try:
            obj = context.active_object
            if not obj:
                self.report({'ERROR'}, "No active object")
                return {'CANCELLED'}
            
            index = obj.uvv_stack_groups_index

            if index < 0 or index >= len(obj.uvv_stack_groups):
                self.report({'WARNING'}, "No active stack group")
                return {'CANCELLED'}

            active_group = obj.uvv_stack_groups[index]
            group_id = active_group.group_id

            # Call the stack group operator
            bpy.ops.uv.uvv_stack_group(group_id=group_id)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to stack group: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class UVV_OT_HighlightStackGroup(bpy.types.Operator):
    """Temporarily highlight all islands in this stack group"""
    bl_idname = "uv.uvv_highlight_stack_group"
    bl_label = "Highlight Stack Group"
    bl_options = {'REGISTER'}

    group_id: IntProperty(
        name="Group ID",
        description="ID of the stack group to highlight",
        default=-1
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ..utils.stack_overlay import StackOverlayManager

        try:
            settings = context.scene.uvv_settings

            # Only highlight if feature is enabled
            if not settings.stack_overlay_highlight_on_click:
                return {'CANCELLED'}

            manager = StackOverlayManager.instance()

            # If overlay is enabled in settings but manager isn't initialized, enable it now
            if not manager.enabled and settings.stack_overlay_enabled:
                manager.enable(context)

            if not manager.enabled:
                return {'CANCELLED'}

            # Trigger highlight
            manager.highlight_group(self.group_id)

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to highlight group: {str(e)}")
            return {'CANCELLED'}


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
    UVV_OT_HighlightStackGroup,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
