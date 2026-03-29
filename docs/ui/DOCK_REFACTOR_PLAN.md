# Dock Refactor Plan

**Status:** obsolete as primary roadmap, superseded by WORKBENCH_INTERACTION_REVIEW.md and OCW_DOCKLESS_WORKBENCH_PLAN.md

## Scope

This document captures the **current technical state** of the Open Controller Workbench dock UI and defines a **low-risk refactor sequence** for the next implementation steps.

It is intentionally limited to the existing FreeCAD workbench shell and related UI plumbing:

- dock creation and lifecycle
- workbench shell composition
- panel builders and common Qt helpers
- command-to-UI activation paths
- icon resource coverage
- UI-focused test coverage

This is **not** a redesign spec and **not** a task-panel migration plan. For task-panel direction, see [TASK_PANEL_STRATEGY.md](./TASK_PANEL_STRATEGY.md).

## Current State

### 1. Dock creation and lifecycle

The persistent right-side dock is created and managed in [`ocw_workbench/gui/docking.py`](../../ocw_workbench/gui/docking.py):

- `create_or_reuse_dock(...)`
- `find_existing_dock(...)`
- `focus_dock(...)`
- `remove_dock(...)`
- `_tabify_with_existing_dock(...)`

Current behavior:

- uses a stable dock object name: `OCWWorkbenchDock`
- reuses an existing dock when possible
- docks on the right side by default
- tabifies with an existing right-side dock when FreeCAD/Qt allows it
- applies a minimum width hint (`380`) and base size hint (`440 x 720`)

### 2. Workbench shell composition

The main shell is assembled in [`ocw_workbench/workbench.py`](../../ocw_workbench/workbench.py):

- `ProductWorkbenchPanel.__init__(...)`
- `ProductWorkbenchPanel._build_shell(...)`
- `ProductWorkbenchPanel._mount_panels(...)`
- `ProductWorkbenchPanel.focus_panel(...)`
- `ensure_workbench_ui(...)`

Current structure:

- compact header with:
  - `title`
  - `context_summary`
- one primary navigation surface:
  - `QTabWidget` with tabs `Create`, `Layout`, `Components`, `Validate`, `Plugins`
- footer with:
  - `status`
  - `overlay_status`

The primary dock navigation is now explicitly centralized in [`ocw_workbench/workbench.py`](../../ocw_workbench/workbench.py) via `_PRIMARY_DOCK_TABS`, `_PRIMARY_DOCK_TAB_INDEX`, and `_PRIMARY_DOCK_TAB_LABELS` so the shell, focus logic, and tests all use the same single-flow contract.

The current single-flow shell is already represented in code in `_build_shell(...)`, especially around:

- header creation
- `tabs.addTab(...)`
- `_tab_page(...)`
- `_update_context_summary(...)`

### 3. Panel mounting

Mounted panels:

- [`ocw_workbench/gui/panels/create_panel.py`](../../ocw_workbench/gui/panels/create_panel.py)
- [`ocw_workbench/gui/panels/info_panel.py`](../../ocw_workbench/gui/panels/info_panel.py)
- [`ocw_workbench/gui/panels/layout_panel.py`](../../ocw_workbench/gui/panels/layout_panel.py)
- [`ocw_workbench/gui/panels/components_panel.py`](../../ocw_workbench/gui/panels/components_panel.py)
- [`ocw_workbench/gui/panels/constraints_panel.py`](../../ocw_workbench/gui/panels/constraints_panel.py)
- [`ocw_workbench/gui/panels/plugin_manager_panel.py`](../../ocw_workbench/gui/panels/plugin_manager_panel.py)

Mount rules in `_mount_panels(...)`:

- `Create` tab contains a vertical splitter:
  - `CreatePanel`
  - `InfoPanel`
- `Layout`, `Components`, `Validate`, `Plugins` each mount a single panel widget

### 4. Shared panel/UI helpers

The common UI builder surface lives in [`ocw_workbench/gui/panels/_common.py`](../../ocw_workbench/gui/panels/_common.py).

Important shared helpers:

- `build_panel_container(...)`
- `build_group_box(...)`
- `build_collapsible_section(...)`
- `build_form_layout(...)`
- `wrap_widget_in_scroll_area(...)`
- `create_row_widget(...)`
- `add_layout_content(...)`
- `set_button_role(...)`
- `set_size_policy(...)`
- `configure_text_panel(...)`
- `configure_combo_box(...)`

These helpers are now the main abstraction boundary for:

- spacing and margins
- `QScrollArea` wrapping
- `QSizePolicy`
- widget-vs-layout insertion safety

### 5. Command activation paths

Most primary commands already focus the dock via `ensure_workbench_ui(...)`:

- [`create_from_template.py`](../../ocw_workbench/commands/create_from_template.py) -> `focus="create"`
- [`apply_layout.py`](../../ocw_workbench/commands/apply_layout.py) -> `focus="layout"`
- [`validate_constraints.py`](../../ocw_workbench/commands/validate_constraints.py) -> `focus="constraints"`
- [`open_plugin_manager.py`](../../ocw_workbench/commands/open_plugin_manager.py) -> `focus="plugins"`
- [`add_component.py`](../../ocw_workbench/commands/add_component.py) -> `focus="components"`
- [`select_component.py`](../../ocw_workbench/commands/select_component.py) -> `focus="components"`
- overlay/view commands also route back into the dock shell

There are still legacy or side-surface command paths:

- [`auto_layout.py`](../../ocw_workbench/commands/auto_layout.py) opens `LayoutTaskPanel`
- [`move_component.py`](../../ocw_workbench/commands/move_component.py) opens a task panel path
- [`validate_layout.py`](../../ocw_workbench/commands/validate_layout.py) still references `constraints_taskpanel`
- [`open_component_palette.py`](../../ocw_workbench/commands/open_component_palette.py) opens a separate palette dock

This means the shell is already dock-first, but the command layer is not yet fully consolidated around that model.

### 6. Icon handling

Workbench icon handling is split between:

- [`ocw_workbench/gui/runtime.py`](../../ocw_workbench/gui/runtime.py)
  - `icon_path(...)`
  - `component_icon_path(...)`
- [`ocw_workbench/commands/base.py`](../../ocw_workbench/commands/base.py)
  - `BaseCommand.ICON_NAME = "default"`
  - `BaseCommand.resources(...)`

Current state:

- most actively registered workbench commands set `ICON_NAME` explicitly
- `resources/icons/` already contains concrete SVGs for the main dock/tool commands
- `icon_path(...)` still silently falls back to `default.svg` for missing icons

Concrete gaps or fallback-prone cases:

- [`ocw_workbench/commands/create_from_schema.py`](../../ocw_workbench/commands/create_from_schema.py) has no `GetResources()` and no icon contract
- [`ocw_workbench/commands/validate_project.py`](../../ocw_workbench/commands/validate_project.py) has no `GetResources()` and no icon contract
- [`ocw_workbench/workbench.py`](../../ocw_workbench/workbench.py) `_FavoriteComponentCommand.GetResources()` intentionally falls back to `default.svg` when a favorite slot is empty
- any future command inheriting `BaseCommand` without overriding `ICON_NAME` will silently use `default.svg`

### 7. Existing UI tests

Current UI-focused tests already cover important pieces:

- [`tests/unit/test_qt_compat.py`](../../tests/unit/test_qt_compat.py)
  - Qt binding fallback behavior
  - widget-vs-layout safety via `add_layout_content(...)`
  - `wrap_widget_in_scroll_area(...)`
  - dock tabification in `create_or_reuse_dock(...)`
  - tab-shell smoke for `ProductWorkbenchPanel`
  - fallback behavior when the plugin panel fails
- [`tests/unit/test_workbench_v2.py`](../../tests/unit/test_workbench_v2.py)
  - panel orchestration through `ProductWorkbenchPanel`
  - create/layout/components/validate flow
  - context summary behavior
  - panel tooltips and action labels
- [`tests/unit/test_command_resources.py`](../../tests/unit/test_command_resources.py)
  - verifies pixmaps exist for a selected set of registered commands
- [`tests/unit/test_component_favorites_toolbar.py`](../../tests/unit/test_component_favorites_toolbar.py)
  - validates component icon usage for favorite-toolbar slots

The coverage is useful, but still incomplete for a larger dock refactor.

## Pain Points

### A. High priority

#### 1. Command layer still leaks legacy UI surfaces

The shell itself is already tab-based and single-flow, but some commands still bypass it with task panels or alternate surfaces:

- [`auto_layout.py`](../../ocw_workbench/commands/auto_layout.py)
- [`move_component.py`](../../ocw_workbench/commands/move_component.py)
- [`validate_layout.py`](../../ocw_workbench/commands/validate_layout.py)

This is the main remaining structural inconsistency.

#### 2. Icon fallback policy is still too implicit

`BaseCommand` plus `icon_path(...)` makes missing icons non-failing by default.

That is convenient short-term, but it hides regressions:

- a new command can silently ship with `default.svg`
- tests only cover a curated subset of commands

#### 3. Panel builder usage is centralized, but not yet fully normalized

The common helper layer is much better than before, but the panel files still mix:

- plain labels
- group-box sections
- form sections
- widget rows
- ad hoc section composition

The code is stable enough to work with, but still not fully uniform.

### B. Medium priority

#### 4. Layout stability depends on conventions, not strict enforcement

Recent fixes established better defaults in `_common.py`, but there is still no explicit guardrail that prevents:

- new fixed-height regressions
- direct raw `QScrollArea` misuse outside the shared helper path
- inconsistent panel-level spacing in future edits

#### 5. Create tab currently multiplexes two surfaces

`CreatePanel` and `InfoPanel` are intentionally combined in one vertical splitter inside the `Create` tab.

That is valid, but it is the one tab that still acts as a two-surface workspace. Any future dock simplification needs to treat this area carefully.

### C. Later

#### 6. Legacy task panels remain under-defined

The files under [`ocw_workbench/gui/taskpanels`](../../ocw_workbench/gui/taskpanels) are not the primary UX path anymore, but they still exist and still influence command behavior.

They should either:

- stay as focused secondary flows with a clear contract
- or be reduced further so they do not drift from the dock implementation

## Target UI Architecture

The target architecture for the next implementation steps should remain:

- **dock-first**
- **single-flow**
- **panel-based**
- **shared-builder-backed**

### Shell

Keep the current shell direction in [`ocw_workbench/workbench.py`](../../ocw_workbench/workbench.py):

- compact header
- one `QTabWidget`
- one active panel surface per tab
- compact footer/status area

### Primary flow

The primary workbench flow should remain:

1. `Create`
2. `Layout`
3. `Components`
4. `Validate`
5. `Plugins`

### Command contract

Primary workbench commands should:

- open or focus the dock
- activate the matching tab
- execute the action there when appropriate

Task panels should remain explicitly secondary and limited to narrow workflow cases only.

### Shared UI contract

Panel composition should continue to converge on `_common.py` helpers for:

- layout containers
- form rows
- group sections
- collapsible sections
- scroll wrapping
- size policy defaults

## Refactor Sequence

### Step 1. High priority: lock the command layer to the dock-first shell

Files:

- [`ocw_workbench/commands/auto_layout.py`](../../ocw_workbench/commands/auto_layout.py)
- [`ocw_workbench/commands/move_component.py`](../../ocw_workbench/commands/move_component.py)
- [`ocw_workbench/commands/validate_layout.py`](../../ocw_workbench/commands/validate_layout.py)
- [`ocw_workbench/workbench.py`](../../ocw_workbench/workbench.py)

Actions:

- review every active command that still opens a task panel or alternate UI surface
- decide command-by-command whether it should:
  - focus the dock tab
  - execute immediately in the dock-backed panel
  - remain explicitly secondary
- remove ambiguous overlap between dock-first and task-panel-first behavior

Why first:

- this gives the dock a single technical activation model
- it reduces future UX drift without a large UI rewrite

### Step 2. High priority: harden icon contracts

Files:

- [`ocw_workbench/commands/base.py`](../../ocw_workbench/commands/base.py)
- [`ocw_workbench/gui/runtime.py`](../../ocw_workbench/gui/runtime.py)
- [`ocw_workbench/commands/`](../../ocw_workbench/commands)
- [`tests/unit/test_command_resources.py`](../../tests/unit/test_command_resources.py)

Actions:

- enumerate all registered workbench commands from `OpenControllerWorkbench.Initialize(...)`
- verify every registered command has an explicit icon name with a matching SVG
- decide how to treat legacy commands without `GetResources()`
- extend tests so missing command icons fail earlier

Why second:

- icon consistency is low-risk to fix
- it closes a recurring regression class quickly

### Step 3. High priority: normalize panel builder usage

Files:

- [`ocw_workbench/gui/panels/create_panel.py`](../../ocw_workbench/gui/panels/create_panel.py)
- [`ocw_workbench/gui/panels/layout_panel.py`](../../ocw_workbench/gui/panels/layout_panel.py)
- [`ocw_workbench/gui/panels/components_panel.py`](../../ocw_workbench/gui/panels/components_panel.py)
- [`ocw_workbench/gui/panels/constraints_panel.py`](../../ocw_workbench/gui/panels/constraints_panel.py)
- [`ocw_workbench/gui/panels/info_panel.py`](../../ocw_workbench/gui/panels/info_panel.py)
- [`ocw_workbench/gui/panels/plugin_manager_panel.py`](../../ocw_workbench/gui/panels/plugin_manager_panel.py)
- [`ocw_workbench/gui/widgets/`](../../ocw_workbench/gui/widgets)
- [`ocw_workbench/gui/panels/_common.py`](../../ocw_workbench/gui/panels/_common.py)

Actions:

- map repeated section patterns panel by panel
- migrate obvious ad hoc layout code to existing shared helpers
- keep refactors local and behavior-preserving
- avoid new helper proliferation unless a pattern is used in multiple panels

Why third:

- this improves maintainability without changing the shell architecture
- it lowers the risk of future widget/layout regressions

### Step 4. Medium priority: add explicit layout regression checks

Files:

- [`tests/unit/test_qt_compat.py`](../../tests/unit/test_qt_compat.py)
- [`tests/unit/test_workbench_v2.py`](../../tests/unit/test_workbench_v2.py)

Actions:

- add tests for shell spacing/structure assumptions where practical
- add tests for command-to-tab focus behavior
- add smoke tests for panel builders most likely to regress

### Step 5. Later: decide the steady-state role of legacy task panels

Files:

- [`ocw_workbench/gui/taskpanels/`](../../ocw_workbench/gui/taskpanels)
- [`docs/ui/TASK_PANEL_STRATEGY.md`](./TASK_PANEL_STRATEGY.md)

Actions:

- define whether each task panel remains:
  - supported secondary UX
  - legacy compatibility surface
  - deletion candidate

## Risks

### 1. Dock and command behavior can drift apart

If command entry points continue to mix dock-first and task-panel-first behavior, users and tests will see inconsistent flows even if the dock shell itself is correct.

### 2. Shared helper refactors can create broad regressions

`_common.py` is now a central dependency. Small helper changes can affect many panels at once.

Mitigation:

- keep changes incremental
- add targeted smoke tests before broad helper rewrites

### 3. FreeCAD/Qt behavior is only partially reproducible in headless tests

Dock tabification, real docking behavior, and some widget sizing edge cases depend on live FreeCAD/Qt runtime behavior.

Mitigation:

- keep unit tests focused on builder contracts and command routing
- use real FreeCAD checks only for thin verification passes

### 4. Create tab refactors can easily overreach

Because `Create` currently combines `CreatePanel` and `InfoPanel`, “simplification” work there can accidentally change working behavior rather than structure.

Mitigation:

- treat `Create` as a special case
- refactor by containment, not by merging unrelated logic

## Acceptance Criteria

The dock refactor effort should be considered successful only when all of the following are true:

1. The dock remains the primary workbench UI surface.
2. Active commands route consistently into the dock unless a task panel is intentionally justified.
3. Registered command icons are explicit and verified, not silently relying on `default.svg`.
4. Panel builders use shared helper contracts consistently enough that widget/layout regressions are harder to reintroduce.
5. Existing workbench functionality remains intact:
   - create
   - layout
   - components
   - validate
   - plugins
6. UI-focused tests cover:
   - dock shell smoke
   - command resource/icon coverage
   - command focus paths
   - shared builder contracts

## Test Strategy

### Keep

- [`tests/unit/test_qt_compat.py`](../../tests/unit/test_qt_compat.py)
- [`tests/unit/test_workbench_v2.py`](../../tests/unit/test_workbench_v2.py)
- [`tests/unit/test_command_resources.py`](../../tests/unit/test_command_resources.py)
- [`tests/unit/test_component_favorites_toolbar.py`](../../tests/unit/test_component_favorites_toolbar.py)

### Add next

#### 1. Command focus path tests

Target:

- confirm the main commands route to the expected dock tab via `ensure_workbench_ui(..., focus=...)`

Priority:

- high

#### 2. Registered-command icon coverage

Target:

- validate the full set of commands added in `OpenControllerWorkbench.Initialize(...)`, not just a curated subset

Priority:

- high

#### 3. Panel-builder smoke tests

Target:

- instantiate the main panels and assert the widget shell builds without helper misuse

Priority:

- medium

#### 4. Optional live FreeCAD verification pass

Target:

- thin manual or scripted verification that the dock attaches, focuses, and tabifies correctly inside a real FreeCAD session

Priority:

- later

## Affected Files Summary

Primary implementation files for the next refactor steps:

- [`ocw_workbench/workbench.py`](../../ocw_workbench/workbench.py)
- [`ocw_workbench/gui/docking.py`](../../ocw_workbench/gui/docking.py)
- [`ocw_workbench/gui/panels/_common.py`](../../ocw_workbench/gui/panels/_common.py)
- [`ocw_workbench/gui/panels/create_panel.py`](../../ocw_workbench/gui/panels/create_panel.py)
- [`ocw_workbench/gui/panels/layout_panel.py`](../../ocw_workbench/gui/panels/layout_panel.py)
- [`ocw_workbench/gui/panels/components_panel.py`](../../ocw_workbench/gui/panels/components_panel.py)
- [`ocw_workbench/gui/panels/constraints_panel.py`](../../ocw_workbench/gui/panels/constraints_panel.py)
- [`ocw_workbench/gui/panels/info_panel.py`](../../ocw_workbench/gui/panels/info_panel.py)
- [`ocw_workbench/gui/panels/plugin_manager_panel.py`](../../ocw_workbench/gui/panels/plugin_manager_panel.py)
- [`ocw_workbench/gui/taskpanels/`](../../ocw_workbench/gui/taskpanels)
- [`ocw_workbench/commands/`](../../ocw_workbench/commands)

Primary tests:

- [`tests/unit/test_qt_compat.py`](../../tests/unit/test_qt_compat.py)
- [`tests/unit/test_workbench_v2.py`](../../tests/unit/test_workbench_v2.py)
- [`tests/unit/test_command_resources.py`](../../tests/unit/test_command_resources.py)
- [`tests/unit/test_component_favorites_toolbar.py`](../../tests/unit/test_component_favorites_toolbar.py)
