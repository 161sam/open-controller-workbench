# Interaction System Review — 2026-03-28

**Status:** partially outdated reference

## Architecture Overview

The interaction system is split across three layers:

| Layer | Files | Responsibility |
|---|---|---|
| **Persistent state** | `interaction_service.py` | Stores `active_interaction`, `hovered_component_id`, `move_component_id`, `active_component_template_id` in document metadata |
| **In-process controllers** | `view_place_controller.py`, `view_drag_controller.py` | Own the FreeCAD event loop, preview rendering, commit/cancel lifecycle |
| **Session guard** | `lifecycle.py: InteractionSessionManager` | Singleton in `ProductWorkbenchPanel`, prevents two concurrent modes |

The `ViewEventCallbackRegistry` (also in `lifecycle.py`) manages attaching/detaching Coin3D event handlers for `SoMouseButtonEvent`, `SoLocation2Event`, `SoKeyboardEvent`.

---

## State Machine

### Interaction States

| State | `active_interaction` | Controller state |
|---|---|---|
| **idle** | `None` | `doc=None`, `view=None` |
| **placing** | `"place"` | `place_controller.doc` set, `preview_active=True` |
| **drag armed** | `"drag"` | `drag_controller.armed=True`, `session=None` |
| **dragging** | `"drag"` | `drag_controller.session.dragging=True` |
| **finished/cancelled** | `None` | Controller fields reset to `None` |

### Placement Flow
```
start(doc, template_id)
  → begin_interaction(doc, "place")
  → attach view callbacks
  → mouse move → update_preview_from_screen() → stores OCWDragPreview in doc
  → left click → commit() → controller_service.add_component()
                           → clear preview → refresh overlay
                           → _notify_committed() [NEW]
                           → mode continues for next click
  → ESC → cancel() → end_interaction() → clear preview → refresh overlay → _notify_finished()
```

### Drag Flow
```
start(doc)
  → begin_interaction(doc, "drag")
  → attach view callbacks
  → hover → update_hover_from_screen() → hit test → highlight component
  → left click down → _begin_drag() → hit test → select component → create DragMoveSession
  → mouse move → update_preview_from_screen() → stores OCWDragPreview
  → left click up → commit() → controller_service.move_component()
                              → cancel(reason="finish") → _notify_finished()
  → ESC → cancel() → restore previous selection → end_interaction() → _notify_finished()
```

---

## Issues Found and Fixed (2026-03-28)

### CRITICAL: UI panels not refreshed after placement/drag commit

**Location:** `workbench.py:_handle_interaction_finished` (was line 963)

**Problem:** After a placement click or drag commit, `_handle_interaction_finished` only cleared the `InteractionSessionManager`. The Components panel, Layout panel, and Constraints panel were not refreshed — the user did not see the placed/moved component in the dock.

For placement specifically, `_handle_interaction_finished` is not called after each commit (the placement loop continues). There was no `on_committed` callback to hook.

**Fix:**
- Added `on_committed` callback to `ViewPlaceController` ([view_place_controller.py](../../ocw_workbench/gui/interaction/view_place_controller.py))
- `_notify_committed()` fires after every placement click
- `workbench.py: _handle_placement_committed()` calls `refresh_context_panels(refresh_components=True)`
- `_handle_interaction_finished()` now also calls `refresh_context_panels(refresh_components=True)` — covers drag commit and all mode exits

**Files:** `view_place_controller.py`, `workbench.py`

---

### HIGH: No feedback when drag click misses all components

**Location:** `view_drag_controller.py:_begin_drag()` (was line 146)

**Problem:** When drag mode was active and the user clicked on an empty position in the 3D view, `_begin_drag` returned `False` silently. No status message was published. The user had no indication of why nothing happened.

**Fix:** After a miss hit test, publish:
> "No component at that position. Hover over a component to highlight it, then click to drag."

**File:** `view_drag_controller.py`

---

### HIGH: Re-initiating drag while session already active

**Location:** `view_drag_controller.py:handle_view_event()` (was line 120)

**Problem:** If `session.dragging` was already `True` and the user clicked again (e.g., after a missed release event), `_begin_drag` would be called again. If a component was found at the new position, the active session would be overwritten silently.

**Fix:** Guard: `_begin_drag` is only called if `self.session is None or not self.session.dragging`.

**File:** `view_drag_controller.py`

---

### MEDIUM: `_begin_drag` used stale overlay cache for hit testing

**Location:** `view_drag_controller.py:_begin_drag()` (was line 142)

**Problem:** The overlay was only refreshed if `doc.OCWOverlayState` was missing. If the overlay cache was present but stale (e.g., a component was just placed), the hit test used outdated geometry.

**Fix:** Always force `overlay_renderer.refresh(self.doc)` on every click-down (once per user action, not per frame — acceptable cost).

**File:** `view_drag_controller.py`

---

## Remaining Known Issues (not fixed in this pass)

### `_active_view()` duplicated in both controllers
Identical implementation in `view_place_controller.py:179` and `view_drag_controller.py:241`. Should be extracted to a module-level helper. No active bug, maintenance risk only.

### Event parser helpers duplicated in both controllers
`_extract_position()`, `_is_mouse_move()`, `_is_left_click_down()`, `_is_escape_event()`, `_view_point()` are identical. Extract to `view_event_helpers.py`.

### `MoveTool` is a second parallel move pathway
`MoveTool` (`move_tool.py`) handles programmatic moves via `arm_move_for_selection()`. `ViewDragController` handles interactive drag. Both call `controller_service.move_component()` eventually. No active conflict but creates two mental models.

### No "click to select" mode in 3D
`SelectionController` exists but no FreeCAD command activates a mode where clicking in the 3D view selects a component and syncs the dock. Selection is dock-only. `SelectionController.select_from_overlay()` is implemented but not wired to a view event loop.

---

## Manual Test Matrix

| Scenario | Expected behaviour | Status |
|---|---|---|
| Place new component | Preview ghost follows cursor, click commits, Components panel updates immediately | **Fixed** |
| Place multiple in sequence | Each click places and refreshes panel, mode continues, ESC exits | **Fixed** |
| Cancel placement (ESC) | Mode exits, preview cleared, status "Placement cancelled." | Working |
| Start drag mode | Status "Drag in 3D..." shown | Working |
| Hover component in drag mode | Component highlighted, status "Ready to drag '...'" | Working |
| Click empty space in drag mode | Status "No component at that position..." shown | **Fixed** |
| Drag component to new position | Preview follows mouse, release commits, Components panel updates | **Fixed** |
| Cancel drag (ESC) | Component restored to original position, mode exits cleanly | Working |
| Cancel drag after begin | Previous selection restored | Working |
| Double-click during active drag | Second click ignored, active session unchanged | **Fixed** |
| Switch modes (place→drag) | Previous mode cancelled cleanly via InteractionSessionManager | Working |
| Document change during active mode | Mode cancelled via `handle_document_changed` | Working |
| Document close during active mode | Mode cancelled via `handle_document_closed` | Working |
| Invalid preview (out of bounds) | Commit blocked, status shows constraint reason | Working |
