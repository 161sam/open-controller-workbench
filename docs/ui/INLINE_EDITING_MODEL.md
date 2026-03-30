# Inline Editing Model

GeneratorWorkbench supports lightweight inline editing directly in the 3D view.

## Goal

Inline editing reduces the need for form-based property changes during common component adjustments.

The MVP focuses on:

- direct position adjustment
- direct rotation adjustment
- one real parameter handle for a supported component family

## Handle Types

Current handle types:

- `move`
- `rotate`
- `cap_width` for button components

Handles are transient overlay items and are only shown for a single selected component when no conflicting placement or drag tool is active.

## Lifecycle

Inline editing uses a small session model:

1. idle
2. hover handle
3. active edit
4. committed
5. cancelled

The controller attaches to the active 3D view and reacts to the same mouse event stream as the other direct-manipulation tools.

## Behavior

### Position

- click move handle
- drag in 3D
- snapping is reused
- `SHIFT` axis lock is reused
- mouse release commits

### Rotation

- click rotate handle
- drag around the component center
- rotation updates live
- mouse release commits

### Parameter

Current MVP parameter:

- button `cap_width`

The parameter handle updates component properties directly and relies on the existing state + sync pipeline for visible geometry refresh.

## Cancel and Tool Switch

- `ESC` restores the original component state
- starting placement or drag cancels inline editing
- document change or close clears the session
- handles never create tree objects

## Non-Goals

This MVP intentionally does not include:

- full gizmo systems
- multi-object inline editing
- complex parametric constraints
- generic editing for every component family
- persistent edit widgets
