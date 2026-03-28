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

The dock is the main control surface. Legacy task panels still exist for a few focused flows, but they are not the primary path.

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

## Direct Interaction

The current dock UI supports two interactive 3D workflows:

- click-to-place with continuous placement until `ESC`
- drag-to-move with hover highlight before the drag starts

Both workflows:

- keep preview state in transient metadata only
- clean up on `ESC`
- cancel automatically when another interactive tool starts

## Release Notes For The Current UI

- Naming is standardized around `Open Controller Workbench`.
- The dock uses a single visible navigation level.
- Validate is a first-class workflow step.
- Placement and drag are now documented as part of the main dock workflow instead of as side behavior.
