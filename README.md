
# Open Controller Workbench

FreeCAD-Workbench zur parametrischen Entwicklung modularer MIDI-Controller.

## Ziel

Dieses Repository ist als FreeCAD-Modulroot aufgebaut. FreeCAD soll den gesamten Repo-Root als Modul laden, nicht nur das Python-Package `ocw_workbench/`.

Die relevante Struktur ist:

```text
open-controller-workbench/
├── Init.py
├── InitGui.py
├── ocw_workbench/
├── ocw_kicad/
├── resources/
├── examples/
└── docs/
```

Wichtig:
- `Init.py` und `InitGui.py` liegen im Modulroot, wie FreeCAD es erwartet
- `ocw_workbench/` enthält das Python-Package
- `resources/` enthält Icons und weitere Runtime-Ressourcen
- YAML-Daten für Templates, Varianten, Libraries und Plugins liegen im Package unter `ocw_workbench/`

## Dev-Installation unter Linux

1. Repository klonen:

```bash
git clone https://github.com/161sam/open-controller-workbench.git
cd open-controller-workbench
```

2. Python-Abhängigkeiten für lokale Entwicklung installieren:

```bash
pip install -e .
```

3. FreeCAD-Mod-Symlink setzen:

```bash
mkdir -p ~/.local/share/FreeCAD/Mod
ln -s "$(pwd)" ~/.local/share/FreeCAD/Mod/OpenControllerWorkbench
```

Alternativ für Snap-FreeCAD:

```bash
mkdir -p ~/snap/freecad/common/Mod
ln -s "$(pwd)" ~/snap/freecad/common/Mod/OpenControllerWorkbench
```

Wichtig:
- Ziel ist immer der Repo-Root
- nicht `$(pwd)/ocw_workbench`
- der Modulname darf frei gewählt werden, sollte aber stabil sein, z. B. `OpenControllerWorkbench`

## FreeCAD-Test

```bash
freecad
```

Danach in FreeCAD:
- Workbench-Liste öffnen
- `Open Controller Workbench` auswählen

Wenn die Installation stimmt, sieht FreeCAD `InitGui.py`, registriert die Workbench und lädt Icons/Ressourcen aus demselben Modulroot.

## Troubleshooting

### Workbench erscheint nicht

- prüfen, ob der Symlink auf den Repo-Root zeigt
- prüfen, ob `Init.py` und `InitGui.py` direkt im Zielordner liegen
- FreeCAD komplett neu starten

### Workbench erscheint, aber Icons fehlen

- prüfen, ob `resources/icons/` im verlinkten Repo vorhanden ist
- keinen Symlink auf `ocw_workbench/` setzen, sondern auf den Repo-Root

### YAML/Templates/Libraries werden nicht gefunden

- prüfen, ob `ocw_workbench/templates/`, `ocw_workbench/variants/`, `ocw_workbench/library/` im verlinkten Repo vorhanden sind
- prüfen, ob FreeCAD wirklich das richtige Modulverzeichnis geladen hat

## Dokumentation

- `docs/architecture.md`
- `docs/workbench.md`
- `docs/workflows.md`
- `docs/schema-v1.md`
- `docs/development.md`
- `docs/plugin-installation.md`
- `docs/kicad-workflow.md`

## Vision

Parametrischer Hardware-Controller-Builder mit durchgängiger Pipeline:

FreeCAD → Schema → KiCad → OCF Framework → Runtime

OCW bezeichnet dieses FreeCAD-Workbench-Repository.
OCF bezeichnet das separate Framework-Repository.

## Lizenz

Noch nicht final festgelegt. Vor Veröffentlichung oder externer Weitergabe muss eine eindeutige Lizenz für dieses Repository ergänzt werden.
