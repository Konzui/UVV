""" UVV Texel Density Display Utilities - Complete Zen UV 1:1 Copy """

import bpy
from dataclasses import dataclass
from mathutils import Color

from .td_utils import TdContext
from .td_islands_storage import TdIslandsStorage, TdPresetsStorage


class TdColorManager:
    """Color scheme manager - Zen UV pattern"""

    color_scheme_names = {
        "USER_THREE",
        "FULL_SPEC",
        "REVERSED_SPEC",
        "USER_LINEAR",
        "MONO"
    }

    black = [0.0, 0.0, 0.0]
    white = [1.0, 1.0, 1.0]

    # Full spectrum (blue high density → red low density)
    full: list = [
        (0.0, 0.0, 1.0),      # Blue (highest)
        (0.0, 0.5, 1.0),      # Light blue
        (0.0, 1.0, 1.0),      # Cyan
        (0.5, 1.0, 0.5),      # Light green
        (1.0, 1.0, 0.0),      # Yellow
        (1.0, 0.5, 0.0),      # Orange
        (1.0, 0.0, 0.0),      # Red (lowest)
    ]

    mono = [
        (0.0, 0.0, 0.0),
        (0.5, 0.5, 0.5),
        (0.9, 0.9, 0.9)
    ]

    three_default = [
        (0.0, 0.0, 1.0),  # Under (blue)
        (0.0, 1.0, 0.0),  # Equal (green)
        (1.0, 0.0, 0.0)   # Over (red)
    ]

    alert_purple = (1.0, 0.0, 1.0)
    alert_green = (0.0, 1.0, 0.0)

    @classmethod
    def get_mid_color(cls, context: bpy.types.Context, color_scheme_name: str) -> list:
        """Get middle color for given scheme"""
        if color_scheme_name == "USER_THREE":
            return cls.get_user_equal(context)
        elif color_scheme_name == "FULL_SPEC":
            return cls.full[3]
        elif color_scheme_name == "REVERSED_SPEC":
            return cls.full[3]
        elif color_scheme_name == "USER_LINEAR":
            return cls.get_user_linear(context)[1]
        elif color_scheme_name == "MONO":
            return cls.mono[1]
        else:
            return cls.full[3]

    @classmethod
    def get_middle_color(cls, color_01: Color, color_02: Color) -> Color:
        """Calculate middle color between two colors"""
        return ((Color(color_01) + Color(color_02)) * 0.5)[:]

    @classmethod
    def get_user_three(cls, context: bpy.types.Context) -> list:
        """Get user-defined three color scheme"""
        settings = context.scene.uvv_settings
        return [
            settings.td_color_under[:],
            settings.td_color_equal[:],
            settings.td_color_over[:]
        ]

    @classmethod
    def get_user_equal(cls, context: bpy.types.Context) -> list:
        """Get user-defined equal color"""
        return context.scene.uvv_settings.td_color_equal[:]

    @classmethod
    def get_user_linear(cls, context: bpy.types.Context):
        """Get user-defined linear color scheme"""
        settings = context.scene.uvv_settings
        p_col_sch = cls.get_user_three(context)
        p_col_sch[1] = cls.get_middle_color(
            settings.td_color_under.copy(),
            settings.td_color_over.copy()
        )
        return p_col_sch


class TdRangesMapper:
    """Map TD ranges to colors - Zen UV pattern"""

    @classmethod
    def calc_remap_scope(cls, td_inputs: TdContext, SCOPE: TdIslandsStorage, colors: list, range_limits=[0.0, 0.0], mesh_limits=[0.0, 0.0]):
        """Remap TD scope to color scheme"""

        td_min = mesh_limits[0]
        td_max = mesh_limits[1]

        if td_min >= td_max:
            td_max += 1

        SCOPE.append_color_scheme_reference_values(colors, td_min, td_max)

        underrated = False
        overrated = False

        for isl in SCOPE.islands:
            if isl.td < range_limits[0]:
                isl.color = TdColorManager.black
                if not underrated:
                    underrated = True
                    SCOPE.append_reference(td=range_limits[0], color=TdColorManager.black)
                    SCOPE.append_reference(td=range_limits[0] - 0.01, color=TdColorManager.black)

            elif isl.td > range_limits[1]:
                isl.color = TdColorManager.white
                if not overrated:
                    overrated = True
                    SCOPE.append_reference(td=range_limits[1] - 0.01, color=cls._calc_island_color(td_min, td_max, colors, isl.td))
                    SCOPE.append_reference(td=range_limits[1], color=TdColorManager.white)

            else:
                isl.color = cls._calc_island_color(td_min, td_max, colors, isl.td)

        return SCOPE

    @classmethod
    def _calc_island_color(cls, td_min: float, td_max: float, colors: list, island_td: float):
        """Calculate island color based on TD value"""
        td_clamped = max(td_min, min(td_max, island_td))
        p_val = td_max - td_min
        if p_val == 0:
            p_val = 1

        index = int((td_clamped - td_min) / p_val * (len(colors) - 1))
        alpha = (td_clamped - td_min) / p_val * (len(colors) - 1) - index

        if index == len(colors) - 1:
            return colors[-1]
        else:
            return [(1 - alpha) * c1 + alpha * c2 for c1, c2 in zip(colors[index], colors[index + 1])]


class TdDisplayLimits:
    """Store display limits - Zen UV pattern"""

    cl_td_limits: list = [0.0, 0.0]

    @classmethod
    @property
    def upper_limit(cls):
        return round(cls.cl_td_limits[1], 2)

    @classmethod
    @property
    def lower_limit(cls):
        return round(cls.cl_td_limits[0], 2)

    @classmethod
    @property
    def middle(cls):
        return round(cls.cl_td_limits[0] + ((cls.cl_td_limits[1] - cls.cl_td_limits[0]) / 2), 2)

    @classmethod
    def is_limits_are_equal(cls) -> bool:
        return cls.cl_td_limits[0] == cls.cl_td_limits[1]


@dataclass
class TdDisplayProperties:
    """Texel Density Display Properties"""

    display_method: str = 'SPECTRUM'  # in ("BALANCED", "SPECTRUM", "PRESETS")
    color_scheme_name: str = 'FULL_SPEC'  # in ["FULL_SPEC", "USER_THREE", "USER_LINEAR", "REVERSED_SPEC", "MONO"]
    is_range_manual: bool = False
    use_presets_only: bool = False
    values_filter: float = 10.0


class TdColorProcessor(TdDisplayProperties):
    """Main color processor - Zen UV 1:1 pattern"""

    def __init__(self, context: bpy.types.Context, Scope: TdIslandsStorage, PROPS, update_ui_limits: bool = True) -> None:
        # Copy properties from PROPS
        self.display_method = getattr(PROPS, 'display_method', 'SPECTRUM')
        self.color_scheme_name = getattr(PROPS, 'color_scheme_name', 'FULL_SPEC')
        self.is_range_manual = getattr(PROPS, 'is_range_manual', False)
        self.use_presets_only = getattr(PROPS, 'use_presets_only', False)
        self.values_filter = getattr(PROPS, 'values_filter', 10.0)

        self.SCOPE: TdIslandsStorage = Scope
        self.init(context, update_ui_limits)

    def init(self, context: bpy.types.Context, update_ui_limits: bool = True):
        """Initialize color processor"""
        self.td_values = self.SCOPE.get_sorted_td_values()

        settings = context.scene.uvv_settings

        self.user_limits = [settings.td_range_min, settings.td_range_max]
        if not len(self.td_values):
            self.mesh_limits = [0.0, 1.0]
        else:
            self.mesh_limits = [min(self.td_values), max(self.td_values)]

        if update_ui_limits:
            TdDisplayLimits.cl_td_limits = self.mesh_limits

        self.pr_td_limits = [0.0, 0.0]

        if self.is_range_manual:
            self.pr_td_limits[0] = round(self.user_limits[0], 2)
            self.pr_td_limits[1] = round(self.user_limits[1], 2)
        else:
            if self._is_all_values_uniform():
                self.pr_td_limits[0] = 0.0
                self.pr_td_limits[-1] = self.td_values[-1] * 2
                settings.td_range_min = self.pr_td_limits[0]
                settings.td_range_max = self.pr_td_limits[1]
            else:
                self.pr_td_limits = self.mesh_limits
                settings.td_range_min = self.mesh_limits[0]
                settings.td_range_max = self.mesh_limits[1]

        self.color_scheme = self.set_color_scheme(context, self.color_scheme_name)

    def _is_all_values_uniform(self):
        return self.td_values[0] == self.td_values[-1]

    def calc_output_range(self, context: bpy.types.Context, td_inputs: TdContext, method: str) -> TdIslandsStorage:
        """
        Calculate color output range
        method: in {'SPECTRUM', 'BALANCED', 'PRESETS'}
        """
        self.SCOPE.reset_colors()
        self.SCOPE.remove_referenced_items()

        if method == 'SPECTRUM':
            # Spectrum mode (most common - full color gradient)
            if self.SCOPE.is_td_uniform():
                p_color = TdColorManager.get_mid_color(context, self.color_scheme_name)
                self.SCOPE.set_color(p_color)
            else:
                TdRangesMapper.calc_remap_scope(
                    td_inputs,
                    self.SCOPE,
                    self.color_scheme,
                    range_limits=self.pr_td_limits,
                    mesh_limits=self.mesh_limits)

            return self.SCOPE

        elif method == 'BALANCED':
            # Balanced mode (3-color scheme based on target TD)
            self.set_color_scheme(context, 'USER_THREE')
            if self.SCOPE.is_td_uniform():
                self.SCOPE.set_color(TdColorManager.get_user_equal(context))
            else:
                # Simple balanced implementation
                TdRangesMapper.calc_remap_scope(
                    td_inputs,
                    self.SCOPE,
                    self.color_scheme,
                    range_limits=self.pr_td_limits,
                    mesh_limits=self.mesh_limits)

            return self.SCOPE

        elif method == 'PRESETS':
            # Presets mode (not implemented for now)
            self.SCOPE.set_color(TdColorManager.full[3])
            return self.SCOPE

    def set_color_scheme(self, context: bpy.types.Context, color_scheme: str) -> list:
        """
        Set color scheme
        values in {'FULL_SPEC', 'USER_THREE', 'USER_LINEAR', 'REVERSED_SPEC', 'MONO'}
        """
        if color_scheme == 'FULL_SPEC':
            return TdColorManager.full.copy()

        elif color_scheme == 'REVERSED_SPEC':
            p_cols = TdColorManager.full.copy()
            p_cols.reverse()
            return p_cols

        elif color_scheme == 'USER_THREE':
            return TdColorManager.get_user_three(context)

        elif color_scheme == 'USER_LINEAR':
            return TdColorManager.get_user_linear(context)

        elif color_scheme == 'MONO':
            return TdColorManager.mono.copy()

        else:
            return TdColorManager.full.copy()


def register():
    pass


def unregister():
    pass
