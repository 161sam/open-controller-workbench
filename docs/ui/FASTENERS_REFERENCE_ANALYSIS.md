# Fasteners Workbench — Reference Analysis for OCW

**Date:** 2026-03-29
**Purpose:** Technical patterns from FastenersWB that OCW should adopt, adapt, or explicitly skip.

---

## 1. Architecture Overview

FastenersWB follows a pure toolbar-first, selection-driven, property-panel-editing model with no persistent dock UI.

### Workbench Registration (`InitGui.py`)

```python
class FastenersWorkbench(FreeCADGui.Workbench):
    def Initialize(self):
        import FastenersCmd  # all commands registered as side-effect of import
        cmdlist   = FastenerBase.FSGetCommands("command")    # utility ops
        screwlist = FastenerBase.FSGetCommands("screws")     # one entry per fastener type
        self.appendToolbar("FS Commands", cmdlist)
        self.appendToolbar("FS Screws", screwlist)           # can be split into sub-toolbars
        self.appendMenu(["Fasteners"], cmdlist)
```

Key: all `Gui.addCommand()` calls happen at import time in `FastenersCmd.py`, not in `Initialize()`. `Initialize()` only organises already-registered commands into toolbars.

---

## 2. Command Pattern

### Creation command (`FSScrewCommand`)

```python
class FSScrewCommand:
    def IsActive(self):
        return Gui.ActiveDocument is not None   # always active with open doc

    def Activated(self):
        FreeCAD.ActiveDocument.openTransaction("Add fastener")
        for selObj in FastenerBase.FSGetAttachableSelections():
            a = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", self.TypeName)
            FSScrewObject(a, self.Type, selObj)   # proxy + properties
            FSViewProviderTree(a.ViewObject)
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()
```

**Pattern:**
1. `IsActive()` only guards on document existence — not on selection.
2. Selection is consumed in `Activated()`, not before.
3. If no valid selection → `FSGetAttachableSelections()` returns `[None]` → one free-floating object is created.
4. If N circular edges selected → N objects created and attached.

### Selection detection (`FSGetAttachableSelections`)

```python
def FSGetAttachableSelections(screwObj=None):
    for selObj in Gui.Selection.getSelectionEx("", 0):   # resolve=0 → raw sub-elements
        for baseObjectName in selObj.SubElementNames:
            shape = obj.getSubObject(baseObjectName)
            if hasattr(shape, "Curve") and hasattr(shape.Curve, "Center"):
                asels.append((obj, [baseObjectName]))   # circular edge
            elif isinstance(shape, Part.Face):
                # scan inner edges of face for circles (holes)
                ...
    if not asels:
        asels.append(None)   # free-floating fallback
    return asels
```

### Utility commands: selection-gated `IsActive()`

```python
# FSFlipCommand — requires attached fastener
def IsActive(self):
    for selobj in Gui.Selection.getSelectionEx():
        obj = selobj.Object
        if hasattr(obj, "Proxy") and isinstance(obj.Proxy, FSBaseObject):
            if obj.BaseObject is not None:
                return True
    return False

# FSMoveCommand — requires fastener + circular edge simultaneously
def IsActive(self):
    screw_valid = any(...)
    edge_valid  = any(...)
    return screw_valid and edge_valid
```

---

## 3. Object / Property Model

All fasteners are `Part::FeaturePython` objects with a Python Proxy:

```python
a = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Screw")
FSScrewObject(a, type, attachTo)      # attaches proxy, adds Properties
FSViewProviderTree(a.ViewObject)      # attaches view proxy
```

### Properties (all in `"Parameters"` group)

| Property | Type | Purpose |
|---|---|---|
| `Type` | `App::PropertyEnumeration` | Fastener standard (ISO4017, etc.) |
| `Diameter` | `App::PropertyEnumeration` | Standard diameter or "Auto" |
| `Length` | `App::PropertyEnumeration` or `PropertyLength` | Standard or custom length |
| `Thread` | `App::PropertyBool` | Threading detail on/off |
| `Invert` | `App::PropertyBool` | Flip direction |
| `Offset` | `App::PropertyDistance` | Distance along hole axis |
| `OffsetAngle` | `App::PropertyAngle` | Rotation around hole axis |
| `BaseObject` | `App::PropertyXLinkSub` | Attachment target `(obj, ["EdgeN"])` |

All `addProperty()` calls are guarded with `if not hasattr(obj, "PropName")` — idempotent on document restore.

### `execute(fp)` — the recompute entry point

Called automatically whenever any property changes:
1. Read `BaseObject` attachment → resolve edge/face shape
2. Detect which properties changed → cascade enum updates (Type → Diameter list, Diameter → Length list)
3. Resolve `Diameter = "Auto"` from edge radius
4. Generate or fetch cached `Part.Shape`
5. Assign `fp.Shape = s`
6. Call `FSMoveToObject(fp, shape, ...)` to position on attachment

**No dialog. No panel. User edits properties → recompute fires automatically.**

### Re-attachment (Move)

```python
# FSMoveCommand.Activated()
screwObj.BaseObject = new_edge_tuple   # reassign the link
FreeCAD.ActiveDocument.recompute()    # triggers execute() → repositioning
```

Move is implemented as one property assignment.

---

## 4. Toolbar Organization Pattern

FastenersWB organizes 200+ fastener commands into sub-toolbars via a mixed list:

```python
screwlist = [
    "FSDIN7984",              # plain string → single command
    "FSDIN933",
    ("Hex socket", ["FSISO4762", "FSDIN912", ...], "Hex socket screws"),  # tuple → sub-toolbar
    ("Nuts",       ["FSISO4032", "FSDIN934", ...], "Nuts"),
    ...
]
```

`Initialize()` checks for tuples and creates separate toolbars per group.

For OCW, the equivalent would be component-type sub-toolbars:
`("Buttons", ["OCW_PlaceButton_...", ...], "Buttons")`, etc.

---

## 5. What NOT to Adopt from FastenersWB

| Pattern | Reason to skip |
|---|---|
| `Part::FeaturePython` with `fp.Shape` | OCW components are not 3D solids in the traditional sense; their geometry lives in an overlay / generated group — not as standalone Part shapes |
| `App::PropertyXLinkSub` for attachment | OCW components are placed on a 2D plane (controller surface), not attached to 3D edges; attachment is XY position, not edge reference |
| Shape geometry kernel in `execute()` | OCW uses a JSON state model + overlay renderer, not per-object Part kernels |
| 200+ commands (one per screw type) | OCW should use one command per **component type** (button, encoder, etc.), not one per library variant |
| `Diameter = "Auto"` from edge radius | No 3D attachment point in OCW; position comes from 3D view cursor |

---

## 6. Concrete Transfer Rules for OCW

| Fasteners Pattern | OCW Equivalent |
|---|---|
| `FSScrewCommand.IsActive()` → `Gui.ActiveDocument is not None` | `OCW_Place*Command.IsActive()` → `_has_controller()` |
| Selection consumed in `Activated()`, not in `IsActive()` | OCW place commands should **always** start placement; use 3D pick if something is selected |
| One command per fastener **type group** (Hex, Socket, Nuts, …) | One command per OCW **component type** (button, encoder, fader, pad, display, rgb_button) |
| Sub-toolbar per fastener group | Sub-toolbar "OCW Components" per component type, or grouped toolbar |
| `addObject("Part::FeaturePython", ...)` + Proxy in `Activated()` | `controller_service.add_component(doc, library_ref, x, y)` in `Activated()` — already correct |
| All editing via Property Panel (no dock) | OCW: remove formular-dock dependency; use TaskPanel or Property-based approach for editing |
| `FSMoveCommand`: reassign `BaseObject` → recompute | OCW: `DragMoveComponentCommand` → `ViewDragController` (already exists, already correct) |
| `FreeCAD.ActiveDocument.openTransaction(...)` / `commitTransaction()` | OCW already wraps mutations in transactions via `_mutate_with_full_sync()` |
| `FSViewProviderTree.getIcon()` dynamic per type | OCW components in model tree could use dynamic icons per component type |

---

## 7. Key Insight: Why FastenersWB Has No Dock

FastenersWB has no persistent dock because:

1. **Object creation** is a single click on a toolbar button → no form needed.
2. **Property editing** uses FreeCAD's built-in Properties panel → no custom form needed.
3. **Selection-driven behavior** means the tool knows what to do from context → no wizard needed.
4. **State lives on the FreeCAD object** via `App::Property*` fields → no separate state management UI needed.

OCW's current dock contains these panels because OCW currently stores state in JSON and operates via a service layer — not via FreeCAD's native property system. The dock is a workaround for missing FreeCAD-native integration.

**The path to dockless OCW is not to remove the dock — it is to move the workflows out of the dock** into toolbar commands, 3D interaction, and (where needed) TaskPanels.
