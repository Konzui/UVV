"""Create trimsheet from plane cutting workflow"""

import bpy
from bpy.types import Operator
import bmesh
from mathutils import Vector
from ..utils import trimsheet_utils


class UVV_OT_trim_from_plane_start(Operator):
    """Start the trim creation from plane workflow"""
    bl_idname = "uv.uvv_trim_from_plane_start"
    bl_label = "Create Trims from Plane"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.active_material is not None and
                context.mode == 'EDIT_MESH')

    def execute(self, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material")
            return {'CANCELLED'}

        # Store current state
        scene = context.scene
        if not hasattr(scene, 'uvv_trim_plane_data'):
            scene['uvv_trim_plane_data'] = {}

        # Save current selection and view
        original_obj = context.active_object
        original_mode = context.mode

        # Get selected objects and active object
        selected_objects = context.selected_objects.copy()

        # Store state
        scene['uvv_trim_plane_data'] = {
            'original_object': original_obj.name,
            'original_mode': original_mode,
            'selected_objects': [obj.name for obj in selected_objects],
            'material_name': material.name,
            'active': True
        }

        # Switch to object mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # Create plane
        bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        plane = context.active_object
        plane.name = "UVV_TrimPlane_TEMP"
        scene['uvv_trim_plane_data']['plane_name'] = plane.name

        # Assign material to plane
        if len(plane.data.materials) == 0:
            plane.data.materials.append(material)
        else:
            plane.data.materials[0] = material

        # Setup UV for the plane (full 0-1 square)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)

        # Scale UVs to fill 0-1 space
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.transform.resize(value=(1, 1, 1), orient_type='GLOBAL')

        bpy.ops.object.mode_set(mode='OBJECT')

        # Hide all other objects
        for obj in context.scene.objects:
            if obj != plane:
                obj.hide_set(True)

        # Select only the plane
        bpy.ops.object.select_all(action='DESELECT')
        plane.select_set(True)
        context.view_layer.objects.active = plane

        # Frame the plane in 3D view
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override = context.copy()
                        override['area'] = area
                        override['region'] = region
                        with context.temp_override(**override):
                            bpy.ops.view3d.view_selected()
                        break

        # Enable texture display in viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'SOLID'
                        space.shading.color_type = 'TEXTURE'

        # Enter edit mode for cutting
        bpy.ops.object.mode_set(mode='EDIT')

        self.report({'INFO'}, "Cut the plane to create trim shapes. Press 'Apply to Trim Set' when done.")

        return {'FINISHED'}


class UVV_OT_trim_from_plane_apply(Operator):
    """Apply plane cuts to create trims"""
    bl_idname = "uv.uvv_trim_from_plane_apply"
    bl_label = "Apply to Trim Set"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if 'uvv_trim_plane_data' not in scene:
            return False
        data = scene.get('uvv_trim_plane_data', {})
        return data.get('active', False)

    def execute(self, context):
        scene = context.scene
        data = scene.get('uvv_trim_plane_data', {})

        if not data or not data.get('active'):
            self.report({'WARNING'}, "No active trim plane session")
            return {'CANCELLED'}

        # Get the plane object
        plane_name = data.get('plane_name')
        if not plane_name or plane_name not in bpy.data.objects:
            self.report({'WARNING'}, "Trim plane not found")
            return {'CANCELLED'}

        plane = bpy.data.objects[plane_name]

        # Switch to object mode to read mesh data
        bpy.ops.object.mode_set(mode='OBJECT')

        # Get material
        material_name = data.get('material_name')
        if not material_name or material_name not in bpy.data.materials:
            self.report({'WARNING'}, "Material not found")
            return {'CANCELLED'}

        material = bpy.data.materials[material_name]

        # Extract and save plane mesh data for later editing
        mesh = plane.data
        uv_layer = mesh.uv_layers.active

        if not uv_layer:
            self.report({'WARNING'}, "No UV layer found")
            return {'CANCELLED'}

        # Save plane mesh data to material for future editing
        self.save_plane_data(material, mesh)

        # Store old trim data BEFORE clearing
        old_trims = []
        for trim in material.uvv_trims:
            old_trims.append({
                'name': trim.name,
                'color': (trim.color[0], trim.color[1], trim.color[2]),
                'left': trim.left,
                'top': trim.top,
                'right': trim.right,
                'bottom': trim.bottom,
                'enabled': trim.enabled,
                'selected': trim.selected
            })

        # Clear existing trims
        material.uvv_trims.clear()

        # Create BMesh for analysis
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()

        uv_layer_bm = bm.loops.layers.uv.active

        if not uv_layer_bm:
            bm.free()
            self.report({'WARNING'}, "No UV layer in BMesh")
            return {'CANCELLED'}

        # Collect new trim bounds first
        new_trim_bounds = []
        for face in bm.faces:
            # Get UV coordinates for this face
            uvs = [loop[uv_layer_bm].uv.copy() for loop in face.loops]

            if len(uvs) < 3:
                continue

            # Calculate bounding box
            min_u = min(uv.x for uv in uvs)
            max_u = max(uv.x for uv in uvs)
            min_v = min(uv.y for uv in uvs)
            max_v = max(uv.y for uv in uvs)

            # Skip if too small
            width = max_u - min_u
            height = max_v - min_v
            if width < 0.001 or height < 0.001:
                continue

            new_trim_bounds.append({
                'left': min_u,
                'top': max_v,
                'right': max_u,
                'bottom': min_v
            })

        bm.free()

        # Match new trims with old trims based on position
        def find_matching_old_trim(new_bounds, old_trims, tolerance=0.01):
            """Find an old trim that matches the new bounds"""
            for old_trim in old_trims:
                # Check if bounds are similar (within tolerance)
                if (abs(old_trim['left'] - new_bounds['left']) < tolerance and
                    abs(old_trim['right'] - new_bounds['right']) < tolerance and
                    abs(old_trim['top'] - new_bounds['top']) < tolerance and
                    abs(old_trim['bottom'] - new_bounds['bottom']) < tolerance):
                    return old_trim
            return None

        # Create trims with preserved data where possible
        trim_count = 0
        used_old_trims = set()

        for new_bounds in new_trim_bounds:
            # Create new trim
            material.uvv_trims.add()
            trim = material.uvv_trims[-1]

            # Try to find matching old trim
            matching_old = find_matching_old_trim(new_bounds, old_trims)

            if matching_old and id(matching_old) not in used_old_trims:
                # Preserve old trim data
                trim.name = matching_old['name']
                trim.color = matching_old['color']
                trim.enabled = matching_old['enabled']
                trim.selected = matching_old['selected']
                used_old_trims.add(id(matching_old))
            else:
                # New trim - generate fresh data
                trim.name = f"Trim.{trim_count:03d}"
                trim.color = trimsheet_utils.generate_trim_color(material.uvv_trims)
                trim.selected = False

            # Set bounds
            trim.set_rect(new_bounds['left'], new_bounds['top'], new_bounds['right'], new_bounds['bottom'])
            trim_count += 1

        # Set active trim to first one
        if len(material.uvv_trims) > 0:
            material.uvv_trims_index = 0
            material.uvv_trims[0].selected = True

        # Restore original state
        self.restore_original_state(context, data)

        # Clean up
        if 'uvv_trim_plane_data' in scene:
            del scene['uvv_trim_plane_data']

        self.report({'INFO'}, f"Created {trim_count} trims from plane")

        # Redraw all areas
        for area in context.screen.areas:
            area.tag_redraw()

        return {'FINISHED'}

    def save_plane_data(self, material, mesh):
        """Save plane mesh data to material for future editing"""
        import json

        # Create BMesh to read mesh data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        uv_layer = bm.loops.layers.uv.active

        if not uv_layer:
            bm.free()
            return

        # Store vertices, edges, faces, and UVs
        plane_data = {
            'vertices': [],
            'edges': [],
            'faces': [],
            'uvs': []
        }

        # Store vertex positions
        for vert in bm.verts:
            plane_data['vertices'].append([vert.co.x, vert.co.y, vert.co.z])

        # Store edges
        for edge in bm.edges:
            plane_data['edges'].append([edge.verts[0].index, edge.verts[1].index])

        # Store faces and UVs
        for face in bm.faces:
            face_verts = [v.index for v in face.verts]
            plane_data['faces'].append(face_verts)

            # Store UVs for this face
            face_uvs = []
            for loop in face.loops:
                uv = loop[uv_layer].uv
                face_uvs.append([uv.x, uv.y])
            plane_data['uvs'].append(face_uvs)

        bm.free()

        # Save to material as JSON string
        material['uvv_plane_data'] = json.dumps(plane_data)

    def restore_original_state(self, context, data):
        """Restore the original scene state"""
        # First, make sure we're in object mode
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Unhide all objects first
        for obj in context.scene.objects:
            obj.hide_set(False)

        # Restore original selection and active object BEFORE deleting plane
        bpy.ops.object.select_all(action='DESELECT')

        original_obj_name = data.get('original_object')
        original_obj = None
        if original_obj_name and original_obj_name in bpy.data.objects:
            original_obj = bpy.data.objects[original_obj_name]
            context.view_layer.objects.active = original_obj
            original_obj.select_set(True)

            # Restore selection
            selected_names = data.get('selected_objects', [])
            for obj_name in selected_names:
                if obj_name in bpy.data.objects:
                    bpy.data.objects[obj_name].select_set(True)

        # NOW delete the plane (after we have a valid active object)
        plane_name = data.get('plane_name')
        if plane_name and plane_name in bpy.data.objects:
            plane = bpy.data.objects[plane_name]
            # Deselect plane before deleting
            plane.select_set(False)
            bpy.data.objects.remove(plane, do_unlink=True)

        # Restore mode (we have valid active object now)
        if original_obj:
            original_mode = data.get('original_mode', 'OBJECT')
            if original_mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='EDIT')
            elif original_mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')


class UVV_OT_trim_from_plane_cancel(Operator):
    """Cancel the trim creation from plane workflow"""
    bl_idname = "uv.uvv_trim_from_plane_cancel"
    bl_label = "Cancel Trim Creation"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if 'uvv_trim_plane_data' not in scene:
            return False
        data = scene.get('uvv_trim_plane_data', {})
        return data.get('active', False)

    def execute(self, context):
        scene = context.scene
        data = scene.get('uvv_trim_plane_data', {})

        if not data or not data.get('active'):
            return {'CANCELLED'}

        # Restore state using the apply operator's method
        apply_op = UVV_OT_trim_from_plane_apply()
        apply_op.restore_original_state(context, data)

        # Clean up
        if 'uvv_trim_plane_data' in scene:
            del scene['uvv_trim_plane_data']

        self.report({'INFO'}, "Cancelled trim creation from plane")

        return {'FINISHED'}


class UVV_OT_trim_from_plane_edit(Operator):
    """Edit existing trimsheet by recreating the plane"""
    bl_idname = "uv.uvv_trim_from_plane_edit"
    bl_label = "Edit Trimsheet Plane"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        material = trimsheet_utils.get_active_material(context)
        if not material:
            return False
        # Check if plane data exists
        return 'uvv_plane_data' in material

    def execute(self, context):
        import json

        material = trimsheet_utils.get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material")
            return {'CANCELLED'}

        # Check if plane data exists
        if 'uvv_plane_data' not in material:
            self.report({'WARNING'}, "No saved plane data found")
            return {'CANCELLED'}

        # Store current state (same as start operator)
        scene = context.scene
        if not hasattr(scene, 'uvv_trim_plane_data'):
            scene['uvv_trim_plane_data'] = {}

        original_obj = context.active_object
        original_mode = context.mode
        selected_objects = context.selected_objects.copy()

        # Store state
        scene['uvv_trim_plane_data'] = {
            'original_object': original_obj.name,
            'original_mode': original_mode,
            'selected_objects': [obj.name for obj in selected_objects],
            'material_name': material.name,
            'active': True
        }

        # Switch to object mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # Load plane data
        plane_data = json.loads(material['uvv_plane_data'])

        # Create new mesh
        mesh = bpy.data.meshes.new("UVV_TrimPlane_TEMP")

        # Create BMesh and build mesh from saved data
        bm = bmesh.new()

        # Create vertices
        verts = []
        for v_co in plane_data['vertices']:
            verts.append(bm.verts.new(v_co))

        bm.verts.ensure_lookup_table()

        # Create edges
        for e_indices in plane_data['edges']:
            try:
                bm.edges.new([verts[e_indices[0]], verts[e_indices[1]]])
            except:
                pass  # Edge might already exist

        # Create faces
        for f_indices in plane_data['faces']:
            try:
                face_verts = [verts[i] for i in f_indices]
                bm.faces.new(face_verts)
            except:
                pass  # Face might already exist

        # Update BMesh
        bm.faces.ensure_lookup_table()

        # Create UV layer and set UVs
        uv_layer = bm.loops.layers.uv.new("UVMap")
        for face_idx, face in enumerate(bm.faces):
            if face_idx < len(plane_data['uvs']):
                face_uvs = plane_data['uvs'][face_idx]
                for loop_idx, loop in enumerate(face.loops):
                    if loop_idx < len(face_uvs):
                        loop[uv_layer].uv = face_uvs[loop_idx]

        # Write BMesh to mesh
        bm.to_mesh(mesh)
        bm.free()

        # Create object
        plane = bpy.data.objects.new("UVV_TrimPlane_TEMP", mesh)
        context.collection.objects.link(plane)
        scene['uvv_trim_plane_data']['plane_name'] = plane.name

        # Assign material to plane
        if len(plane.data.materials) == 0:
            plane.data.materials.append(material)
        else:
            plane.data.materials[0] = material

        # Hide all other objects
        for obj in context.scene.objects:
            if obj != plane:
                obj.hide_set(True)

        # Select only the plane
        bpy.ops.object.select_all(action='DESELECT')
        plane.select_set(True)
        context.view_layer.objects.active = plane

        # Frame the plane in 3D view
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override = context.copy()
                        override['area'] = area
                        override['region'] = region
                        with context.temp_override(**override):
                            bpy.ops.view3d.view_selected()
                        break

        # Enable texture display in viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'SOLID'
                        space.shading.color_type = 'TEXTURE'

        # Enter edit mode for editing
        bpy.ops.object.mode_set(mode='EDIT')

        self.report({'INFO'}, "Edit the plane. Press 'Apply to Trim Set' when done.")

        return {'FINISHED'}


classes = [
    UVV_OT_trim_from_plane_start,
    UVV_OT_trim_from_plane_apply,
    UVV_OT_trim_from_plane_cancel,
    UVV_OT_trim_from_plane_edit,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
