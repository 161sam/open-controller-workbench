
# Architecture

## Rolle des Repos

FreeCAD-basierte Design-Schicht für Controller-Hardware.

Keine Runtime. Kein OCF Framework-Core.

## Architekturprinzipien

- UI ≠ Logik
- Schema-first
- FreeCAD nur Adapter
- Zwischenrepräsentationen testbar halten

## Layer

### 1. UI / Workbench
- workbench.py
- commands/

### 2. Domain
- controller.py
- component.py

### 3. Schema
- loader.py
- validator.py

### 4. Generator
- controller_builder.py
- mechanical_resolver.py

### 5. Geometry
- primitives.py
- freecad_api/shapes.py

The geometry pipeline is staged through `ControllerBuilder` plans:
surface resolution, body plan, top plate plan, cutout primitive collection, and boolean planning.

### 6. Layout
- grid.py
- placement.py
- strategies.py
- zone_layout.py

### 7. Services
- controller_service.py
- controller_state_service.py
- document_sync_service.py
- layout_service.py
- constraint_service.py

`ControllerService` is a compatibility facade.
State mutations live in `ControllerStateService`.
FreeCAD document rebuild and visual refresh live in `DocumentSyncService`.

### 7a. Project State
- freecad_api/model.py
- freecad_api/state.py

Project state is persisted on the `OCW_Controller` document object.
`ProjectJson` is the primary source of truth for controller projects.
Legacy document metadata and `OCW_State` containers are migration inputs only.

Generated document geometry is owned by the `OCW_Generated` group.
Regular cleanup and rebuild paths operate on group membership instead of global name scans.
Keepout helper geometry is overlay-driven by default and is only materialized as document objects in explicit debug mode.
The document tree uses `OCW_Controller` as the visible project root.
`OCW_Controller` only claims `OCW_Generated` as a tree child.
`OCW_Overlay` remains a separate visual helper object instead of being implicitly nested under the controller root.

### 8. Export
- exporters/
- ocw_kicad/

## Datenfluss

Schema → Domain → Resolver → Geometry → FreeCAD → Export

## Zielarchitektur

- Schema-driven Design
- Library-driven Komponenten
- reproduzierbare Layouts

See also:

- `docs/ARCHITECTURE_FREECAD_WORKBENCH.md`
