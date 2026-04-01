# Demo Flow

This is the shortest reliable demo for showing the current OCW interaction maturity.

## Recommended setup

- Start from `pad_grid_4x4` or `encoder_module`
- Keep the 3D view, mini-inspector, and toolbar visible
- Use one suggested addition that has a clear target area, such as `display_header`

## Demo script

### 1. Start from a template

1. Open `Open Controller Workbench`.
2. Create a controller from `encoder_module` or `pad_grid_4x4`.

Show:

- compact mini-inspector
- workflow card with one clear next step
- simplified toolbar groups

### 2. Guided placement

1. Start a suggested addition from the workflow card.
2. Move through the valid target zone.
3. Move briefly into an invalid area.
4. Drag back into the valid area and release to place.

Show:

- placement mode active
- target hover vs active target vs invalid target
- preview following the cursor
- inspector switching into targeting context

### 3. Select and inspect

1. Click an existing component in the 3D view.
2. Pause briefly.

Show:

- idle hover before selection
- strong selected state after click
- inspector switching to `Selected`

### 4. Direct manipulation

1. Start drag mode.
2. Drag the selected component to a nearby position.
3. Release to commit.

Show:

- direct movement in the 3D view
- preview-before-commit behavior
- stable cleanup after release

### 5. On-object action

1. Keep one component selected.
2. Hover the on-object actions.
3. Click `Duplicate` or `Rotate`.

Show:

- on-object actions near the selected component
- no need to leave the 3D view
- selection and inspector staying in sync

### 6. Cancel consistency

1. Start a new placement.
2. Press `ESC`.

Show:

- same cleanup behavior as explicit cancel
- no leftover ghost or stuck mode

## What this demo proves

- OCW is no longer only a dock-driven editor
- workflow, inspector, overlay, and direct interaction now work as one authoring flow
- placement, selection, drag, and on-object actions are stable enough for review and early release demos

## Keep the demo within scope

Do not rely on:

- multi-selection-heavy flows
- plugin-specific advanced tools
- missing on-object delete
- complex CAD-style gizmos
