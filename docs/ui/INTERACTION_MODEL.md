# Interaction Model

GeneratorWorkbench uses direct manipulation in the 3D view as the primary interaction model for placement and movement tools.

## Principles

- Toolbar commands start tools directly.
- Mouse movement updates a visual preview before any commit.
- Left click commits the current action in the 3D view.
- `ESC` always cancels the active tool.
- Starting a new tool cancels the previous tool first.
- Preview state must never create permanent document tree objects.

## Tool Lifecycle

The interaction stack is split into two layers:

- `PlacementController` is the lightweight tool entry point used by commands.
- `ViewPlaceController` and `ViewDragController` own the actual 3D view event loop.

The shared lifecycle is:

1. `activate`
2. `on_mouse_move`
3. `on_click`
4. `finish` or `cancel`

`ToolManager` guarantees that only one direct-manipulation tool is active at a time.

## Placement Flow

Placement commands call `PlacementController.start_component_placement(...)`.

The placement tool then:

1. starts the view-bound placement controller
2. binds mouse callbacks to the active 3D view
3. maps screen coordinates into project XY coordinates
4. writes preview state through `InteractionService`
5. refreshes the overlay renderer
6. commits the component through `ControllerService.add_component(...)` on click

After commit, the tool remains active for repeated placement until `ESC` or tool switch.

## Move Flow

Move commands call `PlacementController.start_move_mode(...)`.

The drag tool then:

1. highlights selectable components under the cursor
2. locks to the selected component when one is already selected
3. starts a drag session on mouse down
4. updates preview position on mouse move
5. commits the move through `ControllerService.move_component(...)` on mouse release

The move tool ends after a successful commit or when cancelled.

## Preview Model

Preview state is stored as transient document metadata and rendered through the overlay layer.

- no permanent FreeCAD object is created for preview
- preview is cleared on commit, cancel, document change, and tool switch
- preview validation controls whether commit is allowed

## Selection Sync

3D interaction and project selection share the same source of truth:

- hover and drag targeting update interaction settings
- committed selection changes flow through controller state and FreeCAD selection sync

This keeps direct manipulation compatible with the existing document synchronization pipeline.

## Cancel and Tool Switch

- `ESC` cancels the active tool
- starting a new tool cancels the previous one first
- losing the active 3D view cancels the running tool
- document change or close cancels any active interaction

These rules prevent hanging tool state and keep the workbench predictable.
