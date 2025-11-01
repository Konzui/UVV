"""
UVV Constants
Defines constant values and planes used throughout the addon
"""

from mathutils import Vector

# UV axis constants
u_axis = Vector((1.0, 0.0))
v_axis = Vector((0.0, 1.0))

# Face UV area multiplication factor
FACE_UV_AREA_MULT = 100000


class Planes:
    """3D and 2D plane/axis definitions"""

    # 3D axes
    x3 = Vector((1, 0, 0))
    y3 = Vector((0, 1, 0))
    z3 = Vector((0, 0, 1))

    x3_negative = Vector((-1.0, 0.0, 0.0))
    y3_negative = Vector((0.0, -1.0, 0.0))
    z3_negative = Vector((0.0, 0.0, -1.0))

    # 2D axes
    axis_x = Vector((1, 0))
    axis_y = Vector((0, 1))

    # 3D axis dictionary (all axes)
    pool_3d_dict = {
        "x": x3,
        "y": y3,
        "z": z3,
        "-x": x3_negative,
        "-y": y3_negative,
        "-z": z3_negative
    }

    # 3D orientation dictionary (excludes Z axes)
    pool_3d_orient_dict = {
        "x": x3,
        "y": y3,
        "-x": x3_negative,
        "-y": y3_negative,
    }

    # Tuples
    pool_3d = (
        x3,
        y3,
        z3,
        x3_negative,
        y3_negative,
        z3_negative
    )
    pool_2d = (axis_x, axis_y)
