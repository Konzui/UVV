"""
Helper functions for raycast operations
"""

def calc_visible_uv_faces_iter(umesh):
    """Calculate visible UV faces iterator"""
    if umesh.is_full_face_selected:
        return umesh.bm.faces
    if umesh.sync:
        return (f for f in umesh.bm.faces if not f.hide)

    if umesh.is_full_face_deselected:
        return []
    return (f for f in umesh.bm.faces if f.select)


def linked_crn_to_vert_with_seam_3d_iter(crn):
    """Linked to arg corner by visible faces"""
    first_vert = crn.vert
    bm_iter = crn

    while True:
        bm_iter_prev = bm_iter.link_loop_prev
        bm_iter = bm_iter_prev.link_loop_radial_prev  # get ccw corner
        if first_vert != bm_iter.vert or bm_iter_prev.edge.seam or bm_iter.face.hide:  # Skip boundary or flipped
            bm_iter = crn
            while True:
                if bm_iter.edge.seam:  # clamp by seam
                    break
                bm_iter = bm_iter.link_loop_radial_next.link_loop_next  # get cw corner
                # Skip boundary or flipped or clamp by hide
                if first_vert != bm_iter.vert or bm_iter.face.hide:
                    break

                if bm_iter == crn:
                    break
                yield bm_iter
            break

        if bm_iter == crn:
            break
        yield bm_iter
