import bmesh
import mathutils
from math import sqrt


def get_object_scale(obj):
    """Get object scale factor for 3D area calculations"""
    scale = obj.scale
    # Return average scale factor
    return (scale.x + scale.y + scale.z) / 3.0


def calc_face_area_3d(face, scale=1.0):
    """Calculate 3D area of a face"""
    area = face.calc_area()
    return area * scale * scale


def calc_face_area_uv(face, uv_layer):
    """Calculate UV area of a face"""
    if len(face.loops) < 3:
        return 0.0

    # Get UV coordinates
    uv_coords = [loop[uv_layer].uv for loop in face.loops]

    # Calculate area using shoelace formula for polygon
    area = 0.0
    n = len(uv_coords)
    for i in range(n):
        j = (i + 1) % n
        area += uv_coords[i].x * uv_coords[j].y
        area -= uv_coords[j].x * uv_coords[i].y

    return abs(area) / 2.0


def calc_total_area_3d(faces, scale=1.0):
    """Calculate total 3D area of faces - UniV implementation"""
    from mathutils import Vector
    from math import isclose
    
    if scale:
        avg_scale = (sum(abs(s_) for s_ in scale) / 3)
        if all(isclose(abs(s_), avg_scale, abs_tol=0.01) for s_ in scale):
            return sum(f.calc_area() for f in faces) * avg_scale ** 2
        # newell_cross
        area = 0.0
        for f in faces:
            n = Vector()
            corners = f.loops
            v_prev = corners[-1].vert.co * scale
            for crn in corners:
                v_curr = crn.vert.co * scale
                # (inplace optimization ~20%) - n += (v_prev.yzx - v_curr.yzx) * (v_prev.zxy + v_curr.zxy)
                v_prev_yzx = v_prev.yzx
                v_prev_zxy = v_prev.zxy

                v_prev_yzx -= v_curr.yzx
                v_prev_zxy += v_curr.zxy

                v_prev_yzx *= v_prev_zxy
                n += v_prev_yzx

                v_prev = v_curr

            area += n.length
        return area * 0.5
    else:
        return sum(f.calc_area() for f in faces)


def calc_total_area_uv(faces, uv_layer):
    """Calculate total UV area of faces - UniV implementation"""
    return sum(calc_face_area_uv(f, uv_layer) for f in faces)


def get_selected_faces(bm):
    """Get selected faces from bmesh"""
    return [face for face in bm.faces if face.select]


def get_active_uv_layer(bm):
    """Get active UV layer from bmesh"""
    if not bm.loops.layers.uv:
        return None
    return bm.loops.layers.uv.active


def calculate_texel_density(area_3d, area_uv, texture_size):
    """Calculate texel density from areas and texture size"""
    if area_3d <= 0 or area_uv <= 0:
        return 0.0

    # Average texture size
    avg_texture_size = (texture_size[0] + texture_size[1]) / 2.0

    # Calculate texel density
    area_3d_sqrt = sqrt(area_3d)
    area_uv_sqrt = sqrt(area_uv) * avg_texture_size

    if area_3d_sqrt <= 0:
        return 0.0

    return area_uv_sqrt / area_3d_sqrt


def set_texel_density(target_density, area_3d, area_uv, texture_size):
    """Calculate scale factor needed to achieve target texel density"""
    if area_3d <= 0 or area_uv <= 0 or target_density <= 0:
        return 1.0

    current_density = calculate_texel_density(area_3d, area_uv, texture_size)

    if current_density <= 0:
        return 1.0

    # Scale factor to achieve target density
    scale_factor = target_density / current_density
    return scale_factor


def scale_uv_selection(bm, uv_layer, scale_factor, pivot=None):
    """Scale UV selection around pivot point"""
    if not uv_layer or scale_factor <= 0:
        return

    selected_loops = [loop for face in bm.faces if face.select for loop in face.loops]

    if not selected_loops:
        return

    # Calculate pivot if not provided
    if pivot is None:
        uv_sum = mathutils.Vector((0, 0))
        for loop in selected_loops:
            uv_sum += loop[uv_layer].uv
        pivot = uv_sum / len(selected_loops)

    # Scale UVs around pivot
    for loop in selected_loops:
        uv = loop[uv_layer].uv
        direction = uv - pivot
        loop[uv_layer].uv = pivot + direction * scale_factor