# UVV Addon Development - Troubleshooting Guide

## Common Blender 4.4 Operator Registration Issues

### 🔴 ERROR: "unable to get Python class for RNA struct"

**Symptoms:**
- Operator button is grayed out
- `hasattr(op_rna_type, 'poll')` returns `False`
- Warning in VSCode terminal: `WARN (bpy.rna): unable to get Python class for RNA struct 'UV_OT_...'`

**Root Causes & Solutions:**

#### 1. Reload Block Corruption (MOST COMMON)
```python
# ❌ WRONG - This corrupts property descriptors
if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

# ✅ CORRECT - Remove reload blocks from operator files
# Just import normally - Blender handles reloading
```

**Why:** The `reload.reload(globals())` corrupts `_PropertyDeferred` objects before Blender can convert them to actual properties.

#### 2. Wrong Registration Order
```python
# ❌ WRONG - Parent registered before child
classes = [
    ParentOperator,
    ChildOperator,  # Inherits from ParentOperator
]

# ✅ CORRECT - Child registered before parent
classes = [
    ChildOperator,   # Inherits from ParentOperator
    ParentOperator,
]
```

**Why:** When the parent class is registered first, its content changes, breaking inheritance for child classes registered later.

**Reference:** https://blender.stackexchange.com/questions/323245/

---

### 🟡 Properties Not Working (axis, shear, etc.)

**Symptoms:**
- `hasattr(MyOperator, 'axis')` returns `False` before registration
- Properties show as `<_PropertyDeferred>` in `__annotations__` but never become real properties
- UI can't set properties: `op.axis = 'XY'` fails silently

**Solution:**

```python
# ✅ CORRECT
from bpy.props import BoolProperty, EnumProperty  # Explicit imports
from bpy.types import Operator

class MyOperator(Operator):
    axis: EnumProperty(name='Axis', default='XY', items=(...))  # Colon syntax OK in Blender 4.4

# ❌ WRONG
from bpy.props import *  # Wildcard imports
if 'bpy' in locals():    # Reload block
    reload.reload(globals())
```

**Why:** Wildcard imports + reload blocks = property corruption

---

### 🟢 Missing Utility Functions

**Symptoms:**
- `AttributeError: module 'bl_ext...utils' has no attribute 'function_name'`
- Operator works initially but crashes during execution

**Common Missing Functions:**
- `get_select_mode_uv()`
- `get_select_mode_mesh()`
- `get_aspect_ratio()`

**Prevention:**
1. When porting operators from reference addons, trace ALL dependencies
2. Check what utility functions are called in the operator code
3. Copy utility functions to your `utils/__init__.py`
4. Test the entire execution path, not just registration

---

## Debugging Methodology

### What to Check (In Order):

1. **VSCode Terminal for C++ Warnings**
   ```
   WARN (bpy.rna): unable to get Python class for RNA struct 'UV_OT_...'
   ```
   This is the MOST reliable indicator of registration issues.

2. **RNA Type Has Methods**
   ```python
   import bpy
   op = bpy.ops.uv.my_operator.get_rna_type()
   print("Has poll:", hasattr(op, 'poll'))  # Should be True
   print("Has execute:", hasattr(op, 'execute'))  # Should be True
   ```

3. **Python Class vs RNA Struct**
   ```python
   # Check Python module
   import bl_ext.vscode_development.UVV.operators.my_module as mod
   print("Python class has poll:", hasattr(mod.MyOperator, 'poll'))
   print("Python class has axis:", hasattr(mod.MyOperator, 'axis'))

   # Compare with RNA
   op_rna = bpy.ops.uv.my_operator.get_rna_type()
   print("RNA has poll:", hasattr(op_rna, 'poll'))
   ```

4. **Compare with Working Operators**
   - Find a working operator in your codebase
   - Compare imports, inheritance, registration order
   - Look for differences in file structure

### What NOT to Trust:

- ❌ "SUCCESS: Registered" messages - can be misleading
- ❌ `'operator_name' in dir(bpy.ops.namespace)` - shows True even if broken
- ❌ Poll never being called - symptom, not root cause

---

## Code Porting Checklist

When copying operators from reference addons (UniV, UV Toolkit, etc.):

- [ ] Copy operator class definition
- [ ] Copy ALL utility functions it uses (trace dependencies)
- [ ] Copy mixin classes (OverlapHelper, etc.)
- [ ] Remove reload blocks (`if 'bpy' in locals()`)
- [ ] Change to explicit imports (`from bpy.props import BoolProperty`)
- [ ] Check class registration order (child before parent)
- [ ] Add missing utility functions to `utils/__init__.py`
- [ ] Test registration: verify RNA has `poll` method
- [ ] Test execution: click button and check for AttributeErrors
- [ ] Verify all features work (X/Y buttons, properties, etc.)

---

## Best Practices for Blender 4.4 Addons

### Operator File Structure (CORRECT)
```python
# my_operator.py

# No reload block!

import bpy
from bpy.props import BoolProperty, EnumProperty  # Explicit
from bpy.types import Operator

from .. import utils
from ..types import MyType

class MyOperator(Operator, utils.MyMixin):
    bl_idname = "uv.my_operator"
    bl_label = "My Operator"
    bl_options = {'REGISTER', 'UNDO'}

    my_prop: BoolProperty(name="My Prop", default=True)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        # Implementation
        return {'FINISHED'}

classes = [MyOperator]
```

### Registration (CORRECT)
```python
# __init__.py

from . import my_module

classes = []
classes.extend(my_module.classes)

def register():
    import bpy
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    import bpy
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```

---

## Quick Reference: Error → Solution

| Error | Most Likely Cause | Solution |
|-------|------------------|----------|
| Button grayed out | No `poll()` method on RNA | Check for reload block, registration order |
| `unable to get Python class` | Reload block or wrong order | Remove reload, fix registration order |
| `AttributeError: no attribute 'axis'` | Property not registered | Remove reload block, use explicit imports |
| `AttributeError: no attribute 'get_select_mode_uv'` | Missing utility function | Copy from reference addon to `utils/__init__.py` |
| Properties show as `<_PropertyDeferred>` | Reload mechanism interference | Remove reload block |

---

## When in Doubt:

1. **Remove all reload blocks** from operator files
2. **Use explicit imports** for bpy.props
3. **Register child classes before parent classes**
4. **Check VSCode terminal** for C++ warnings
5. **Compare with working operators** in the same codebase
6. **Test incrementally** - one fix at a time

---

*Last Updated: 2025-01-04*
*Blender Version: 4.4*
*Python Version: 3.10.6*
