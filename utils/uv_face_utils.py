# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

"""
UV Face calculation utilities.
Based on UniV's ubm.py implementation.
"""

from bmesh.types import BMFace


def calc_selected_uv_faces(umesh):
    """
    Calculate selected UV faces based on UniV implementation.
    Based on UniV's calc_selected_uv_faces() (ubm.py:949-967).
    """
    if umesh.is_full_face_deselected:
        return []

    if umesh.sync:
        if umesh.is_full_face_selected:
            return umesh.bm.faces
        return [f for f in umesh.bm.faces if f.select]

    uv = umesh.uv
    if umesh.is_full_face_selected:
        if umesh.elem_mode == 'VERT':
            return [f for f in umesh.bm.faces if all(crn[uv].select for crn in f.loops)]
        else:
            return [f for f in umesh.bm.faces if all(crn[uv].select_edge for crn in f.loops)]
    if umesh.elem_mode == 'VERT':
        return [f for f in umesh.bm.faces if all(crn[uv].select for crn in f.loops) and f.select]
    else:
        return [f for f in umesh.bm.faces if all(crn[uv].select_edge for crn in f.loops) and f.select]


def calc_visible_uv_faces(umesh):
    """
    Calculate visible UV faces based on UniV implementation.
    Based on UniV's calc_visible_uv_faces() (ubm.py:1018-1026).
    """
    if umesh.is_full_face_selected:
        return umesh.bm.faces
    if umesh.sync:
        return [f for f in umesh.bm.faces if not f.hide]

    if umesh.is_full_face_deselected:
        return []
    return [f for f in umesh.bm.faces if f.select]


def calc_uv_faces(umesh, *, selected):
    """
    Calculate UV faces based on selection state.
    Based on UniV's calc_uv_faces() (ubm.py:1046-1049).
    """
    if selected:
        return calc_selected_uv_faces(umesh)
    return calc_visible_uv_faces(umesh)
