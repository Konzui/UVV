

""" UVV Texel Density Calculator """

import bpy
import bmesh
from mathutils import Vector


class TexelDensityProcessor:
    """Calculate and manage texel density data for mesh objects"""

    @staticmethod
    def calculate_polygon_area_2d(coords):
        """Calculate area of 2D polygon using shoelace formula"""
        area = 0.0
        for i in range(len(coords)):
            j = (i + 1) % len(coords)
            area += coords[i].x * coords[j].y
            area -= coords[j].x * coords[i].y
        return abs(area) / 2.0

    @staticmethod
    def calculate_face_texel_density(face, uv_layer, texture_size=1024):
        """Calculate texel density for a single face"""
        # Get UV coordinates
        uv_coords = [loop[uv_layer].uv.copy() for loop in face.loops]

        # Calculate UV area
        uv_area = TexelDensityProcessor.calculate_polygon_area_2d(uv_coords)

        # Calculate world space area
        world_area = face.calc_area()

        # Calculate texel density (texels per unit area)
        if world_area > 0 and uv_area > 0:
            density = (uv_area * texture_size * texture_size) / world_area
            return density
        return 0.0

    @staticmethod
    def get_texture_size_from_context(context):
        """Get active texture size from context"""
        # Try to get texture size from active image
        if hasattr(context, 'space_data'):
            if context.space_data and hasattr(context.space_data, 'image'):
                image = context.space_data.image
                if image:
                    return max(image.size[0], image.size[1])

        # Default to 1024
        return 1024

    @staticmethod
    def process_objects(context, objects=None, texture_size=None):
        """Process mesh objects and return texel density data"""
        if objects is None:
            objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if texture_size is None:
            texture_size = TexelDensityProcessor.get_texture_size_from_context(context)

        texel_data_map = {}
        all_densities = []

        for obj in objects:
            if obj.mode != 'EDIT':
                continue

            # Get bmesh
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                continue

            obj_data = []

            # Calculate density for each face
            for face in bm.faces:
                if len(face.verts) < 3:
                    continue

                density = TexelDensityProcessor.calculate_face_texel_density(
                    face, uv_layer, texture_size
                )
                all_densities.append(density)

                # Get world space vertices
                world_verts = [obj.matrix_world @ vert.co for vert in face.verts]

                # Triangulate face
                triangles = TexelDensityProcessor.triangulate_face(face)

                obj_data.append({
                    'vertices': world_verts,
                    'triangles': triangles,
                    'density': density,
                    'face_index': face.index
                })

            texel_data_map[obj.name] = obj_data

        # Calculate min/max for normalization
        if all_densities:
            min_density = min(all_densities)
            max_density = max(all_densities)
        else:
            min_density = 0.0
            max_density = 1.0

        return {
            'texel_data_map': texel_data_map,
            'min_density': min_density,
            'max_density': max_density,
            'texture_size': texture_size
        }

    @staticmethod
    def triangulate_face(face):
        """Triangulate a face and return triangle indices"""
        verts = face.verts
        triangles = []

        # Simple fan triangulation from first vertex
        for i in range(1, len(verts) - 1):
            triangles.append([0, i, i + 1])

        return triangles


def register():
    pass


def unregister():
    pass
