# Open Controller Workbench

Open Controller Workbench (OCW) is a FreeCAD workbench for designing modular MIDI controller hardware with template-driven controller generation, component placement, validation overlays, and export-oriented project data.

Current release target: `v0.1.0`

## What v0.1 includes

- FreeCAD workbench registration through `InitGui.py`
- Controller creation from YAML templates and variants
- FCStd template import:
  - Stage A: FCStd to YAML template
  - Stage B: FCStd-backed base geometry reference
- Template inspector with parameter editing and preset application
- Project parameter roundtrip for reopening and re-parameterizing saved documents
- Interactive placement and drag tools with preview validation and cleanup hardening
- Multi-selection, bulk edit, align/distribute, rotate/mirror, duplicate, and array placement workflows
- Constraint validation, overlay rendering, and export-oriented state generation

## Repository layout

This repository is intentionally structured as a FreeCAD module root. FreeCAD must load the repository root, not only the `ocw_workbench/` Python package.

```text
OpenControllerWorkbench/
├── Init.py
├── InitGui.py
├── ocw_workbench/
├── ocw_kicad/
├── resources/
├── docs/
└── examples/
```

## Installation

### Development install on Linux

```bash
git clone https://github.com/161sam/open-controller-workbench.git
cd open-controller-workbench
pip install -e .
mkdir -p ~/.local/share/FreeCAD/Mod
ln -s "$(pwd)" ~/.local/share/FreeCAD/Mod/OpenControllerWorkbench
```

### Development install for Snap FreeCAD

```bash
git clone https://github.com/161sam/open-controller-workbench.git
cd open-controller-workbench
pip install -e .
mkdir -p ~/snap/freecad/common/Mod
ln -s "$(pwd)" ~/snap/freecad/common/Mod/OpenControllerWorkbench
```

Important:

- Symlink the repository root.
- Do not symlink only `ocw_workbench/`.
- Keep the module directory name stable, for example `OpenControllerWorkbench`.

## First run

1. Start FreeCAD.
2. Open the workbench selector.
3. Select `Open Controller Workbench`.
4. Create a controller from a template or import a template from FCStd.

## Documentation

- [User Guide](docs/user-guide.md)
- [Workflows](docs/workflows.md)
- [Installation](docs/plugin-installation.md)
- [Architecture](docs/architecture.md)
- [Service Architecture](docs/service-architecture.md)
- [State Architecture](docs/state-architecture.md)
- [Geometry Pipeline](docs/geometry-pipeline.md)
- [Development](docs/development.md)
- [Release Checklist](docs/release-checklist.md)
- [Release Process](docs/release-process.md)
- [Release Notes v0.1](RELEASE_NOTES_v0.1.md)
- [Changelog](CHANGELOG.md)

## Testing

Run the unit test suite with:

```bash
.venv/bin/python -m pytest -q
```

For release sanity checks, include the metadata/resource checks:

```bash
.venv/bin/python -m pytest -q tests/unit/test_release_metadata.py
```

## Known limits for v0.1

- The project is still alpha-quality and focused on a productive FreeCAD workflow rather than long-term file-format guarantees.
- Mirror currently uses the existing component rotation path rather than a dedicated mirrored geometry model.
- Pattern generation is intentionally simple and not constraint-aware.
- A final public license selection is still required before an external public release should be published.

## License status

No final project license has been selected yet. This is a release blocker for any public distribution beyond internal or private evaluation.
