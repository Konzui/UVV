# Overlap helper mixin for operators
# Ported from UniV addon

import bpy


class OverlapHelper:
    """Mixin class for overlap detection in operators"""
    lock_overlap: bpy.props.BoolProperty(name='Lock Overlaps', default=False)
    lock_overlap_mode: bpy.props.EnumProperty(
        name='Lock Overlaps Mode',
        default='ANY',
        items=(('ANY', 'Any', ''), ('EXACT', 'Exact', ''))
    )
    threshold: bpy.props.FloatProperty(
        name='Distance',
        default=0.001,
        min=0.0,
        soft_min=0.00005,
        soft_max=0.00999
    )

    def draw_overlap(self, toggle=True):
        layout = self.layout
        if self.lock_overlap:
            if self.lock_overlap_mode == 'EXACT':
                layout.prop(self, 'threshold', slider=True)
            layout.row().prop(self, 'lock_overlap_mode', expand=True)
        layout.prop(self, 'lock_overlap', toggle=toggle)

    def calc_overlapped_island_groups(self, all_islands):
        from .. import types
        assert self.lock_overlap, 'Enable Lock Overlap option'
        threshold = None if self.lock_overlap_mode == 'ANY' else self.threshold
        return types.UnionIslands.calc_overlapped_island_groups(all_islands, threshold)
