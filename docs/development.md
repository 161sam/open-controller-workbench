
# Development Guide

## Setup

```bash
git clone https://github.com/161sam/open-controller-workbench.git
cd open-controller-workbench
pip install -e .
```

Für FreeCAD-Entwicklung zusätzlich:

```bash
mkdir -p ~/.local/share/FreeCAD/Mod
ln -s "$(pwd)" ~/.local/share/FreeCAD/Mod/OpenControllerWorkbench
```

## FreeCAD-Modulstruktur

```text
open-controller-workbench/
├── Init.py
├── InitGui.py
├── ocw_workbench/
│   ├── commands/
│   ├── domain/
│   ├── freecad_api/
│   ├── generator/
│   ├── geometry/
│   ├── gui/
│   ├── layout/
│   ├── library/
│   ├── plugins/
│   ├── schema/
│   ├── services/
│   ├── templates/
│   └── variants/
├── ocw_kicad/
├── resources/
└── docs/
```

Wichtig:
- FreeCAD lädt den Modulroot
- `InitGui.py` registriert die Workbench
- Ressourcen im Top-Level-Ordner `resources/` müssen relativ zum Modulroot auffindbar bleiben
- Laufzeit-YAML-Daten liegen im Package unter `ocw_workbench/`

## Prinzipien

- keine Logik in Commands
- Domain unabhängig von FreeCAD
- Geometry testbar
- Repo-Root bleibt FreeCAD-kompatibler Modulroot

## Einstiegspunkte

- `InitGui.py`
- `ocw_workbench/workbench.py`
- `ocw_workbench/services/controller_service.py`
- `ocw_workbench/generator/controller_builder.py`

## Packaging

Für Packaging müssen mitkommen:
- `Init.py`
- `InitGui.py`
- `resources/icons/*`
- YAML-Dateien in `ocw_workbench/library/`
- YAML-Dateien in `ocw_workbench/templates/`
- YAML-Dateien in `ocw_workbench/variants/`
- interne Plugin-Manifest- und Daten-Dateien in `ocw_workbench/plugins/internal/`

## Roadmap Dev

1. Schema erweitern
2. Mapping bauen
3. Builder testen
4. GUI erweitern
5. Export stabilisieren

## Tests

- Schema
- Builder
- Resolver
- Workbench-/Command-Flows
