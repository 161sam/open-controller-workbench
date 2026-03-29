# OCW Template Model

## Responsibility

- `Plugin`: provides template, component-library, variant, and exporter sources.
- `Template`: defines a controller blueprint.
- `Variant`: applies a bounded override set to one template.
- `Component`: is one instantiated control in the generated project state.

## What A Template Describes

- controller geometry defaults
  - `width`, `depth`, `height`
  - `top_thickness`, `wall_thickness`, `bottom_thickness`
  - `lid_inset`, `inner_clearance`
  - `surface` and optional custom base geometry
- layout defaults
  - `strategy`
  - `grid_mm`
  - `padding_mm`
  - `spacing_mm` / `spacing_x_mm` / `spacing_y_mm`
- logical zones
  - placement areas such as pad, display, transport, or encoder zones
- starter components
  - direct component entries
  - generated component groups through parameter bindings such as `component_grids`
- component blueprint defaults
  - `defaults.component_defaults.all`
  - `defaults.component_defaults.by_type`
  - `defaults.component_defaults.by_zone`
- parameter model
  - parameter definitions
  - presets
  - bindings into controller, layout, and starter component data

## What A Variant Does

- changes one template through explicit overrides only
- can modify:
  - controller geometry
  - layout config
  - zones
  - starter components
  - defaults
  - parameter schema or bindings when needed

## What Does Not Belong In Templates

- plugin discovery or registration logic
- runtime interaction state
- dock or panel behavior
- per-session UI state
- ad-hoc direct-manipulation state

## Generated Project Expectations

- template output must already contain a valid controller definition
- starter components must already be concrete component instances
- generated component groups should carry stable metadata such as:
  - `group_id`
  - `group_role`
  - `row`
  - `col`
  - `label`

This keeps templates as blueprints while the resulting project stays fully component-driven.
