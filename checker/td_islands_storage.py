""" UVV TD Islands Storage - Zen UV Architecture """

import bpy
from dataclasses import dataclass, field
from mathutils import Color


@dataclass
class TdIsland:
    """Storage for single island texel density data"""

    index: int = -1
    name: str = 'TdIsland'
    indices: list = field(default_factory=list)  # Face indices in this island
    obj_name: str = None
    td: float = 0.0  # Texel density value
    color: Color = field(default_factory=lambda: Color((0.0, 0.0, 0.0)))
    is_fake: bool = False  # For reference values in gradient
    color_ref_point: bool = False

    def __hash__(self):
        return hash(self.td)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.td == other.td


class TdReferencedManager:
    """Manage reference values for gradient display"""

    def __init__(self) -> None:
        self.ref_td: list = []
        self.ref_colors: list = []

    def append_color_scheme_reference_values(self, colors: list, td_min: float, td_max: float):
        """Add color scheme reference points for gradient"""
        # Generate evenly spaced TD values across range
        if len(colors) > 1:
            step = (td_max - td_min) / (len(colors) - 1)
            p_r_td_values = [td_min + i * step for i in range(len(colors))]
        else:
            p_r_td_values = [(td_min + td_max) / 2]

        for td, col in zip(p_r_td_values, colors):
            self.append_reference(td=td, color=col, color_ref_point=True)

    def append_reference(self, td: float, color, color_ref_point: bool = False) -> None:
        """Add a reference point"""
        self.islands.append(TdIsland(td=td, color=color, is_fake=True, color_ref_point=color_ref_point))
        self.sort()

    def remove_referenced_items(self) -> None:
        """Remove fake reference items"""
        self.islands = [i for i in self.islands if i.is_fake is False]

    def get_referenced_values_for_gradient(self, td_inputs) -> tuple:
        """Get TD values and colors for gradient display"""
        p_islands = [i for i in self.islands if i.is_fake]
        p_islands = sorted(p_islands, key=lambda island: island.td)
        return [round(i.td, td_inputs.round_value) for i in p_islands], [i.color for i in p_islands]


class TdIslandsStorage(TdReferencedManager):
    """Storage for all island TD data"""

    def __init__(self) -> None:
        super().__init__()
        self.islands: list = []

    def is_empty(self) -> bool:
        return not len(self.islands)

    def clear(self) -> None:
        self.islands.clear()

    def append(self, island: TdIsland) -> None:
        island.td = round(island.td, 2)
        self.islands.append(island)

    def get(self) -> list:
        return self.islands

    def get_colors(self, include_fake=False):
        """Get all colors"""
        self.sort()
        if include_fake:
            return [i.color for i in self.islands]
        else:
            return [i.color for i in self.islands if not i.is_fake]

    def reset_colors(self):
        """Reset all colors to black"""
        for i in self.islands:
            i.color = Color((0.0, 0.0, 0.0))

    def set_color(self, color):
        """Set same color for all islands"""
        for i in self.islands:
            i.color = color

    def get_max_td_value(self) -> float:
        return max([i.td for i in self.islands]) if self.islands else 0.0

    def get_min_td_value(self) -> float:
        return min([i.td for i in self.islands]) if self.islands else 0.0

    def is_td_uniform(self):
        """Check if all islands have same TD"""
        return self.get_min_td_value() == self.get_max_td_value()

    def get_all_td_values(self, include_fake=False) -> list:
        """Get all TD values"""
        if include_fake:
            return sorted(round(i.td, 2) for i in self.islands)
        else:
            return sorted(round(i.td, 2) for i in self.islands if not i.is_fake)

    def get_sorted_islands(self) -> list:
        return sorted(self.islands, key=lambda island: island.td)

    def get_sorted_td_values(self, rounded: bool = True) -> list:
        if not len(self.islands):
            return [0.0]
        if rounded:
            return [round(v, 2) for v in self.get_all_td_values()]
        else:
            return self.get_all_td_values()

    def get_islands_by_objects(self) -> dict:
        """Group islands by object name"""
        p_output = dict()
        for p_obj_name in {i.obj_name for i in self.islands}:
            if p_obj_name is None:
                continue
            p_output[p_obj_name] = [island for island in self.islands if island.obj_name == p_obj_name]
        return p_output

    def get_island_by_value(self, value, method: str = 'EXACT'):
        """
        Get island by TD value
        method: in {'EXACT', 'NEAR'}
        """
        if method == 'EXACT':
            return next((i for i in self.islands if i.td == value), None)
        elif method == 'NEAR':
            return min(self.islands, key=lambda island: abs(island.td - value))

    def sort(self) -> None:
        """Sort islands by TD value"""
        self.islands = self.get_sorted_islands()

    def get_islands_in_td_range(self, td_min, td_max) -> list:
        """Get islands within TD range"""
        self.sort()
        return [i for i in self.islands if td_min <= i.td <= td_max]

    def _fill_fake_values(self):
        """Add fake values for empty scopes (gradient needs at least some data)"""
        for p_td in [0.0, 0.5, 1.0]:
            self.islands.append(TdIsland(td=p_td, is_fake=True))


@dataclass
class TdPreset:
    """Single TD Preset with value and color"""

    index: int = -1
    td: float = 0.0
    color: Color = field(default_factory=lambda: Color((0.0, 0.0, 0.0)))
    is_fake: bool = False

    def __str__(self):
        return f'\nTdPreset\n{self.index} -> {self.td} -> {self.color}'


class TdPresetsStorage:
    """
    Storage for TD presets (ZenUV compatibility)
    Uses Blender scene property 'uvv_td_presets' as data source
    """

    presets: list = []

    @classmethod
    def show(cls):
        """Debug: print all presets"""
        print('\nTdPresetsStorage State:\n')
        for i in cls.presets:
            print(i)

    @classmethod
    def is_empty(cls):
        """Check if no presets exist"""
        return len(cls.presets) == 0

    @classmethod
    def clear(cls) -> None:
        """Clear all presets"""
        cls.presets.clear()

    @classmethod
    def append(cls, preset: TdPreset) -> None:
        """Add a preset"""
        cls.presets.append(preset)

    @classmethod
    def get_all_td_values(cls) -> list:
        """Get all preset TD values, sorted"""
        cls.sort()
        return sorted(i.td for i in cls.presets)

    @classmethod
    def sort(cls) -> None:
        """Sort presets by TD value"""
        cls.presets = cls.get_sorted_presets()

    @classmethod
    def get_sorted_presets(cls) -> list:
        """Get presets sorted by TD value"""
        return sorted(cls.presets, key=lambda preset: preset.td)

    @classmethod
    def get_colors(cls):
        """Get all preset colors, sorted by TD"""
        cls.sort()
        return [i.color for i in cls.presets]

    @classmethod
    def append_reference(cls, td: float):
        """Add a fake reference preset"""
        cls.presets.append(TdPreset(td=td, is_fake=True))
        cls.sort()

    @classmethod
    def remove_referenced_items(cls):
        """Remove fake reference presets"""
        cls.presets = [pr for pr in cls.presets if pr.is_fake is False]

    @classmethod
    def collect_presets(cls, context: bpy.types.Context) -> bool:
        """
        Collect presets from scene property
        Returns True if presets were collected, False if none exist
        """
        if len(context.scene.uvv_td_presets) == 0:
            return False
        else:
            cls.clear()
            for pr in context.scene.uvv_td_presets:
                cls.append(
                    TdPreset(
                        index=-1,
                        td=round(pr.value, 2),
                        color=Color(pr.display_color)))
            return True

    @classmethod
    def get_presets_td_range(cls):
        """Get min/max TD range from presets"""
        p_full = [p.td for p in cls.presets]
        if not p_full:
            return 0.0, 0.0
        return min(p_full), max(p_full)


class IslandSize:
    """Placeholder for island size (for future use)"""
    pass


def register():
    pass


def unregister():
    pass
