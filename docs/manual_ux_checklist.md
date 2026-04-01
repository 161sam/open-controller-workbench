# Manual UX / QA Checklist

Use this checklist for short manual verification of the current OCW workbench UX.

## 1. Start and template setup

1. Open FreeCAD and switch to `Open Controller Workbench`.
2. Create a controller from a visible template such as `pad_grid_4x4` or `encoder_module`.
3. Confirm the dock opens with the compact mini-inspector layout.
4. Confirm the workflow card shows a clear next step instead of a long explanation block.

Expected:

- the workbench loads without hidden modal panels
- the mini-inspector shows current template context
- the toolbar shows the simplified grouped command surface

## 2. Workflow card and inspector context

1. Read the workflow card after template creation.
2. Confirm the next step is understandable without reading long prose.
3. Select one existing component in the 3D view.
4. Confirm the inspector switches to `Selected` context.

Expected:

- the workflow card highlights one primary next action
- the inspector updates on selection, not on hover
- selection context is concise and object-focused

## 3. Suggested addition and guided placement

1. Trigger a suggested addition from the workflow card.
2. Move the cursor across the valid target area.
3. Move the cursor outside the valid target area.
4. Press `ESC`.

Expected:

- placement mode becomes visually obvious in the 3D view
- hover, active target, and invalid target are visually distinct
- the inspector shows targeting context
- `ESC` clears preview, target highlighting, and status text cleanly

## 4. Drag-based placement

1. Start adding a component from the component library or add flow.
2. Press and hold the left mouse button in the 3D view.
3. Move the cursor while still holding the button.
4. Release on a valid position.

Expected:

- the ghost preview follows continuously
- release commits the placement
- the session can continue for repeated placement until `ESC`
- no stale ghost remains after commit

## 5. Normal hover and selection

1. Move the cursor over several existing components without clicking.
2. Click one component.
3. Click empty space.

Expected:

- hover gives subtle pre-selection feedback
- selected state is stronger than hover
- hover clears when leaving a component
- empty-space click does not create inconsistent highlight leftovers

## 6. Drag move of existing components

1. Select a component.
2. Start drag mode.
3. Hover the selected component.
4. Click and drag it to a new position.
5. Release to commit.
6. Repeat and press `ESC` before release.

Expected:

- the selected component is the active drag target
- preview moves without mutating the model until release
- release commits once
- `ESC` cancels cleanly and restores the original position

## 7. On-object actions

1. Select a single component.
2. Confirm small on-object actions appear near the component.
3. Hover each action.
4. Click `Duplicate`.
5. Re-select a single component and click `Rotate`.
6. Re-select a single component and click `Mirror`.

Expected:

- on-object actions only appear for single selection
- they disappear during placement or drag
- action hover is visible but does not deselect the component
- clicking an action executes immediately and keeps selection coherent

## 8. Cancel, escape, and tool switching

1. Start placement, then start drag mode.
2. Start drag mode, then trigger another interactive tool.
3. Start placement and cancel from the inspector button.
4. Start placement and cancel with `ESC`.

Expected:

- only one interactive session remains active at a time
- switching tools clears the previous preview and callbacks
- cancel from UI and `ESC` produce the same visible cleanup result
- no stuck hover, ghost, or action overlay remains

## 9. Toolbar and helpers

1. Confirm the visible toolbar groups remain `Start`, `Add`, `Edit`, `Workflow`, and `View`.
2. Run one workflow helper such as validation overlay or measurements.
3. Return to normal editing.

Expected:

- toolbar surface stays compact
- commands are grouped logically
- helpers do not break selection, inspector, or overlay state

## 10. Final consistency check

1. End all active interactions.
2. Leave one component selected.
3. Then clear selection.

Expected:

- overlay, inspector, and status area agree about the current state
- no stale preview or inline action markers remain
- idle state is visually calm and stable
