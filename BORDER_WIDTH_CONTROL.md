# Border Width Control - User-Adjustable Flash Thickness

## Overview

Users can now control the **maximum thickness** of the flash border animation through the overlay settings.

## New Property

### `stack_overlay_flash_border_width`

```python
stack_overlay_flash_border_width: FloatProperty(
    name="Flash Border Width",
    description="Maximum thickness of the flash border (shrinks to minimum during animation)",
    default=12.0,
    min=2.0,
    max=20.0,
    step=10,
    precision=1,
    subtype='PIXEL'
)
```

**Default**: 12.0 pixels
**Range**: 2.0 - 20.0 pixels
**Purpose**: Controls the starting thickness of the flash animation

## UI Location

**Stack Overlay Settings Dropdown:**

```
┌─────────────────────────────────┐
│ Overlay Settings                │
├─────────────────────────────────┤
│ Opacity: [====] 50%             │
│ ─────────────────────────────   │
│ ☑ Fill                          │
│ ☑ Border                        │
│ ─────────────────────────────   │
│ ☐ Labels                        │
│ ─────────────────────────────   │
│ ☑ Flash Highlight               │
│ ☐ Selection Border              │
│ ─────────────────────────────   │
│ Flash Border Width: [====] 12px │ ← NEW SLIDER
└─────────────────────────────────┘
```

**Smart UI**: Slider only appears when "Flash Highlight" is enabled.

## How It Works

### Animation Behavior

The flash animation always:
- **Starts** at the user-defined width (adjustable 2-20px)
- **Ends** at 2px (fixed minimum)
- **Shrinks** smoothly using ease-out cubic curve

### Examples

**Width = 12px (Default):**
```
t=0.0s: ████████████ (12px thick)
        ↓ shrinks
t=0.5s: ▓▓▓▓▓▓▓▓     (7.25px)
        ↓ shrinks
t=1.0s: ░░           (2px)
```

**Width = 20px (Maximum):**
```
t=0.0s: ████████████████████ (20px thick - VERY BOLD)
        ↓ shrinks dramatically
t=0.5s: ▓▓▓▓▓▓▓▓▓▓▓         (11.25px)
        ↓ shrinks
t=1.0s: ░░                   (2px)
```

**Width = 6px (Subtle):**
```
t=0.0s: ██████ (6px thick - subtle)
        ↓ shrinks
t=0.5s: ▓▓▓▓   (4.25px)
        ↓ shrinks
t=1.0s: ░░     (2px)
```

## Use Cases

### Large Groups / Complex Scenes (12-20px)
- **Width**: 15-20px
- **Why**: Need bold, attention-grabbing flash
- **Effect**: Very dramatic shrinking animation
- **Best for**: Dense UV layouts with many islands

### Medium Groups (8-12px) - Default Range
- **Width**: 10-12px (default)
- **Why**: Balanced visibility without being overwhelming
- **Effect**: Clear animation, professional look
- **Best for**: Most use cases

### Subtle Flash (4-8px)
- **Width**: 4-8px
- **Why**: Minimal visual disruption
- **Effect**: Gentle pulse effect
- **Best for**: Clean UI preference, simple scenes

### Minimal (2-4px)
- **Width**: 2-4px
- **Why**: Just want a hint of feedback
- **Effect**: Very subtle, barely shrinks
- **Best for**: Users who want minimal visual effects

## Code Implementation

### Property Read

```python
# In draw callback
thickness_start = settings.stack_overlay_flash_border_width
thickness_end = 2.0  # Fixed minimum

# Animate from max → min
animated_thickness = thickness_end + (thickness_start - thickness_end) * ease_t
```

### Dynamic Range

The animation range automatically adjusts based on user setting:

| User Setting | Range | Shrink Amount |
|-------------|-------|---------------|
| 20px | 20px → 2px | 18px (maximum drama) |
| 12px | 12px → 2px | 10px (default) |
| 6px | 6px → 2px | 4px (subtle) |
| 2px | 2px → 2px | 0px (no shrink, only fade) |

**Note**: At 2px minimum, the border only fades without shrinking.

## UI Behavior

### Conditional Display

```python
# Only show slider if flash is enabled
if settings.stack_overlay_highlight_on_click:
    layout.prop(settings, 'stack_overlay_flash_border_width', slider=True)
```

**Why**: No need to show width control if flash is disabled.

### Slider Properties

- **Type**: Slider (drag to adjust)
- **Range**: 2.0 - 20.0 pixels
- **Step**: 1.0 pixel (0.1 precision)
- **Default**: 12.0 pixels
- **Live Update**: Changes immediately apply on next click

## Performance

**Impact of different widths:**
- All widths use the same cached batches
- Only GPU line width state changes
- No geometry rebuild required
- **Performance**: Identical across all width settings

**Conclusion**: Feel free to use maximum width (20px) with no performance penalty!

## Tips for Users

### For Maximum Impact
1. Set width to **15-20px**
2. Use bright group colors (red, yellow, green)
3. Results in **very dramatic** pulsing effect

### For Subtle Feedback
1. Set width to **4-6px**
2. Use muted group colors
3. Results in **gentle** pulse effect

### For Testing
1. Set width to **20px** first to see maximum effect
2. Adjust down until you find your preferred intensity
3. Default **12px** works well for most users

## Summary

✅ **User-controllable** - Adjust thickness from 2-20px
✅ **Smart UI** - Slider only appears when flash is enabled
✅ **Dynamic range** - Animation automatically adjusts to user setting
✅ **No performance impact** - All widths render at same speed
✅ **Immediate feedback** - Changes apply on next click
✅ **Flexible** - From subtle (4px) to dramatic (20px)

Users now have **full control** over how bold or subtle they want the flash animation! 🎨
