# NumPy math utilities for UV operations
# Ported from UniV addon

import numpy as np
import math
from mathutils import Vector


def np_vec_dot(a, b):
    """Dot product for numpy arrays"""
    return np.einsum('ij,ij->i', a, b)


def np_vec_normalized(a, keepdims=True):
    """Vector normalization for numpy arrays"""
    return np.linalg.norm(a, axis=1, keepdims=keepdims)


def vec_isclose(a, b, abs_tol: float = 0.00001):
    """Check if vectors are close"""
    return all(math.isclose(a1, b1, abs_tol=abs_tol) for a1, b1 in zip(a, b))


def vec_isclose_to_uniform(delta: Vector, abs_tol: float = 0.00001):
    """Check if vector is close to uniform (all components == 1.0)"""
    return all(math.isclose(component, 1.0, abs_tol=abs_tol) for component in delta)


def vec_isclose_to_zero(delta: Vector, abs_tol: float = 0.00001):
    """Check if vector is close to zero"""
    return all(math.isclose(component, 0.0, abs_tol=abs_tol) for component in delta)


def closest_pt_to_line(pt, line_start, line_end):
    """Find closest point on line to given point"""
    line_vec = line_end - line_start
    pt_vec = pt - line_start
    line_len = line_vec.length_squared
    if line_len == 0.0:
        return line_start
    t = max(0.0, min(1.0, pt_vec.dot(line_vec) / line_len))
    return line_start + t * line_vec


def find_closest_edge_3d_to_2d(mouse_pos, face, umesh, region, rv3d):
    """Find closest edge in 3D space to 2D mouse position"""
    pt = Vector(mouse_pos)
    mat = umesh.obj.matrix_world
    min_edge = None
    min_dist = float('inf')
    for e in face.edges:
        v_a, v_b = e.verts

        co_a = loc3d_to_reg2d_safe(region, rv3d, mat @ v_a.co)
        co_b = loc3d_to_reg2d_safe(region, rv3d, mat @ v_b.co)

        close_pt = closest_pt_to_line(pt, co_a, co_b)
        dist = (close_pt - pt).length
        if dist < min_dist:
            min_edge = e
            min_dist = dist

    return min_edge, min_dist


def loc3d_to_reg2d_safe(region, rv3d, coord, push_forward=0.01):
    """Convert 3D location to 2D region coordinates safely"""
    prj = rv3d.perspective_matrix @ Vector((*coord, 1.0))

    for i in range(2, 12):
        if prj.w <= 0.0:
            view_dir = (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()
            coord += view_dir * push_forward * i
            prj = rv3d.perspective_matrix @ Vector((*coord, 1.0))
        else:
            break

    if prj.w <= 0.0:
        return Vector((0.0, 0.0))

    prj /= prj.w
    return Vector((region.x + (prj.x + 1.0) * region.width * 0.5,
                   region.y + (prj.y + 1.0) * region.height * 0.5))