# Workbench Guide

## Purpose

Open Controller Workbench is a dock-first FreeCAD workbench for building modular controller hardware.

The main workflow is:

1. `Create`
2. `Layout`
3. `Components`
4. `Validate`
5. `Plugins`

## Main UI

The primary UI is a persistent right-side dock with:

- one header
- one tab-based navigation level
- one footer status area

The dock is the main control surface, but the 3D view is now the main interaction surface for placement, selection, drag, and on-object actions.

## Core Workflows

### Create

Use `Create` to start a controller from a template or variant and to re-apply saved project parameters.

### Layout

Use `Layout` to run `Auto Place`, tune placement settings, and toggle overlay helpers.

### Components

Use `Components` for:

- selection-aware editing
- quick add
- bulk edit
- direct 3D move preparation

### Validate

Use `Validate` to review blocking errors, warnings, and the next recommended action before moving on to plugins or exports.

### Plugins

Use `Plugins` for plugin overview and plugin operations.

## Core Interaction Flows

### Start / Template-driven workflow

- create from a template
- read the workflow card
- use the next suggested step rather than hunting for commands

### Add / Guided placement

- suggested additions use target-aware placement in the 3D view
- the overlay distinguishes hover, active target, and invalid target
- the mini-inspector switches into targeting context during the session

### Select / Inspect / Move

- hover gives a pre-selection cue in the 3D view
- click selects and stabilizes the object context in the mini-inspector
- drag mode moves existing components with preview-before-commit behavior

### On-object actions

- single selection shows small direct actions near the component
- current MVP actions are `Duplicate`, `Rotate +90`, and `Mirror`
- they complement the toolbar and inspector instead of replacing them

### Validate / Continue

- overlay and validation stay visible while editing
- the workflow card, inspector, and toolbar keep the next step visible

## Direct Interaction

The current dock UI supports two interactive 3D workflows:

- drag-based placement with continuous placement until `ESC`
- drag-to-move with hover highlight before the drag starts
- on-object actions for fast single-selection edits

Both workflows:

- keep preview state in transient metadata only
- clean up on `ESC`
- cancel automatically when another interactive tool starts

## Release Notes For The Current UI

- Naming is standardized around `Open Controller Workbench`.
- The dock uses a single visible navigation level.
- Validate is a first-class workflow step.
- Placement and drag are now documented as part of the main dock workflow instead of as side behavior.
- The current user-facing workflow is now best understood as:
  - create
  - place
  - select
  - move
  - act
  - validate
