
# Architecture

## Rolle des Repos

FreeCAD-basierte Design-Schicht für Controller-Hardware.

Keine Runtime. Kein OCF-Core.

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

### 6. Layout
- grid.py
- placement.py
- strategies.py
- zone_layout.py

### 7. Services
- controller_service.py
- layout_service.py
- constraint_service.py

### 7a. Project State
- freecad_api/model.py
- freecad_api/state.py

Project state is persisted on the `OCF_Controller` document object.
`ProjectJson` is the primary source of truth for controller projects.
Legacy document metadata and `OCF_State` containers are migration inputs only.

### 8. Export
- exporters/
- ocf_kicad/

## Datenfluss

Schema → Domain → Resolver → Geometry → FreeCAD → Export

## Zielarchitektur

- Schema-driven Design
- Library-driven Komponenten
- reproduzierbare Layouts
