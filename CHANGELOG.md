# Changelog

All notable changes to Open Controller Workbench are documented in this file.

The format follows a lightweight Keep a Changelog style.

## [0.1.0] - 2026-03-27

### Added

- FreeCAD workbench bootstrap and command registration
- Template-based controller creation with variants and presets
- Real 3D component objects in the FreeCAD document tree
- Component groups for structured templates such as pad grids
- PCB reference plane, mounting bosses, and simple screw geometry
- Drag, placement, and selection-driven interaction in the 3D view
- Constraint validation and overlay feedback
- KiCad-oriented export bridge through `ocw_kicad`
- FCStd-assisted template import workflow

### Changed

- README, installation guidance, examples, and release metadata were aligned for the `v0.1.0` release target
- Packaging metadata was aligned to `0.1.0`
- Setuptools distribution metadata now explicitly includes icon resources as install data

### Known limitations

- The project remains alpha-quality and should be treated as an early workflow release
- No final public license file is included yet
- Mirror uses the current rotation-based orientation model
- Duplicate and array placement are intentionally simple and not constraint-aware
- ECAD roundtrip import remains a later step beyond `v0.1.0`
