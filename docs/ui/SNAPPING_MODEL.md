# Snapping Model

GeneratorWorkbench uses a lightweight snapping model during direct manipulation in the 3D view.

## Scope

This is an MVP interaction feature.

- no persistence
- no solver
- no domain-specific logic
- no document model changes

Snapping is calculated only for active placement and drag tools.

## Snap Types

Supported snap types:

1. `point`
2. `edge`
3. `none`

Priority order:

- `point` beats `edge`
- `edge` beats free movement

## Geometry Source

Snap candidates are derived from the current overlay geometry that is already available to the interaction layer.

This keeps the feature:

- transient
- visual
- decoupled from domain plugins

## Placement Behavior

During placement:

1. mouse position is mapped into project XY
2. optional axis lock is applied
3. snap candidates are evaluated
4. snapped position is written into preview state
5. preview overlay shows the resulting position and snap marker

The committed placement uses the snapped preview position.

## Move Behavior

During drag:

1. raw pointer movement is converted into projected XY
2. component grab offset is preserved
3. optional axis lock is applied
4. snap candidates are evaluated against other overlay items
5. preview and final commit use the snapped result

The dragged component is excluded from its own snap target search.

## Visual Feedback

Snapping stays fully transient.

- point snap: green marker
- edge snap: blue marker
- snap guide: dashed helper line
- axis lock: dashed amber guide

All feedback is rendered through the existing overlay system and never creates tree objects.

## Key Modifiers

Current modifier support:

- `SHIFT`: axis lock

Axis lock is resolved on the dominant XY direction after movement starts.

## Reset Rules

Snap and axis-lock state reset when:

- tool is cancelled
- tool finishes
- active document changes
- 3D view becomes unavailable
- another tool starts

## Non-Goals

The MVP explicitly does not include:

- full-scene geometric solving
- constraint persistence
- rotation snapping
- plugin-specific snapping rules
- advanced alignment chains
