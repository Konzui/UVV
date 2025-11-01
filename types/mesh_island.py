# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

"""
MeshIsland and MeshIslands classes for 3D mesh island operations.
Based on UniV's implementation for relax functionality.
"""

import bmesh
from typing import List, Optional, Iterator
from bmesh.types import BMFace

from .adv_island import AdvIsland, AdvIslands
from .umesh import UMesh


class MeshIsland:
    """
    Represents a 3D mesh island - a collection of connected faces in 3D space.
    Based on UniV's MeshIsland class.
    """
    
    def __init__(self, umesh: UMesh, faces: List[BMFace] = None):
        """
        Initialize MeshIsland.
        
        Args:
            umesh: UMesh object containing bmesh and UV layer
            faces: List of BMFace objects in this island
        """
        self.umesh = umesh
        self.faces = faces or []
    
    def __len__(self):
        return len(self.faces)
    
    def __iter__(self):
        return iter(self.faces)
    
    def __getitem__(self, index):
        return self.faces[index]
    
    def __contains__(self, face):
        return face in self.faces
    
    def calc_adv_subislands(self) -> AdvIslands:
        """
        Calculate AdvIslands from this MeshIsland based on UV splits WITHOUT marking seams.
        Based on UniV's calc_adv_subislands_with_mark_seam() method but without seam marking.
        
        Returns:
            AdvIslands: Collection of AdvIsland objects split by UV seams
        """
        if not self.faces:
            return AdvIslands(self.umesh)
        
        # Create a temporary UMesh with only this island's faces
        temp_umesh = self.umesh.fake_umesh(self.faces)
        
        # Calculate islands using UV connectivity
        from ..utils.island_utils import get_islands_non_manifold
        island_faces_list = get_islands_non_manifold(temp_umesh.bm, self.faces, temp_umesh.uv)
        
        # Create AdvIsland objects WITHOUT marking seams
        adv_islands = []
        for faces in island_faces_list:
            island = AdvIsland(temp_umesh, faces)
            # Don't call mark_seam() here
            adv_islands.append(island)
        
        return AdvIslands(temp_umesh, adv_islands)

    def calc_adv_subislands_with_mark_seam(self) -> AdvIslands:
        """
        Calculate AdvIslands from this MeshIsland based on UV splits.
        Based on UniV's calc_adv_subislands_with_mark_seam() method.
        
        Returns:
            AdvIslands: Collection of AdvIsland objects split by UV seams
        """
        if not self.faces:
            return AdvIslands(self.umesh)
        
        # Create a temporary UMesh with only this island's faces
        temp_umesh = self.umesh.fake_umesh(self.faces)
        
        # Calculate islands using UV connectivity
        from ..utils.island_utils import get_islands_non_manifold
        island_faces_list = get_islands_non_manifold(temp_umesh.bm, self.faces, temp_umesh.uv)
        
        # Create AdvIsland objects
        adv_islands = []
        for faces in island_faces_list:
            island = AdvIsland(temp_umesh, faces)
            island.mark_seam()
            adv_islands.append(island)
        
        return AdvIslands(temp_umesh, adv_islands)
    
    def to_adv_island(self) -> AdvIsland:
        """
        Convert this MeshIsland to a single AdvIsland.
        
        Returns:
            AdvIsland: Single AdvIsland containing all faces
        """
        return AdvIsland(self.umesh, self.faces)


class MeshIslands:
    """
    Collection of MeshIsland objects with management utilities.
    Based on UniV's MeshIslands class.
    """
    
    def __init__(self, umesh: UMesh, islands: List[MeshIsland] = None):
        """
        Initialize MeshIslands.
        
        Args:
            umesh: UMesh object
            islands: List of MeshIsland objects
        """
        self.umesh = umesh
        self.islands = islands or []
    
    @staticmethod
    def calc_visible(umesh: UMesh) -> 'MeshIslands':
        """
        Calculate visible mesh islands.
        Based on UniV's calc_visible_with_mark_seam() method.
        
        Args:
            umesh: UMesh object
            
        Returns:
            MeshIslands: Collection of visible mesh islands
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
            return MeshIslands(umesh)
        
        # Calculate 3D mesh islands using face connectivity
        from ..utils.island_utils import get_3d_mesh_islands
        island_faces_list = get_3d_mesh_islands(umesh.bm, visible_faces)
        
        # Create MeshIsland objects
        islands = []
        for faces in island_faces_list:
            island = MeshIsland(umesh, faces)
            islands.append(island)
        
        return MeshIslands(umesh, islands)

    @staticmethod
    def calc_extended(umesh: UMesh) -> 'MeshIslands':
        """
        Calculate extended mesh islands.
        Based on UniV's calc_extended_with_mark_seam() method.
        
        Extended mode: Uses ALL visible faces, but filters to only islands with selected faces/edges.
        
        Args:
            umesh: UMesh object
            
        Returns:
            MeshIslands: Collection of extended mesh islands
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
            return MeshIslands(umesh)
        
        # Calculate 3D mesh islands using face connectivity
        from ..utils.island_utils import get_3d_mesh_islands
        island_faces_list = get_3d_mesh_islands(umesh.bm, visible_faces)
        
        # Filter to only islands with selected faces/edges
        filtered_islands = []
        for faces in island_faces_list:
            # Check if this island has any selected faces
            has_selected = False
            for face in faces:
                if face.select:
                    has_selected = True
                    break
            
            if has_selected:
                island = MeshIsland(umesh, faces)
                filtered_islands.append(island)
        
        return MeshIslands(umesh, filtered_islands)

    @staticmethod
    def calc_visible_with_mark_seam(umesh: UMesh) -> 'MeshIslands':
        """
        Calculate visible mesh islands with seam marking.
        Based on UniV's calc_visible_with_mark_seam() method.
        
        Args:
            umesh: UMesh object
            
        Returns:
            MeshIslands: Collection of visible mesh islands
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
            return MeshIslands(umesh)
        
        # Calculate 3D mesh islands using face connectivity
        from ..utils.island_utils import get_3d_mesh_islands
        island_faces_list = get_3d_mesh_islands(umesh.bm, visible_faces)
        
        # Create MeshIsland objects
        islands = []
        for faces in island_faces_list:
            island = MeshIsland(umesh, faces)
            islands.append(island)
        
        return MeshIslands(umesh, islands)
    
    @staticmethod
    def calc_extended_with_mark_seam(umesh: UMesh) -> 'MeshIslands':
        """
        Calculate extended mesh islands with seam marking.
        Based on UniV's calc_extended_with_mark_seam() method.
        
        Extended mode: Uses ALL visible faces, but filters to only islands with selected faces/edges.
        
        Args:
            umesh: UMesh object
            
        Returns:
            MeshIslands: Collection of extended mesh islands
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
            return MeshIslands(umesh)
        
        # Calculate 3D mesh islands using face connectivity
        from ..utils.island_utils import get_3d_mesh_islands
        island_faces_list = get_3d_mesh_islands(umesh.bm, visible_faces)
        
        # Filter: only include islands with at least one selected face
        islands = []
        for faces in island_faces_list:
            # Check if island has any selected faces
            has_selection = False
            if umesh.sync:
                has_selection = any(face.select for face in faces)
            else:
                uv = umesh.uv
                has_selection = any(all(crn[uv].select_edge for crn in face.loops) for face in faces)
            
            if has_selection:
                island = MeshIsland(umesh, faces)
                islands.append(island)
        
        return MeshIslands(umesh, islands)
    
    def to_adv_islands(self) -> AdvIslands:
        """
        Convert all MeshIslands to AdvIslands collection.
        
        Returns:
            AdvIslands: Collection of AdvIsland objects
        """
        all_adv_islands = []
        
        for mesh_island in self.islands:
            # Convert each mesh island to adv subislands
            adv_subislands = mesh_island.calc_adv_subislands_with_mark_seam()
            all_adv_islands.extend(adv_subislands.islands)
        
        return AdvIslands(self.umesh, all_adv_islands)
    
    def __len__(self):
        return len(self.islands)
    
    def __iter__(self):
        return iter(self.islands)
    
    def __getitem__(self, index):
        return self.islands[index]
