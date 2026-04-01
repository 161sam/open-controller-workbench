# OCW v0.x Release Draft

This draft is intended as the base text for the next visible GitHub release.

## Title

`Open Controller Workbench v0.x - workflow and interaction maturity update`

## Short summary

This release turns OCW into a clearer, more direct FreeCAD workbench for controller authoring.

The workbench now combines a compact mini-inspector, guided placement, stronger 3D feedback, direct drag interaction, and small on-object actions into one visible authoring flow.

## Highlights

### Workflow and inspector

- compact mini-inspector instead of a text-heavy dock
- clearer workflow card with one primary next step
- stronger object context for template, targeting, and selection states

### 3D interaction

- guided placement with valid, hover, and invalid target feedback
- drag-based placement and direct drag move in the 3D view
- improved hover and selection behavior for existing components
- small on-object actions for `Duplicate`, `Rotate +90`, and `Mirror`

### Workbench surface

- simplified toolbar with clearer command grouping
- more consistent visual language across toolbar, inspector, workflow, and overlay
- more robust cancel, escape, and tool-switch behavior

### Documentation and review readiness

- manual UX / QA checklist
- compact demo flow for review and walkthroughs
- updated README, user guide, and workflow docs

## What this release is good for

- internal demos
- reviewer walkthroughs
- early tester feedback
- validating the current OCW interaction model before broader feature expansion

## Current scope limits

This release is intentionally still a focused v0.x workbench release.

Not included:

- no large multi-selection UX
- no on-object delete action
- no full CAD gizmos
- no global interaction state machine
- no plugin-wide full UI normalization
- no advanced ECAD roundtrip workflow as a polished end-user feature

## Suggested links for the GitHub release page

- [README](../../README.md)
- [Manual UX / QA Checklist](../manual_ux_checklist.md)
- [Demo Flow](../demo_flow.md)
- [User Guide](../user-guide.md)

## Suggested release assets to mention

- FreeCAD module zip
- source distribution
- wheel
- checksums
