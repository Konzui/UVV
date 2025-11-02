# Separate Border Controls - Stack Group Highlight

## Overview

The highlight system now has **two independent toggles**:

1. **Flash Highlight** - Yellow flash border when clicking (default: ON)
2. **Permanent Border** - White border always visible for selected group (default: OFF)

This gives users full control over the visual feedback they want.

## New Property

### `stack_overlay_show_permanent_border`

```python
stack_overlay_show_permanent_border: BoolProperty(
    name="Permanent Border",
    description="Show permanent white border around islands in the selected group",
    default=False  # Disabled by default
)
```

**Location**: `properties.py` line 1355

## UI Changes

### Stack Overlay Settings Menu

The overlay settings dropdown now shows both options:

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
│ ☑ Flash Highlight               │ ← Yellow flash on click
│ ☐ Permanent Border              │ ← White border always visible
└─────────────────────────────────┘
```

**Location**: `ui/menus.py` in `UVV_MT_StackOverlaySettings`

## Behavior Matrix

| Flash Highlight | Permanent Border | What You See |
|----------------|------------------|--------------|
| ✅ ON | ❌ OFF | Yellow flash only (fades after 1s) |
| ✅ ON | ✅ ON | White border + yellow flash on top |
| ❌ OFF | ✅ ON | White border only (no flash) |
| ❌ OFF | ❌ OFF | No highlight at all |

## Default Configuration

**Out of the box:**
- ✅ Flash Highlight: **ON** (visual feedback on clicks)
- ❌ Permanent Border: **OFF** (clean, minimal UI)

**Result**: Users get click feedback without persistent visual clutter.

## Draw Logic

```python
if has_highlight:
    highlight_batches = get_cached_batches(...)

    # 1. Draw permanent border (if enabled)
    if settings.stack_overlay_show_permanent_border:
        draw_white_border(4px)

    # 2. Draw flash (if active, independent of permanent border)
    if flash_active:
        draw_yellow_flash(6px, fading)
```

**Key points:**
- Flash works **independently** of permanent border setting
- Both can be enabled together (layered rendering)
- Performance stays the same (shared cached batches)

## Use Cases

### 1. Flash Only (Default)
**Best for:** Clean UI, feedback on demand
- Click group → See yellow flash
- Flash fades → Clean view
- No persistent visual clutter

### 2. Both Enabled
**Best for:** Maximum visibility
- Always see which group is selected (white border)
- Get click confirmation (yellow flash)
- Good for complex scenes with many groups

### 3. Permanent Border Only
**Best for:** Traditional selection highlighting
- Like trimsheet system
- Always visible indicator
- No animation

### 4. Both Disabled
**Best for:** Minimal UI
- No visual feedback
- Relies on list selection only

## Implementation Details

### Changes Made

1. **New property** in `properties.py`:
   - `stack_overlay_show_permanent_border` (default: False)
   - Updated `stack_overlay_highlight_on_click` description

2. **UI update** in `ui/menus.py`:
   - Added permanent border toggle to overlay settings menu
   - Both toggles shown together

3. **Draw logic** in `utils/stack_overlay.py`:
   - Permanent border only drawn if `settings.stack_overlay_show_permanent_border`
   - Flash still drawn independently
   - Shared batch cache (no performance penalty)

### Performance

- **No change** - both features use the same cached batches
- **Flash only**: Same performance as before
- **Both enabled**: Still 60 FPS (just draws same batches twice with different colors)

## Testing

1. Reload addon
2. Open Stack Overlay settings dropdown
3. Try different combinations:
   - **Flash only** (default) → Click groups, see yellow flash
   - **Both on** → White border + yellow flash on click
   - **Permanent only** → White border, no flash
   - **Both off** → No visual feedback

## Visual Examples

### Flash Only (Default)
```
Click → [Yellow flash] → [Nothing]
         (6px, fades)     (clean)
```

### Both Enabled
```
Always:  [White border]
         (4px, permanent)

Click → [White + Yellow flash] → [White border]
        (4px + 6px layered)       (4px remains)
```

### Permanent Only
```
Always: [White border]
        (4px, permanent)

Click → [White border]
        (no change)
```

## Result

✅ **Flexible** - Users can choose their preferred feedback style
✅ **Clean by default** - Flash only, no persistent clutter
✅ **Powerful when needed** - Both can be enabled for maximum visibility
✅ **Independent controls** - Each feature can be toggled separately
✅ **No performance cost** - Shared batch cache
