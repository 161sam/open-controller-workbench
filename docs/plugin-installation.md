# Installation

## Module root requirement

This repository is the FreeCAD module root.

FreeCAD expects the following structure directly in the module directory:

```text
OpenControllerWorkbench/
├── Init.py
├── InitGui.py
├── ocw_workbench/
├── ocw_kicad/
└── resources/
```

Always link or copy the repository root itself. Do not point FreeCAD only at `ocw_workbench/`.

## Requirements

- Recommended FreeCAD: `1.0` or newer
- `PyYAML` available in the Python environment used by FreeCAD

## Manual Install

This is the primary installation path for end users.

1. Download the release zip or the repository source archive.
2. Extract it so the top-level folder is `OpenControllerWorkbench/`.
3. Copy or move that folder into your FreeCAD `Mod` directory:
   - Linux: `~/.local/share/FreeCAD/Mod`
   - Windows: `%APPDATA%/FreeCAD/Mod`
   - macOS: `~/Library/Preferences/FreeCAD/Mod`
4. Restart FreeCAD.
5. Select `Open Controller Workbench` in the workbench selector.

## Git Clone Install

This path is useful for development or testing the latest source.

```bash
git clone https://github.com/161sam/open-controller-workbench.git OpenControllerWorkbench
cd OpenControllerWorkbench
pip install -e .
mkdir -p ~/.local/share/FreeCAD/Mod
ln -s "$(pwd)" ~/.local/share/FreeCAD/Mod/OpenControllerWorkbench
```

## Snap FreeCAD Install

If your FreeCAD build comes from Snap, use the Snap-specific `Mod` directory:

```bash
git clone https://github.com/161sam/open-controller-workbench.git OpenControllerWorkbench
cd OpenControllerWorkbench
pip install -e .
mkdir -p ~/snap/freecad/common/Mod
ln -s "$(pwd)" ~/snap/freecad/common/Mod/OpenControllerWorkbench
```

## Startup check

1. Start FreeCAD.
2. Open the workbench selector.
3. Select `Open Controller Workbench`.

If installation is correct:

- FreeCAD finds `InitGui.py`
- the workbench appears in the workbench list
- icons load
- templates, variants, and library YAML data are available

## Troubleshooting

### Workbench does not appear

- Confirm the symlink points to the repository root.
- Confirm `Init.py` and `InitGui.py` are directly inside the target directory.
- Restart FreeCAD completely.

### Icons are missing

- Confirm `resources/icons/` exists in the linked module root.
- Confirm only the repository root is linked, not `ocw_workbench/` alone.

### YAML template or library data is missing

- Confirm these paths exist in the linked module root:
  - `ocw_workbench/templates/`
  - `ocw_workbench/variants/`
  - `ocw_workbench/library/`
  - `ocw_workbench/plugins/internal/`
- Confirm FreeCAD loaded the expected module directory.

### Import errors

- Re-run `pip install -e .`
- Verify which Python environment your FreeCAD build uses

## Release Artifacts

The FreeCAD-focused release artifact is:

- `ocw-workbench-v0.1.0-freecad-mod.zip`

Secondary technical artifacts may also exist:

- source distribution
- wheel
