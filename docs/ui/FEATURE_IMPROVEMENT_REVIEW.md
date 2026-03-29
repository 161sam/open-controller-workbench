# Feature Improvement Review — Open Controller Workbench UI

**Status:** partially outdated reference

**Date:** 2026-03-28
**Scope:** Existing features only. No new features. Stability, UX, and maintainability.

---

## 1. What Is Already Good

- **Stepper shell** ([workbench.py:681](../../ocw_workbench/workbench.py)): clean `QStackedWidget` base, clear step buttons, good shell ↔ panel separation.
- **Service injection** in all panels: consistent constructor pattern with sensible defaults.
- **`_common.py`** ([panels/_common.py](../../ocw_workbench/gui/panels/_common.py)): solid UI utility layer — `configure_layout`, `set_size_policy`, Fallback classes for non-Qt environments.
- **Overlay system** (Coin3D via `OverlayRenderer`): FreeCAD-correct render path selection.
- **All panels have fallback dicts**: testable without FreeCAD/Qt.
- **`ConstraintsPanel`**: summary cards, QTreeWidget with 4 columns — structurally clear.
- **`LayoutPanel`**: Settings form + Primary Action + collapsible Helpers — good layering.
- **`SetMinAndMaxSize` constraint**: set consistently, prevents layout explosions.
- **`wrap_widget_in_scroll_area()`**: used consistently in all panels.
- **Stylesheet scope**: limited to `OCWWorkbenchShell` — no global CSS bleed.

---

## 2. Biggest Problems

### VERIFIED: CreatePanel orphaned widget bug is mostly fixed

**File:** [`create_panel.py:901–922`](../../ocw_workbench/gui/panels/create_panel.py)

The previous bug is no longer present for the main controls. The current code adds row widgets and summaries to the form:

```python
selection_form.addRow("Template", template_fav_row)
selection_form.addRow(template_summary)
selection_form.addRow("Variant", variant_fav_row)
selection_form.addRow(variant_summary)
```

Still worth tracking:

- `template_summary` and `variant_summary` are visible.
- `favorite_template_button` and `favorite_variant_button` are visible and connected.
- `favorite_template_status` / `favorite_variant_status` are still created and updated, but not inserted into any layout.

**Impact:** The original visibility bug is fixed. Remaining cleanup is limited to redundant status labels.

### VERIFIED: `active_project` is already outside the collapsed section

**File:** [`create_panel.py:947–953`](../../ocw_workbench/gui/panels/create_panel.py)

The current code adds `active_project` directly to `action_layout` before the collapsed `document_actions_section`, so the visibility issue has already been fixed.

### Fragile level detector in `set_status()`

**File:** [`workbench.py:476–486`](../../ocw_workbench/workbench.py)

Level is determined by string matching:
```python
level = "error" if message.lower().startswith("could not") ...
```
Any text change in a panel status message breaks the feedback level.

### VERIFIED: no per-call `ControllerService()` instantiation in `_FavoriteComponentCommand`

**File:** [`workbench.py:141–152`](../../ocw_workbench/workbench.py)

The current implementation does not create a `ControllerService()` in `_FavoriteComponentCommand`. It reads favorites via `UserDataService()` during initialization and resolves the component once via `LibraryService()`.

### VERIFIED: workbench stylesheet already extracted to QSS

**File:** [`workbench.py:745–753`](../../ocw_workbench/workbench.py), [`workbench.py:1248–1254`](../../ocw_workbench/workbench.py), [`resources/ui/workbench_shell.qss`](../../resources/ui/workbench_shell.qss)

`workbench.py` now loads stylesheet content from `resources/ui/workbench_shell.qss`, so the previous inline-string maintainability issue is no longer current.

---

## 3. Prioritized Improvement Fields

### HIGH — Fix now

| Problem | File | Line |
|---|---|---|
| Remove orphaned `favorite_template_status` / `favorite_variant_status` labels or surface them intentionally | `create_panel.py` | 861–866, 545–555, 585–599 |

### MEDIUM — Fix next

| Problem | File | Line |
|---|---|---|
| `set_status()` level heuristic → explicit level parameter | `workbench.py` | 476–486 |
| `LayoutPanel`: validation status out of collapsible | `layout_panel.py` | Verified fixed at 371, 391 |
| `ConstraintsPanel`: `results_overview` + `next_step` redundant outputs | `constraints_panel.py` | `results_overview` no longer exists; re-check `review_value` + `next_step` at 183–196, 364–370 |

### LOW — Fix later

| Problem | File | Line |
|---|---|---|
| `_FavoriteComponentCommand` creates new service per call | `workbench.py` | Verified fixed at 141–152 |
| `favorite_template_status` / `favorite_variant_status` labels redundant | `create_panel.py` | 861–866 |
| Extract stylesheet from Python string | `workbench.py` | Verified fixed at 1248–1254 |

---

## 4. Recommended Implementation Order

### Package 1 (this session) — shell + small UI cleanup
1. Remove or intentionally place `favorite_template_status` / `favorite_variant_status`

### Package 2 — Shell feedback stability
2. Fix `set_status()` level detection

### Package 3 — Layout/Validate panel improvements
3. Verify whether `ConstraintsPanel` still needs `review_value` plus `next_step`, then reduce overlap if confirmed

### Package 4 — Code quality
4. Keep current external QSS loading and avoid regressions back to inline styles

---

## 5. FreeCAD Workbench Fit Assessment

- Stepper flow maps well to FreeCAD task panels. ✓
- Dock widget management is correct for FreeCAD dock areas. ✓
- Overlay via Coin3D is the correct FreeCAD approach. ✓
- 3D interaction (drag, place) hooks into the view correctly. ✓
- **Concern:** Dock height — many collapsed sections still take vertical space in narrow FreeCAD dock areas.
- **Concern:** No visible "first run" hero state — empty project + Create panel doesn't strongly guide new users.
- The `InfoPanel` embedded via splitter in the Create step is logical but makes the Create step tall.
