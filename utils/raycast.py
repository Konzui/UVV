"""
RayCast utility for 3D viewport picking operations
Port of UniV's RayCast functionality for UVV
"""

import bpy
import bmesh
import numpy as np
from math import inf, isclose, nextafter
from mathutils import Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from bpy_extras import view3d_utils
from bmesh.types import BMFace, BMLoop

from .. import types
from .. import utils
from .raycast_helpers import calc_visible_uv_faces_iter


class CrnEdgeHit:
    """Hit result for corner/edge picking in 3D viewport"""
    
    def __init__(self, pt, min_dist=1e200):
        self.point = pt
        self.min_dist = min_dist
        self.crn: BMLoop | None = None
        self.face: BMFace | None = None  # use for incref
        self.umesh = None

    def find_nearest_crn_by_visible_faces(self, umesh, use_faces_from_umesh_seq=False):
        """Find nearest corner by visible faces"""
        from mathutils.geometry import intersect_point_line

        pt = self.point
        min_dist = self.min_dist
        min_crn = None

        uv = umesh.uv

        if use_faces_from_umesh_seq:
            visible_faces = umesh.sequence
        else:
            visible_faces = calc_visible_uv_faces_iter(umesh)

        for f in visible_faces:
            corners = f.loops
            v_prev = corners[-1][uv].uv
            for crn in corners:
                v_curr = crn[uv].uv

                # +15% faster without call function
                close_pt, percent = intersect_point_line(pt, v_prev, v_curr)
                if percent < 0.0:
                    close_pt = v_prev
                elif percent > 1.0:
                    close_pt = v_curr

                dist = (close_pt - pt).length
                if dist < min_dist:
                    # If the point is inside the face, we add it immediately,
                    # otherwise, we do nextafter and check again for nearest.
                    if utils.point_inside_face(pt, f, uv):
                        min_crn = crn
                        min_dist = dist
                    else:
                        # Adding dist after nextafter is necessary for the next for_each loop
                        # to "hook" another edge (thus avoiding float point errors).
                        dist = nextafter(dist, inf)
                        if dist < min_dist:
                            min_crn = crn
                            min_dist = dist

                v_prev = v_curr

        if min_crn:
            self.crn = min_crn.link_loop_prev
            self.min_dist = min_dist

            radial_prev = self.crn.link_loop_radial_prev
            if (utils.is_pair_with_flip(self.crn, radial_prev, umesh.uv) and
                    utils.is_visible_func(umesh.sync)(radial_prev.face)):
                if not utils.point_inside_face(pt, radial_prev.face, uv):
                    self.crn = radial_prev
            else:
                # Prioritize boundary edges where the point is inside the face,
                # otherwise lower the priority to find other boundary edges with the point inside the face.
                if utils.point_inside_face(pt, self.crn.face, uv):
                    self.min_dist = nextafter(min_dist, -inf)
                else:
                    self.min_dist = nextafter(min_dist, inf)

            self.umesh = umesh
            return True
        return False

    def calc_mesh_island_with_seam(self) -> tuple[types.AdvIsland, set[BMFace]]:
        """Calculate mesh island with seam boundaries"""
        assert self.crn, 'Not found picked corner'
        island: set[BMFace] = {self.crn.face}
        stack = []
        parts_of_island = [self.crn.face]
        while parts_of_island:
            for f in parts_of_island:
                for crn in f.loops:
                    pair_crn = crn.link_loop_radial_prev
                    ff = pair_crn.face
                    if ff in island or ff.hide or crn.edge.seam:
                        continue

                    island.add(ff)
                    stack.append(ff)
            parts_of_island = stack
            stack = []

        return types.AdvIsland(list(island), self.umesh), island

    def __bool__(self):
        return bool(self.crn)


class RayCast:
    """RayCast utility for 3D viewport picking operations"""
    
    def __init__(self):
        self.mouse_pos_from_3d = None
        self.region = None
        self.rv3d = None
        self.region_data = None
        self.ray_origin = None
        self.ray_direction = None
        self.active_bmesh = None
        self.umeshes = None

    def init_data_for_ray_cast(self, event):
        """Initialize raycast data from mouse event"""
        if bpy.context.area.type == 'VIEW_3D':
            self.mouse_pos_from_3d = event.mouse_region_x, event.mouse_region_y
            self.region = bpy.context.region
            self.rv3d = bpy.context.space_data.region_3d
            self.ray_origin = view3d_utils.region_2d_to_origin_3d(
                self.region, self.rv3d, Vector(self.mouse_pos_from_3d))
            self.ray_direction = view3d_utils.region_2d_to_vector_3d(
                self.region, self.rv3d, Vector(self.mouse_pos_from_3d))

    @staticmethod
    def get_bvh_from_polygon(umesh) -> tuple[BVHTree, list[BMFace]]:
        """Get BVH tree from polygon data for hidden faces"""
        faces = []
        faces_append = faces.append
        flat_tris_coords = []
        flat_tris_coords_append = flat_tris_coords.append

        for crn_a, crn_b, crn_c in umesh.bm.calc_loop_triangles():
            face = crn_a.face
            if face.hide:
                continue
            faces_append(face)
            flat_tris_coords_append(crn_a.vert.co)
            flat_tris_coords_append(crn_b.vert.co)
            flat_tris_coords_append(crn_c.vert.co)

        indices = np.arange(len(flat_tris_coords), dtype='uint32').reshape(-1, 3).tolist()
        bvh = BVHTree.FromPolygons(flat_tris_coords, indices, all_triangles=True)
        return bvh, faces

    def ray_cast_umeshes(self):
        """Raycast against all umeshes"""
        ray_target = self.ray_origin + self.ray_direction
        max_dist = 50_000
        best_length_squared = float('inf')
        umesh = None
        face_index: int = 0

        for umesh_iter in self.umeshes:
            world_matrix = umesh_iter.obj.matrix_world
            ray_origin_obj = world_matrix.inverted() @ self.ray_origin
            ray_direction_obj = world_matrix.inverted().to_3x3() @ self.ray_direction

            bvh = BVHTree.FromBMesh(umesh_iter.bm)
            hit, normal, face_index_, distance = bvh.ray_cast(ray_origin_obj, ray_direction_obj, max_dist)

            if not hit:
                continue

            hit_world = world_matrix @ hit
            length_squared = (hit_world - self.ray_origin).length_squared
            if length_squared < best_length_squared:
                umesh_iter.ensure()
                umesh_iter.bm = bmesh.from_edit_mesh(umesh_iter.obj.data)
                # If a face is hidden, the BVH is computed using FromPolygons.
                if umesh_iter.bm.faces[face_index_].hide:
                    bvh, faces = self.get_bvh_from_polygon(umesh_iter)  # slow
                    hit, normal, face_index_, distance = bvh.ray_cast(ray_origin_obj, ray_direction_obj, max_dist)
                    if not hit:
                        continue
                    hit_world = world_matrix @ hit
                    length_squared = (hit_world - self.ray_origin).length_squared
                    if length_squared >= best_length_squared:
                        continue
                    umesh_iter.bm.faces.index_update()
                    face_index_ = faces[face_index_].index

                best_length_squared = length_squared
                umesh = umesh_iter
                face_index = face_index_

        return umesh, face_index

    def ray_cast(self, max_pick_radius):
        """Main raycast method"""
        # TODO: Add raycast by radial patterns
        deps = bpy.context.view_layer.depsgraph
        result, loc, normal, face_index, obj, matrix = bpy.context.scene.ray_cast(
            deps, origin=self.ray_origin, direction=self.ray_direction)

        if not (result and obj and obj.type == 'MESH'):  # TODO: Fix potential non-mesh overlap object
            # TODO: Add raycast, ignoring objects that are not in Edit Mode
            return

        eval_obj = obj.evaluated_get(deps)
        has_destructive_modifiers = len(obj.data.polygons) != len(eval_obj.data.polygons)
        if obj.mode != 'EDIT' or has_destructive_modifiers:
            # Raycast, ignoring objects that are not in Edit Mode
            umesh, face_index = self.ray_cast_umeshes()
            if not umesh:
                return
        else:
            umesh = next(u for u in self.umeshes if u.obj == obj)
        umesh.ensure()
        umesh.bm = bmesh.from_edit_mesh(umesh.obj.data)

        face = umesh.bm.faces[face_index]
        e, dist = utils.find_closest_edge_3d_to_2d(self.mouse_pos_from_3d, face, umesh, self.region, self.rv3d)
        if dist < max_pick_radius:
            for crn in e.link_loops:
                if crn.face == face:
                    hit = CrnEdgeHit(self.mouse_pos_from_3d)
                    hit.crn = crn
                    hit.umesh = umesh
                    hit.face = crn.face  # incref
                    return hit
