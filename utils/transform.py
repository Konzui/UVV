"""
UVV Transform Utils
Transform utilities for UV operations including bounding boxes and rotation
"""

import bmesh
from math import sin, cos, pi
from mathutils import Vector
from mathutils.geometry import convex_hull_2d, box_fit_2d


# UV area bounding box default
UV_AREA_BBOX = {
    'bl': Vector((0.0, 0.0)),
    'tl': Vector((0.0, 1.0)),
    'tr': Vector((1.0, 1.0)),
    'br': Vector((1.0, 0.0)),
    'cen': Vector((0.5, 0.5)),
    'tc': Vector((0.5, 1.0)),
    'rc': Vector((1.0, 0.5)),
    'bc': Vector((0.5, 0.0)),
    'lc': Vector((0.0, 0.5)),
    'len_x': 1.0,
    'len_y': 1.0
}


class BoundingBox3d:
    """3D Bounding box for mesh objects"""

    # Blender BBox mapping order
    # (LoX, LoY, LoZ),
    # (LoX, LoY, HiZ),
    # (LoX, HiY, HiZ),
    # (LoX, HiY, LoZ),
    # (HiX, LoY, LoZ),
    # (HiX, LoY, HiZ),
    # (HiX, HiY, HiZ),
    # (HiX, HiY, LoZ)

    def __init__(self, obj) -> None:
        self.obj = obj
        self.mv = obj.matrix_world
        self.lc = [Vector((i[:])) for i in obj.bound_box[:]]
        self.loX = self.lc[0][0]
        self.loY = self.lc[0][1]
        self.loZ = self.lc[0][2]
        self.hiX = self.lc[6][0]
        self.hiY = self.lc[6][1]
        self.hiZ = self.lc[6][2]
        self.dim_x = self.hiX - self.loX
        self.dim_y = self.hiY - self.loY
        self.max_dim = max(self.dim_x, self.dim_y)
        self.lo_point = self.lc[0]
        self.hi_point = self.lc[6]


class BoundingBox2d:
    """2D Bounding box for UV islands"""

    def __init__(self, islands=None, points=None, uv_layer=None) -> None:
        self.uv_layer = uv_layer
        self.points = points
        self.islands = islands
        self.bot_left = None
        self.top_left = None
        self.top_right = None
        self.bot_right = None
        self.center = None
        self.len_x = None
        self.len_y = None

        self.top_center = None
        self.right_center = None
        self.bot_center = None
        self.left_center = None

        self._get_bounding_box()

    def _convex_hull_2d(self, points):
        ch_indices = convex_hull_2d(points)
        return [points[i] for i in ch_indices]

    def _get_bounding_box(self):
        minX = +1000
        minY = +1000
        maxX = -1000
        maxY = -1000
        if self.islands and self.uv_layer:
            self.points = []
            for island in self.islands:
                self.points.extend([loop[self.uv_layer].uv for face in island for loop in face.loops])
        if self.points:
            points = self._convex_hull_2d(self.points)
            for point in points:
                u, v = point
                minX = min(u, minX)
                minY = min(v, minY)
                maxX = max(u, maxX)
                maxY = max(v, maxY)
        if minX == +1000 and minY == +1000 and maxX == -1000 and maxY == -1000:
            minX = minY = maxX = maxY = 0

        self.bot_left = Vector((minX, minY))
        self.top_left = Vector((minX, maxY))
        self.top_right = Vector((maxX, maxY))
        self.bot_right = Vector((maxX, minY))
        self.center = (Vector((minX, minY)) + Vector((maxX, maxY))) / 2

        self.top_center = (Vector((minX, maxY)) + Vector((maxX, maxY))) / 2
        self.right_center = (Vector((maxX, maxY)) + Vector((maxX, minY))) / 2
        self.bot_center = (Vector((maxX, minY)) + Vector((minX, minY))) / 2
        self.left_center = (Vector((minX, minY)) + Vector((minX, maxY))) / 2

        self.len_x = (Vector((maxX, maxY)) - Vector((minX, maxY))).length
        self.len_y = (Vector((minX, minY)) - Vector((minX, maxY))).length

        self.max_len = max(self.len_x, self.len_y)
        div = min(self.max_len, 1) if self.max_len != 0 else 1
        self.factor_to_uv_area = max(self.max_len, 1) / div

        self.shift_to_uv_area = Vector((0.5, 0.5)) - self.center

    def get_legacy_bbox(self):
        """Return bbox as dictionary for compatibility"""
        return {
            "tl": self.top_left,
            "tc": self.top_center,
            "tr": self.top_right,
            "lc": self.left_center,
            "cen": self.center,
            "rc": self.right_center,
            "bl": self.bot_left,
            "bc": self.bot_center,
            "br": self.bot_right
        }


def scale2d(v, s, p):
    """Scale 2D coordinate
    v - coordinates
    s - scale by axis [x,y]
    p - anchor point
    """
    return (p[0] + s[0] * (v[0] - p[0]), p[1] + s[1] * (v[1] - p[1]))


def make_rotation_transformation(angle, origin=(0, 0)):
    """Calculate rotation transformation by the angle and origin"""
    cos_theta, sin_theta = cos(angle), sin(angle)
    x0, y0 = origin

    def xform(point):
        x, y = point[0] - x0, point[1] - y0
        return (x * cos_theta - y * sin_theta + x0,
                x * sin_theta + y * cos_theta + y0)
    return xform


def rotate_island(island, uv_layer, angle, anchor):
    """Perform rotation of the given island"""
    rotated = make_rotation_transformation(angle, anchor)
    for face in island:
        for loop in face.loops:
            loop[uv_layer].uv = rotated(loop[uv_layer].uv)


def scale_island(island, uv_layer, scale, anchor):
    """Scale island by given scale from given anchor"""
    loops = [loop for face in island for loop in face.loops]
    for loop in loops:
        loop[uv_layer].uv = scale2d(loop[uv_layer].uv, scale, anchor)


def calculate_fit_scale(pp_pos, padding, bbox, keep_proportion=True, bounds=Vector((1.0, 1.0))):
    """Calculate scale factor to fit island into bounds"""
    bbox_len_x = bbox.len_x if hasattr(bbox, 'len_x') else bbox['len_x']
    bbox_len_y = bbox.len_y if hasattr(bbox, 'len_y') else bbox['len_y']

    if bbox_len_x == 0.0:
        bbox_len_x = 1.0
    if bbox_len_y == 0.0:
        bbox_len_y = 1.0

    factor_u = (bounds.x - padding * 2) / bbox_len_x
    factor_v = (bounds.y - padding * 2) / bbox_len_y

    # Check fit proportions
    if keep_proportion:
        # Scale to fit bounds
        min_factor = min(factor_u, factor_v)
        scale = (min_factor, min_factor)

        # Scale to fit one side
        if pp_pos in ("lc", "rc"):
            scale = (factor_v, factor_v)
        elif pp_pos in ("tc", "bc"):
            scale = (factor_u, factor_u)
    else:
        scale = (factor_u, factor_v)
    return scale


def zen_convex_hull_2d(points):
    """Get convex hull points from list of 2D points"""
    ch_indices = convex_hull_2d(points)
    ch_points = []
    for i in ch_indices:
        ch_points.append(points[i])
    return ch_points


# =============================================================================
# UniV-style Island Transformation Methods for Weld Alignment
# Based on UniV's island.py transformation functions
# =============================================================================

def move_island(island, uv_layer, delta):
    """
    Move all UV coordinates in an island by delta vector.
    Based on UniV's FaceIsland.move() (lines 320-328)

    Args:
        island: List of BMFaces that make up the island
        uv_layer: The UV layer to modify
        delta: Vector to move by (Vector((x, y)))

    Returns:
        bool: True if moved, False if delta is near zero
    """
    # Check if delta is near zero (no need to move)
    if abs(delta.x) < 1e-6 and abs(delta.y) < 1e-6:
        return False

    for face in island:
        for loop in face.loops:
            loop[uv_layer].uv += delta

    return True


def rotate_island_with_aspect(island, uv_layer, angle, pivot, aspect=1.0):
    """
    Rotate island around pivot with aspect ratio correction.
    Based on UniV's FaceIsland.rotate() (lines 346-375)

    Args:
        island: List of BMFaces
        uv_layer: UV layer to modify
        angle: Rotation angle in radians (positive = counter-clockwise)
        pivot: Pivot point for rotation (Vector)
        aspect: Aspect ratio (width/height) for correction

    Returns:
        bool: True if rotated, False if angle is near zero
    """
    from math import isclose
    from mathutils import Matrix

    # Check if angle is near zero
    if isclose(angle, 0, abs_tol=0.0001):
        return False

    if aspect != 1.0:
        # With aspect ratio correction
        rot_matrix = Matrix.Rotation(angle, 2)
        rot_matrix[0][1] = aspect * rot_matrix[0][1]
        rot_matrix[1][0] = rot_matrix[1][0] / aspect

        diff = pivot - (pivot @ rot_matrix)

        for face in island:
            for loop in face.loops:
                loop[uv_layer].uv = loop[uv_layer].uv @ rot_matrix + diff
    else:
        # Without aspect ratio (simpler rotation using make_rotation_transformation)
        # Use the rotation function that works correctly
        rotated = make_rotation_transformation(angle, pivot)

        for face in island:
            for loop in face.loops:
                loop[uv_layer].uv = rotated(loop[uv_layer].uv)

    return True


def scale_island_with_pivot(island, uv_layer, scale, pivot):
    """
    Scale island around a pivot point.
    Based on UniV's FaceIsland.scale() (lines 400-412)

    Args:
        island: List of BMFaces
        uv_layer: UV layer to modify
        scale: Scale vector (Vector((scale_x, scale_y)))
        pivot: Pivot point for scaling (Vector)

    Returns:
        bool: True if scaled, False if scale is near 1.0
    """
    # Check if scale is near uniform (no change needed)
    if abs(scale.x - 1.0) < 1e-6 and abs(scale.y - 1.0) < 1e-6:
        return False

    # Calculate difference: pivot - pivot * scale
    diff = pivot - Vector((pivot.x * scale.x, pivot.y * scale.y))

    for face in island:
        for loop in face.loops:
            uv_co = loop[uv_layer].uv
            uv_co.x *= scale.x
            uv_co.y *= scale.y
            uv_co += diff

    return True


def set_island_position(island, uv_layer, to_pos, from_pos=None):
    """
    Move island from one position to another.
    Based on UniV's AdvIsland.set_position() (lines 1014-1017)

    Args:
        island: List of BMFaces
        uv_layer: UV layer to modify
        to_pos: Target position (Vector)
        from_pos: Current position (Vector). If None, uses island's min corner

    Returns:
        bool: True if moved
    """
    # If from_pos not specified, calculate island's bounding box min
    if from_pos is None:
        bbox = BoundingBox2d(islands=[island], uv_layer=uv_layer)
        from_pos = bbox.bot_left

    # Calculate delta and move
    delta = to_pos - from_pos
    return move_island(island, uv_layer, delta)


def calc_island_bbox_center(island, uv_layer):
    """
    Calculate the center point of an island's bounding box.

    Args:
        island: List of BMFaces
        uv_layer: UV layer

    Returns:
        Vector: Center point of the bounding box
    """
    bbox = BoundingBox2d(islands=[island], uv_layer=uv_layer)
    return bbox.center
