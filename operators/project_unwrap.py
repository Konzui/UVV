"""
Project & Unwrap Operator
Combines project from view (bounds) with unwrap operation.
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, FloatProperty, BoolProperty
from mathutils import Vector

from .. import types
from .. import utils
from ..utils.generic_helpers import linked_crn_uv_by_island_index_unordered_included
from ..utils.stitch_utils import get_aspect_ratio


class UnwrapData:
    def __init__(self, umesh, pins, island, selected):
        self.umesh: types.UMesh = umesh
        self.pins = pins
        self.islands = island
        self.temp_selected = selected


MULTIPLAYER = 1
UNIQUE_NUMBER_FOR_MULTIPLY = -1


class UV_OT_uvv_project_unwrap(Operator):
    """Project from view (bounds) and then unwrap the mesh
    
    First projects the UV coordinates from the current view, then performs unwrap operation.
    Useful for getting a good starting point for UV mapping.
    Note: Project from view requires UV Editor to be open."""
    bl_idname = "uv.uvv_project_unwrap"
    bl_label = "Project Map"
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
    
    mark_seam_inner_island: BoolProperty(
        name='Mark Seam Self Borders', 
        default=True, 
        description='Marking seams where there are split edges within the same island.'
    )
    
    use_correct_aspect: BoolProperty(
        name='Correct Aspect', 
        default=True
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
        self.layout.prop(self, 'use_inplace')
        self.layout.prop(self, 'use_correct_aspect')
        self.layout.prop(self, 'mark_seam_inner_island')

        col = self.layout.column()
        split = col.split(factor=0.3, align=True)
        split.label(text='Unwrap Along')
        row = split.row(align=True)
        row.prop(self, 'unwrap_along', expand=True)

        self.layout.prop(self, 'blend_factor', slider=True)
        self.layout.row(align=True).prop(self, 'unwrap', expand=True)

    def invoke(self, context, event):
        if self.bl_idname.startswith('uv.'):
            if event.value == 'PRESS':
                self.max_distance = utils.get_max_distance_from_px(utils.get_prefs().max_pick_distance, context.region.view2d)
                self.mouse_pos = utils.get_mouse_pos(context, event)
            else:
                self.max_distance = None
        return self.execute(context)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mouse_pos = None
        self.max_distance: float | None = None
        self.umeshes: types.UMeshes | None = None
        self.has_selected: bool = True

    def manual_project_from_view(self, context):
        """Project UVs from the current 3D view using UniV's proven approach"""
        
        # Get 3D view area and region
        area = context.area
        if area.type != 'VIEW_3D':
            # Try to find a 3D view area
            for a in bpy.context.screen.areas:
                if a.type == 'VIEW_3D':
                    area = a
                    break
            else:
                raise Exception("No 3D view area found")
        
        v3d = area.spaces.active
        region = next(reg for reg in area.regions if reg.type == 'WINDOW')
        rv3d = region.data
        
        # Get perspective matrix and window dimensions
        pers_mat = rv3d.perspective_matrix
        winx = region.width
        winy = region.height
        
        # Clear seams from selected faces to create single UV island
        for umesh in self.umeshes:
            if self.umeshes.is_edit_mode and self.has_selected:
                # Clear seams from selected faces
                for face in utils.calc_selected_uv_faces(umesh):
                    for edge in face.edges:
                        edge.seam = False
                umesh.update()
        
        # Project UVs for each umesh
        for umesh in self.umeshes:
            uv = umesh.uv
            aspect = get_aspect_ratio(umesh) if self.use_correct_aspect else 1.0
            
            # Adjust window height for aspect ratio
            winy_adjusted = region.height * aspect
            
            # Get object matrix for rotation
            rot_mat = umesh.obj.matrix_world.copy()
            
            # Project each face
            if self.umeshes.is_edit_mode:
                if self.has_selected:
                    faces = utils.calc_selected_uv_faces(umesh)
                else:
                    faces = utils.calc_visible_uv_faces(umesh)
            else:
                faces = umesh.bm.faces
            
            for face in faces:
                for loop in face.loops:
                    crn_co = loop[uv].uv
                    self.uv_project_from_view(crn_co, loop.vert.co, pers_mat, rot_mat, winx, winy_adjusted)
    
    @staticmethod
    def uv_project_from_view(target: Vector, source: Vector, pers_mat, rot_mat, winx, winy):
        """Project 3D vertex to UV coordinates using perspective projection (from UniV)"""
        pv4 = source.copy()
        pv4.resize(4)
        pv4[3] = 1.0
        
        # Apply object matrix transformation
        pv4 = rot_mat @ pv4
        
        # Apply perspective matrix
        pv4 = pers_mat @ pv4
        
        if abs(pv4[3]) > 0.00001:  # avoid division by zero
            target[0] = winx / 2.0 + (winx / 2.0) * pv4[0] / pv4[3]
            target[1] = winy / 2.0 + (winy / 2.0) * pv4[1] / pv4[3]
        else:
            # scaling is lost but give a valid result
            target[0] = winx / 2.0 + (winx / 2.0) * pv4[0]
            target[1] = winy / 2.0 + (winy / 2.0) * pv4[1]
        
        # Handle aspect ratio adjustments (from UniV)
        x = 0.0
        y = 0.0
        if winx > winy:
            y = (winx - winy) / 2.0
            winy = winx
        else:
            x = (winy - winx) / 2.0
            winx = winy
        
        target[0] = (x + target[0]) / winx
        target[1] = (y + target[1]) / winy

    def execute(self, context):
        # Initialize umeshes first
        self.umeshes = types.UMeshes()
        self.umeshes.fix_context()
        
        # Determine if we have selected faces
        if self.umeshes.is_edit_mode:
            selected, unselected = self.umeshes.filtered_by_selected_and_visible_uv_faces()
            if selected:
                self.umeshes = selected
                self.has_selected = True
            elif unselected:
                self.umeshes = unselected
                self.has_selected = False
        else:
            self.has_selected = True
        
        if not self.umeshes:
            return self.umeshes.update()
        
        # First, perform project from view
        try:
            self.manual_project_from_view(context)
            self.report({'INFO'}, 'Projected from view successfully')
        except Exception as e:
            self.report({'WARNING'}, f'Projection failed: {e}')
            # Continue with unwrap even if projection fails
        
        if self.unwrap == 'MINIMUM_STRETCH' and bpy.app.version < (4, 3, 0):
            self.unwrap = 'ANGLE_BASED'
            self.report({'WARNING'}, 'Organic Mode is not supported in Blender versions below 4.3')

        selected_umeshes, unselected_umeshes = self.umeshes.filtered_by_selected_and_visible_uv_verts()
        self.umeshes = selected_umeshes if selected_umeshes else unselected_umeshes
        
        if not self.umeshes:
            return self.umeshes.update()

        if not selected_umeshes and self.max_distance is not None and context.area.ui_type == 'UV':
            return self.pick_unwrap()
        else:
            if self.umeshes.sync:
                if self.umeshes.elem_mode == 'FACE':
                    self.unwrap_sync_faces()
                else:
                    self.unwrap_sync_verts_edges()
            else:
                self.unwrap_non_sync()

            for umesh in self.umeshes:
                umesh.bm.select_flush_mode()
            return self.umeshes.update()

    def pick_unwrap(self, **unwrap_kwargs):
        hit = types.IslandHit(self.mouse_pos, self.max_distance)
        for umesh in self.umeshes:
            for isl in types.AdvIslands.calc_visible_with_mark_seam(umesh):
                hit.find_nearest_island(isl)

        if not hit or (self.max_distance < hit.min_dist):
            self.report({'WARNING'}, 'Island not found within a given radius')
            return {'CANCELLED'}

        isl = hit.island
        isl.select = True
        shared_selected_faces = []
        pinned_crn_uvs = []

        if self.umeshes.sync and isl.umesh.total_face_sel != len(isl):
            faces = set(isl)
            uv = isl.umesh.uv
            for f in isl.umesh.bm.faces:
                if f.select and f not in faces:
                    shared_selected_faces.append(f)
                    for crn in f.loops:
                        crn_uv = crn[uv]
                        if not crn_uv.pin_uv:
                            crn_uv.pin_uv = True
                            pinned_crn_uvs.append(crn_uv)

        unique_number_for_multiply = hash(isl[0])  # multiplayer
        self.multiply_relax(unique_number_for_multiply, unwrap_kwargs)

        isl.umesh.value = isl.umesh.check_uniform_scale(report=self.report)
        isl.umesh.aspect = get_aspect_ratio() if self.use_correct_aspect else 1.0
        
        # Only save transform if using inplace mode
        save_t = None
        if self.use_inplace:
            isl.apply_aspect_ratio()
            save_t = isl.save_transform()
            save_t.save_coords(self.unwrap_along, self.blend_factor)

        if self.mark_seam_inner_island:
            isl.mark_seam(additional=True)
        else:
            islands = types.AdvIslands([isl], isl.umesh)
            islands.indexing()
            isl.mark_seam_by_index(additional=True)

        bpy.ops.uv.unwrap(method=self.unwrap, correct_aspect=False, **unwrap_kwargs)

        # Only restore transform if using inplace mode
        if self.use_inplace and save_t:
            save_t.inplace(self.unwrap_along)
            save_t.apply_saved_coords(self.unwrap_along, self.blend_factor)
        
        is_updated = isl.reset_aspect_ratio() if self.use_inplace else False

        isl.select = False
        if shared_selected_faces or pinned_crn_uvs or is_updated:
            for f in shared_selected_faces:
                f.select = False
            for crn_uv in pinned_crn_uvs:
                crn_uv.pin_uv = False

            isl.umesh.update()
        return {'FINISHED'}

    @staticmethod
    def has_unlinked_and_linked_selected_faces(f_, uv, idx):
        unlinked_has_selected_face = False
        linked_has_selected_face = False
        for crn_ in f_.loops:
            first_co = crn_[uv].uv
            for l_crn in crn_.vert.link_loops:
                if l_crn.face.index == idx:
                    if l_crn[uv].uv == first_co:
                        if l_crn.face.select:
                            linked_has_selected_face = True
                else:
                    if l_crn.face.select:
                        unlinked_has_selected_face = True
        return unlinked_has_selected_face, linked_has_selected_face

    def unwrap_sync_verts_edges(self, **unwrap_kwargs):
        unique_number_for_multiply = 0
        pin_and_inplace = []
        unwrap_data: list[UnwrapData] = []
        
        for umesh in self.umeshes:
            uv = umesh.uv
            umesh.value = umesh.check_uniform_scale(report=self.report)
            umesh.aspect = get_aspect_ratio() if self.use_correct_aspect else 1.0
            
            islands = types.AdvIslands.calc_extended_any_elem_with_mark_seam(umesh)
            islands.indexing()

            for isl in islands:
                if unwrap_kwargs:
                    unique_number_for_multiply += hash(isl[0])  # multiplayer
                if self.mark_seam_inner_island:
                    isl.mark_seam(additional=True)
                else:
                    isl.mark_seam_by_index(additional=True)

            unpin_uvs = set()
            faces_to_select = set()
            verts_to_select = set()

            # Extend selected
            for idx, isl in enumerate(islands):
                for f in isl:
                    if f.select:
                        continue
                    if sum(v.select for v in f.verts) not in (0, len(f.verts)):
                        unlinked_sel, linked_sel = self.has_unlinked_and_linked_selected_faces(f, uv, idx)
                        if linked_sel or not (unlinked_sel or linked_sel):
                            faces_to_select.add(f)
                            for v in f.verts:
                                if not v.select:
                                    verts_to_select.add(v)
                        else:
                            for crn in f.loops:
                                for l_crn_ in linked_crn_uv_by_island_index_unordered_included(crn, uv, idx):
                                    crn_uv = l_crn_[uv]
                                    if not crn_uv.pin_uv:
                                        crn_uv.pin_uv = True
                                        unpin_uvs.add(crn_uv)

            for f in faces_to_select:
                f.select = True

            for v in verts_to_select:
                v.select = True
                for crn in v.link_loops:
                    crn_uv = crn[uv]
                    if not crn_uv.pin_uv:
                        crn_uv.pin_uv = True
                        unpin_uvs.add(crn_uv)

            if self.umeshes.elem_mode == 'EDGE':  # EDGE
                for e in umesh.bm.edges:
                    e.select = sum(v.select for v in e.verts) == 2

            save_transform_islands = []
            for isl in islands:
                if any(v.select for f in isl for v in f.verts):
                    # Only save transform if using inplace mode
                    if self.use_inplace:
                        isl.apply_aspect_ratio()
                        save_t = isl.save_transform()
                        save_t.save_coords(self.unwrap_along, self.blend_factor)
                        save_transform_islands.append(save_t)

            pin_and_inplace.append((unpin_uvs, save_transform_islands))
            unwrap_data.append(UnwrapData(umesh, unpin_uvs, save_transform_islands, verts_to_select))

        self.multiply_relax(unique_number_for_multiply, unwrap_kwargs)
        bpy.ops.uv.unwrap(method=self.unwrap, correct_aspect=False, **unwrap_kwargs)

        for ud in unwrap_data:
            for pin in ud.pins:
                pin.pin_uv = False
            # Only restore transform if using inplace mode
            if self.use_inplace:
                for isl in ud.islands:
                    isl.inplace(self.unwrap_along)
                    isl.apply_saved_coords(self.unwrap_along, self.blend_factor)
                    isl.island.reset_aspect_ratio()
            for v in ud.temp_selected:
                v.select = False

            if self.umeshes.elem_mode == 'EDGE':  # EDGE
                for e in ud.umesh.bm.edges:
                    e.select = sum(v.select for v in e.verts) == 2

            if self.unwrap == 'MINIMUM_STRETCH':
                if self.umeshes.elem_mode != 'FACE':
                    # It might be worth bug reporting this moment when SLIM causes a "grow effect"
                    ud.umesh.bm.select_flush(False)

    @staticmethod
    def unwrap_sync_faces_extend_select_and_set_pins(isl):
        to_select = []
        unpinned = []
        uv = isl.umesh.uv
        sync = isl.umesh.sync
        for f in isl:
            if f.select:
                continue

            has_selected_linked_faces = False
            temp_static = []
            for crn in f.loops:
                linked = utils.linked_crn_to_vert_pair_with_seam(crn, uv, sync)
                if any(cc.face.select for cc in linked):
                    has_selected_linked_faces = True
                else:
                    temp_static.append(crn)

            if has_selected_linked_faces:
                to_select.append(f)

                for crn in temp_static:
                    crn_uv = crn[uv]
                    if not crn_uv.pin_uv:
                        crn_uv.pin_uv = True
                    unpinned.append(crn_uv)
        for f in to_select:
            f.select = True
        isl.sequence = (unpinned, to_select)

    def unwrap_sync_faces(self, **unwrap_kwargs):
        assert self.umeshes.elem_mode == 'FACE'
        unique_number_for_multiply = 0

        all_transform_islands = []
        for umesh in reversed(self.umeshes):
            umesh.value = umesh.check_uniform_scale(report=self.report)
            umesh.aspect = get_aspect_ratio() if self.use_correct_aspect else 1.0
            islands_extended = types.AdvIslands.calc_extended_with_mark_seam(umesh)
            islands_extended.indexing()

            for isl in islands_extended:
                if unwrap_kwargs:
                    unique_number_for_multiply += hash(isl[0])  # multiplayer

                if self.mark_seam_inner_island:
                    isl.mark_seam(additional=True)
                else:
                    isl.mark_seam_by_index(additional=True)

                self.unwrap_sync_faces_extend_select_and_set_pins(isl)

                # Only save transform if using inplace mode
                if self.use_inplace:
                    isl.apply_aspect_ratio()
                    save_t = isl.save_transform()
                    save_t.save_coords(self.unwrap_along, self.blend_factor)
                    all_transform_islands.append(save_t)

        self.multiply_relax(unique_number_for_multiply, unwrap_kwargs)
        bpy.ops.uv.unwrap(method=self.unwrap, correct_aspect=False, **unwrap_kwargs)

        for isl in all_transform_islands:
            unpinned, to_select = isl.island.sequence
            for pin in unpinned:
                pin.pin_uv = False
            for f in to_select:
                f.select = False

            # Only restore transform if using inplace mode
            if self.use_inplace:
                isl.inplace(self.unwrap_along)
                isl.apply_saved_coords(self.unwrap_along, self.blend_factor)
                isl.island.reset_aspect_ratio()

    def unwrap_non_sync(self, **unwrap_kwargs):
        save_transform_islands: list = []
        unique_number_for_multiply = 0

        tool_settings = bpy.context.scene.tool_settings
        is_sticky_mode_disabled = tool_settings.uv_sticky_select_mode == 'DISABLED'

        for umesh in reversed(self.umeshes):
            uv = umesh.uv
            umesh.value = umesh.check_uniform_scale(report=self.report)
            umesh.aspect = get_aspect_ratio() if self.use_correct_aspect else 1.0
            islands = types.AdvIslands.calc_extended_any_elem_with_mark_seam(umesh)
            if not self.mark_seam_inner_island:
                islands.indexing()

            for isl in islands:
                if unwrap_kwargs:
                    unique_number_for_multiply += hash(isl[0])  # multiplayer

                if self.mark_seam_inner_island:
                    isl.mark_seam(additional=True)
                else:
                    isl.mark_seam_by_index(additional=True)

            if is_sticky_mode_disabled:
                face_select_get = utils.face_select_get_func(umesh)
                crn_select_get = utils.vert_select_get_func(umesh)
                for isl in islands:
                    unpin_uvs = set()
                    corners_to_select = set()
                    for f in isl:
                        if face_select_get(f):
                            continue

                        temp_static = []
                        has_selected = False
                        for crn in f.loops:
                            if crn_select_get(crn):
                                continue
                            linked = utils.linked_crn_to_vert_pair_with_seam(crn, umesh.uv, umesh.sync)
                            if any(crn_select_get(c) for c in linked):
                                has_selected = True
                                corners_to_select.add(crn[uv])
                            else:
                                temp_static.append(crn)
                        if has_selected:
                            for cc in temp_static:
                                cc_uv = cc[uv]
                                if not cc_uv.pin_uv:
                                    unpin_uvs.add(cc_uv)
                                    corners_to_select.add(cc_uv)

                    for unpin_crn in unpin_uvs:
                        unpin_crn.pin_uv = True
                    for unsel_crn in corners_to_select:
                        unsel_crn.select = True
                    isl.sequence = (unpin_uvs, corners_to_select)

            # Only save transform if using inplace mode
            if self.use_inplace:
                for isl in islands:
                    isl.apply_aspect_ratio()
                    save_t = isl.save_transform()
                    save_t.save_coords(self.unwrap_along, self.blend_factor)
                    save_transform_islands.append(save_t)

        self.multiply_relax(unique_number_for_multiply, unwrap_kwargs)

        bpy.ops.uv.unwrap(method=self.unwrap, correct_aspect=False, **unwrap_kwargs)

        # Only restore transform if using inplace mode
        if self.use_inplace:
            for isl in save_transform_islands:
                isl.inplace(self.unwrap_along)
                isl.apply_saved_coords(self.unwrap_along, self.blend_factor)
                isl.island.reset_aspect_ratio()

            if is_sticky_mode_disabled:
                if isl.island.sequence:
                    unpin_uvs, corners_to_select = isl.island.sequence
                    for unpin_crn in unpin_uvs:
                        unpin_crn.pin_uv = False
                    for unsel_crn in corners_to_select:
                        unsel_crn.select = False

    @staticmethod
    def multiply_relax(unique_number_for_multiply, unwrap_kwargs):
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
    UV_OT_uvv_project_unwrap,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
