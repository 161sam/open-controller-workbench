# OCW Workbench Interaction Review

**Status:** active main focus

**Date:** 2026-03-28
**Scope:** Command quality, toolbar registration, selection-driven behavior, dock role — compared against the Fasteners Workbench UX model.

## Progress Update — 2026-03-29

- `OCW_MoveComponentInteractive` is no longer part of the registered command surface.
- The `IsActive()` guard gap described below is largely closed via `_has_controller()` / `_has_selection()` based command activation.
- Direct-action commands for placement, drag, layout, validation, overlays, transforms, arrangement, patterns, and reload now run without opening the workbench dock first.
- Per-type placement commands (`OCW_PlaceButton`, `OCW_PlaceEncoder`, `OCW_PlaceFader`, `OCW_PlacePad`, `OCW_PlaceDisplay`, `OCW_PlaceRgbButton`) are now the primary component toolbar surface.
- The former `OCW Favorites` toolbar has been demoted from the primary toolbar surface to a secondary menu path.
- `OCW_CreateController` remains available, but no longer occupies the primary project toolbar.
- `EnablePlugin` / `DisablePlugin` now behave as explicit plugin-selection actions: they no longer open the dock implicitly and are only active when a plugin is already selected in the open Plugin Manager.
- `Create Controller`, `Open Plugin Manager`, and `Open Components` are now treated explicitly as UI/navigation commands via the dock-opening helper rather than as pseudo-tools.
- The dock-opening API is now expressed via `open_workbench_dock(...)`; `ensure_workbench_ui(...)` remains only as a compatibility alias for older call sites.

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
| `OCW_CreateController` | `CreateFromTemplateCommand` | Opens the Create step in the dock | Navigation command; no longer on primary toolbar |
| `OCW_AddComponent` | `AddComponentCommand` | Starts placement mode or opens palette | Good — direct action |
| `OCW_ImportTemplateFromFCStd` | `ImportTemplateFromFCStdCommand` | Imports template | Good |
| `OCW_SelectComponent` | `SelectComponentCommand` | Opens the Components step in the dock | Navigation command; secondary only |
| `OCW_OpenComponentPalette` | `OpenComponentPaletteCommand` | Opens palette dock | Acceptable |
| `OCW_ApplyLayout` | `ApplyLayoutCommand` | Runs auto-placement directly | Good — direct action |
| `OCW_DragMoveComponent` | `DragMoveComponentCommand` | Starts 3D drag mode directly | Good — direct action |
| `OCW_SnapToGrid` | `SnapToGridCommand` | Snaps selection to grid | Good — direct action |
| `OCW_DuplicateSelected` | `DuplicateSelectionCommand` | Duplicates selection (shows param dialog) | Acceptable |
| `OCW_ArrayHorizontal/Vertical` | `LinearArrayCommand` | Creates linear array (shows param dialog) | Acceptable |
| `OCW_GridArray` | `GridArrayCommand` | Creates grid array (shows param dialog) | Acceptable |
| `OCW_RotateCW90` etc. | `SelectionTransformCommand` | Applies transform to selection | Good — direct action |
| `OCW_AlignLeft` etc. | `SelectionArrangeCommand` | Aligns/distributes selection | Good — direct action |
| `OCW_ValidateConstraints` | `ValidateConstraintsCommand` | Runs validation directly | Good — direct action |
| `OCW_ToggleOverlay` etc. | Toggle commands | Toggle overlay/measurements/etc. | Good |

### 2.2 Legacy command cleanup status

The old duplicate command files mentioned in the first review pass no longer exist in `ocw_workbench/commands`. That cleanup is complete.

### 2.3 `IsActive()` guard status

The original blanket `IsActive()` gap is no longer current for the direct-action surface. The main selection-/controller-dependent commands now use `_has_controller()` / `_has_selection()` and behave like real workbench tools.

Remaining special cases are intentional:
- `_FavoriteComponentCommand` remains dynamic/userdata-driven.
- Navigation commands are UI entry points, not direct manipulation tools.

---

## 3. Key Problems

### Problem 1: `OCW_MoveComponentInteractive` is a weaker duplicate

Status: resolved. The duplicate command is no longer part of the active command surface.

`OCW_DragMoveComponent` remains the direct manipulation path.

### Problem 2: No `IsActive()` guards

Status: largely resolved for the main direct-action surface.

### Problem 3: Dock-navigation commands in the toolbar

Partially resolved. These commands still exist, but they are now clearly framed as navigation/UI commands, and `OCW_CreateController` no longer occupies the primary project toolbar.

---

## 4. Target Model

Every toolbar button is a real, immediate action. Toolbar buttons that require state (document, controller, selection) are greyed out when that state is absent.

### 4.1 Command cleanup status

| Remove from toolbar | Keep as | Reason |
|---|---|---|
| `OCW_MoveComponentInteractive` | resolved | No longer part of the registered command surface |
| Dead files `move_component.py`, `auto_layout.py`, `validate_layout.py` | resolved | No longer present in `ocw_workbench/commands` |

### 4.2 `IsActive()` guards

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

## 5. Current Consolidation Status

**Implemented:**

1. `OCW_MoveComponentInteractive` removed from the active command surface.
2. `_has_controller()` / `_has_selection()` based guards in place for the direct-action command set.
3. Direct-action commands no longer depend on opening the dock first.
4. Per-type placement commands are primary component creation commands.
5. The toolbar favors direct actions over dock-navigation shortcuts.

**Still open:**

1. Navigation commands still exist and remain explicitly dock-opening entry points.
2. Plugin enable/disable remains selection-driven via the open Plugin Manager, not fully dockless.
