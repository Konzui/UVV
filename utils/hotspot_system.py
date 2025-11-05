# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Hotspot mapping system for intelligent trim assignment.
Inspired by ZenUV's hotspot mapping implementation.

This module provides data structures and algorithms for automatically
assigning UV islands to trim rectangles based on similarity matching.
"""

import bmesh
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any
from mathutils import Vector
from math import pi, sqrt


@dataclass
class BoundingBox2d:
    """2D bounding box with computed properties"""
    
    left: float = 0.0
    bottom: float = 0.0
    right: float = 1.0
    top: float = 1.0
    
    def __post_init__(self):
        """Calculate derived properties after initialization"""
        self.width = self.right - self.left
        self.height = self.top - self.bottom
        self.area = self.width * self.height
        self.center = Vector((self.left + self.width / 2, self.bottom + self.height / 2))
        
        # Aspect ratios
        if self.height > 0:
            self.aspect = self.width / self.height
            self.aspect_inverted = self.height / self.width
        else:
            self.aspect = 1.0
            self.aspect_inverted = 1.0
            
        # Orientation detection
        self.is_vertical = None
        if self.width > self.height * 1.1:  # 10% tolerance
            self.is_vertical = False  # Horizontal
        elif self.height > self.width * 1.1:
            self.is_vertical = True   # Vertical
        else:
            self.is_vertical = None  # Square-ish
    
    @classmethod
    def from_points(cls, points: List[Vector]) -> 'BoundingBox2d':
        """Create bounding box from list of UV points"""
        if not points:
            return cls()
            
        min_x = min(p.x for p in points)
        max_x = max(p.x for p in points)
        min_y = min(p.y for p in points)
        max_y = max(p.y for p in points)
        
        return cls(min_x, min_y, max_x, max_y)
    
    @classmethod
    def from_trim(cls, trim) -> 'BoundingBox2d':
        """Create bounding box from UVV_TrimRect"""
        return cls(trim.left, trim.bottom, trim.right, trim.top)
    
    def is_circle(self, tolerance: float = 0.1) -> bool:
        """Check if bounding box is roughly circular/square"""
        if self.width == 0 or self.height == 0:
            return False
        aspect_diff = abs(self.aspect - 1.0)
        return aspect_diff <= tolerance
    
    def get_longest_axis_vector(self) -> Vector:
        """Get vector representing the longest axis"""
        if self.width > self.height:
            return Vector((1.0, 0.0))
        else:
            return Vector((0.0, 1.0))


@dataclass
class HspTrim:
    """Hotspot trim wrapper with computed properties"""

    trim: Any = None  # UVV_TrimRect object
    bbox: BoundingBox2d = None
    aspect: float = None
    aspect_inverted: float = None
    _radial: bool = None
    _is_circle: bool = None

    def __post_init__(self):
        """Calculate properties after initialization"""
        if self.trim is not None:
            self.bbox = BoundingBox2d.from_trim(self.trim)
            self.aspect = self.bbox.aspect
            self.aspect_inverted = self.bbox.aspect_inverted
            # Check if trim is circular
            if hasattr(self.trim, 'shape_type'):
                self._is_circle = self.trim.shape_type == 'CIRCLE'
            else:
                self._is_circle = False

    def __hash__(self):
        """Make hashable for use in sets"""
        return hash(tuple(self.bbox.center))

    @property
    def is_circle(self) -> bool:
        """Check if trim is explicitly a circle shape"""
        if self._is_circle is None:
            if hasattr(self.trim, 'shape_type'):
                self._is_circle = self.trim.shape_type == 'CIRCLE'
            else:
                self._is_circle = False
        return self._is_circle

    @property
    def radial(self) -> bool:
        """Check if trim is circular (either explicit circle or tagged as radial)"""
        if self._radial is None:
            # First check explicit circle shape
            if self.is_circle:
                self._radial = True
            # Then check if trim has a tag property and if it contains "radial"
            elif hasattr(self.trim, 'tag') and self.trim.tag:
                self._radial = 'radial' in self.trim.tag.lower()
            else:
                self._radial = False
        return self._radial

    @property
    def area(self) -> float:
        """Get trim area"""
        return self.bbox.area if self.bbox else 0.0


@dataclass
class HspIsland:
    """Hotspot island wrapper with computed properties"""
    
    faces: List[Any] = field(default_factory=list)  # List of BMFace objects
    bbox: BoundingBox2d = None
    aspect: float = None
    aspect_inverted: float = None
    _radial: bool = None
    _loops: List[Any] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate properties after initialization"""
        # Don't calculate bbox here - it needs UV layer
        # Bbox will be calculated when _calculate_bbox_with_uv_layer is called
        pass
    
    def __hash__(self):
        """Make hashable for use in sets"""
        return hash(tuple(self.faces))
    
    @property
    def loops(self) -> List[Any]:
        """Get all loops from all faces"""
        if not self._loops and self.faces:
            self._loops = [loop for face in self.faces for loop in face.loops]
        return self._loops
    
    @property
    def radial(self) -> bool:
        """Check if island is roughly circular"""
        if self._radial is None:
            self._radial = self.bbox.is_circle() if self.bbox else False
        return self._radial
    
    @radial.setter
    def radial(self, value):
        """Prevent setting radial property"""
        raise RuntimeError('HspIsland.radial is read-only')
    
    @property
    def area(self) -> float:
        """Get island area"""
        return self.bbox.area if self.bbox else 0.0
    
    def _calculate_bbox(self):
        """Calculate bounding box from UV coordinates"""
        if not self.faces:
            self.bbox = BoundingBox2d()
            return
            
        # This method requires a UV layer to be passed
        # Use _calculate_bbox_with_uv_layer instead
        self.bbox = BoundingBox2d()
    
    def _calculate_bbox_with_uv_layer(self, uv_layer):
        """Calculate bounding box using provided UV layer"""
        if not self.faces or not uv_layer:
            self.bbox = BoundingBox2d()
            self.aspect = 1.0
            self.aspect_inverted = 1.0
            return
            
        uv_points = []
        
        try:
            for face in self.faces:
                for loop in face.loops:
                    uv_points.append(Vector(loop[uv_layer].uv))
            
            if uv_points:
                self.bbox = BoundingBox2d.from_points(uv_points)
                self.aspect = self.bbox.aspect
                self.aspect_inverted = self.bbox.aspect_inverted
            else:
                self.bbox = BoundingBox2d()
                self.aspect = 1.0
                self.aspect_inverted = 1.0
        except Exception as e:
            print(f"Error calculating bbox for island: {e}")
            self.bbox = BoundingBox2d()
            self.aspect = 1.0
            self.aspect_inverted = 1.0


class HspStorage:
    """Central manager for hotspot matching operations"""
    
    def __init__(self):
        self.trims: Set[HspTrim] = set()
        self.islands: Set[HspIsland] = set()
        
        self.radial_trims: Set[HspTrim] = set()
        self.radial_islands: Set[HspIsland] = set()
        
        self._trims_count = 0
        self._islands_count = 0
    
    @property
    def trims_count(self) -> int:
        """Get total number of trims"""
        self._trims_count = len(self.trims)
        return self._trims_count
    
    @property
    def islands_count(self) -> int:
        """Get total number of islands"""
        self._islands_count = len(self.islands) + len(self.radial_islands)
        return self._islands_count
    
    def collect_trims(self, trim_list: List[Any], detect_radial: bool = False, category_filter: str = "", tag_filter: str = "") -> None:
        """Collect trims from material and categorize them"""
        self.trims.clear()
        self.radial_trims.clear()
        
        print(f"Collecting trims from {len(trim_list)} trim objects")
        for i, trim in enumerate(trim_list):
            # Apply tag filtering
            if category_filter and hasattr(trim, 'category') and trim.category != category_filter:
                continue
            if tag_filter and hasattr(trim, 'tag') and tag_filter not in trim.tag.lower():
                continue
            
            hsp_trim = HspTrim(trim)
            self.trims.add(hsp_trim)
            print(f"  Trim {i+1}: aspect={hsp_trim.aspect:.3f}, area={hsp_trim.area:.3f}")
        
        if detect_radial:
            # Separate radial trims
            self.radial_trims = {trim for trim in self.trims if trim.radial}
            self.trims = self.trims.difference(self.radial_trims)
    
    def collect_islands(self, context, bm: bmesh.types.BMesh, uv_layer, detect_radial: bool = False) -> None:
        """Collect islands from bmesh and categorize them"""
        self.islands.clear()
        self.radial_islands.clear()
        
        # Use existing island collection system - try multiple approaches
        islands = []
        
        # Check sync mode and report
        uv_sync_mode = self._is_uv_sync_mode(bm, uv_layer)
        print(f"UV Sync Mode: {'Enabled' if uv_sync_mode else 'Disabled'}")
        
        try:
            # First try: Use zen_get_islands from island_utils
            from ..utils.island_utils import zen_get_islands
            
            # Get selected faces based on sync mode
            if self._is_uv_sync_mode(bm, uv_layer):
                selected_faces = [f for f in bm.faces if f.select]
                print(f"Using 3D view selection: {len(selected_faces)} faces")
            else:
                selected_faces = [f for f in bm.faces if self._is_face_selected_in_uv(f, uv_layer)]
                print(f"Using UV editor selection: {len(selected_faces)} faces")
            
            if selected_faces:
                islands = zen_get_islands(bm, selected_faces, has_selected_faces=True)
        except (ImportError, AttributeError, Exception) as e:
            print(f"zen_get_islands failed: {e}")
            # Fallback: Use AdvIslands system
            try:
                from ..types.adv_island import AdvIslands
                adv_islands = AdvIslands.calc_visible_with_mark_seam(bm, uv_layer)
                islands = [island.faces for island in adv_islands]
            except (ImportError, AttributeError, Exception) as e:
                print(f"AdvIslands failed: {e}")
                # Last resort: Simple island detection
                islands = self._simple_island_detection(bm, uv_layer)
        
        # Convert to HspIsland objects
        print(f"Found {len(islands)} islands to process")
        for i, island_faces in enumerate(islands):
            if island_faces:  # Skip empty islands
                print(f"Processing island {i+1} with {len(island_faces)} faces")
                hsp_island = HspIsland(list(island_faces))
                # Calculate bbox with UV layer
                hsp_island._calculate_bbox_with_uv_layer(uv_layer)
                if hsp_island.bbox and hsp_island.bbox.area > 0:
                    print(f"Island {i+1} bbox: {hsp_island.bbox.width:.3f}x{hsp_island.bbox.height:.3f}")
                    self.islands.add(hsp_island)
                else:
                    print(f"Island {i+1} has invalid bbox, skipping")
        
        if detect_radial:
            # Separate radial islands
            self.radial_islands = {island for island in self.islands if island.radial}
            self.islands = self.islands.difference(self.radial_islands)
    
    def _simple_island_detection(self, bm: bmesh.types.BMesh, uv_layer) -> List[List[Any]]:
        """Simple island detection as fallback"""
        islands = []
        processed_faces = set()
        
        # Check if we're in UV sync mode by looking at face selection vs UV selection
        uv_sync_mode = self._is_uv_sync_mode(bm, uv_layer)
        
        for face in bm.faces:
            # Use appropriate selection method based on sync mode
            if uv_sync_mode:
                is_selected = face.select
            else:
                is_selected = self._is_face_selected_in_uv(face, uv_layer)
            
            if is_selected and face not in processed_faces:
                island_faces = []
                faces_to_check = [face]
                
                while faces_to_check:
                    current_face = faces_to_check.pop()
                    if current_face in processed_faces:
                        continue
                    
                    island_faces.append(current_face)
                    processed_faces.add(current_face)
                    
                    # Find connected faces
                    for edge in current_face.edges:
                        if not edge.seam:  # Not a seam
                            for linked_face in edge.link_faces:
                                # Use appropriate selection method for linked faces too
                                if uv_sync_mode:
                                    linked_selected = linked_face.select
                                else:
                                    linked_selected = self._is_face_selected_in_uv(linked_face, uv_layer)
                                
                                if linked_selected and linked_face not in processed_faces:
                                    faces_to_check.append(linked_face)
                
                if island_faces:
                    islands.append(island_faces)
        
        return islands
    
    def _is_uv_sync_mode(self, bm: bmesh.types.BMesh, uv_layer) -> bool:
        """Check if we're in UV sync mode by comparing face selection with UV selection"""
        if not uv_layer:
            return True  # Default to sync mode if no UV layer
        
        # Sample a few faces to check if selection matches
        face_selection_count = 0
        uv_selection_count = 0
        
        for face in bm.faces:
            if face.select:
                face_selection_count += 1
                
                # Check if any loop of this face is selected in UV
                for loop in face.loops:
                    try:
                        if loop[uv_layer].select:
                            uv_selection_count += 1
                            break
                    except (KeyError, AttributeError):
                        continue
        
        # If UV selection count is significantly different from face selection count,
        # we're likely not in sync mode
        return abs(face_selection_count - uv_selection_count) <= 1
    
    def _is_face_selected_in_uv(self, face, uv_layer) -> bool:
        """Check if a face is selected in the UV editor"""
        if not uv_layer:
            return face.select  # Fallback to face selection
        
        # A face is selected in UV if any of its loops are selected
        for loop in face.loops:
            try:
                if loop[uv_layer].select:
                    return True
            except (KeyError, AttributeError):
                continue
        
        return False
    
    def get_aspect_suited_trims(self, container: Set[HspTrim], aspect: float, allow_rotation: bool, tolerance: float = 0.1, aspect_precision: float = 0.0) -> List[HspTrim]:
        """Find trims with similar aspect ratios"""
        suited_trims = []
        
        # Apply aspect precision correction
        if aspect is None:
            print(f"Warning: Island aspect is None, using default 1.0")
            aspect = 1.0
        corrected_aspect = aspect + aspect_precision
        
        # Adaptive tolerance: higher tolerance for extreme aspect ratios
        adaptive_tolerance = tolerance
        if corrected_aspect > 5.0 or corrected_aspect < 0.2:  # Very wide or very tall
            adaptive_tolerance = max(tolerance, corrected_aspect * 0.2)  # 20% of aspect ratio
        elif corrected_aspect > 1.5 or corrected_aspect < 0.7:  # Wide or tall
            adaptive_tolerance = max(tolerance, corrected_aspect * 0.3)  # 30% of aspect ratio
        
        print(f"Looking for trims with aspect {corrected_aspect:.3f} (original: {aspect:.3f}, precision: {aspect_precision:.3f})")
        print(f"Using tolerance: {adaptive_tolerance:.3f} (base: {tolerance:.3f})")
        
        for trim in container:
            # Check normal orientation
            aspect_diff = abs(trim.aspect - corrected_aspect)
            if aspect_diff <= adaptive_tolerance:
                suited_trims.append(trim)
                print(f"  Found trim with aspect {trim.aspect:.3f} (diff: {aspect_diff:.3f})")
                continue
            
            # Check rotated orientation if allowed
            if allow_rotation:
                aspect_diff_rotated = abs(trim.aspect_inverted - corrected_aspect)
                if aspect_diff_rotated <= adaptive_tolerance:
                    suited_trims.append(trim)
                    print(f"  Found rotated trim with aspect {trim.aspect_inverted:.3f} (diff: {aspect_diff_rotated:.3f})")
        
        print(f"Found {len(suited_trims)} aspect-suited trims out of {len(container)} total trims")
        return suited_trims
    
    def get_area_suited_trims(self, container: List[HspTrim], island: HspIsland, scalar: float, allow_rotation: bool) -> List[HspTrim]:
        """Find trims with similar areas"""
        if not container:
            return []
        
        # Calculate target area
        island_area = island.area if island.area is not None else 0.0
        target_area = island_area * scalar
        print(f"  Area matching: island area={island_area:.3f}, scalar={scalar:.3f}, target={target_area:.3f}")
        
        # Calculate area differences
        area_diffs = []
        for trim in container:
            area_diff = abs(trim.area - target_area)
            area_diffs.append((area_diff, trim))
            print(f"    Trim area={trim.area:.3f}, diff={area_diff:.3f}")
        
        # Sort by area difference and return trims within reasonable range
        area_diffs.sort(key=lambda x: x[0])
        
        # Return trims within 50% of the best match
        if not area_diffs:
            return []
        
        best_diff = area_diffs[0][0]
        max_diff = best_diff * 1.5  # 50% tolerance
        print(f"  Best area diff: {best_diff:.3f}, max allowed: {max_diff:.3f}")
        
        suited_trims = [trim for diff, trim in area_diffs if diff <= max_diff]
        print(f"  Found {len(suited_trims)} area-suited trims out of {len(container)} aspect-suited trims")
        return suited_trims
        
    def get_world_size_suited_trims(self, context, container: List[HspTrim], island: HspIsland, scalar: float, allow_rotation: bool) -> List[HspTrim]:
        """Find trims with similar world size (real-world dimensions)"""
        if not container:
            return []
        
        # Calculate island world area (sum of face areas in 3D)
        island_world_area = 0.0
        for face in island.faces:
            island_world_area += face.calc_area()
        
        target_world_area = island_world_area * scalar
        
        # Calculate world area differences
        world_area_diffs = []
        for trim in container:
            trim_world_area = self._get_trim_world_area(trim)
            if trim_world_area is not None:
                area_diff = abs(trim_world_area - target_world_area)
                world_area_diffs.append((area_diff, trim))
        
        if not world_area_diffs:
            return []
        
        # Sort by world area difference
        world_area_diffs.sort(key=lambda x: x[0])
        
        # Return trims within reasonable range
        best_diff = world_area_diffs[0][0]
        max_diff = best_diff * 2.0  # 100% tolerance for world size
        
        suited_trims = [trim for diff, trim in world_area_diffs if diff <= max_diff]
        return suited_trims
    
    def _get_trim_world_area(self, trim: HspTrim) -> Optional[float]:
        """Get world area for trim if available"""
        # Check if trim has world size properties
        if hasattr(trim.trim, 'world_size_x') and hasattr(trim.trim, 'world_size_y'):
            if trim.trim.world_size_x > 0 and trim.trim.world_size_y > 0:
                return trim.trim.world_size_x * trim.trim.world_size_y
        
        # Check for alternative world size properties
        if hasattr(trim.trim, 'world_size') and len(trim.trim.world_size) >= 2:
            if trim.trim.world_size[0] > 0 and trim.trim.world_size[1] > 0:
                return trim.trim.world_size[0] * trim.trim.world_size[1]
        
        return None
        
    def get_trims_by_world_size_priority(self, context, island: HspIsland, scalar: float, allow_rotation: bool, tolerance: float = 0.1) -> List[HspTrim]:
        """Two-stage filtering: world size first, then aspect"""
        # Stage 1: Filter by world size
        world_size_suited_trims = self.get_world_size_suited_trims(context, list(self.trims), island, scalar, allow_rotation)
        
        # Stage 2: Filter by aspect from world-size-matched trims
        return self.get_aspect_suited_trims(set(world_size_suited_trims), island.aspect, allow_rotation, tolerance)
    
    def get_trims_by_aspect_priority(self, island: HspIsland, scalar: float, allow_rotation: bool, tolerance: float = 0.1, aspect_precision: float = 0.0) -> List[HspTrim]:
        """Two-stage filtering: aspect first, then area"""
        # Stage 1: Filter by aspect ratio
        aspect_suited_trims = self.get_aspect_suited_trims(self.trims, island.aspect, allow_rotation, tolerance, aspect_precision)
        
        # Stage 2: Filter by area from aspect-matched trims
        return self.get_area_suited_trims(aspect_suited_trims, island, scalar, allow_rotation)
    
    def get_trims_by_area_priority(self, island: HspIsland, scalar: float, allow_rotation: bool, tolerance: float = 0.1) -> List[HspTrim]:
        """Two-stage filtering: area first, then aspect"""
        # Stage 1: Filter by area
        area_suited_trims = self.get_area_suited_trims(list(self.trims), island, scalar, allow_rotation)
        
        # Stage 2: Filter by aspect from area-matched trims
        return self.get_aspect_suited_trims(set(area_suited_trims), island.aspect, allow_rotation, tolerance)
    
    def calculate_rotation_angle(self, island: HspIsland, trim: HspTrim, allow_rotation: bool) -> float:
        """Calculate rotation angle needed to match island to trim"""
        if not allow_rotation:
            return 0.0
        
        # Check if orientations match
        island_vertical = island.bbox.is_vertical
        trim_vertical = trim.bbox.is_vertical
        
        # If orientations don't match, rotate 90 degrees
        if island_vertical != trim_vertical:
            return pi / 2  # 90 degrees
        
        return 0.0
    
    def update_islands(self, uv_layer) -> None:
        """Recalculate island properties after UV changes"""
        for island in self.islands:
            island._calculate_bbox()
        for island in self.radial_islands:
            island._calculate_bbox()
