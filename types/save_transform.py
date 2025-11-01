# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

"""
SaveTransform class for preserving island transform state.
Based on UniV's SaveTransform implementation for relax functionality.

"""

import bmesh
from mathutils import Vector
from typing import List, Optional, Union
from bmesh.types import BMLoop

from .adv_island import AdvIsland, AdvIslands
from .mesh_island import MeshIsland, MeshIslands

print("DEBUG: save_transform.py imported")

class SaveTransform:
    print("DEBUG: SaveTransform class definition started")
    """
    Stores island transform state for restoration after operations.
    Based on UniV's SaveTransform class.
    """
    
    def __init__(self, island: Union[AdvIsland, AdvIslands, MeshIsland, MeshIslands]):
        """
        Initialize SaveTransform.
        Based on UniV's SaveTransform.__init__() method.
        
        Args:
            island: Island or collection of islands to save transform for
        """
        self.island = island
        self.old_crn_pos: List[Union[Vector, float]] = []  # For mix coords
        self.is_full_selected = False
        self.target_crn: Optional[BMLoop] = None
        self.old_coords: List[Vector] = [Vector((0, 0)), Vector((0, 0))]
        self.rotate = True
        
        # Only set target_subisland for collections (AdvIslands), not single islands
        if isinstance(island, AdvIslands):
            # For AdvIslands collections, find the largest subisland
            self.target_subisland = max((i for i in self.island), key=lambda i: i.bbox.area)
            self.calc_target_rotate_corner()
            self.bbox = self.target_subisland.bbox
        else:
            # For single islands (AdvIsland, MeshIsland, MeshIslands), don't set target_subisland
            self.calc_target_rotate_corner()
            self.bbox = self.island.calc_bbox()
    
    def calc_target_rotate_corner(self):
        """
        Calculate target corner for rotation.
        Based on UniV's calc_target_rotate_corner() method.
        """
        uv = self.island.umesh.uv
        if isinstance(self.island, AdvIslands):
            corners = []
            pinned_corners = []
            for isl in self.island:
                corners_, pinned_corners_ = self.calc_static_corners(isl, uv)
                corners.extend(corners_)
                pinned_corners.extend(pinned_corners_)
        else:
            corners, pinned_corners = self.calc_static_corners(self.island, uv)
        
        if corners or pinned_corners:
            # Based on the static corners, determine whether to rotate and scale
            # If there are at least two non-overlapping corners, don't rotate
            import itertools
            corners_iter = itertools.chain(corners, pinned_corners)
            co = next(corners_iter)[uv].uv
            for crn_ in corners_iter:
                if co != crn_[uv].uv:
                    self.rotate = False
                    break
            
            if self.rotate:
                max_length = -1.0
                max_length_crn = None
                for crn_ in itertools.chain(corners, pinned_corners):
                    if max_length < (new_length := (crn_[uv].uv - crn_.link_loop_next[uv].uv).length_squared):
                        max_length = new_length
                        max_length_crn = crn_
                
                self.target_crn = max_length_crn
                self.old_coords = [max_length_crn[uv].uv.copy(), max_length_crn.link_loop_next[uv].uv.copy()]
        else:
            self.is_full_selected = True
            if isinstance(self.island, AdvIslands):
                max_uv_area_face = self.target_subisland.calc_max_uv_area_face()
            else:
                max_uv_area_face = self.island.calc_max_uv_area_face()
            
            # Find corner with maximum length
            from .. import utils
            max_length_crn = utils.calc_max_length_uv_crn(max_uv_area_face.loops, uv)
            max_length_crn[uv].pin_uv = True
            self.target_crn = max_length_crn
            self.old_coords = [max_length_crn[uv].uv.copy(), max_length_crn.link_loop_next[uv].uv.copy()]
    
    @staticmethod
    def calc_static_corners(island, uv) -> tuple[List[BMLoop], List[BMLoop]]:
        """
        Calculate static corners for the island.
        Based on UniV's calc_static_corners() method.
        
        Args:
            island: Island to calculate corners for
            uv: UV layer
            
        Returns:
            Tuple of (corners, pinned_corners) lists
        """
        corners = []
        pinned_corners = []
        
        if island.umesh.sync:
            if island.umesh.elem_mode == 'FACE':
                for f in island:
                    if f.select:
                        for crn in f.loops:
                            if crn[uv].pin_uv:
                                pinned_corners.append(crn)
                    else:
                        for crn in f.loops:
                            crn_uv = crn[uv]
                            if crn_uv.pin_uv:
                                pinned_corners.append(crn)
                            else:
                                corners.append(crn)
            elif island.umesh.elem_mode == 'EDGE':
                for f in island:
                    for crn in f.loops:
                        crn_uv = crn[uv]
                        if not crn.edge.select:
                            corners.append(crn)
                        elif crn_uv.pin_uv:
                            pinned_corners.append(crn)
            else:  # VERTS
                for f in island:
                    for crn in f.loops:
                        crn_uv = crn[uv]
                        if not crn.vert.select:
                            corners.append(crn)
                        elif crn_uv.pin_uv:
                            pinned_corners.append(crn)
        else:
            for f in island:
                for crn in f.loops:
                    crn_uv = crn[uv]
                    if not crn_uv.select:
                        corners.append(crn)
                    elif crn_uv.pin_uv:
                        pinned_corners.append(crn)
        
        return corners, pinned_corners
    
    def inplace(self, axis: str = 'BOTH'):
        """
        Restore island position and scale in place.
        Based on UniV's inplace() method.
        
        Args:
            axis: Axis to restore ('BOTH', 'X', 'Y')
        """
        if not self.rotate:
            return
        
        uv = self.island.umesh.uv
        
        crn_co = self.target_crn[uv].uv if self.target_crn else Vector((0.0, 0.0))
        crn_next_co = self.target_crn.link_loop_next[uv].uv if self.target_crn else Vector((0.0, 0.0))
        
        old_dir = self.old_coords[0] - self.old_coords[1]
        new_dir = crn_co - crn_next_co
        
        def set_texel():
            """Set texel density for the island."""
            self.island.calc_area_uv()
            self.island.calc_area_3d(scale=self.island.umesh.value)
            # Use default texel settings
            texel = 512.0  # Default texel density
            texture_size = 1024.0  # Default texture size
            if hasattr(self.island, 'set_texel'):
                self.island.set_texel(texel, texture_size)
        
        if self.bbox.max_length < 2e-05:  # Small and zero area island protection
            new_bbox = self.island.calc_bbox()
            pivot = new_bbox.center
            if new_bbox.max_length != 0:
                self.island.rotate(old_dir.angle_signed(new_dir, 0), pivot)
                if hasattr(self.island, 'calc_area_uv'):
                    set_texel()
                else:
                    scale = 0.15 / new_bbox.max_length
                    self.island.scale(Vector((scale, scale)), pivot)
            
            self.island.set_position(self.bbox.center, pivot)
        else:
            if angle := old_dir.angle_signed(new_dir, 0):
                self.island.rotate(-angle, pivot=self.target_crn[uv].uv)
            new_bbox = self.island.calc_bbox()
            
            old_center = self.bbox.center
            new_center = new_bbox.center
            
            if axis == 'BOTH':
                if self.bbox.width > self.bbox.height:
                    if new_bbox.width:
                        scale = self.bbox.width / new_bbox.width
                        self.island.scale(Vector((scale, scale)), new_bbox.center)
                    else:
                        set_texel()
                else:
                    if new_bbox.height:
                        scale = self.bbox.height / new_bbox.height
                        self.island.scale(Vector((scale, scale)), new_bbox.center)
                    else:
                        set_texel()
                self.island.set_position(old_center, new_center)
            else:
                if axis == 'X':
                    if new_bbox.height:
                        scale = self.bbox.height / new_bbox.height
                        self.island.scale(Vector((scale, scale)), new_bbox.center)
                    else:
                        set_texel()
                else:
                    if new_bbox.width:
                        scale = self.bbox.width / new_bbox.width
                        self.island.scale(Vector((scale, scale)), new_bbox.center)
                    else:
                        set_texel()
                self.island.set_position(old_center, new_center)
        
        if self.is_full_selected:
            self.target_crn[uv].pin_uv = False
    
    def inplace_mesh_island(self):
        """
        Restore mesh island position and scale in place.
        Based on UniV's inplace_mesh_island() method.
        """
        if not self.rotate:
            return
        
        uv = self.island.umesh.uv
        
        crn_co = self.target_crn[uv].uv if self.target_crn else Vector((0.0, 0.0))
        crn_next_co = self.target_crn.link_loop_next[uv].uv if self.target_crn else Vector((0.0, 0.0))
        
        old_dir = self.old_coords[0] - self.old_coords[1]
        new_dir = crn_co - crn_next_co
        
        def set_texel():
            """Set texel density for the mesh island."""
            self.island.calc_area_uv()
            self.island.calc_area_3d(scale=self.island.umesh.value)
            # Use default texel settings
            texel = 512.0  # Default texel density
            texture_size = 1024.0  # Default texture size
            if isinstance(self.island, AdvIslands):
                from .island import UnionIslands
                union_islands = UnionIslands(self.island.islands)
                union_islands.set_texel(texel, texture_size)
        
        # For AdvIslands, use target_subisland; for single islands, use island itself
        if isinstance(self.island, AdvIslands):
            calc_bbox_target = self.target_subisland
        else:
            calc_bbox_target = self.island
        
        if self.bbox.max_length < 2e-05:  # Small and zero area island protection
            new_bbox = calc_bbox_target.calc_bbox()
            pivot = new_bbox.center
            if new_bbox.max_length != 0:
                self.island.rotate(old_dir.angle_signed(new_dir, 0), pivot)
                set_texel()
            self.island.set_position(self.bbox.center, pivot)
        else:
            if angle := old_dir.angle_signed(new_dir, 0):
                self.island.rotate(-angle, pivot=self.target_crn[uv].uv)
            new_bbox = calc_bbox_target.calc_bbox()
            
            old_center = self.bbox.center
            new_center = new_bbox.center
            
            if self.bbox.width > self.bbox.height:
                if new_bbox.width:
                    scale = self.bbox.width / new_bbox.width
                    self.island.scale(Vector((scale, scale)), new_bbox.center)
                else:
                    set_texel()
            else:
                if new_bbox.height:
                    scale = self.bbox.height / new_bbox.height
                    self.island.scale(Vector((scale, scale)), new_bbox.center)
                else:
                    set_texel()
            self.island.set_position(old_center, new_center)
        
        if self.is_full_selected:
            self.target_crn[uv].pin_uv = False
    
    def save_coords(self, axis: str, mix: float):
        """
        Save coordinates for blending.
        Based on UniV's save_coords() method.
        
        Args:
            axis: Axis to save ('X', 'Y', 'BOTH')
            mix: Mix factor (0-1)
        """
        if mix == 1:
            return
        
        uv = self.island.umesh.uv
        if axis == 'X':
            self.old_crn_pos = [crn[uv].uv.x for f in self.island for crn in f.loops]
        elif axis == 'Y':
            self.old_crn_pos = [crn[uv].uv.y for f in self.island for crn in f.loops]
        else:
            self.old_crn_pos = [crn[uv].uv.copy() for f in self.island for crn in f.loops]
    
    def apply_saved_coords(self, axis: str, mix: float):
        """
        Apply saved coordinates with blending.
        Based on UniV's apply_saved_coords() method.
        
        Args:
            axis: Axis to apply ('X', 'Y', 'BOTH')
            mix: Mix factor (0-1)
        """
        uv = self.island.umesh.uv
        corners = (crn[uv].uv for f in self.island for crn in f.loops)
        
        if axis == 'BOTH':
            if mix == 1:
                return
            if mix == 0:
                for crn_uv, old_co in zip(corners, self.old_crn_pos):
                    crn_uv.xy = old_co
            else:
                for crn_uv, old_co in zip(corners, self.old_crn_pos):
                    crn_uv[:] = old_co.lerp(crn_uv, mix)
            return
        
        if mix == 1:
            if axis == 'X':
                for crn_uv, old_co in zip(corners, self.old_crn_pos):
                    crn_uv.x = old_co
            else:
                for crn_uv, old_co in zip(corners, self.old_crn_pos):
                    crn_uv.y = old_co
        else:
            from bl_math import lerp
            if axis == 'X':
                for crn_uv, old_co in zip(corners, self.old_crn_pos):
                    crn_uv.x = lerp(old_co, crn_uv.x, mix)
            else:
                for crn_uv, old_co in zip(corners, self.old_crn_pos):
                    crn_uv.y = lerp(old_co, crn_uv.y, mix)
