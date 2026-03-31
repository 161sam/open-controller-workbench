# MIDI Controller Layout Intelligence

## Scope

This MVP adds lightweight layout guidance to `plugin_midicontroller`.

It does not attempt full auto-layout or generic recommendation logic across every domain.

## What The MVP Adds

Templates can now describe:

- `workflow_hint`
- `ideal_for`
- `next_step`
- `layout_zones`
- `smart_defaults`
- `suggested_additions`

Components can now describe:

- `ocf.role`
- `ocf.placement_preference`

Suggested additions can also carry UI-facing metadata:

- `label`
- `short_label`
- `tooltip`
- `icon`
- `priority`
- `group`
- `order`
- `command_id`
- `status_message`

## Template Patterns

Current high-value patterns:

- `pad_grid_4x4`
  - utility strip on the right
  - navigation encoder pair on the top row
  - centered display header
- `encoder_module`
  - centered display header
  - compact utility buttons below
- `fader_strip`
  - display or label area above the lane
  - one top encoder above the strip
- `display_nav_module`
  - transport row below the navigation controls
- `transport_module`
  - display header above the row
  - jog encoder on the right

## Placement Heuristics

The MVP uses a small deterministic rule set:

- `right_of_main`
- `top_row`
- `centered_above_group`
- `bottom_transport_row`
- `aligned_with_group`

Anchor selection prefers:

1. template smart default primary zone
2. template smart default primary group role
3. current component bounds

## What It Can Do

- expose template-specific next-step suggestions
- build template-specific workflow cards with one primary action and a short secondary action list
- surface those suggestions in the existing `InfoPanel` as clickable workflow actions
- register suggested additions as direct commands such as `OCW_AddUtilityStrip`
- generate deterministic default positions for suggested additions
- suggest a sensible default position for a newly added component type
- keep added controls grouped through `group_id` and `group_role`

## How Users Trigger It

After creating a MIDI controller template, the `InfoPanel` now shows a compact `Workflow Card`.

Each card includes:

- the template title
- a short workflow hint
- a compact `Ideal for` summary
- one `Primary Action`
- a short `Next Steps` list

Typical actions include:

- `Add Utility Strip`
- `Add Display Header`
- `Add Navigation Encoder`
- `Add Transport Buttons`

These actions:

- stay hidden when the current document has no relevant suggestion
- apply the existing layout-intelligence heuristics
- add grouped components with deterministic default positions
- reuse the same plugin logic as the command path
- surface the most likely next build step first

## What It Does Not Do

- full controller relayout
- collision solving beyond normal layout / validation paths
- adaptive optimization or AI placement
- generic cross-domain recommendation logic

## Next Evolution

Later product work can build on this metadata to add:

- template-aware one-click add flows
- richer secondary-layout patterns for larger controllers
- lightweight placement previews for next-step actions
