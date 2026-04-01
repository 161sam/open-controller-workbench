# OCW UI Visual Language

This note captures the small shared semantics used across the toolbar, mini-inspector, and placement flow.

## Badge semantics

- `Template`: current template or idle controller context
- `Selected`: current selection context
- `Targeting`: active guided placement target context
- `Next`: next workflow step
- `Active`: current in-progress workflow or placement state
- `Done`: completed workflow step

## Placement status language

Prefer these short status texts:

- `Move over target area`
- `Click to place`
- `Invalid target`
- `Placement cancelled`
- `Placement complete`
- `Interaction error`

Do not mix these with alternate phrasings like `No valid target here` or `Cannot place here`.

## Interaction hierarchy

Prefer this visible priority when states compete:

- actively manipulated
- selected and context relevant
- selected
- hovered
- placement context
- idle

On-object actions inherit that same rule:

- visible for one selected component
- hidden during placement and drag
- hover on an action should not visually demote the selected component

## Toolbar language

Use short, product-style command labels:

- `Import Template`
- `Component Library`
- `Move`
- `Measurements`
- `Issue Overlay`

The visible toolbar should keep the higher-level group language:

- `Start`
- `Add`
- `Edit`
- `Workflow`
- `View`

## Scope limits

Current deliberate limits:

- no on-object delete action
- no large multi-selection interaction model beyond pragmatic current tools
- no full CAD gizmos
- no global interaction state machine
- no plugin-wide full design-system normalization
