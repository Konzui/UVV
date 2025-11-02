"""
UVV Keymap Registration
Handles ALT+SHIFT+X hotkey for pie menu
"""

import bpy


def register_keymaps():
    """Register UVV keymaps"""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    if kc is None:
        print("UVV: No addon keyconfig found")
        return []

    keymaps = []

    # Mesh keymap (3D View context) - EDIT_MESH
    try:
        km = kc.keymaps.new(name='Mesh', space_type='EMPTY')
        kmi = km.keymap_items.new("uvv.pie_menu", 'X', 'PRESS', alt=True, shift=True)
        keymaps.append((km, kmi))
        print("UVV: Registered Mesh keymap")
    except Exception as e:
        print(f"UVV: Failed to register Mesh keymap: {e}")

    # Image keymap (UV Editor context) - IMAGE_EDITOR
    try:
        km = kc.keymaps.new(name='Image', space_type='IMAGE_EDITOR')
        kmi = km.keymap_items.new("uvv.pie_menu", 'X', 'PRESS', alt=True, shift=True)
        keymaps.append((km, kmi))
        print("UVV: Registered Image keymap")
    except Exception as e:
        print(f"UVV: Failed to register Image keymap: {e}")

    return keymaps


def unregister_keymaps(keymaps):
    """Unregister UVV keymaps"""
    for km, kmi in keymaps:
        km.keymap_items.remove(kmi)


# Global storage for keymaps
uvv_keymaps = []


def register():
    """Register keymaps"""
    global uvv_keymaps
    uvv_keymaps = register_keymaps()
    print(f"UVV: Registered {len(uvv_keymaps)} keymaps")
    
    # Debug: List all keymaps to verify registration
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        print("UVV: Available keymaps:")
        for km in kc.keymaps:
            if 'uvv' in km.name.lower() or 'mesh' in km.name.lower() or 'image' in km.name.lower():
                print(f"  - {km.name} ({km.space_type})")
                for kmi in km.keymap_items:
                    if 'uvv' in kmi.idname:
                        # Build key string representation safely
                        try:
                            # Try to use key_string if available (older Blender versions)
                            if hasattr(kmi, 'key_string') and kmi.key_string:
                                key_str = kmi.key_string
                            else:
                                # Construct manually from properties (Blender 4.x)
                                key_str_parts = []
                                if kmi.shift:
                                    key_str_parts.append("Shift")
                                if kmi.ctrl:
                                    key_str_parts.append("Ctrl")
                                if kmi.alt:
                                    key_str_parts.append("Alt")
                                if kmi.oskey:
                                    key_str_parts.append("OS")
                                key_str_parts.append(kmi.type)
                                key_str = " + ".join(key_str_parts)
                        except Exception:
                            # Fallback to just the key type
                            key_str = kmi.type
                        print(f"    - {kmi.idname} ({key_str})")


def unregister():
    """Unregister keymaps"""
    global uvv_keymaps
    if uvv_keymaps:
        unregister_keymaps(uvv_keymaps)
        uvv_keymaps = []
        print("UVV: Unregistered keymaps")
