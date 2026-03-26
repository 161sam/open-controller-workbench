# Geometry Pipeline

## Goal

Keep controller geometry generation modular and testable before a later transition to a more parametric FreeCAD feature stack.

## Current Build Stages

Geometry generation is coordinated by `ControllerBuilder`.

### 1. Surface Resolution

- `resolve_surface()`

Resolves the controller surface primitive from controller data.

### 2. Body Planning

- `plan_body_build()`
- `_build_body_shape()`

The body pipeline is split into:

- outer body prism
- optional cavity/shell surface
- cavity offset and cavity height

The build plan exposes these values before document feature creation.

### 3. Top Plate Planning

- `plan_top_plate_build()`
- `_build_top_plate_shape()`

The top plate pipeline is split into:

- top plate prism
- optional lid tongue surface
- tongue offset and tongue height

This stage now also supports an optional custom base source:

- `controller.geometry.base.type = custom_fcstd`
- the builder resolves the FCStd reference only when the top plate base shape is built
- existing controller surface data remains the logical source for bounds, layout, preview, and validation workflows
- existing templates without `controller.geometry.base` still use the standard prism-based top plate path

### 4. Cutout Primitive Collection

- `build_cutout_primitives()`

Collects normalized cutout metadata for diagnostics, overlay, manufacturing, and boolean preparation.

### 5. Boolean Planning

- `plan_cutout_boolean()`
- `_build_cutout_tool_shape()`
- `_cutout_diagnostics()`

This stage separates:

- tool metadata and placement
- cutout diagnostics
- shape construction for the final boolean cut

### 6. Document Feature Creation

- `build_body()`
- `build_top_plate()`
- `apply_cutouts()`

These methods remain the compatibility layer used by document sync.

## Design Rule

Prefer planning and primitive preparation first, then boolean execution, and finally document feature assignment.
This keeps later migration paths toward more parametric FreeCAD-native features open without changing current behavior.

## Custom FCStd Base Geometry

`custom_fcstd` is a narrow extension point, not a full geometry-architecture replacement.

- The template stores the source `FCStd` filename, target object or face reference, origin metadata, and optional rotation metadata.
- A dedicated loader service opens the referenced FCStd document temporarily, resolves the requested object or face, builds a shape, applies origin offset and rotation, and closes the temporary document again.
- The current integration point is the top-plate base geometry path. This keeps Stage B compatible with the existing staged builder and avoids invasive changes to body generation, sync, or overlay state.
- Cutout application still happens on the resulting built shape through the existing boolean workflow.
- Failure cases such as missing files, missing target objects, or invalid references are surfaced as explicit errors. The temporary FCStd document is always closed on the way out.
