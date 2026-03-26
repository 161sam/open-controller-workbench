
# Open Controller FreeCAD

FreeCAD-Workbench zur parametrischen Entwicklung modularer MIDI-Controller.

## Ziel

Dieses Plugin bildet die mechanische Design-Schicht im Open-Controller-Stack:

- Gehäuse & Top-Plate designen
- Komponenten platzieren
- Cutouts & Keepouts generieren
- Hardware-Schema (`controller.hw.yaml`) erzeugen
- Vorbereitung für KiCad & OCF

## Stack-Kontext

- C++ → Giada Fork (Runtime)
- Rust → OCF (Core Framework)
- TypeScript → Tools / UI / Plugins
- Python (dieses Repo) → FreeCAD Workbench

## Status

Frühe Entwicklungsphase.

✔ vorhanden:
- Workbench-Registration
- erste Commands
- Domain-Modelle (Controller, Component)
- YAML Loader & Validator
- Geometry Builder (Surface + Cutouts)

🚧 fehlt:
- vollständige GUI
- Schema ↔ Domain Mapping
- KiCad Export
- vollständige Workflows

## Installation (Dev)

```bash
git clone https://github.com/161sam/open-controller-freecad.git
cd open-controller-freecad
pip install -e .
````

```bash
mkdir -p ~/.local/share/FreeCAD/Mod
ln -s "$(pwd)/ocf_freecad" ~/.local/share/FreeCAD/Mod/OpenController
```

FreeCAD starten → Workbench „Open Controller“ auswählen

## Dokumentation

* docs/architecture.md
* docs/workbench.md
* docs/workflows.md
* docs/schema-v1.md
* docs/development.md
* docs/plugin-installation.md
* docs/kicad-workflow.md

## Vision

Parametrischer Hardware-Controller-Builder mit durchgängiger Pipeline:

FreeCAD → Schema → KiCad → OCF → Runtime

## Lizenz

TBD
