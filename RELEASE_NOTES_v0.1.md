# Release Notes v0.1.0

Open Controller Workbench is a FreeCAD workbench for designing custom MIDI controller hardware mechanically and structurally.

`v0.1.0` is the first public-facing release candidate for the core OCW workflow:

- create a controller from a template
- inspect real 3D components in the tree
- place and drag components in the 3D view
- model PCB reference and mounting
- export board-oriented data toward KiCad

## Highlights

- Template-based controller creation
- Real component objects and component groups in the FreeCAD document tree
- PCB reference plane with mounting bosses and simple screws
- Selection-driven placement and drag workflow
- Constraint and overlay feedback for layout work
- KiCad bridge through `ocw_kicad`

## Who This Is For

- makers building custom MIDI controllers
- hardware developers shaping enclosures before PCB completion
- FreeCAD users who want a controller-focused workbench instead of a generic CAD flow

## Install

- Download the FreeCAD module zip or source
- Put `OpenControllerWorkbench` into your FreeCAD `Mod` directory
- Start FreeCAD and switch to `Open Controller Workbench`

See:

- [README](README.md)
- [Installation guide](docs/plugin-installation.md)

## Current Status

Early but functional.

Core workflow is ready for evaluation and demos, but the project is still evolving and advanced ECAD roundtrip remains a later step.
