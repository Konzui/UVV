# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later
# Ported from UniV addon for stitch functionality

"""
Advanced Island classes for UV stitching operations.
Based on UniV's utypes/island.py implementation.

AdvIsland provides enhanced island functionality with transform operations.
AdvIslands is a collection of AdvIsland objects with management utilities.
"""

import bmesh
import math
from mathutils import Vector, Matrix
from bmesh.types import BMFace, BMLoop
from typing import List, Optional, Iterator, Set
from collections import defaultdict

from .bbox import BBox
from .loop_group import LoopGroup, LoopGroups
from ..utils import stitch_utils as utils


class AdvIsland:
    """
    Enhanced island with transform operations for stitching.
    Based on UniV's AdvIsland class.
    """
    
    def __init__(self, umesh, faces: List[BMFace] = None):
        """
        Initialize AdvIsland.
        Based on UniV's AdvIsland.__init__() (island.py:972-988).

        Args:
            umesh: UMesh object containing bmesh and UV layer
            faces: List of BMFace objects in this island
        """
        self.umesh = umesh
        self.faces = faces or []
        self.bbox = BBox()
        self.area_3d = 0.0
        self.area_uv = -1.0  # Initialize to -1.0 like in island.py
        self.select_state = None
        self.tag = True  # UniV default: True (line 983)
        self.sequence = []

        # Cached properties
        self._dirt = True
        self._bbox_cache: Optional[BBox] = None
    
    def __len__(self):
        return len(self.faces)
    
    def __iter__(self):
        return iter(self.faces)
    
    def __getitem__(self, index):
        return self.faces[index]

    def scale_simple(self, scale_vector: Vector):
        """
        Scale island by vector.
        Based on UniV's scale_simple() method.
        
        Args:
            scale_vector: Vector to scale by (x, y)
        """
        if not self.faces:
            return
            
        uv = self.umesh.uv
        center = self.bbox.center
        
        for face in self.faces:
            for loop in face.loops:
                co = loop[uv].uv
                # Scale relative to center
                new_co = center + (co - center) * scale_vector
                loop[uv].uv = new_co
        
        self._dirt = True

    def rotate_simple(self, angle: float, aspect: float):
        """
        Rotate island by angle with aspect correction.
        Based on UniV's rotate_simple() method.
        
        Args:
            angle: Rotation angle in radians
            aspect: Aspect ratio for correction
        """
        if not self.faces:
            return
            
        uv = self.umesh.uv
        center = self.bbox.center
        
        # Create rotation matrix with aspect correction
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        
        for face in self.faces:
            for loop in face.loops:
                co = loop[uv].uv
                # Translate to origin
                rel_co = co - center
                # Apply aspect correction
                rel_co.x *= aspect
                # Rotate
                new_x = rel_co.x * cos_a - rel_co.y * sin_a
                new_y = rel_co.x * sin_a + rel_co.y * cos_a
                # Apply inverse aspect correction
                new_x /= aspect
                # Translate back
                new_co = Vector((new_x, new_y)) + center
                loop[uv].uv = new_co
        
        self._dirt = True

    def set_position(self, target_pos: Vector, current_pos: Vector):
        """
        Move island to target position.
        Based on UniV's set_position() method.
        
        Args:
            target_pos: Target position
            current_pos: Current position
        """
        if not self.faces:
            return
            
        uv = self.umesh.uv
        delta = target_pos - current_pos
        
        for face in self.faces:
            for loop in face.loops:
                co = loop[uv].uv
                loop[uv].uv = co + delta
        
        self._dirt = True

    def move(self, delta: Vector) -> bool:
        """
        Move island by delta vector.
        Based on UniV's move() method (island.py:990-993).
        
        Args:
            delta: Movement vector
            
        Returns:
            bool: True if movement was applied
        """
        if self._bbox_cache is not None:
            self._bbox_cache.move(delta)
        # Apply movement to all UV coordinates
        if not self.faces:
            return False
        
        uv = self.umesh.uv
        for face in self.faces:
            for loop in face.loops:
                loop[uv].uv += delta
        
        self._dirt = True
        return True

    def scale(self, scale_vector: Vector, center: Vector):
        """
        Scale island by vector around center.
        Based on UniV's scale() method.
        
        Args:
            scale_vector: Vector to scale by
            center: Center point for scaling
        """
        if not self.faces:
            return
            
        uv = self.umesh.uv
        
        for face in self.faces:
            for loop in face.loops:
                co = loop[uv].uv
                # Scale relative to center
                new_co = center + (co - center) * scale_vector
                loop[uv].uv = new_co
        
        self._dirt = True

    def set_boundary_tag(self, match_idx: bool = True):
        """
        Set boundary tags on island faces.
        Based on UniV's set_boundary_tag() method.
        
        Args:
            match_idx: Whether to match face indices
        """
        uv = self.umesh.uv
        
        for face in self.faces:
            for loop in face.loops:
                if match_idx:
                    # Tag based on face index matching
                    loop.tag = (loop.face.index == face.index)
                else:
                    # Tag all loops in face
                    loop.tag = True

    def calc_tris(self):
        """Calculate triangles for this island"""
        tris_isl = []
        for f in self.faces:
            corners = f.loops
            if (n := len(corners)) == 4:
                l1, l2, l3, l4 = corners
                tris_isl.append((l1, l2, l3))
                tris_isl.append((l3, l4, l1))
            elif n == 3:
                tris_isl.append(tuple(corners))
            else:
                first_crn = corners[0]
                for i in range(1, n - 1):
                    tris_isl.append((first_crn, corners[i], corners[i + 1]))
        
        self.tris = tris_isl
        return bool(tris_isl)

    def calc_flat_coords(self, save_triplet=False):
        """Calculate flat coordinates from triangles"""
        assert self.tris, 'Calculate tris'
        
        uv = self.umesh.uv
        if save_triplet:
            self.flat_coords = [(t[0][uv].uv, t[1][uv].uv, t[2][uv].uv) for t in self.tris]
        else:
            if not hasattr(self, 'flat_coords'):
                self.flat_coords = []
            self.flat_coords.extend(t_crn[uv].uv for t in self.tris for t_crn in t)
    
    def __contains__(self, face):
        return face in self.faces
    
    @property
    def bbox(self) -> BBox:
        """Get bounding box of the island."""
        if self._bbox_cache is None or self._dirt:
            self._bbox_cache = self._calc_bbox()
            self._dirt = False
        return self._bbox_cache
    
    @bbox.setter
    def bbox(self, value):
        self._bbox_cache = value
    
    def _calc_bbox(self) -> BBox:
        """Calculate bounding box of the island."""
        if not self.faces:
            return BBox()
        
        uv = self.umesh.uv
        uvs = []
        
        for face in self.faces:
            for loop in face.loops:
                uvs.append(loop[uv].uv)
        
        if not uvs:
            return BBox()
        
        min_x = min(uv.x for uv in uvs)
        max_x = max(uv.x for uv in uvs)
        min_y = min(uv.y for uv in uvs)
        max_y = max(uv.y for uv in uvs)
        
        return BBox(min_x, max_x, min_y, max_y)
    
    def rotate_simple(self, angle: float, aspect: float = 1.0):
        """
        Rotate island around world origin (0, 0).
        Based on UniV's rotate_simple() method (island.py:377-398).

        Args:
            angle: Rotation angle in radians
            aspect: Aspect ratio for rotation correction
        """
        import math

        if math.isclose(angle, 0, abs_tol=0.0001):
            return False

        uv = self.umesh.uv

        if aspect != 1.0:
            rot_matrix = Matrix.Rotation(-angle, 2)
            rot_matrix[0][1] = aspect * rot_matrix[0][1]
            rot_matrix[1][0] = rot_matrix[1][0] / aspect

            for face in self.faces:
                for crn in face.loops:
                    crn_uv = crn[uv]
                    crn_uv.uv = crn_uv.uv @ rot_matrix
        else:
            vec_rotate = Vector.rotate
            rot_matrix = Matrix.Rotation(angle, 2)
            for face in self.faces:
                for crn in face.loops:
                    vec_rotate(crn[uv].uv, rot_matrix)

        self._dirt = True
        return True
    
    def rotate(self, angle: float, pivot: Vector, aspect: float = 1.0):
        """
        Rotate island around a specific pivot point.
        Based on UniV's rotate() method (island.py:352-375).

        Args:
            angle: Rotation angle in radians
            pivot: Pivot point for rotation
            aspect: Aspect ratio for rotation correction
        """
        import math

        if math.isclose(angle, 0, abs_tol=0.0001):
            return False

        uv = self.umesh.uv

        if aspect != 1.0:
            rot_matrix = Matrix.Rotation(angle, 2)
            rot_matrix[0][1] = aspect * rot_matrix[0][1]
            rot_matrix[1][0] = rot_matrix[1][0] / aspect

            diff = pivot - (pivot @ rot_matrix)
            for face in self.faces:
                for crn in face.loops:
                    crn_uv = crn[uv]
                    crn_uv.uv = crn_uv.uv @ rot_matrix + diff
        else:
            rot_matrix = Matrix.Rotation(-angle, 2)
            diff = pivot - (rot_matrix @ pivot)
            vec_rotate = Vector.rotate
            for face in self.faces:
                for crn in face.loops:
                    crn_co = crn[uv].uv
                    vec_rotate(crn_co, rot_matrix)
                    crn_co += diff

        self._dirt = True
        return True
    
    def calc_area_uv(self):
        """
        Calculate UV area of the island.
        Based on UniV's calc_area_uv() method.
        
        Returns:
            float: Total UV area
        """
        area = 0.0
        uv = self.umesh.uv
        
        for face in self.faces:
            if len(face.loops) >= 3:
                # Calculate area using shoelace formula
                uvs = [loop[uv].uv for loop in face.loops]
                face_area = 0.0
                for i in range(len(uvs)):
                    j = (i + 1) % len(uvs)
                    face_area += uvs[i].cross(uvs[j])
                area += abs(face_area) * 0.5
        
        self.area_uv = area
        return area
    
    def calc_area_3d(self, scale=None):
        """
        Calculate 3D area of the island.
        Based on UniV's calc_area_3d() method.
        
        Args:
            scale: Optional scale factor for area calculation
            
        Returns:
            float: Total 3D area
        """
        area = 0.0
        
        for face in self.faces:
            if scale:
                # Apply scale to face area
                face_area = face.calc_area()
                if hasattr(scale, 'x'):  # Vector scale
                    area += face_area * (scale.x * scale.y)
                else:  # Scalar scale
                    area += face_area * (scale * scale)
            else:
                area += face.calc_area()
        
        self.area_3d = area
        return area
    
    def set_texel(self, texel: float, texture_size: float):
        """
        Set texel density for the island.
        Based on UniV's set_texel() method (island.py:1000-1008).
        
        Args:
            texel: Target texel density
            texture_size: Texture size for calculation
            
        Returns:
            bool: True if texel was set successfully, None if failed
        """
        import math
        
        # Check if areas are calculated (Univ uses assert)
        if self.area_3d == -1.0 or self.area_uv == -1.0:
            return None
        
        area_3d = math.sqrt(self.area_3d)
        area_uv = math.sqrt(self.area_uv) * texture_size
        
        if math.isclose(area_3d, 0.0, abs_tol=1e-6) or math.isclose(area_uv, 0.0, abs_tol=1e-6):
            return None
        
        scale = texel / (area_uv / area_3d)
        return self.scale(Vector((scale, scale)), self.bbox.center)
    
    def scale_simple(self, scale: Vector):
        """
        Scale island from world center.
        Based on UniV's scale_simple() method (island.py:414-421).
        
        Args:
            scale: Scale factors (x, y)
        """
        from ..utils.umath_numpy import vec_isclose_to_uniform
        
        if vec_isclose_to_uniform(scale):
            return False
        
        uv = self.umesh.uv
        for face in self.faces:
            for crn in face.loops:
                crn[uv].uv *= scale
        
        self._dirt = True
        return True
    
    def scale(self, scale: Vector, pivot: Vector) -> bool:
        """
        Scale island from a specific pivot point.
        Based on UniV's scale() method (island.py:400-412).
        
        Args:
            scale: Scale factors (x, y)
            pivot: Pivot point for scaling
            
        Returns:
            bool: True if scaling was applied
        """
        from ..utils.umath_numpy import vec_isclose_to_uniform
        
        if vec_isclose_to_uniform(scale):
            return False
        
        if self._bbox_cache is not None:
            self._bbox_cache.scale(scale, pivot)
        
        diff = pivot - pivot * scale
        
        uv = self.umesh.uv
        for face in self.faces:
            for crn in face.loops:
                crn_co = crn[uv].uv
                crn_co *= scale
                crn_co += diff
        
        self._dirt = True
        return True
    
    
    def set_position(self, to: Vector, _from: Vector = None):
        """
        Move island to align source_point with target_point.
        Based on UniV's set_position() method (island.py:1014-1017).
        
        Args:
            to: Where to move to
            _from: Current position to move from (defaults to bbox.min)
        """
        if _from is None:
            _from = self.bbox.min
        return self.move(to - _from)
    
    def set_boundary_tag(self, match_idx: bool = False):
        """
        Tag boundary edges of the island.
        Based on UniV's set_boundary_tag() method.
        
        Args:
            match_idx: Whether to match face indices
        """
        uv = self.umesh.uv
        
        for face in self.faces:
            for loop in face.loops:
                shared = loop.link_loop_radial_prev
                
                if shared == loop:
                    # Boundary edge
                    loop.tag = True
                elif match_idx and shared.face.index != face.index:
                    # Different face index
                    loop.tag = True
                else:
                    # Check if UV coordinates match
                    if (loop[uv].uv != shared.link_loop_next[uv].uv or 
                        loop.link_loop_next[uv].uv != shared[uv].uv):
                        loop.tag = True
                    else:
                        loop.tag = False
    
    def mark_seam(self):
        """
        Mark seams on the island's boundary edges.
        Based on UniV's mark_seam() method.
        """
        for face in self.faces:
            for loop in face.loops:
                if loop.tag:
                    loop.edge.seam = True
    
    def calc_max_uv_area_face(self) -> Optional[BMFace]:
        """
        Calculate the face with maximum UV area.
        Based on UniV's calc_max_uv_area_face() method.
        
        Returns:
            BMFace: Face with maximum UV area, or None if no faces
        """
        if not self.faces:
            return None
        
        uv = self.umesh.uv
        max_area = -1.0
        max_face = None
        
        for face in self.faces:
            area = self._calc_face_uv_area(face, uv)
            if area > max_area:
                max_area = area
                max_face = face
        
        return max_face
    
    def _calc_face_uv_area(self, face: BMFace, uv) -> float:
        """Calculate UV area of a face."""
        if len(face.loops) < 3:
            return 0.0

        uvs = [loop[uv].uv for loop in face.loops]

        # Calculate area using shoelace formula
        area = 0.0
        for i in range(len(uvs)):
            j = (i + 1) % len(uvs)
            area += uvs[i].cross(uvs[j])

        return abs(area) * 0.5

    def calc_edge_length(self, selected: bool = False) -> float:
        """
        Calculate total edge length of the island in 3D.
        Based on UniV's calc_edge_length() method.

        Args:
            selected: Whether to only count selected edges

        Returns:
            float: Total 3D edge length
        """
        total_length = 0.0
        seen_edges = set()

        for face in self.faces:
            for loop in face.loops:
                edge = loop.edge
                if edge in seen_edges:
                    continue

                if selected and not edge.select:
                    continue

                seen_edges.add(edge)
                total_length += edge.calc_length()

        return total_length

    def calc_selected_edge_corners_iter(self):
        """
        Calculate selected edge corners iterator.
        Exact UniV implementation from AdvIsland.calc_selected_edge_corners_iter().
        """
        if self.umesh.sync:
            return (crn for f in self for crn in f.loops if crn.edge.select)
        else:
            uv = self.umesh.uv
            return (crn for f in self for crn in f.loops if crn[uv].select_edge)

    def set_corners_tag(self, value: bool):
        """
        Set tag on all corners in the island.
        Based on UniV's set_corners_tag() method.

        Args:
            value: Tag value to set
        """
        for face in self.faces:
            for loop in face.loops:
                loop.tag = value

    def iter_corners_by_tag(self) -> Iterator[BMLoop]:
        """
        Iterate over tagged corners in the island.
        Based on UniV's iter_corners_by_tag() method.

        Returns:
            Iterator of tagged BMLoop objects
        """
        for face in self.faces:
            for loop in face.loops:
                if loop.tag:
                    yield loop

    def calc_bbox(self) -> BBox:
        """
        Calculate and return bounding box.
        Based on UniV's calc_bbox() method.

        Returns:
            BBox: Bounding box of the island
        """
        self._bbox_cache = self._calc_bbox()
        self._dirt = False
        return self._bbox_cache
    
    def mark_seam(self, additional: bool = True):
        """
        Mark seams on the island's boundary edges.
        Based on UniV's mark_seam() method.
        
        Args:
            additional: If True, add to existing seams; if False, replace them
        """
        uv = self.umesh.uv
        if self.umesh.sync:
            for face in self.faces:
                for loop in face.loops:
                    shared_loop = loop.link_loop_radial_prev
                    if loop == shared_loop or shared_loop.face.hide:
                        loop.edge.seam = True
                        continue
                    seam = not (loop[uv].uv == shared_loop.link_loop_next[uv].uv and 
                               loop.link_loop_next[uv].uv == shared_loop[uv].uv)
                    if additional:
                        loop.edge.seam |= seam
                    else:
                        loop.edge.seam = seam
        else:
            for face in self.faces:
                for loop in face.loops:
                    shared_loop = loop.link_loop_radial_prev
                    if loop == shared_loop or not shared_loop.face.select:
                        loop.edge.seam = True
                        continue
                    seam = not (loop[uv].uv == shared_loop.link_loop_next[uv].uv and 
                               loop.link_loop_next[uv].uv == shared_loop[uv].uv)
                    if additional:
                        loop.edge.seam |= seam
                    else:
                        loop.edge.seam = seam
    
    def mark_seam_by_index(self, additional: bool = True):
        """
        Mark seams using face.index for island boundaries.
        Based on UniV's mark_seam_by_index() method.
        
        Args:
            additional: If True, add to existing seams; if False, replace them
        """
        if not self.faces:
            return
        
        index = self.faces[0].index
        for face in self.faces:
            for loop in face.loops:
                shared_loop = loop.link_loop_radial_prev
                if loop == shared_loop:
                    loop.edge.seam = True
                    continue
                
                if additional:
                    loop.edge.seam |= shared_loop.face.index != index
                else:
                    loop.edge.seam = shared_loop.face.index != index
    
    def apply_aspect_ratio(self):
        """
        Apply aspect ratio scaling to the island.
        Based on UniV's apply_aspect_ratio() method.
        """
        if not self.faces:
            return
        
        scale = Vector((self.umesh.aspect, 1))
        self.scale_simple(scale)
    
    def reset_aspect_ratio(self):
        """
        Reset aspect ratio scaling for the island.
        Based on UniV's reset_aspect_ratio() method.
        
        Returns:
            bool: True if aspect ratio was applied and reset
        """
        if not self.faces:
            return False
        
        scale = Vector((1 / self.umesh.aspect, 1))
        self.scale_simple(scale)
        return True
    
    def save_transform(self):
        """
        Save current island transform state.
        Based on UniV's save_transform() method.
        
        Returns:
            SaveTransform: Object storing current island state
        """
        from .island import SaveTransform
        return SaveTransform(self)
    
    @property
    def select(self):
        """
        Get selection state of the island.
        Based on UniV's select property.
        """
        if self.umesh.sync:
            return any(face.select for face in self.faces)
        else:
            uv = self.umesh.uv
            return any(crn[uv].select for face in self.faces for crn in face.loops)
    
    @select.setter
    def select(self, state: bool):
        """
        Set selection state of the island.
        Based on UniV's select setter.
        
        Args:
            state: Selection state to set
        """
        if self.umesh.sync:
            for face in self.faces:
                face.select = state
        else:
            uv = self.umesh.uv
            for face in self.faces:
                for loop in face.loops:
                    loop[uv].select = state
                    loop[uv].select_edge = state
    
    def set_pins(self, state: bool, with_pinned: bool = False):
        """
        Set pin state for all corners in the island.
        Based on UniV's set_pins() method.
        
        Args:
            state: Pin state to set
            with_pinned: If True, only pin unpinned corners and return list of pinned corners
        """
        uv = self.umesh.uv
        pinned_corners = []
        
        if with_pinned:
            # Only pin unpinned corners and return list
            for face in self.faces:
                for loop in face.loops:
                    loop_uv = loop[uv]
                    if not loop_uv.pin_uv:
                        loop_uv.pin_uv = True
                        pinned_corners.append(loop_uv)
            return pinned_corners
        else:
            # Set pin state for all corners
            for face in self.faces:
                for loop in face.loops:
                    loop[uv].pin_uv = state


class IslandHit:
    """
    Hit detection for mouse-to-island distance calculation.
    Based on UniV's IslandHit class.
    """
    def __init__(self, mouse_pos: Vector, max_distance: float = None):
        self.mouse_pos = mouse_pos
        self.max_distance = max_distance
        self.min_dist = float('inf')
        self.island = None
    
    def find_nearest_island(self, isl: 'AdvIsland'):
        """
        Find nearest island to mouse position.
        Based on UniV's find_nearest_island() method.
        
        Args:
            isl: AdvIsland to check distance to
        """
        if not isl.faces:
            return
        
        # Calculate distance to island bbox
        bbox = isl.bbox
        if not bbox:
            return
        
        # Calculate distance from mouse to bbox center
        bbox_center = bbox.center
        distance = (self.mouse_pos - bbox_center).length
        
        # Check if within max distance
        if self.max_distance and distance > self.max_distance:
            return
        
        # Update if closer
        if distance < self.min_dist:
            self.min_dist = distance
            self.island = isl
    
    @staticmethod
    def closest_pt_to_selected_edge(island: AdvIsland, pt) -> float:
        """
        Calculate closest point to selected edge.
        Exact UniV implementation from IslandHit.closest_pt_to_selected_edge().
        """
        min_dist = float('inf')
        uv = island.umesh.uv
        for crn in island.calc_selected_edge_corners_iter():
            closest_pt = utils.closest_pt_to_line(pt, crn[uv].uv, crn.link_loop_next[uv].uv)
            min_dist = min(min_dist, (closest_pt - pt).length_squared)
        return min_dist

    def __bool__(self):
        """Return True if island was found"""
        return self.island is not None


class AdvIslands:
    """
    Collection of AdvIsland objects with management utilities.
    Based on UniV's AdvIslands class.
    """

    def __init__(self, umesh, islands: List[AdvIsland] = None):
        """
        Initialize AdvIslands.

        Args:
            umesh: UMesh object
            islands: List of AdvIsland objects
        """
        self.umesh = umesh
        self.islands = islands or []

    @staticmethod
    def island_filter_is_any_edge_selected(island_faces: List[BMFace], umesh) -> bool:
        """
        Check if island has any selected edges.
        Based on UniV's IslandsBase.island_filter_is_any_edge_selected().

        Args:
            island_faces: List of faces in the island
            umesh: UMesh object

        Returns:
            bool: True if island has any selected edges
        """
        if umesh.sync:
            # Sync mode: check mesh edge selection
            for face in island_faces:
                for edge in face.edges:
                    if edge.select:
                        return True
        else:
            # Non-sync mode: check UV edge selection
            uv = umesh.uv
            for face in island_faces:
                for loop in face.loops:
                    if loop[uv].select_edge:
                        return True
        return False

    @staticmethod
    def island_filter_is_any_face_selected(island_faces: List[BMFace], umesh) -> bool:
        """
        Check if island has any selected faces.
        Based on UniV's IslandsBase.island_filter_is_any_face_selected() (island.py:1324-1329).

        Args:
            island_faces: List of faces in the island
            umesh: UMesh object

        Returns:
            bool: True if island has any selected faces
        """
        if umesh.sync:
            # Sync mode: check if any face is selected
            return any(face.select for face in island_faces)
        else:
            # Non-sync mode: check if any face has all UV edges selected
            uv = umesh.uv
            return any(all(crn[uv].select_edge for crn in face.loops) for face in island_faces)
    
    def __len__(self):
        return len(self.islands)
    
    def __iter__(self):
        return iter(self.islands)
    
    def __getitem__(self, index):
        return self.islands[index]
    
    @classmethod
    def calc_extended_with_mark_seam(cls, umesh) -> 'AdvIslands':
        """
        Calculate extended islands with seam marking.
        Based on UniV's Islands.calc_extended_with_mark_seam() (island.py:1569-1578).

        EXACT COPY of UniV's implementation - uses tagging system.
        """
        if umesh.is_full_face_deselected:
            return cls(umesh)

        # Tag faces as visible first
        cls.tag_filter_visible(umesh)

        # Calculate islands from tagged faces, filtering by face selection
        if umesh.sync and umesh.is_full_face_deselected:
            islands = [AdvIsland(umesh, i) for i in cls.calc_with_markseam_iter_ex(umesh)]
        else:
            islands = [AdvIsland(umesh, i) for i in cls.calc_with_markseam_iter_ex(umesh)
                       if cls.island_filter_is_any_face_selected(i, umesh)]

        return cls(umesh, islands)
    
    @staticmethod
    def calc_with_markseam_iter_ex(umesh):
        """
        Calculate islands with seam marking using iteration.
        Based on UniV's IslandsBase.calc_with_markseam_iter_ex() (island.py:1412-1442).

        This is the EXACT UniV algorithm that respects face tags.
        """
        uv = umesh.uv
        island = []

        for face in umesh.bm.faces:
            if not face.tag:
                continue
            face.tag = False

            parts_of_island = [face]
            temp = []

            while parts_of_island:
                for f in parts_of_island:
                    for l in f.loops:
                        shared_crn = l.link_loop_radial_prev
                        ff = shared_crn.face
                        if not ff.tag:
                            continue
                        if l.edge.seam:  # Skip if seam
                            continue
                        # Check if UVs match (island connectivity)
                        if l[uv].uv == shared_crn.link_loop_next[uv].uv and l.link_loop_next[uv].uv == shared_crn[uv].uv:
                            temp.append(ff)
                            ff.tag = False

                island.extend(parts_of_island)
                parts_of_island = temp
                temp = []

            yield island
            island = []

    @staticmethod
    def tag_filter_visible(umesh):
        """
        Tag faces as visible based on sync mode.
        Based on UniV's IslandsBaseTagFilterPre.tag_filter_visible() (island.py:1290-1300).

        This is CRITICAL - it determines which faces are considered for islands.
        """
        if umesh.sync:
            for face in umesh.bm.faces:
                face.tag = not face.hide
        else:
            if umesh.is_full_face_selected:
                for face in umesh.bm.faces:
                    face.tag = True
            else:
                for face in umesh.bm.faces:
                    face.tag = face.select

    @classmethod
    def calc_visible_with_mark_seam(cls, umesh) -> 'AdvIslands':
        """
        Calculate visible islands with seam marking.
        Based on UniV's Islands.calc_visible_with_mark_seam() (island.py:1555-1558).

        EXACT COPY of UniV's implementation - uses tagging system instead of get_islands_non_manifold.
        """
        # Tag faces as visible first
        cls.tag_filter_visible(umesh)

        # Calculate islands from tagged faces
        islands = [AdvIsland(umesh, i) for i in cls.calc_with_markseam_iter_ex(umesh)]

        return cls(umesh, islands)
    
    def indexing(self, force=True):
        """
        Set face indices for island management.
        Based on UniV's indexing() method (island.py:1908-1922).

        Args:
            force: If True, reset all face indices first
        """
        if force:
            if sum(len(isl) for isl in self.islands) != len(self.umesh.bm.faces):
                for f in self.umesh.bm.faces:
                    f.index = -1
            for idx, island in enumerate(self.islands):
                for face in island:
                    face.index = idx
            return

        for idx, island in enumerate(self.islands):
            for face in island:
                face.tag = True
                face.index = idx
    
    def apply_aspect_ratio(self):
        """
        Apply aspect ratio to all islands in collection.
        Based on UniV's apply_aspect_ratio() method.
        """
        for island in self.islands:
            island.apply_aspect_ratio()
    
    def reset_aspect_ratio(self):
        """
        Reset aspect ratio for all islands in collection.
        Based on UniV's reset_aspect_ratio() method.
        """
        for island in self.islands:
            island.reset_aspect_ratio()
    
    @classmethod
    def calc_extended_any_elem_with_mark_seam(cls, umesh) -> 'AdvIslands':
        """
        Calculate extended islands for any element type with seam marking.
        Based on UniV's calc_extended_any_elem_with_mark_seam() method.
        
        Args:
            umesh: UMesh object
            
        Returns:
            AdvIslands: Collection of extended islands
        """
        # Get visible faces based on sync mode
        visible_faces = []
        if umesh.sync:
            # Sync mode: get ALL non-hidden faces
            for face in umesh.bm.faces:
                if not face.hide:
                    visible_faces.append(face)
        else:
            # Non-sync mode: get selected faces
            for face in umesh.bm.faces:
                if face.select:
                    visible_faces.append(face)
        
        if not visible_faces:
            return cls(umesh)
        
        # Calculate islands using non-manifold detection
        from ..utils.island_utils import get_islands_non_manifold
        island_faces_list = get_islands_non_manifold(umesh.bm, visible_faces, umesh.uv)
        
        # Create AdvIsland objects, filtering by any element selection
        islands = []
        for faces in island_faces_list:
            # Filter: only include islands with any selected elements
            has_selection = False
            if umesh.sync:
                if umesh.elem_mode == 'FACE':
                    has_selection = any(face.select for face in faces)
                elif umesh.elem_mode == 'VERT':
                    has_selection = any(v.select for face in faces for v in face.verts)
                else:  # EDGE
                    has_selection = any(e.select for face in faces for e in face.edges)
            else:
                uv = umesh.uv
                if umesh.elem_mode == 'VERT':
                    has_selection = any(crn[uv].select for face in faces for crn in face.loops)
                else:  # EDGE
                    has_selection = any(crn[uv].select_edge for face in faces for crn in face.loops)
            
            if has_selection:
                island = AdvIsland(umesh, faces)
                island.mark_seam()
                islands.append(island)
        
        return cls(umesh, islands)

    @classmethod
    def calc_extended_or_visible_with_mark_seam(cls, umesh, *, extended) -> 'AdvIslands':
        """Calculate extended or visible islands with mark seam based on extended parameter"""
        if extended:
            return cls.calc_extended_with_mark_seam(umesh)
        return cls.calc_visible_with_mark_seam(umesh)

    @classmethod
    def calc_extended_any_edge_with_markseam(cls, umesh) -> 'AdvIslands':
        """Calculate extended islands with any edge selection and mark seam"""
        return cls.calc_extended_any_elem_with_mark_seam(umesh)

    def calc_tris(self):
        """Calculate triangles for all islands"""
        if not self.islands:
            return False
        # Calculate triangles for each island
        for island in self.islands:
            island.calc_tris()
        return True

    def calc_flat_coords(self, save_triplet=False):
        """Calculate flat coordinates for all islands"""
        for island in self.islands:
            island.calc_flat_coords(save_triplet)

    def extend(self, other_islands):
        """Extend this collection with islands from another AdvIslands collection"""
        if hasattr(other_islands, 'islands'):
            self.islands.extend(other_islands.islands)
        else:
            self.islands.extend(other_islands)

