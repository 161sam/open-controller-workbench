# State Architecture

## Goal

Open Controller keeps one project-specific source of truth per FreeCAD document.

## Primary Persistence Path

- Document object: `OCF_Controller`
- Property: `ProjectJson`

`ProjectJson` stores the full controller project snapshot.
Mirrored scalar FreeCAD properties on `OCF_Controller` exist for inspection and tooling,
but `ProjectJson` remains the canonical project payload.
The `ControllerProxy` keeps mirrored properties and `ProjectJson` aligned during
`execute()`, restore, and property-change handling.

## State API

Project state access is centralized in `ocf_freecad.freecad_api.state`.

- `ProjectStateStore.load()`
- `ProjectStateStore.save()`
- `ProjectStateStore.migrate_legacy_state()`
- compatibility wrappers:
  - `read_state()`
  - `write_state()`
  - `has_persisted_state()`

`ControllerService` and other callers should use the state API instead of writing
document metadata directly.

## Runtime Cache

`STATE_CACHE_KEY` is a lightweight runtime cache for mocked or partially available
document environments. It is not a second persisted project format.

New writes do not populate:

- `STATE_CACHE_JSON_KEY`
- `OCFState`
- `OCF_State_JSON`

Those keys are only read during migration.

## Legacy Migration

The following legacy paths are still read:

- `OCF_State.StateJson`
- document metadata `OCFState`
- document metadata `OCF_State_JSON`

When a legacy payload is found and `OCF_Controller.ProjectJson` is empty, the state
layer migrates the payload into `ProjectJson`.

## Separation From User Data

Project state is document-local and belongs to the FreeCAD file.

Global user data remains separate under `ocf_freecad.userdata`, for example:

- favorites
- recents
- presets
- plugin registry and plugin state

The state layer must not write user preferences into `ProjectJson`.
