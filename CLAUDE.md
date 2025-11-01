# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UVV (Universal UV Toolkit) is a Blender 4.2+ addon for UV mapping operations. The addon provides texel density tools, UV sync controls, seam operations, and workspace tools.

## Architecture

The addon follows Blender's standard addon structure:

- `__init__.py` - Main addon registration/unregistration with icon loading
- `blender_manifest.toml` - Addon metadata and permissions
- `properties.py` - Addon settings and properties
- `operators/` - Blender operators for UV operations (texel density, UV sync, seam ops)
- `ui/` - User interface panels and menus
- `tools/` - Workspace tools (seam brush tool)
- `utils/` - Utility functions for math and island operations
- `icons/` - Icon assets (PNG files)

### Key Components

- **Icon System**: Custom icon loading similar to UV Toolkit, stored in global `icons_collections`
- **Module Registration**: All modules are registered/unregistered through the main `__init__.py`
- **Tool Registration**: Workspace tools have separate registration after main modules
- **UI Structure**: Main panel in UV editor sidebar with texel density, UV sync, and seam controls

### Import Structure

The addon uses relative imports extensively:
- Operators import from `..properties` for settings
- UI imports from `..properties` and `..` for icon access
- Tools are registered separately from main module registration

## Development Workflow

### Addon Reloading
Use the development script at `C:\Users\Benutzer1\OneDrive - Hogeschool West-Vlaanderen\Documenten\_Dev\Blender\Addons\reload_uvv.py` to reload the addon during development:

1. Open Blender and go to Scripting workspace
2. Load the `reload_uvv.py` script
3. Run the script to install/reload the addon after code changes
4. The script handles disabling the old addon, clearing modules, copying files, and re-enabling

### Reference Addons
The `_ref` directory contains source code from other UV addons for implementation inspiration:
- `magic_uv` - UV mapping utilities
- `mio3_uv` - UV tools
- `rmKit_uv` - UV workflow tools
- `univ` - Universal UV tools
- `UV_Flatten_Tool` - UV flattening operations
- `uv_maps_plus` - Extended UV functionality
- `UV_Snapper` - UV snapping tools
- `uv_toolkit` - Comprehensive UV toolkit
- `ZenUVChecker` - UV checking utilities
- `Key_Ops_Toolkit` - Reference for Box Mapping (triplanar UV) implementation

## Feature Details

### Box Mapping (Triplanar UV Mapping)

The Box Mapping feature provides selection-based triplanar UV projection:

**Implementation:**
- Based on Key Ops Toolkit's triplanar UV mapping system
- Uses geometry nodes modifier for non-destructive workflow
- Supports both Object mode (whole mesh) and Edit mode (face selection)

**Workflow:**
1. **Object Mode:** Applies box mapping to entire mesh
2. **Edit Mode:** Uses face attribute system (`UVV_Box_Mapping`) to map only selected faces
   - Creates boolean face attribute to track selection
   - Multiple runs add more faces to the mapping
   - Non-destructive - modifier can be adjusted or removed

**Files:**
- `operators/triplanar_mapping.py` - Box mapping operator and node group creation
- `ui/viewport_3d_panel.py` - "Box Unwrap" and "Remove" buttons in 3D View panel

**Previous Implementation:**
- Old gizmo-based visualization system was removed for simplicity
- No longer uses `gizmos/box_mapping_gizmo.py` (deleted)
- Cleaner approach without GPU drawing overhead

## Development Notes

- This is a pure Blender addon with no external build system or dependencies
- No package.json, requirements.txt, or build scripts - addon loads directly into Blender
- Testing would be done within Blender's environment using the reload script
- Icon paths use relative navigation (`..`) to access the icons directory
- Error handling includes try/catch blocks for tool registration failures

## Troubleshooting

**IMPORTANT**: Before debugging operator issues, consult `TROUBLESHOOTING.md` for known Blender 4.4 registration problems and solutions.

### Critical Rules for Operator Development:

1. **Never use reload blocks in operator files** - No `if 'bpy' in locals(): reload.reload(globals())`
2. **Always use explicit imports** - `from bpy.props import BoolProperty, EnumProperty` (not `import *`)
3. **Register child classes before parent classes** - When using inheritance, reverse the registration order
4. **Check VSCode terminal for C++ warnings** - `WARN (bpy.rna): unable to get Python class` indicates registration failure
5. **Trace all dependencies when porting** - Copy utility functions, not just the operator class

### Common Errors:
- **"unable to get Python class for RNA struct"** → Remove reload blocks, fix registration order
- **Button grayed out** → Check if RNA type has `poll()` method with `hasattr(op.get_rna_type(), 'poll')`
- **Properties not working** → Remove reload blocks, use explicit imports
- **Missing utility functions** → Copy from reference addon to `utils/__init__.py`

See `TROUBLESHOOTING.md` for detailed solutions and examples.