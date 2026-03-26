# Service Architecture

## Goal

Keep project state mutations, FreeCAD document rebuilds, and UI interactions separate.

## Services

### ControllerStateService

Responsibilities:

- load and save normalized project state
- create projects from templates and variants
- add, update, move, and select components
- update controller parameters
- apply layout strategies to state
- validate the current state
- provide UI context derived from state

This service should stay testable without FreeCAD document-object APIs.

### DocumentSyncService

Responsibilities:

- rebuild generated FreeCAD geometry from project state
- refresh selection highlighting
- manage generated object cleanup
- update sync timing metadata
- isolate FreeCAD GUI focus and reveal behavior

This service consumes state and applies it to the document.

Overlay refresh is not part of the geometry rebuild path.
Visual overlay updates should not trigger `doc.recompute()` and should remain view-only operations.
Workbench status feedback should stay centralized at the shell level.
Panels may show local hints, but user-facing success, warning, and error summaries should be routed through the shared workbench status path where possible.

## Sync Modes

The current update model uses explicit sync modes:

- `full`
- `visual_only`
- `partial_ready`
- `state_only`

Current behavior:

- `full`: complete generated-geometry rebuild plus document recompute
- `visual_only`: selection and visual refresh only, without geometry rebuild
- `partial_ready`: reserved migration path, currently falls back to `full`
- `state_only`: headless fallback when the document has no FreeCAD object API

### ControllerService

Responsibilities:

- compatibility facade for commands, panels, and interaction helpers
- delegate state changes to `ControllerStateService`
- delegate document rebuilds to `DocumentSyncService`

This facade exists to keep the current UI stable while internals are split into smaller services.

## Boundaries

- Project persistence: `freecad_api/state.py`
- Document model root: `freecad_api/model.py`
- State mutation: `services/controller_state_service.py`
- Document rebuild: `services/document_sync_service.py`
- Global user data: `ocw_workbench.userdata`

## Migration Notes

- Existing callers can continue using `ControllerService`.
- New logic should prefer the narrower services when it only needs state mutation or only needs document sync.
- UI code should avoid directly performing FreeCAD rebuild work when a state-only update is sufficient.

## Performance Instrumentation

See also:

- `docs/performance-metrics.md`
