# MIDI Controller Quickstart

## Goal

Build a plausible first MIDI controller concept without leaving the normal GeneratorWorkbench flow.

## Choose A Starting Point

1. Use `Select Domain` and choose `MIDI Controller`.
2. In the Create panel, start with one of these templates:
   - `Finger Drum Pad Grid` for beat pads, clip launching, and performance-first surfaces
   - `Channel Strip` for one mixer or track-control lane
   - `Macro Encoder Bank` for synth macros, sends, or parameter pages
   - `Transport Control Strip` for play / stop / record sections
   - `Display And Navigation Module` for menu-driven or browser-heavy devices
3. Apply a built-in preset if it matches your intent, then create the controller.

## First Useful Result

- `Finger Drum Pad Grid`: lock in the pad spacing first, then add transport buttons, a small OLED, or a pair of encoders around the edges.
- `Channel Strip`: keep the fader as the anchor, then add mute / solo / select buttons or one encoder above the lane.
- `Macro Encoder Bank`: treat the four knobs as the core interaction, then decide whether a display or utility buttons are needed.
- `Transport Control Strip`: start with the playback row, then widen it only if rewind / fast-forward spacing feels cramped.
- `Display And Navigation Module`: tune display size and encoder spacing first, then place any extra utility controls around it.

## Typical Next Steps

1. Add the most-used controls from the toolbar groups in this order:
   - `Performance Surface`
   - `Mixing & Levels`
   - `Rotary Controls`
   - `Navigation & Feedback`
   - `Buttons & Utility`
2. Move and align components directly in the 3D view.
3. Use snapping and inline editing to clean up spacing, alignment, and reachability.
4. Check panel openings, keepouts, and mounting space once the layout feels plausible.
5. Continue toward KiCad-oriented export and manufacturing outputs after the control surface is stable.
