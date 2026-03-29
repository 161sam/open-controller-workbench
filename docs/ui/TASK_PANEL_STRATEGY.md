# Task Panel Strategy

**Status:** partially outdated, superseded in priority by WORKBENCH_INTERACTION_REVIEW.md

## Current State

The current Workbench UI is centered around a persistent right-side dock created in [`ocw_workbench/gui/docking.py`](../../ocw_workbench/gui/docking.py) and assembled in [`ocw_workbench/workbench.py`](../../ocw_workbench/workbench.py).

The dock is the active UI hub for the main workflows:

- `Create`: template selection, variants, presets, parameters
- `Layout`: auto placement settings, overlay toggles, feedback
- `Components`: selection, editing, quick add, bulk edit
- `Validate`: validation results and issue review
- `Plugins`: installed and remote plugin management

The commands currently registered in the Workbench mostly focus the dock and execute work there:

- `Create Controller` -> focuses `create`
- `Auto Place` -> focuses `layout` and applies immediately
- `Validate Layout` -> focuses `constraints` (Validate tab) and validates there
- `Plugin Manager` -> focuses `plugins`

## Existing Task Panels

Task panels already exist in [`ocw_workbench/gui/taskpanels`](../../ocw_workbench/gui/taskpanels):

- `LayoutTaskPanel`
- `ConstraintsTaskPanel`
- `LibraryTaskPanel`

These task panels are currently thin standalone forms:

- `LayoutTaskPanel`: mixes auto placement and direct component move in one small form
- `ConstraintsTaskPanel`: renders validation as plain text
- `LibraryTaskPanel`: offers quick add from the component library

They are not the primary UX path of the active Workbench. They are better understood as legacy or experimental focused dialogs than as the main interaction model.

## UI Classification

### Better kept in the Dock

These areas benefit from being persistent, always reachable, and non-modal:

- overlay state and view toggles
- current selection details
- quick component edits
- issue summary and passive validation browsing
- plugin status overview

Reason:

- users often need to look at the 3D view and the control surface in parallel
- these areas behave like an inspector or dashboard
- keeping them visible reduces context switching

### Better suited for Task Panels

These workflows are guided, goal-oriented, and have a natural `accept / cancel` shape:

- create controller from template or variant
- import template from FCStd
- remote plugin install / import / export flows
- focused validation review sessions with explicit “review issues” intent
- placement setup when the user wants a deliberate placement run instead of one-click execution

Reason:

- task panels fit short-lived, workflow-driven actions
- they make it easier to present a sequence without overloading the dock
- they align with FreeCAD’s existing task workflow model

## Recommendation

Use a **hybrid architecture**.

### Keep the Dock as the Workbench Home

The dock should remain the persistent control hub for:

- overview
- status
- selection
- quick edits
- overlays
- passive issue browsing

This matches the current command architecture and avoids destabilizing the Workbench.

### Introduce Task Panels only for focused flows

Task panels should be used for workflows that are:

- guided
- short-lived
- commit-oriented
- easier to understand as a step-by-step task than as permanent sidebar content

## Recommended Target Architecture

### Phase 1: Stabilize the Hybrid Model

- Keep the existing dock as the main Workbench shell.
- Treat current task panels as secondary focused surfaces.
- Do not migrate the whole dock into task panels.

### Phase 2: Add focused task panels where they help UX

Priority candidates:

1. **Create Controller Task Panel**
   - Best candidate.
   - Benefits from step-oriented flow: choose template -> variant -> parameters -> create.
   - The dock can still show current project, recents, and quick create status.

2. **Plugin Operations Task Panel**
   - Good candidate for remote install, ZIP import/export, and registry-driven flows.
   - The dock should remain the plugin overview and status surface.

3. **Layout Setup Task Panel**
   - Useful as an optional advanced mode for explicit placement runs.
   - The dock should still keep fast overlay toggles and layout summary.

4. **Validation Review Task Panel**
   - Optional candidate, not primary.
   - Only worthwhile if it becomes a real issue-review workflow with focus/jump/next actions.
   - The current dock is already the right home for persistent findings and quick revalidation.

### Phase 3: Share UI building blocks

If task panels are expanded, they should reuse the same panel widgets or shared sub-builders as the dock where possible.

The desired direction is:

- shared panel logic
- thin dock container
- thin task-panel container

Not:

- two separate UI implementations with duplicated behavior

## Concrete Decisions

### Create Controller

**Move toward hybrid.**

- Keep the dock `Create` tab for always-available browsing and quick creation.
- Add a future focused task panel for guided controller creation.

### Plugin Manager

**Use hybrid.**

- Keep plugin overview in the dock.
- Move remote install/import/export into focused task panels if complexity grows.

### Validate

**Keep primarily in the dock for now.**

- The dock is better for persistent issue visibility and repeated validation.
- A task panel only becomes valuable once issue review supports step-through navigation and focus actions well.

### Layout

**Use hybrid, but dock-first.**

- One-click `Auto Place` fits the dock and toolbar well.
- A future task panel can support advanced placement sessions.

## Low-Risk Migration Plan

1. Keep all primary commands dock-first.
2. When adding a new task panel, limit it to one workflow.
3. Reuse existing panel logic instead of cloning service calls and UI rules.
4. Only migrate a workflow once the task panel is clearly better than the dock for that specific use case.

## Immediate Follow-up Work

- design a `CreateControllerTaskPanel` as the first serious hybrid candidate
- define shared sub-widgets for task-panel reuse from `CreatePanel` and `PluginManagerPanel`
- decide whether `ApplyLayout` should stay instant-action or also offer `Open Layout Task`
- postpone any full validation-panel migration until issue navigation is stronger
