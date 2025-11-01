# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

# UniV Quadrify Utility Functions

def linked_crn_uv_by_face_tag_unordered_included(crn, uv):
    """Linked to arg corner by face tag with arg corner and unordered - from UniV ubm.py line 541"""
    first_co = crn[uv].uv
    return [l_crn for l_crn in crn.vert.link_loops if l_crn.face.tag and l_crn[uv].uv == first_co]


def set_faces_tag(faces, tag=True):
    """Set face tag for all faces - from UniV ubm.py line 81"""
    if tag:
        for f in faces:
            f.tag = True
    else:
        for f in faces:
            f.tag = False
