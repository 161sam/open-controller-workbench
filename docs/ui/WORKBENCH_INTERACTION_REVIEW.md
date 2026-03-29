# OCW Workbench Interaction Review

**Status:** active main focus

**Date:** 2026-03-28
**Scope:** Command quality, toolbar registration, selection-driven behavior, dock role — compared against the Fasteners Workbench UX model.

---

## 1. Reference Model: Fasteners Workbench

The Fasteners Workbench is the canonical example of a direct-action FreeCAD workbench:

- **Toolbar-first:** Every toolbar button triggers a real, immediate action.
- **Selection-driven:** `IsActive()` gates commands on document/selection state — buttons are grey when they cannot act.
- **No dialogs for basic operations:** Adding, placing, and moving objects happens directly in the 3D view or via simple toolbar state, not through task-panel dialogs.
- **Dock as context, not workflow:** The side panel shows information about the current selection; it does not host the primary workflow.

---

## 2. Current OCW Command Inventory

### 2.1 Commands in the toolbar (registered in Initialize())

| Command ID | Class | What it does | Quality |
|---|---|---|---|
| `OCW_CreateController` | `CreateFromTemplateCommand` | Opens workbench UI + focuses Create panel | Dock navigation only, no direct action |
| `OCW_AddComponent` | `AddComponentCommand` | Starts placement mode or opens palette | Good — direct action |
| `OCW_ImportTemplateFromFCStd` | `ImportTemplateFromFCStdCommand` | Imports template | Good |
| `OCW_SelectComponent` | `SelectComponentCommand` | Focuses Components panel in dock | Dock navigation only, no direct action |
| `OCW_OpenComponentPalette` | `OpenComponentPaletteCommand` | Opens palette dock | Acceptable |
| `OCW_ApplyLayout` | `ApplyLayoutCommand` | Runs auto-placement directly | Good — direct action |
| `OCW_MoveComponentInteractive` | `MoveComponentInteractiveCommand` | Arms move mode for selected component (2-step workflow) | Weaker duplicate of `DragMoveComponent` |
| `OCW_DragMoveComponent` | `DragMoveComponentCommand` | Starts 3D drag mode directly | Good — direct action |
| `OCW_SnapToGrid` | `SnapToGridCommand` | Snaps selection to grid | Good — direct action |
| `OCW_DuplicateSelected` | `DuplicateSelectionCommand` | Duplicates selection (shows param dialog) | Acceptable |
| `OCW_ArrayHorizontal/Vertical` | `LinearArrayCommand` | Creates linear array (shows param dialog) | Acceptable |
| `OCW_GridArray` | `GridArrayCommand` | Creates grid array (shows param dialog) | Acceptable |
| `OCW_RotateCW90` etc. | `SelectionTransformCommand` | Applies transform to selection | Good — direct action |
| `OCW_AlignLeft` etc. | `SelectionArrangeCommand` | Aligns/distributes selection | Good — direct action |
| `OCW_ValidateConstraints` | `ValidateConstraintsCommand` | Runs validation directly | Good — direct action |
| `OCW_ToggleOverlay` etc. | Toggle commands | Toggle overlay/measurements/etc. | Good |

### 2.2 Dead command files (exist but not registered)

The following command files exist but are **never imported or registered** in `Initialize()`. They are pure dead code:

- `move_component.py` — `MoveComponentCommand`: opens `LayoutTaskPanel` dialog
- `auto_layout.py` — `AutoLayoutCommand`: opens `LayoutTaskPanel` dialog
- `validate_layout.py` — `ValidateLayoutCommand`: opens `ConstraintsTaskPanel` dialog

Each has a registered direct-action twin (`DragMoveComponent`, `ApplyLayout`, `ValidateConstraints`). The dead files can be deleted.

### 2.3 Missing `IsActive()` guards

**Every command** (except `_FavoriteComponentCommand`) inherits `IsActive()` from `BaseCommand`, which unconditionally returns `True`. This means:

- `SnapToGrid`, `AlignDistribute`, `SelectionTransform` are active even with no selection or no document.
- `DragMoveComponent` is active even with no open document.
- `ValidateConstraints`, `ApplyLayout` are active even with no controller.

In Fasteners, `IsActive()` reflects real preconditions. In OCW, every button is always enabled.

---

## 3. Key Problems

### Problem 1: `OCW_MoveComponentInteractive` is a weaker duplicate

`OCW_MoveComponentInteractive` ("Move Component") uses a two-step "arm then click" workflow:
1. Click toolbar button → calls `panel.arm_move_for_selection()` → arms move mode
2. Click in 3D view → actually moves the component

`OCW_DragMoveComponent` ("Drag Move Component") is strictly better: click toolbar → immediately start 3D drag. Both share the same icon. The interactive version adds confusion and should be removed from the toolbar.

### Problem 2: No `IsActive()` guards

Selection-dependent commands are always enabled, misleading users into clicking them when nothing will happen (or an error will appear).

### Problem 3: Dock-navigation commands in the toolbar

`OCW_SelectComponent` only focuses the dock's Components tab. `OCW_CreateController` only focuses the dock's Create tab. These are not FreeCAD commands in the Fasteners sense — they're navigation shortcuts. They are not harmful but they weaken the toolbar as an action surface.

---

## 4. Target Model

Every toolbar button is a real, immediate action. Toolbar buttons that require state (document, controller, selection) are greyed out when that state is absent.

### 4.1 Command cleanup

| Remove from toolbar | Keep as | Reason |
|---|---|---|
| `OCW_MoveComponentInteractive` | (remove entirely) | Weaker version of `OCW_DragMoveComponent` |
| Dead files `move_component.py`, `auto_layout.py`, `validate_layout.py` | (delete) | Unregistered dead code |

### 4.2 `IsActive()` guards to add

| Command | Precondition |
|---|---|
| `DragMoveComponent` | Active document with OCW controller |
| `ApplyLayout` | Active document with OCW controller |
| `ValidateConstraints` | Active document with OCW controller |
| `SnapToGrid` | Active document + OCW selection |
| `SelectionArrangeCommand` (align/distribute) | Active document + OCW selection |
| `SelectionTransformCommand` (rotate/mirror) | Active document + OCW selection |
| `DuplicateSelectionCommand`, `LinearArrayCommand`, `GridArrayCommand` | Active document + OCW selection |

---

## 5. First Improvement Package

**Changes applied:**

1. Remove `OCW_MoveComponentInteractive` from all toolbar/menu registrations in `workbench.py`.
2. Add `IsActive()` guards to the 8 command classes listed in §4.2.
3. Delete dead command files: `move_component.py`, `auto_layout.py`, `validate_layout.py`.
4. Add `_has_controller()` and `_has_selection()` helper statics to `BaseCommand` so guards are one-liners.
