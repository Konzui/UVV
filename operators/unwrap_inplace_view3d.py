"""
Unwrap Inplace VIEW3D Operator
3D viewport variant of the unwrap inplace operator with raycast picking
"""

print("DEBUG: unwrap_inplace_view3d.py module imported")

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, FloatProperty
from mathutils import Vector

from .. import types
from .. import utils
from ..utils.raycast import RayCast, CrnEdgeHit
from ..utils.raycast_helpers import linked_crn_to_vert_with_seam_3d_iter
from ..types.mesh_island import MeshIslands


MULTIPLAYER = 1
UNIQUE_NUMBER_FOR_MULTIPLY = -1


class UnwrapData:
    """Helper class to store unwrap processing data"""
    def __init__(self, umesh, pins, island, selected):
        self.umesh: types.UMesh = umesh
        self.pins = pins
        self.islands = island
        self.temp_selected = selected


class MESH_OT_uvv_unwrap_inplace(Operator, RayCast):
    """Unwrap the mesh with optional in-place preservation"""
    bl_idname = "mesh.uvv_unwrap_inplace"
    bl_label = "Unwrap"
    bl_description = ("Unwrap the mesh of object being edited. Enable 'Unwrap Inplace' to preserve island position and scale\n\n "
                      "Organic Mode has incorrect behavior with pinned and flipped islands")
    bl_options = {'REGISTER', 'UNDO'}

    unwrap: EnumProperty(
        name='Unwrap',
        default='ANGLE_BASED',
        items=(
            ('ANGLE_BASED', 'Hard Surface', ''),
            ('CONFORMAL', 'Conformal', ''),
            ('MINIMUM_STRETCH', 'Organic', '')
        )
    )

    mark_seam_inner_island: BoolProperty(
        name='Mark Seam Self Borders', 
        default=False, 
        description='Marking seams where there are split edges within the same island.'
    )
    
    use_correct_aspect: BoolProperty(
        name='Correct Aspect', 
        default=True
    )
    
    unwrap_along: EnumProperty(
        name='Unwrap Along', 
        default='BOTH', 
        items=(
            ('BOTH', 'Both', ''),
            ('X', 'U', ''),
            ('Y', 'V', '')
        ),
        description="Doesn't work properly with disk-shaped topologies, which completely change their structure with default unwrap"
    )
    
    blend_factor: FloatProperty(
        name='Blend Factor', 
        default=1, 
        soft_min=0, 
        soft_max=1
    )
    
    use_inplace: BoolProperty(
        name='Unwrap Inplace',
        description='Preserve island position and scale. When disabled, acts like regular unwrap',
        default=True
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH' and 
                context.active_object is not None and 
                context.active_object.type == 'MESH')

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'use_inplace')
        layout.prop(self, 'use_correct_aspect')
        layout.prop(self, 'mark_seam_inner_island')
        layout.row(align=True).prop(self, 'unwrap', expand=True)

    def invoke(self, context, event):
        if event.value == 'PRESS':
            self.init_data_for_ray_cast(event)
            return self.execute(context)
        return self.execute(context)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        RayCast.__init__(self)
        self.umeshes: types.UMeshes | None = None
        self.texel = -1
        self.texture_size = -1
        # Initialize seam marking to False by default
        self.mark_seam_inner_island = False
        # Store save transforms for inplace restoration
        self.save_transform_islands: list = []

    def execute(self, context):
        self.umeshes = types.UMeshes.calc(self.report, verify_uv=False)

        self.umeshes.fix_context()
        self.umeshes.set_sync()

        # Get texel density settings
        prefs = utils.get_prefs()
        self.texel = getattr(prefs, 'texel_density', 512.0)
        self.texture_size = (getattr(prefs, 'texture_size_x', 1024) + getattr(prefs, 'texture_size_y', 1024)) / 2

        if self.use_correct_aspect:
            self.umeshes.calc_aspect_ratio(from_mesh=True)

        if self.unwrap == 'MINIMUM_STRETCH' and bpy.app.version < (4, 3, 0):
            self.unwrap = 'ANGLE_BASED'
            self.report({'WARNING'}, 'Organic Mode is not supported in Blender versions below 4.3')

        selected_umeshes, unselected_umeshes = self.umeshes.filtered_by_selected_and_visible_uv_verts()
        self.umeshes = selected_umeshes if selected_umeshes else unselected_umeshes
        if not self.umeshes:
            return self.umeshes.update()

        if not selected_umeshes and self.mouse_pos_from_3d:
            return self.pick_unwrap()
        else:
            for u in reversed(self.umeshes):
                if not u.has_uv and not u.total_face_sel:
                    self.umeshes.umeshes.remove(u)
            if not self.umeshes:
                self.report({'WARNING'}, 'Need selected faces for objects without uv')
                return {'CANCELLED'}

            self.unwrap_selected()
            self.umeshes.update()
            return {'FINISHED'}

    def pick_unwrap(self, **unwrap_kwargs):
        """Pick and unwrap island from 3D viewport"""
        if not (hit := self.ray_cast(utils.get_prefs().max_pick_distance)):
            return {'CANCELLED'}

        umesh = hit.umesh
        umesh.value = umesh.check_uniform_scale(report=self.report)
        if umesh.has_uv:
            umesh.verify_uv()
            mesh_island, mesh_isl_set = hit.calc_mesh_island_with_seam()
            # Create AdvIslands from the mesh island
            adv_islands = mesh_island.calc_adv_subislands()
            for adv_island in adv_islands:
                adv_island.select = True

            shared_selected_faces = []
            pinned_crn_uvs = []
            # In vert/edge selection mode, you can accidentally select extra faces.
            # To avoid this, we pin them.
            if umesh.total_face_sel != len(mesh_isl_set):
                uv = umesh.uv
                for f in umesh.bm.faces:
                    if f.select and f not in mesh_isl_set:
                        shared_selected_faces.append(f)
                        for crn in f.loops:
                            crn_uv = crn[uv]
                            if not crn_uv.pin_uv:
                                crn_uv.pin_uv = True
                                pinned_crn_uvs.append(crn_uv)

            unique_number_for_multiply = hash(mesh_island[0])  # multiplayer
            self.multiply_relax(unique_number_for_multiply, unwrap_kwargs)

            # Only save transform if using inplace mode
            save_t = None
            if self.use_inplace:
                adv_islands.apply_aspect_ratio()
                save_t = types.SaveTransform(adv_islands)

            bpy.ops.uv.unwrap(method=self.unwrap, correct_aspect=False, **unwrap_kwargs)
            umesh.verify_uv()

            # Only restore transform if using inplace mode
            if self.use_inplace and save_t:
                save_t.island = adv_islands
                save_t.inplace()

            if self.use_inplace:
                for adv_island in adv_islands:
                    adv_island.reset_aspect_ratio()
                    
            for adv_island in adv_islands:
                adv_island.select = False

            for f in shared_selected_faces:
                f.select = False
            for crn_uv in pinned_crn_uvs:
                crn_uv.pin_uv = False
        else:
            mesh_island, mesh_isl_set = hit.calc_mesh_island_with_seam()
            # Create AdvIslands from the mesh island
            adv_islands = mesh_island.calc_adv_subislands()
            for adv_island in adv_islands:
                adv_island.select = True

            bpy.ops.uv.unwrap(method=self.unwrap, correct_aspect=False, **unwrap_kwargs)

            umesh.verify_uv()
            unique_number_for_multiply = hash(mesh_island[0])  # multiplayer
            self.multiply_relax(unique_number_for_multiply, unwrap_kwargs)

            for adv_island in adv_islands:
                adv_island.calc_area_uv()
                adv_island.calc_area_3d(scale=umesh.value)

                if (status := adv_island.set_texel(self.texel, self.texture_size)) is None:  # noqa
                    # zero_area_islands.append(isl)
                    pass

                # reset aspect
                scale = Vector((1 / umesh.aspect, 1))
                adv_island.scale(scale, adv_island.bbox.center)
                adv_island.select = False

        umesh.update()
        return {'FINISHED'}

    def unwrap_selected(self, **unwrap_kwargs):
        """Unwrap selected elements"""
        # Clear previous save transforms
        self.save_transform_islands.clear()
        
        meshes_with_uvs: list = []
        meshes_without_uvs: list = []
        unique_number = 0
        for umesh in self.umeshes:
            umesh.value = umesh.check_uniform_scale(report=self.report)
            if not umesh.has_uv:
                meshes_without_uvs.append(umesh)
            else:
                umesh.verify_uv()
                meshes_with_uvs.append(umesh)
                if self.umeshes.elem_mode == 'VERT':
                    if umesh.total_face_sel:
                        unique_number += self.unwrap_selected_faces_preprocess_vert_edge_mode(umesh)
                    else:
                        unique_number += self.unwrap_selected_verts(umesh)
                elif self.umeshes.elem_mode == 'EDGE':
                    if umesh.total_face_sel:
                        unique_number += self.unwrap_selected_faces_preprocess_vert_edge_mode(umesh)
                    else:
                        unique_number += self.unwrap_selected_edges(umesh)
                else:
                    unique_number += self.unwrap_selected_faces_preprocess(umesh)

        unique_number = unique_number % (1 << 62)  # Prevent overflow
        self.multiply_relax(unique_number, unwrap_kwargs)
        bpy.ops.uv.unwrap(method=self.unwrap, correct_aspect=False, **unwrap_kwargs)

        # Only restore transform if using inplace mode
        if self.use_inplace:
            for safe_transform in self.save_transform_islands:
                safe_transform.inplace(self.unwrap_along)
                safe_transform.apply_saved_coords(self.unwrap_along, self.blend_factor)
                safe_transform.island.reset_aspect_ratio()

        for umesh in meshes_with_uvs:
            self.unwrap_selected_faces_postprocess(umesh)
            umesh.bm.select_flush(False)

        self.unwrap_without_uvs(meshes_without_uvs)

    def unwrap_selected_faces_preprocess_vert_edge_mode(self, umesh):
        """Preprocess selected faces for vert/edge mode"""
        assert umesh.total_face_sel
        assert self.umeshes.elem_mode in ('VERT', 'EDGE')
        mesh_islands = MeshIslands.calc_visible(umesh)
        unique_number = 0
        pinned: list = []
        to_select: list = []
        without_selection_islands: list = []

        uv = umesh.uv
        for mesh_isl in mesh_islands:
            if not any(f.select for f in mesh_isl):
                without_selection_islands.append(mesh_isl)
                continue
            unique_number += hash(mesh_isl[0])
            # Create AdvIslands from MeshIsland and save transform if using inplace
            adv_islands = mesh_isl.calc_adv_subislands()
            
            # Mark seams if requested (copied from UV editor unwrap)
            for isl in adv_islands:
                if self.mark_seam_inner_island:
                    isl.mark_seam(additional=True)
                # Don't mark seams when mark_seam_inner_island is False
            
            if self.use_inplace:
                adv_islands.apply_aspect_ratio()
                for isl in adv_islands:
                    save_t = isl.save_transform()
                    save_t.save_coords(self.unwrap_along, self.blend_factor)
                    self.save_transform_islands.append(save_t)

            for f in mesh_isl:
                if f.select:
                    continue
                to_select.append(f)
                for crn in f.loops:
                    crn_uv = crn[uv]
                    if crn_uv.pin_uv:
                        continue

                    if crn.vert.select:
                        # If linked faces are selected, then crn should unwrap as well
                        if any(crn_.face.select for crn_ in linked_crn_to_vert_with_seam_3d_iter(crn)):
                            continue
                    crn_uv.pin_uv = True
                    pinned.append(crn_uv)

        expected_total_selected_faces = umesh.total_face_sel + len(to_select)
        if self.umeshes.elem_mode == 'VERT':
            to_deselect_elements = [v for f in to_select for v in f.verts if not v.select]
        else:
            to_deselect_elements = [e for f in to_select for e in f.edges if not e.select]

        for f in to_select:
            f.select = True

        # May select faces from other islands, if so pin them and safe face to unselect
        if expected_total_selected_faces != umesh.total_face_sel:
            for isl in without_selection_islands:
                for f in isl:
                    if f.select:
                        to_deselect_elements.append(f)
                        for crn in f.loops:
                            crn_uv = crn[uv]
                            if not crn_uv.pin_uv:
                                pinned.append(crn_uv)

        umesh.other = UnwrapData(None, pinned, save_transform_islands, to_deselect_elements)
        return unique_number

    def unwrap_selected_verts(self, umesh):
        """Unwrap selected vertices"""
        assert not umesh.total_face_sel
        assert self.umeshes.elem_mode == 'VERT'
        mesh_islands = MeshIslands.calc_visible(umesh)
        unique_number = 0
        pinned: list = []
        to_select: list = []
        without_selection_islands: list = []

        uv = umesh.uv
        for mesh_isl in mesh_islands:
            if not any(v.select for f in mesh_isl for v in f.verts):
                without_selection_islands.append(mesh_isl)
                continue

            unique_number += hash(mesh_isl[0])
            # Create AdvIslands from MeshIsland and save transform if using inplace
            adv_islands = mesh_isl.calc_adv_subislands()
            
            # Mark seams if requested (copied from UV editor unwrap)
            for isl in adv_islands:
                if self.mark_seam_inner_island:
                    isl.mark_seam(additional=True)
                # Don't mark seams when mark_seam_inner_island is False
            
            if self.use_inplace:
                adv_islands.apply_aspect_ratio()
                for isl in adv_islands:
                    save_t = isl.save_transform()
                    save_t.save_coords(self.unwrap_along, self.blend_factor)
                    self.save_transform_islands.append(save_t)
            to_select.extend(mesh_isl)

            for f in mesh_isl:
                for crn in f.loops:
                    if crn.vert.select:
                        continue

                    crn_uv = crn[uv]
                    if crn_uv.pin_uv:
                        continue

                    crn_uv.pin_uv = True
                    pinned.append(crn_uv)

        expected_total_selected_faces = umesh.total_face_sel + len(to_select)
        to_deselect_elements = [v for f in to_select for v in f.verts if not v.select]

        for f in to_select:
            f.select = True

        # May select faces from other islands, if so pin them and safe face to unselect
        if expected_total_selected_faces != umesh.total_face_sel:
            for isl in without_selection_islands:
                for f in isl:
                    if f.select:
                        to_deselect_elements.append(f)
                        for crn in f.loops:
                            crn_uv = crn[uv]
                            if not crn_uv.pin_uv:
                                pinned.append(crn_uv)

        umesh.other = UnwrapData(None, pinned, save_transform_islands, to_deselect_elements)
        return unique_number

    def unwrap_selected_edges(self, umesh):
        """Unwrap selected edges"""
        assert not umesh.total_face_sel
        assert self.umeshes.elem_mode == 'EDGE'
        mesh_islands = MeshIslands.calc_visible(umesh)
        unique_number = 0
        pinned: list = []
        to_select: list = []
        without_selection_islands: list = []

        uv = umesh.uv
        for mesh_isl in mesh_islands:
            if not any(e.select for f in mesh_isl for e in f.edges):
                without_selection_islands.append(mesh_isl)
                continue
            unique_number += hash(mesh_isl[0])
            # Create AdvIslands from MeshIsland and save transform if using inplace
            adv_islands = mesh_isl.calc_adv_subislands()
            
            # Mark seams if requested (copied from UV editor unwrap)
            for isl in adv_islands:
                if self.mark_seam_inner_island:
                    isl.mark_seam(additional=True)
                # Don't mark seams when mark_seam_inner_island is False
            
            if self.use_inplace:
                adv_islands.apply_aspect_ratio()
                for isl in adv_islands:
                    save_t = isl.save_transform()
                    save_t.save_coords(self.unwrap_along, self.blend_factor)
                    self.save_transform_islands.append(save_t)
            to_select.extend(mesh_isl)

            for f in mesh_isl:
                if all(not v.select for v in f.verts):
                    for crn in f.loops:
                        crn_uv = crn[uv]
                        if crn_uv.pin_uv:
                            continue
                        crn_uv.pin_uv = True
                        pinned.append(crn_uv)
                    continue

                for crn in f.loops:
                    if crn.edge.select:
                        continue
                    crn_uv = crn[uv]
                    if crn.vert.select:
                        if crn_uv.pin_uv:
                            continue
                        if any(crn_.edge.select for crn_ in linked_crn_to_vert_with_seam_3d_iter(crn)):
                            continue

                    if crn_uv.pin_uv:
                        continue
                    crn_uv.pin_uv = True
                    pinned.append(crn_uv)

        expected_total_selected_faces = umesh.total_face_sel + len(to_select)
        to_deselect_elements = [e for f in to_select for e in f.edges if not e.select]

        for f in to_select:
            f.select = True

        # May select faces from other islands, if so pin them and safe face to unselect
        if expected_total_selected_faces != umesh.total_face_sel:
            for isl in without_selection_islands:
                for f in isl:
                    if f.select:
                        to_deselect_elements.append(f)
                        for crn in f.loops:
                            crn_uv = crn[uv]
                            if not crn_uv.pin_uv:
                                pinned.append(crn_uv)

        umesh.other = UnwrapData(None, pinned, save_transform_islands, to_deselect_elements)
        return unique_number

    def unwrap_selected_faces_preprocess(self, umesh):
        """Preprocess selected faces"""
        assert umesh.total_face_sel
        mesh_islands = MeshIslands.calc_extended(umesh)
        unique_number = 0
        pinned: list = []
        to_select: list = []

        uv = umesh.uv
        for mesh_isl in mesh_islands:
            unique_number += hash(mesh_isl[0])
            # Create AdvIslands from MeshIsland and save transform if using inplace
            adv_islands = mesh_isl.calc_adv_subislands()
            
            # Mark seams if requested (copied from UV editor unwrap)
            for isl in adv_islands:
                if self.mark_seam_inner_island:
                    isl.mark_seam(additional=True)
                # Don't mark seams when mark_seam_inner_island is False
            
            if self.use_inplace:
                adv_islands.apply_aspect_ratio()
                for isl in adv_islands:
                    save_t = isl.save_transform()
                    save_t.save_coords(self.unwrap_along, self.blend_factor)
                    self.save_transform_islands.append(save_t)

            for f in mesh_isl:
                if f.select:
                    continue
                to_select.append(f)
                for crn in f.loops:
                    crn_uv = crn[uv]
                    if crn_uv.pin_uv:
                        continue

                    if crn.vert.select:
                        # If linked faces are selected, then crn should unwrap as well
                        if any(crn_.face.select for crn_ in linked_crn_to_vert_with_seam_3d_iter(crn)):
                            continue
                    crn_uv.pin_uv = True
                    pinned.append(crn_uv)

        for f in to_select:
            f.select = True
        umesh.other = UnwrapData(None, pinned, [], to_select)
        return unique_number

    def unwrap_selected_faces_postprocess(self, umesh):
        """Postprocess selected faces"""
        unwrap_data: UnwrapData = umesh.other
        for f in unwrap_data.temp_selected:
            f.select = False
        for crn_uv in unwrap_data.pins:
            crn_uv.pin_uv = False

    def unwrap_without_uvs(self, umeshes):
        """Unwrap meshes without UV layers"""
        for umesh in umeshes:
            mesh_islands = MeshIslands.calc_extended(umesh)
            umesh.verify_uv()

            # Create AdvIslands from MeshIslands
            adv_islands = mesh_islands.to_adv_islands()

            for adv_isl in adv_islands:
                adv_isl.calc_area_uv()
                adv_isl.calc_area_3d(scale=umesh.value)

            # reset aspect
            for adv_isl in adv_islands:
                adv_isl.set_texel(self.texel, self.texture_size)
                scale = Vector((1 / umesh.aspect, 1))
                adv_isl.scale(scale, adv_isl.bbox.center)

    @staticmethod
    def multiply_relax(unique_number_for_multiply, unwrap_kwargs):
        """Multiply relax iterations for better results"""
        if unwrap_kwargs:
            global MULTIPLAYER
            global UNIQUE_NUMBER_FOR_MULTIPLY
            if UNIQUE_NUMBER_FOR_MULTIPLY == unique_number_for_multiply:
                MULTIPLAYER += 1
                unwrap_kwargs['iterations'] *= MULTIPLAYER
            else:
                MULTIPLAYER = 1
                UNIQUE_NUMBER_FOR_MULTIPLY = unique_number_for_multiply


classes = [
    MESH_OT_uvv_unwrap_inplace,
]


def register():
    print(f"DEBUG: unwrap_inplace_view3d.py registering {len(classes)} classes")
    for cls in classes:
        print(f"DEBUG: Registering {cls.__name__} with bl_idname: {cls.bl_idname}")
        bpy.utils.register_class(cls)
        print(f"DEBUG: Successfully registered {cls.__name__}")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
