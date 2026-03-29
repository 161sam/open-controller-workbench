# UI Documentation Audit

**Date:** 2026-03-29
**Scope:** Audit of all files in `docs/ui/` against the current codebase and the current main development focus in [`WORKBENCH_INTERACTION_REVIEW.md`](./WORKBENCH_INTERACTION_REVIEW.md).

## 1. Reading Order

Use the UI/workbench documentation in this order:

1. [`WORKBENCH_INTERACTION_REVIEW.md`](./WORKBENCH_INTERACTION_REVIEW.md)
2. [`OCW_DOCKLESS_WORKBENCH_PLAN.md`](./OCW_DOCKLESS_WORKBENCH_PLAN.md)
3. [`FASTENERS_REFERENCE_ANALYSIS.md`](./FASTENERS_REFERENCE_ANALYSIS.md)
4. [`FEATURE_IMPROVEMENT_REVIEW.md`](./FEATURE_IMPROVEMENT_REVIEW.md)
5. [`INTERACTION_REVIEW.md`](./INTERACTION_REVIEW.md)
6. [`DOCK_UI_REDESIGN_SUMMARY.md`](./DOCK_UI_REDESIGN_SUMMARY.md)
7. [`TASK_PANEL_STRATEGY.md`](./TASK_PANEL_STRATEGY.md)
8. [`DOCK_REFACTOR_PLAN.md`](./DOCK_REFACTOR_PLAN.md)

## 2. Current Leadership Model

### Leading documents

- [`WORKBENCH_INTERACTION_REVIEW.md`](./WORKBENCH_INTERACTION_REVIEW.md): main implementation reference and current development priority.
- [`OCW_DOCKLESS_WORKBENCH_PLAN.md`](./OCW_DOCKLESS_WORKBENCH_PLAN.md): secondary strategy document for the same direction, focused on command decoupling and optional dock role.
- [`FASTENERS_REFERENCE_ANALYSIS.md`](./FASTENERS_REFERENCE_ANALYSIS.md): supporting rationale and pattern reference, not an execution plan by itself.

### Reference documents

- [`FEATURE_IMPROVEMENT_REVIEW.md`](./FEATURE_IMPROVEMENT_REVIEW.md): still useful for panel-level cleanup, but no longer a leading roadmap.
- [`INTERACTION_REVIEW.md`](./INTERACTION_REVIEW.md): useful as fixed-issues and state-machine record for direct interaction behavior.
- [`DOCK_UI_REDESIGN_SUMMARY.md`](./DOCK_UI_REDESIGN_SUMMARY.md): useful as historical snapshot of a dock-centered stabilization phase.

### Archived / non-leading strategy

- [`TASK_PANEL_STRATEGY.md`](./TASK_PANEL_STRATEGY.md): still informative, but its dock-first hybrid framing is no longer the current priority.
- [`DOCK_REFACTOR_PLAN.md`](./DOCK_REFACTOR_PLAN.md): no longer a valid primary roadmap.

## 3. Inventory and Status

| File | Purpose / Theme | Current Status | Relevance Now | Relationship to Main Focus | Main Conflict / Note |
|---|---|---|---|---|---|
| `WORKBENCH_INTERACTION_REVIEW.md` | command quality, toolbar role, `IsActive()`, dock role | active | highest | primary source of truth | none; current main focus |
| `OCW_DOCKLESS_WORKBENCH_PLAN.md` | toolbar-first, dock-optional workbench plan | active | high | aligned supporting strategy | broader than current execution scope; should not override main focus ordering |
| `FASTENERS_REFERENCE_ANALYSIS.md` | Fasteners-derived reference patterns | active reference | high | supports the same direction | reference only, not a roadmap |
| `FEATURE_IMPROVEMENT_REVIEW.md` | panel-level UI cleanup review | partially outdated | medium | complementary | several original findings already fixed; not main priority |
| `INTERACTION_REVIEW.md` | lower-level interaction system analysis and fixes | partially outdated reference | medium | adjacent | overlaps with interaction focus, but mostly as implementation history |
| `DOCK_UI_REDESIGN_SUMMARY.md` | summary of dock cleanup phase | partially outdated summary | medium-low | historical context only | implies a settled dock-centered target |
| `TASK_PANEL_STRATEGY.md` | hybrid dock + task panel strategy | partially outdated | low-medium | partly divergent | prioritizes dock-first hybrid model over toolbar/direct-action emphasis |
| `DOCK_REFACTOR_PLAN.md` | dock-first refactor roadmap | obsolete as roadmap | low | conflicts with current focus | assumes dock-first shell as target and contains stale shell description |

## 4. Code-Checked Findings

These points were verified against the current code, not only against the docs.

### Shell and navigation

- The current workbench shell is stepper-based with a `QStackedWidget`, not a `QTabWidget`. Verified in [`workbench.py`](/home/dev/open-controller-workbench/ocw_workbench/workbench.py#L782) and [`workbench.py`](/home/dev/open-controller-workbench/ocw_workbench/workbench.py#L817).
- This makes the shell description in [`DOCK_REFACTOR_PLAN.md`](./DOCK_REFACTOR_PLAN.md) factually stale where it still describes a `QTabWidget`.

### Command layer direction

- `PlaceComponentTypeCommand` exists and is registered in the workbench. Verified in [`workbench.py`](/home/dev/open-controller-workbench/ocw_workbench/workbench.py#L226) and [`workbench.py`](/home/dev/open-controller-workbench/ocw_workbench/workbench.py#L269).
- `_has_controller()` and `_has_selection()` already exist in [`base.py`](/home/dev/open-controller-workbench/ocw_workbench/commands/base.py#L28), so part of the command-hardening work described in the newer documents has already landed.
- At the same time, many commands still call `ensure_workbench_ui(...)`, so dock decoupling is incomplete. Verified by current call sites in [`apply_layout.py`](/home/dev/open-controller-workbench/ocw_workbench/commands/apply_layout.py), [`drag_move_component.py`](/home/dev/open-controller-workbench/ocw_workbench/commands/drag_move_component.py), [`toggle_overlay.py`](/home/dev/open-controller-workbench/ocw_workbench/commands/toggle_overlay.py), and related files.

### Legacy command surface

- `auto_layout.py`, `move_component.py`, and `validate_layout.py` no longer exist under [`ocw_workbench/commands`](/home/dev/open-controller-workbench/ocw_workbench/commands), so documents treating them as current command files are stale.

## 5. Per-Document Analysis

### `WORKBENCH_INTERACTION_REVIEW.md`

- Status: active
- Why: it matches the current high-priority development direction: command quality, toolbar realism, `IsActive()` behavior, removal of weak command duplication, and reducing dock-only behavior.
- Conflicts: none that should demote it.
- Reading rule: when another UI document disagrees with this file on priority or target model, this file wins.

### `OCW_DOCKLESS_WORKBENCH_PLAN.md`

- Status: active supporting strategy
- Why: it extends the same toolbar-first and dock-optional direction.
- Current accuracy: mixed
- Accurate parts:
  - per-type component commands as target
  - decouple commands from dock
  - keep dock as optional context
- Partially outdated parts:
  - some goals are already partly implemented, especially per-type commands and `IsActive()` helpers
  - it still frames several changes as future work that are now partially present in code
- Conflict level with main focus: low
- Reading rule: use as medium-range architecture support, not as the top execution checklist while `WORKBENCH_INTERACTION_REVIEW.md` is actively being implemented.

### `FASTENERS_REFERENCE_ANALYSIS.md`

- Status: active reference
- Why: it provides the rationale behind the current toolbar-first direction.
- Current accuracy: largely still valid because it is comparative, not a fragile implementation checklist.
- Conflict level with main focus: none; it reinforces it.
- Reading rule: use for design intent and transfer rules, not for deciding exact OCW implementation order.

### `FEATURE_IMPROVEMENT_REVIEW.md`

- Status: partially outdated reference
- Why: it still contains useful panel-level cleanup items, but several original findings were already fixed and were minimally corrected.
- Current accuracy: mixed
- Still useful:
  - `set_status()` heuristic issue
  - possible redundancy in `ConstraintsPanel`
  - cleanup around dormant favorite-status labels
- No longer current as original problem statements:
  - orphaned CreatePanel widgets
  - `active_project` hidden in collapsed section
  - inline stylesheet concern
  - `_FavoriteComponentCommand` per-call service concern
- Conflict level with main focus: low
- Reading rule: treat as secondary cleanup backlog only after interaction/command work.

### `INTERACTION_REVIEW.md`

- Status: partially outdated reference
- Why: it documents lower-level interaction fixes and remaining issues well, but it is not the current roadmap authority.
- Current accuracy: mostly good as a history/debugging record.
- Conflict level with main focus: low
- Main overlap:
  - direct interaction lifecycle
  - drag/place behavior
- Reading rule: use for controller-level behavior details and already-fixed issues, not for prioritization.

### `DOCK_UI_REDESIGN_SUMMARY.md`

- Status: partially outdated summary
- Why: it captures a completed dock stabilization phase, but it presents that state as the settled destination.
- Current accuracy: mixed
- Still useful:
  - summary of what the dock cleanup phase achieved
  - test coverage references
- Outdated framing:
  - implies the dock shape is the main strategic endpoint rather than a stable intermediate state
- Conflict level with main focus: medium
- Reading rule: historical summary only.

### `TASK_PANEL_STRATEGY.md`

- Status: partially outdated
- Why: the hybrid model is not completely invalid, but the current main focus is not “dock-first hybrid expansion”; it is command/direct-interaction quality and reducing dock dependence.
- Current accuracy: mixed
- Still useful:
  - task panels as narrow, optional focused flows
  - reuse shared logic instead of duplicating UI logic
- Conflict with main focus:
  - positions the dock as the active UI hub
  - gives future task panels higher strategic weight than the current main focus does
- Reading rule: only as optional future UX exploration after the main interaction work settles.

### `DOCK_REFACTOR_PLAN.md`

- Status: obsolete as primary roadmap
- Why: both its factual shell description and its strategic direction are behind the current state.
- Factual issues:
  - describes a `QTabWidget` shell, while the current shell is stepper + `QStackedWidget`
  - treats removed legacy command files as current
- Strategic conflict:
  - locks the command layer to a dock-first shell
  - conflicts directly with the current effort to make commands more direct and less dock-dependent
- Reading rule: archive/reference only; do not use as a live implementation plan.

## 6. Conflict Matrix

| Document | Conflicts with | Conflict Type | Resolution |
|---|---|---|---|
| `DOCK_REFACTOR_PLAN.md` | `WORKBENCH_INTERACTION_REVIEW.md`, `OCW_DOCKLESS_WORKBENCH_PLAN.md` | strategic + factual | newer interaction/dockless docs take precedence |
| `TASK_PANEL_STRATEGY.md` | `WORKBENCH_INTERACTION_REVIEW.md` | strategic priority | keep only as future secondary exploration |
| `DOCK_UI_REDESIGN_SUMMARY.md` | `WORKBENCH_INTERACTION_REVIEW.md` | framing | treat as historical snapshot, not target state |
| `FEATURE_IMPROVEMENT_REVIEW.md` | current code | factual aging | keep as cleanup reference after corrections |
| `INTERACTION_REVIEW.md` | `WORKBENCH_INTERACTION_REVIEW.md` | roadmap overlap | use as implementation history, not as leading backlog |

## 7. Recommended Roadmap Structure

### Active roadmap

1. `WORKBENCH_INTERACTION_REVIEW.md`
2. `OCW_DOCKLESS_WORKBENCH_PLAN.md`

Interpretation:

- `WORKBENCH_INTERACTION_REVIEW.md` defines what should be executed now.
- `OCW_DOCKLESS_WORKBENCH_PLAN.md` defines the broader architectural direction around the same effort.

### Active reference set

- `FASTENERS_REFERENCE_ANALYSIS.md`
- `INTERACTION_REVIEW.md`
- `FEATURE_IMPROVEMENT_REVIEW.md`

Interpretation:

- These documents support implementation decisions but should not compete with the active roadmap.

### Historical / archive set

- `DOCK_UI_REDESIGN_SUMMARY.md`
- `TASK_PANEL_STRATEGY.md`
- `DOCK_REFACTOR_PLAN.md`

Interpretation:

- Keep them for context.
- Do not use them to overrule current priority or to reopen dock-first direction by accident.

## 8. Minimal Documentation Actions Taken

- Added concise status markers at the top of the UI documents.
- Preserved `WORKBENCH_INTERACTION_REVIEW.md` as the explicit main-focus document.
- Did not rewrite product strategy or alter OCW production code.

## 9. Recommended Next Documentation Maintenance

1. Keep `WORKBENCH_INTERACTION_REVIEW.md` updated as the live implementation checklist while the parallel work continues.
2. After the current interaction package lands, update `OCW_DOCKLESS_WORKBENCH_PLAN.md` so already-completed items are marked as verified instead of still planned.
3. Move `DOCK_REFACTOR_PLAN.md` and `TASK_PANEL_STRATEGY.md` toward explicit archive/reference wording if they stop receiving active maintenance.
4. Keep `FEATURE_IMPROVEMENT_REVIEW.md` as a secondary cleanup backlog only after interaction/command work.
