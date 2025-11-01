""" UVV Texel Density Utilities - Zen UV Architecture """

import bpy
import bmesh
import math
from mathutils import Vector

from .td_islands_storage import TdIslandsStorage, TdIsland


class TdContext:
    """Context for texel density calculations"""

    def __init__(self, context: bpy.types.Context) -> None:
        settings = context.scene.uvv_settings

        self.td: float = round(settings.texel_density, 2)
        self.image_size: list = [settings.texture_size_x, settings.texture_size_y]
        self.set_mode: str = 'ISLAND'
        self.obj_mode: bool = False
        self.by_island: bool = False
        self.bl_units_scale: float = context.scene.unit_settings.scale_length
        self.selected_only: bool = False
        self.td_calc_precision: int = 100  # 100 = use all faces
        self.units: float = 1.0  # For cm/m conversion (simplified for now)
        self.round_value: int = 2


class UvFaceArea:
    """UV area calculation utilities"""

    @classmethod
    def polygon_area(cls, p):
        """Calculate 2D polygon area using shoelace formula"""
        return 0.5 * abs(sum(x0 * y1 - x1 * y0 for ((x0, y0), (x1, y1)) in cls.segments(p)))

    @classmethod
    def segments(cls, p):
        """Get polygon segments"""
        return zip(p, p[1:] + [p[0]])

    @classmethod
    def get_uv_faces_area(cls, faces, uv_layer):
        """Calculate total UV area for faces"""
        return sum([cls.polygon_area([loop[uv_layer].uv for loop in face.loops]) for face in faces])


class TexelDensityFactory:
    """Factory for texel density calculations"""

    @classmethod
    def calc_averaged_td(cls, obj: bpy.types.Object, uv_layer, islands: list, td_inputs: TdContext):
        """
        Calculate averaged texel density for all islands.
        Take into account the object transformation matrix.
        """
        if not len(islands):
            return [0.0, 0.0]

        ob_scale = obj.matrix_world.inverted().median_scale
        p_islands = cls.reduce_islands_polycount(islands, precision=td_inputs.td_calc_precision)
        p_td_data = [cls._calculate_texel_density(uv_layer, island, td_inputs) for island in p_islands]
        return sum(val[0] for val in p_td_data) * ob_scale / len(p_islands), sum(val[1] for val in p_td_data)

    @classmethod
    def reduce_islands_polycount(cls, islands, precision: int = 100):
        """Reduce island face count for performance (precision 0-100)"""
        if precision != 100:
            return [list(island)[::max(round(len(island) / precision), 1)] for island in islands]
        else:
            return islands

    @classmethod
    def _calculate_texel_density(cls, uv_layer, faces: list, td_inputs: TdContext):
        """
        Calculate texel density for particular faces.
        Does not take into account the object transformation matrix.
        """
        image_size = td_inputs.image_size
        max_side = max(image_size)
        image_aspect = max(image_size) / min(image_size)

        # Calculate geometry area (3D)
        geometry_area = sum(f.calc_area() for f in faces)

        # Calculate UV area (2D)
        uv_area = UvFaceArea.get_uv_faces_area(faces, uv_layer)

        if geometry_area > 0 and uv_area > 0:
            return (((max_side / math.sqrt(image_aspect)) * math.sqrt(uv_area)) /
                   (math.sqrt(geometry_area) * 100) / td_inputs.bl_units_scale) * td_inputs.units, uv_area * 100.0
        else:
            return 0.0001, uv_area * 100.0


class TdBmeshManager:
    """Manage bmesh instances for TD calculations"""

    @classmethod
    def _bm_from_edit(cls, obj: bpy.types.Object):
        return bmesh.from_edit_mesh(obj.data)

    @classmethod
    def get_bm(cls, td_inputs: TdContext, obj):
        """Get bmesh for object"""
        return cls._bm_from_edit(obj)


class TdUtils:
    """Main texel density utilities"""

    @classmethod
    def get_td_data_with_precision(cls, context: bpy.types.Context, objs: list, td_inputs: TdContext, td_influence: str = False):
        """
        Collect texel density data for all objects.
        Returns TdIslandsStorage with island-based TD calculations.
        """
        Scope = TdIslandsStorage()
        Scope.clear()

        for obj in objs:
            bm = TdBmeshManager.get_bm(td_inputs, obj)
            Scope = cls._collect_td_data(context, Scope, td_inputs, td_influence, obj, bm, precision=td_inputs.td_calc_precision)

        return Scope

    @classmethod
    def _collect_td_data(
        cls,
        context: bpy.types.Context,
        Scope: TdIslandsStorage,
        td_inputs: TdContext,
        td_influence: str,
        obj: bpy.types.Object,
        bm: bmesh.types.BMesh,
        precision: int = 100
    ) -> TdIslandsStorage:
        """Collect TD data for a single object"""

        uv_layer = bm.loops.layers.uv.active
        if not uv_layer:
            return Scope

        # Get UV islands (not individual faces!)
        from ..utils.island_utils import get_islands_ignore_context
        islands = get_islands_ignore_context(bm, is_include_hidden=False)

        for idx, island in enumerate(islands):
            td_value = TexelDensityFactory.calc_averaged_td(obj, uv_layer, [island], td_inputs)[0]

            Scope.append(
                TdIsland(
                    index=idx,
                    indices=[f.index for f in island],
                    obj_name=obj.name,
                    td=td_value
                )
            )

        return Scope


def register():
    pass


def unregister():
    pass
