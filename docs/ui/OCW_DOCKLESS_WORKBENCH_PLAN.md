# OCW Dockless Workbench Plan

**Status:** active supporting strategy

**Date:** 2026-03-29
**Goal:** Remove dependency on the permanent dock/sidebar as the primary workflow. Make OCW feel like FastenersWB — toolbar-first, selection-driven, direct-action.

## Progress Update — 2026-03-29

- Package A is implemented: per-type component placement commands are registered and grouped in the primary `OCW Components` toolbar.
- Package B is mostly implemented for the high-value direct actions: layout, validation, drag, placement, transforms, arrangement, overlays, patterns, and plugin reload no longer require `ensure_workbench_ui(...)` as a prerequisite.
- Package C is implemented in the current direct-action form: `OCW_AddComponent` starts placement directly when a template is already active, otherwise it falls back to the palette without forcing the workbench dock.
- Toolbar cleanup has progressed toward the target model: the `OCW Favorites` toolbar has been removed from the primary toolbar surface, while favorites remain available as a secondary menu path.
- Remaining dock-reduced cleanup is concentrated in navigation-oriented commands and plugin-selection commands rather than the main direct-action workflow.

---

## 1. What Is Already FreeCAD-Workbench-Tauglich

These elements already conform to a FreeCAD-native workbench pattern and require no structural change:

| Element | File | Status |
|---|---|---|
| `OpenControllerWorkbench(Gui.Workbench)` | `workbench.py:195` | Correct FreeCAD workbench subclass |
| `GetClassName() → "Gui::PythonWorkbench"` | `workbench.py:199` | Required, correct |
| `Gui.addCommand()` calls in `Initialize()` | `workbench.py:227–272` | Correct pattern |
| `appendToolbar()` / `appendMenu()` | `workbench.py:325–342` | Correct |
| `FreeCAD.ActiveDocument.openTransaction()` | `controller_service.py` via `_mutate_with_full_sync` | Correct undo integration |
| `OCW_Controller` as `App::FeaturePython` | `freecad_api/model.py` | FreeCAD document object, correct |
| `IsActive()` guards via `_has_controller()` / `_has_selection()` | `commands/base.py:28–50` | Now correct (fast cache path) |
| `ViewPlaceController`, `ViewDragController`, `ViewPickController` | `gui/interaction/` | FreeCAD-native Coin3D event hooks, correct |
| `refresh_favorite_component_commands()` | `workbench.py:1593` | Correct dynamic command refresh |
| All toggle commands | `commands/toggle_*.py` | Direct actions, correct |

---

## 2. What Is Currently Dock-Dependent (The Problem)

### 2.1 All Toolbar Commands call `ensure_workbench_ui()` first

Every command in OCW calls `ensure_workbench_ui(doc, focus="...")` before doing anything. This function:
1. Creates `ProductWorkbenchPanel` (the full 5-panel stepper UI)
2. Shows it in a dock widget via `create_or_reuse_dock()`
3. Calls `panel.<specific_method>()`

**Example — `ApplyLayoutCommand.Activated()` (`apply_layout.py:18`):**
```python
panel = ensure_workbench_ui(doc, focus="layout")
result = panel.layout_panel.apply_auto_layout()
```

The command cannot do anything without a live dock panel. If `ensure_workbench_ui()` fails (headless, no Qt), the command crashes.

**Example — `DragMoveComponentCommand.Activated()` (`drag_move_component.py:18`):**
```python
ensure_workbench_ui(doc, focus="components")
started = start_component_drag_mode(doc)
```

Even drag mode — which is pure 3D interaction — requires the dock to be open.

### 2.2 The Five Core Panels are Dock-Only Workflows

| Panel | File | Dock-dependent workflow |
|---|---|---|
| `CreatePanel` | `gui/panels/create_panel.py` | Controller creation, template/variant selection, geometry parameters |
| `ComponentsPanel` | `gui/panels/components_panel.py` | Component selection, editing X/Y/rotation/label, add, duplicate |
| `LayoutPanel` | `gui/panels/layout_panel.py` | Auto-layout, overlay toggles, grid settings |
| `ConstraintsPanel` | `gui/panels/constraints_panel.py` | Validation results, constraint overlay |
| `InfoPanel` | `gui/panels/info_panel.py` | Export, template info |

None of these are task panels or dialogs. They are permanent forms that require the dock to be open.

### 2.3 State Reading / Writing Routed Through Panel Methods

Many commands call `panel.layout_panel.apply_auto_layout()` or `panel.constraints_panel.validate()` — the business logic lives on the panel instance, not in the service layer or command directly. Commands are UI hooks, not real tools.

**Full dependency map:**

| Command | Panel method called | Could be direct? |
|---|---|---|
| `OCW_ApplyLayout` | `panel.layout_panel.apply_auto_layout()` | Yes — call `InteractionService` directly |
| `OCW_ValidateConstraints` | `panel.constraints_panel.validate()` | Yes — call `ControllerService` directly |
| `OCW_SnapToGrid` | `panel.snap_selection_to_grid()` | Yes — call `InteractionService` directly |
| `OCW_DragMoveComponent` | `start_component_drag_mode(doc)` → `panel.start_drag_mode()` | Partially — 3D interaction correct; panel refresh not needed upfront |
| `OCW_DuplicateSelected` | `panel.duplicate_selection_once(...)` | Yes — call `ControllerService` directly |
| `OCW_Array*` | `panel.array_selection_*()` | Yes — call service directly |
| `OCW_Rotate/Mirror/Align` | `panel.apply_selection_transform/arrangement()` | Yes — call service directly |

### 2.4 `AddComponentCommand` Opens Dock Before Starting Placement

`add_component.py:18–38`: calls `ensure_workbench_ui(doc, focus="components")` even when the only purpose is to start 3D placement. The dock is opened as a prerequisite.

---

## 3. Per-Component-Type Commands Are Missing

Currently OCW has:
- `OCW_AddComponent` — opens palette OR starts placement for last-used template
- 6 `OCW_FavoriteComponent_N` slots — quick-place for user-assigned favorites
- `OCW_OpenComponentPalette` — opens a palette dock

**Missing:** One command per component **type** in the toolbar, like FastenersWB.

Library has 6 component types:
- `button` → 2 variants
- `encoder` → 4 variants
- `fader` → 2 variants
- `pad` → 1 variant
- `display` → 3 variants
- `rgb_button` → 1 variant

A Fasteners-style toolbar would have: `OCW_PlaceButton`, `OCW_PlaceEncoder`, `OCW_PlaceFader`, `OCW_PlacePad`, `OCW_PlaceDisplay`, `OCW_PlaceRgbButton` — each starting placement mode with a sensible default variant, or (with selection) prompting variant choice.

---

## 4. Required Architecture Changes for Dockless OCW

### 4.1 Decouple Commands from `ensure_workbench_ui()`

Commands must call services directly. The dock may optionally be refreshed **after** the action via a separate notification path — but the dock must not be a prerequisite.

**Pattern change:**

```python
# Current (dock-dependent):
def Activated(self):
    panel = ensure_workbench_ui(doc, focus="layout")
    result = panel.layout_panel.apply_auto_layout()

# Target (direct):
def Activated(self):
    from ocw_workbench.services.controller_service import ControllerService
    result = ControllerService().apply_auto_layout(doc)
    # optionally notify dock if open:
    _refresh_active_workbench_if_open(doc)
```

### 4.2 Business Logic Must Live in Services, Not Panels

Current state: logic like `apply_auto_layout()`, `validate()`, `snap_selected_component()`, `duplicate_selection_once()` etc. is on the panel instances. It must move to services so commands can call it without a dock.

The services are already there (`ControllerService`, `InteractionService`) — the logic just needs to be exposed at service level, not only at panel level.

### 4.3 Per-Component-Type Commands

Add one `PlaceComponentTypeCommand` per type, registered in `Initialize()` and in a dedicated `"OCW Components"` toolbar. Each command:
- `IsActive()` → `_has_controller()`
- `Activated()` → picks best variant for the type → starts `ViewPlaceController`
- Icon: the component type icon

### 4.4 `ensure_workbench_ui()` Becomes Optional Notification

After a command runs, the dock (if open) should refresh. This is done via a lightweight notification:

```python
def _refresh_active_workbench_if_open(doc):
    if _ACTIVE_WORKBENCH is not None and _ACTIVE_WORKBENCH.doc is doc:
        _ACTIVE_WORKBENCH.refresh_context_panels(refresh_components=True)
```

This is already partly done (`_handle_placement_committed`, `_handle_interaction_finished`). It needs to be used everywhere.

### 4.5 Dock Becomes Optional Context Panel

The dock remains as an **optional** UI for users who want it. `Activated()` on `OpenControllerWorkbench.Activated()` still shows the dock (good entry point for new users). But toolbar commands must work without it.

---

## 5. Target Toolbar Structure

### OCW Project toolbar
- `OCW_CreateController` — create/load controller (opens task panel for template selection)
- `OCW_ImportTemplateFromFCStd` — import

### OCW Components toolbar (NEW — Fasteners-style)
- `OCW_PlaceButton` — place button (starts placement mode)
- `OCW_PlaceEncoder` — place encoder
- `OCW_PlaceFader` — place fader
- `OCW_PlacePad` — place pad
- `OCW_PlaceDisplay` — place display
- `OCW_PlaceRgbButton` — place RGB button
- `---` separator
- `OCW_OpenComponentPalette` — more variants / full palette

### OCW Layout toolbar (existing, keep)
- `OCW_ApplyLayout`
- `OCW_DragMoveComponent`
- `OCW_SnapToGrid`
- `OCW_DuplicateSelected`
- `OCW_ArrayHorizontal`, `OCW_ArrayVertical`, `OCW_GridArray`
- `OCW_RotateCW90`, `OCW_RotateCCW90`, `OCW_Rotate180`
- `OCW_MirrorHorizontal`, `OCW_MirrorVertical`
- `OCW_AlignLeft`, …, `OCW_DistributeVertically`

### OCW Validate toolbar (existing, keep)
- `OCW_ValidateConstraints`
- `OCW_ShowConstraintOverlay`

### OCW View toolbar (existing, keep)
- `OCW_ToggleOverlay`
- `OCW_ToggleMeasurements`
- `OCW_ToggleConflictLines`
- `OCW_ToggleConstraintLabels`

### Remove
- `OCW Favorites` toolbar (replace with per-type component commands above)
- Or: keep Favorites as secondary quick-access, demote from primary slot

---

## 6. Implementation Packages

### Package A — Per-component-type place commands (highest value)

Create `ocw_workbench/commands/place_component_type.py` with:
- `PlaceComponentTypeCommand(component_type: str, default_library_ref: str)`
- One instance per type: button, encoder, fader, pad, display, rgb_button
- `IsActive()` → `_has_controller()`
- `Activated()` → calls `start_component_place_mode(doc, default_library_ref)` directly
- Icons from existing component icon assets
- Register all 6 in `Initialize()`, add to new `"OCW Components"` toolbar

**Impact:** Users can click "Button", "Encoder", etc. from toolbar — Fasteners-style.

### Package B — Decouple commands from dock (service-direct calls)

For each dock-dependent command, replace:
```python
panel = ensure_workbench_ui(doc, focus="layout")
result = panel.layout_panel.apply_auto_layout()
```
with:
```python
result = ControllerService().apply_auto_layout(doc)
_refresh_active_workbench_if_open(doc)
```

Move `apply_auto_layout()`, `validate()` etc. to service layer if not already there.

**Impact:** Commands work in headless mode, without dock, without Qt.

### Package C — `AddComponentCommand` without dock prerequisite

`AddComponentCommand.Activated()` should call `start_component_place_mode()` directly, without `ensure_workbench_ui()` as prerequisite. If no active template → open palette as a dialog or task panel, not a dock.

**Impact:** Add Component works without the dock being open.

### Package D — Dock becomes optional (cleanup)

- `Workbench.Activated()` still opens the dock as a welcome screen
- All command `Activated()` methods do NOT call `ensure_workbench_ui()` anymore
- Dock (if open) is refreshed via `_refresh_active_workbench_if_open(doc)`
- `ensure_workbench_ui()` is renamed to `open_workbench_dock()` to clarify intent

**Impact:** Full dockless operation possible; dock becomes opt-in context panel.

---

## 7. What Stays in the Dock

The dock panels can remain and provide value as context UI:

| Panel | Keep? | As what? |
|---|---|---|
| `CreatePanel` | Yes | Entry wizard for new users; template selection |
| `ComponentsPanel` | Yes | Context detail view for selected component |
| `LayoutPanel` | Yes | Grid/overlay settings |
| `ConstraintsPanel` | Yes | Validation results display |
| `InfoPanel` | Yes | Export panel |

But their content must be **read-only context** (reflecting selection/state), not the primary action surface.

---

## 8. Implementation Order

1. **Package A** — Place-per-type commands → immediate Fasteners-style toolbar
2. **Package B** — `ApplyLayout` and `ValidateConstraints` direct (these are the most-used commands, highest value)
3. **Package C** — `AddComponent` without dock
4. **Package D** — Full dock-optional cleanup
