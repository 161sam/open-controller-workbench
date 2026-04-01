# Changelog

All notable changes to Open Controller Workbench are documented in this file.

The format follows a lightweight Keep a Changelog style.

## [Unreleased]

### Added

- compact mini-inspector workflow with clearer context and next-step guidance
- guided placement with target hover, active target, and invalid target feedback
- drag-based placement and direct drag move flows in the 3D view
- improved hover and selection feedback for existing components
- on-object actions for `Duplicate`, `Rotate +90`, and `Mirror`
- manual UX / QA checklist and compact demo flow docs

### Changed

- workflow card, inspector, toolbar, and overlay now use a more consistent visual language
- toolbar command surface was simplified into clearer visible groups
- status and cancellation behavior across placement, drag, and tool switching were polished
- README and core user-facing docs now describe the current workbench UX model more clearly

### Scope limits

- multi-selection remains pragmatic and is not yet a full interaction model
- no on-object delete action is included in the current release scope
- no full CAD gizmos or global interaction state machine are part of this release
- advanced ECAD roundtrip remains outside the current visible v0.x scope

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
