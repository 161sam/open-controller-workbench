# Open Controller Workbench (OCW)

Design your custom MIDI controllers mechanically and structurally inside FreeCAD.

OCW is a FreeCAD workbench for controller enclosures, top plates, real 3D component placement, PCB reference modeling, and KiCad-oriented export data.

## What Is OCW?

OCW helps you build the mechanical side of a custom controller:

- controller body and top plate
- component placement in the 3D view
- visible components in the FreeCAD tree
- PCB reference and mounting model
- export-ready data for KiCad workflows

It is not a PCB editor. OCW prepares the enclosure, layout intent, and mechanical integration around a future board.

## Features

- Template-based controller creation
- Real 3D component objects in the document tree
- Component groups for structured templates such as pad grids
- PCB reference plane with mounting bosses and screws
- Drag and place interaction directly in the 3D view
- Selection-driven editing, layout commands, and validation overlays
- KiCad export bridge through `ocw_kicad`

## Demo Templates

Start with one of these templates:

- `pad_grid_4x4`
- `encoder_module`
- `fader_strip`

Release examples are listed in [examples/README.md](examples/README.md).

## Installation

OCW must be installed as a FreeCAD module root named `OpenControllerWorkbench`.

### Manual Install

1. Download the release zip or repository source.
2. Extract the folder as `OpenControllerWorkbench`.
3. Copy or move it into your FreeCAD `Mod` directory:
   - Linux: `~/.local/share/FreeCAD/Mod`
   - Windows: `%APPDATA%/FreeCAD/Mod`
   - macOS: `~/Library/Preferences/FreeCAD/Mod`
4. Restart FreeCAD.
5. Select `Open Controller Workbench` from the workbench selector.

### Git Clone Install

```bash
git clone https://github.com/161sam/open-controller-workbench.git OpenControllerWorkbench
cd OpenControllerWorkbench
pip install -e .
mkdir -p ~/.local/share/FreeCAD/Mod
ln -s "$(pwd)" ~/.local/share/FreeCAD/Mod/OpenControllerWorkbench
```

Important:

- Link or copy the repository root.
- Do not link only `ocw_workbench/`.
- Keep the directory name `OpenControllerWorkbench`.

More detail: [docs/plugin-installation.md](docs/plugin-installation.md)

## Requirements

- Recommended FreeCAD: `1.0` or newer
- Python dependency used by the workbench: `PyYAML`
- Operating systems tested in docs and packaging:
  - Linux
  - Windows
  - macOS

## Quick Start

1. Open FreeCAD.
2. Switch to `Open Controller Workbench`.
3. Create a controller from a template such as `pad_grid_4x4`.
4. Inspect the generated `OCW_PCB`, `OCW_Components`, and component groups in the tree.
5. Place or drag components directly in the 3D view.
6. Export the board-oriented data for KiCad.

## Architecture

- `OCW`: controller body, top plate, component model, PCB reference, mounting
- `ocw_kicad`: bridge from OCW data to KiCad-oriented board data
- `KiCad`: PCB, footprints, routing, manufacturing outputs
- `kicadStepUp`: optional ECAD/MCAD synchronization and fit-check workflow

Architecture references:

- [Component Model](docs/architecture/COMPONENT_MODEL.md)
- [Template Model](docs/architecture/TEMPLATE_MODEL.md)
- [PCB Integration Model](docs/architecture/PCB_INTEGRATION_MODEL.md)

## Documentation

- [Documentation Index](docs/README.md)
- [Installation](docs/plugin-installation.md)
- [User Guide](docs/user-guide.md)
- [Workflows](docs/workflows.md)
- [Changelog](CHANGELOG.md)
- [Release Notes v0.1](RELEASE_NOTES_v0.1.md)

## Status

`v0.1.0` — early but functional.

The core workflow is working:

- create from template
- inspect tree and 3D components
- drag and move components
- validate and export

Known limits:

- still an early release with evolving file-format guarantees
- no final public license file is included yet
- advanced ECAD roundtrip remains a later step beyond `v0.1.0`
