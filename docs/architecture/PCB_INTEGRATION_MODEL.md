# OCW PCB Integration Model

## Responsibility Split

- `OCW`
  - owns the controller enclosure model
  - defines top plate cutouts, body dimensions, mounting-hole positions, and component placement logic
  - carries the internal board reference plane used to align enclosure, components, and future ECAD export
- `ocw_kicad`
  - imports OCW-generated board/layout data into KiCad
  - creates the board outline, mounting holes, footprints, and keepout geometry in pcbnew
  - acts as the translation layer between OCW's controller model and KiCad's native board model
- `KiCad`
  - owns the real PCB
  - owns footprints, copper, routing, net classes, and manufacturing output
- `kicadStepUp`
  - synchronizes KiCad board data and 3D component models with FreeCAD
  - supports board-outline exchange, 3D board inspection, and ECAD/MCAD fit checking

## Transfer Rules

- OCW should natively model enclosure mechanics, cutout-driving placement, and the controller-side board reference.
- OCW should export a board intent model to `ocw_kicad`, not a full PCB implementation.
- KiCad should remain the source of truth for final board layout, footprints, routing, and fabrication artifacts.
- kicadStepUp should be used for ECAD/MCAD synchronization and fit validation, not as a replacement for OCW's own controller model.

## Current OCW Document Model

- `OCW_Controller`
- `OCW_Generated`
  - `OCW_ControllerBody`
  - `OCW_TopPlate` or `OCW_TopPlateCut`
  - `OCW_PCB`
  - `OCW_Components`
  - `OCW_Mounting`

## Mechanical Relationships

- The top plate is the user-facing interface plane.
- The PCB is an internal support and reference plane defined by:
  - `pcb_thickness`
  - `pcb_inset`
  - `pcb_standoff_height`
- Components no longer conceptually sit only on the top plate.
  - Their generated solids now span from the PCB top face toward the top plate.
  - Their cutouts still drive top plate openings.
- Mounting bosses are generated from controller `mounting_holes`.
  - They rise from the body floor to the PCB underside.
  - They provide the body-side support model for PCB fastening.
- Simple screw geometry is generated from the same mounting-hole map.
  - `OCW_Screw_<id>` represents a simplified M2/M3 fastener body plus head.
  - The fastener preset is derived from the hole diameter unless `controller.mounting.fastener_type` or per-hole overrides specify otherwise.
- Optional boss counterbores can be defined per hole or through controller mounting defaults.

## OCW -> KiCad Data Boundary

OCW currently produces:

- board width / height / corner radius
- mounting hole positions and diameters
- component footprint placement intent
- keepout geometry
- PCB stack-up metadata
- mounting hardware metadata
- roundtrip import hints

That data is consumed by `ocw_kicad`, which then creates:

- KiCad board outline
- mounting hole footprints
- component footprints
- keepout items

The exported layout now also carries three supporting sections:

- `mechanical_stackup`
  - PCB thickness, inset, standoff height, and resolved PCB reference placement
- `mounting`
  - fastener/boss metadata derived from controller mounting holes
- `roundtrip`
  - import strategy and mapping hints for a later KiCad/StepUp return path

## What Belongs Where

### In OCW

- enclosure geometry
- top plate geometry and cutouts
- mechanical stack-up
- component placement intent
- PCB reference plane and mounting support geometry
- simplified fastener geometry
- minimal mechanical validation:
  - PCB vs body cavity
  - component bottom keepout vs PCB support area

### In ocw_kicad

- board-import bridge logic
- KiCad-specific object creation
- mapping from OCW component intent to KiCad footprints

### In KiCad

- final PCB shape and edits
- footprint instances and pad geometry
- routing and electrical design
- fabrication exports

### In kicadStepUp

- import/export between KiCad board data and FreeCAD
- STEP model alignment
- board / enclosure fit validation
- ECAD/MCAD iteration support

## v0.1 Status

Implemented:

- PCB reference object in the FreeCAD document
- controller parameters for PCB thickness, inset, and standoff height
- component solids anchored to the PCB/top-plate stack-up
- boss/standoff geometry from mounting holes
- simplified screw/fastener geometry in `OCW_Mounting`
- KiCad export metadata for mechanical stack-up, mounting, and roundtrip preparation
- minimal mechanical validation for PCB/body stack height and component support area vs PCB
- roundtrip import descriptor hook in `ocw_kicad`

Not finished yet:

- richer board connector / cable clearance checks
- direct board import back from KiCad/StepUp into the OCW document
- richer board-specific grouping or per-component electrical attachment metadata
- detailed fastener catalogue beyond the current simple M2/M3 presets
