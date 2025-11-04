# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

"""
Units Converter for Texel Density calculations (ZenUV compatibility)
"""


class UnitsConverter:
    """
    Units converter for texel density display
    Current system is centimeters based (Blender default)
    """

    # Conversion factors from cm to other units
    converter = {
        'km': 100000.0,
        'm': 100.0,
        'cm': 1.0,
        'mm': 0.1,
        'um': 0.0001,
        'mil': 160934.0,
        'ft': 30.48,
        'in': 2.54,
        'th': 0.00254
    }

    # Reverse conversion (to meters)
    rev_con = {
        'km': 0.001,
        'm': 1.0,
        'cm': 100,
        'mm': 1000,
        'um': 1000000,
        'mil': 0.000621371,
        'ft': 3.28084,
        'in': 39.3701,
        'th': 39370.0787
    }

    # Meters-based conversion
    meters_based = {
        'km': 1000.0,
        'm': 1.0,
        'cm': 0.01,
        'mm': 0.001,
        'um': 0.000001,
        'mil': 1609.344,
        'ft': 0.3048,
        'in': 0.0254,
        'th': 0.0000254
    }

    base_mult = 1.0
    base_unit = 'cm'

    @classmethod
    def get_count_after_point(cls, units: str) -> int:
        """Get number of decimal places needed for this unit"""
        s = str(cls.converter[units])
        return abs(s.find('.') - len(s)) - 1

    @classmethod
    def get_mult_for(cls, units):
        """Get multiplication factor for given units"""
        if cls._units_valid(units):
            return cls.converter[units] * cls.base_mult
        else:
            return None

    @classmethod
    def convert_raw_world_distance(cls, distance=None, units='m'):
        """Convert raw world distance to specified units"""
        if distance and cls._units_valid(units):
            return distance * 100 / cls.get_mult_for(units)

    @classmethod
    def _units_valid(cls, units):
        """Check if units are valid"""
        return units in cls.converter.keys()

    @classmethod
    def set_base_units(cls, unit):
        """Set base units for conversion"""
        if not cls._units_valid(unit):
            print("Units Converter --> The requested units is not valid.")
            return None
        cls.base_mult = 1 / cls.converter[unit]
        cls.base_unit = unit
        return cls.base_mult

    @classmethod
    def get_base_units(cls):
        """Get current base units"""
        base_unit = [key for key in cls.converter.keys() if cls.converter[key] * cls.base_mult == 1]
        if base_unit:
            return base_unit[0]
        return None


def get_td_round_value(td_unit: str) -> int:
    """
    Get appropriate rounding precision for TD value based on unit

    Args:
        td_unit: Unit string like 'px/cm', 'px/m', 'px/in'

    Returns:
        Number of decimal places to round to
    """
    # Parse unit from format like 'px/cm' -> 'cm'
    if '/' in td_unit:
        unit_part = td_unit.split('/')[1]
    else:
        unit_part = td_unit

    # Higher precision for smaller units
    precision_map = {
        'cm': 2,   # 512.25 px/cm
        'm': 0,    # 512 px/m (larger values, no decimals needed)
        'mm': 3,   # 512.125 px/mm (very precise)
        'in': 2,   # 512.25 px/in
        'ft': 1,   # 512.2 px/ft
    }

    return precision_map.get(unit_part, 2)  # Default to 2 decimal places


def get_current_units_string(td_unit: str) -> str:
    """
    Get display string for current units

    Args:
        td_unit: Unit string like 'px/cm', 'px/m', 'px/in'

    Returns:
        Formatted string for display (e.g., "px/cm")
    """
    return td_unit
