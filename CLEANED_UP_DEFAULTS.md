# Cleaned Up - Debug Prints Removed & Default Settings Updated

## Changes Made

### 1. Removed Debug Prints

**Removed from `utils/stack_overlay.py`:**
```python
# OLD - Line 1157 (removed):
print(f"[UVV Stack] Selected group changed: '{selected_group.name}' (ID: {selected_group.group_id})")
```

**Result:** No more console spam when clicking stack groups.

**Error prints kept:** The error handler `print(f"Stack group selection error: {e}")` is kept for debugging actual errors.

---

### 2. Updated Default Settings

All overlay settings now default to **OFF** except Flash Highlight:

#### Stack Overlay Settings (properties.py)

| Setting | Old Default | New Default | Reason |
|---------|-------------|-------------|--------|
| Show Fill | ✅ ON | ❌ OFF | Clean by default |
| Show Border | ❌ OFF | ❌ OFF | (unchanged) |
| Show Labels | ❌ OFF | ❌ OFF | (unchanged) |
| Flash Highlight | ✅ ON | ✅ ON | Main feature |
| Selection Border | ❌ OFF | ❌ OFF | (unchanged) |
| Flash Border Width | 12.0px | **4.0px** | More subtle |

---

## Default User Experience

### Out of the Box (Fresh Install)

**When user first enables Stack Overlay:**

```
┌─────────────────────────────────┐
│ Stack Overlay Settings          │
├─────────────────────────────────┤
│ Opacity: [========] 50%         │
│ ─────────────────────────────   │
│ ☐ Fill                          │ ← OFF by default
│ ☐ Border                        │ ← OFF by default
│ ─────────────────────────────   │
│ ☐ Labels                        │ ← OFF by default
│ ─────────────────────────────   │
│ ☑ Flash Highlight               │ ← ON by default (only one)
│ ☐ Selection Border              │ ← OFF by default
│ ─────────────────────────────   │
│ Flash Border Width: [=] 4px     │ ← 4px by default (subtle)
└─────────────────────────────────┘
```

**What the user sees:**
- **Clean viewport** - No fills, no borders, no labels
- **Flash feedback only** - Subtle 4px flash when clicking groups
- **Color-coded** - Flash uses group's color
- **Minimal** - Just enough feedback without visual clutter

---

## Rationale

### Why Disable Everything by Default?

**1. Clean First Impression**
- Users aren't overwhelmed with visual overlays
- Viewport stays clean and uncluttered
- Professional, minimalist look

**2. Let Users Discover Features**
- Users can enable features as needed
- Each feature becomes a discovery
- Better onboarding experience

**3. Flash Highlight is Enough**
- Provides instant feedback on clicks
- Color-coded for quick identification
- Non-intrusive (disappears after 1 second)

**4. Subtle Flash Width (4px)**
- Less aggressive than 12px
- Still clearly visible
- Professional look
- Users can increase if needed

---

## Migration Notes

### For Existing Users

**If users have already used the addon:**
- Their existing settings are preserved
- These defaults only apply to fresh installs
- Blender stores per-scene settings

**If users want to reset to new defaults:**
1. Delete `.blend` file settings
2. Or manually adjust settings to match new defaults

---

## Recommended User Workflow

### Beginner Workflow (Default)
1. Enable Stack Overlay
2. Click on groups → See subtle flash (4px)
3. Clean viewport, minimal visual feedback
4. **Most users stay here**

### Intermediate Workflow
1. Enable "Show Fill" for color-coded islands
2. Keep flash at 4px
3. Good balance of visibility and cleanliness

### Advanced Workflow
1. Enable Fill + Border + Labels
2. Increase flash width to 10-12px
3. Maybe enable Selection Border
4. Maximum visual feedback for complex scenes

---

## Visual Comparison

### Old Defaults (Before)
```
ON:  Fill, Flash (12px)
OFF: Border, Labels, Selection Border

Result: Colored islands + bold flash
        Medium visual clutter
```

### New Defaults (After)
```
ON:  Flash (4px) only
OFF: Fill, Border, Labels, Selection Border

Result: Clean viewport + subtle flash
        Minimal visual clutter
```

---

## Summary of Changes

### Code Changes

**File: `utils/stack_overlay.py`**
- ❌ Removed: Debug print statement (line 1157)
- ✅ Kept: Error print for actual errors

**File: `properties.py`**
- `stack_overlay_show_fill`: `True` → `False`
- `stack_overlay_flash_border_width`: `12.0` → `4.0`
- All other settings already defaulted to `False`

### User Impact

✅ **Cleaner default experience** - Minimal visual clutter
✅ **No console spam** - Debug prints removed
✅ **Subtle flash** - 4px instead of 12px
✅ **Flash still enabled** - Main feature works out of the box
✅ **Discoverability** - Users can enable features as needed

---

## Test Instructions

1. **Fresh Install Test:**
   - Remove existing addon
   - Install fresh version
   - Enable Stack Overlay
   - Verify: Only flash is enabled, width is 4px
   - Click on group → See subtle 4px flash

2. **Existing User Test:**
   - Update addon
   - Existing settings should be preserved
   - No console prints when clicking groups

3. **Settings Test:**
   - Open overlay settings dropdown
   - Verify all settings OFF except Flash Highlight
   - Verify Flash Border Width slider shows 4px

---

## Final Default Configuration

```python
# Stack Overlay Defaults (properties.py)
stack_overlay_enabled: False              # (must be manually enabled)
stack_overlay_opacity: 0.5                # (unchanged)
stack_overlay_show_fill: False            # ← Changed from True
stack_overlay_show_border: False          # (unchanged)
stack_overlay_show_labels: False          # (unchanged)
stack_overlay_highlight_on_click: True    # (unchanged)
stack_overlay_show_permanent_border: False # (unchanged)
stack_overlay_flash_border_width: 4.0     # ← Changed from 12.0
```

The addon now provides a **clean, professional default experience** with just enough visual feedback! ✨
