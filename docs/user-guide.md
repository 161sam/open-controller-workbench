
# User Guide

## Zielgruppe

- Maker
- Hardware Devs
- DIY Controller Builder

## Einstieg

1. Plugin installieren
2. Workbench öffnen
3. Projekt starten

## Workflow

1. Größe definieren
2. Komponenten platzieren
3. Cutouts prüfen
4. Export

## Parameters And Presets

- Templates can expose declarative parameters in the Create panel.
- The parameter editor renders matching controls automatically:
  - numeric input or slider for `int` and `float`
  - select or button-style choice for `enum`
  - toggle for `bool`
  - text input for `string`
- Changing a parameter in the panel only updates the staged preview first. It does not trigger a heavy document sync on every control change.
- `Create` uses the currently selected parameter values when a new controller is generated.
- `Apply Parameters` regenerates the current controller from the selected template or variant and writes the current parameter values into project state.
- Parameter values are stored in project metadata together with their source:
  - `default`
  - `preset`
  - `user`
- Template presets are built into templates and can be applied before fine-tuning.
- Saved user presets in the Presets box also persist parameter values and the selected template preset id.
- If you reopen a controller document that was created from a template or variant, the Create panel reloads the saved project parameter values for that document.
- `Apply Parameters` regenerates the current controller from the saved project-linked template or variant, so existing projects remain re-parameterizable.
- Older project documents that only stored parameter overrides fall back to a legacy re-parameterization mode.
- In that legacy mode, the panel explains that values were recovered from overrides and should be reviewed and re-applied once to persist explicit project parameter metadata.
- If the original template or variant is no longer available in the registry, the panel keeps the document readable but marks re-parameterization as unavailable.

## Parameterized Template Examples

- `pad_grid_4x4`
  - `pad_count_x`, `pad_count_y`
  - `case_width`, `case_depth`
  - built-in presets such as `4x4 Pad Grid` and `8x2 Pad Grid`
- `fader_strip`
  - `fader_length`
  - `case_width`, `case_depth`
  - switches between matching 45 mm and 60 mm fader library entries
- `display_nav_module`
  - `display_size_inch`
  - `knob_diameter`
  - switches between display and encoder clearance profiles

## Component Palette

- Öffne die Palette über `OCW_OpenComponentPalette`
- Suche live über Name, ID, Part Number und Tags
- Filtere nach UI-Kategorie oder nur nach Favoriten
- Ein Klick wählt ein Component Template für den nächsten Add/Place-Schritt vor
- Favoriten können direkt in der Palette per Stern markiert werden
- Bis zu 8 Favoriten erscheinen als Icon-Buttons in der Toolbar `OCW Favorites`
- Favoriten werden in UserData gespeichert und bleiben über Neustarts erhalten
- `Place In 3D` startet den interaktiven Platzierungsmodus im 3D-View
- Die Ghost-Vorschau folgt der Maus nur über Overlay-Preview
- Klick platziert die Komponente, `ESC` bricht den Modus ohne Modelländerung ab
- `OCW_DragMoveComponent` startet den Drag-Modus für bestehende Komponenten
- Klicke eine vorhandene Komponente im 3D-View an, ziehe sie und lasse los zum Commit
- Während des Ziehens bleibt das Modell unverändert; nur das Overlay-Ghost wird aktualisiert

## Interactive Placement And Drag

- `Place In 3D` starts a single active placement session for the current document.
- `OCW_DragMoveComponent` starts a single active drag session for existing components.
- Starting a second interactive tool automatically cancels the previous one and clears its preview ghost.
- `ESC` always cancels the active interaction and removes transient preview metadata.
- Placement and drag previews are overlay-only and are never written into `ProjectJson`.
- Live preview validation runs during mouse move without rebuilding the model.
- Blue preview means the current position is valid.
- Orange preview means a warning-level risk was detected.
- Red preview means the preview is invalid, for example out of bounds, overlapping, or conflicting with keepout-related clearance.
- The status area reports the current preview state as `Valid placement`, `Out of bounds`, `Overlap risk`, or `Keepout warning`.
- If the active document changes, the document closes, or the 3D view becomes unavailable, the current interaction is cancelled and callbacks are removed before another tool can start.
- A committed click or drag release applies the model change and then clears preview state and view callbacks.
- If an interaction update or commit raises an exception, the session is cleaned up and the workbench reports `Interaction error`.
- Invalid preview states block commit until the component is moved back to an allowed position.

## Component Property Panel

- Selecting a component updates the Components panel into a context-sensitive property editor.
- Multi-selection keeps one primary selected component plus additional selected component ids.
- A normal selection action replaces the current selection with one primary component.
- A modifier-based selection action in the 3D selection flow can add or remove components from the current selection.
- The Components panel continues to edit the primary selected component.
- Secondary selected components stay visible in overlay and project summary views so later bulk actions can reuse the same selection set.
- The panel always shows:
  - selected component `ID`
  - component `Type`
  - active library `Variant`
  - placement fields `X`, `Y`, and `Rotation`
  - generic metadata such as `Label`, `Tags`, and `Visible`
- Type-specific fields are generated from the selected library component:
  - pad-like buttons show variant and pad size context
  - faders show variant, travel-related information, and editable cap width metadata
  - displays show variant, orientation, and bezel metadata
  - encoders show variant plus mounting-related dimensions
- `Apply Changes` writes the edited values back into project state.
- Placement-affecting changes, such as `X`, `Y`, `Rotation`, or a variant switch, trigger the normal geometry sync path.
- Metadata-only edits, such as `Label`, `Tags`, `Visible`, or component-specific metadata fields, stay lightweight and do not force a full rebuild on their own.
- `Reset Properties` reloads the selected component from current project state and discards unsaved panel edits.
- If no component is selected, the panel falls back to a neutral empty state.

## Multi-Select

- OCW now stores selection as:
  - one primary selection
  - a list of selected component ids
- Overlay feedback distinguishes:
  - primary selected component
  - secondary selected components
- The info and workbench status areas report the current selected component count.
- Existing single-selection workflows remain valid because the primary selection still drives property editing, single-component move, and other current tools.

## Undo And Redo

- Overlay previews do not open FreeCAD document transactions and do not create undo entries.
- Each completed place action creates exactly one undoable document transaction.
- Each completed drag-move action creates exactly one undoable document transaction.
- `ESC` cancel only clears transient preview state and does not add an undo step.
- Template Import Stage A writes a YAML template file and refreshes template discovery, but it does not mutate the active controller project document, so there is no project undo entry for the import itself.

## Import Template From FCStd

- Starte `OCW_ImportTemplateFromFCStd`
- Wähle eine `.FCStd` Datei und lade die importierbaren Objekte oder Flächen
- Wähle die Referenzfläche für die Top Surface und optional einen Origin-Vertex
- Passe Offsets, Rotation und optional die Höhe an
- Wähle anschließend bewusst zwischen zwei Modi:
  - `Stage A`: YAML-only Import in die User-Template-Library
  - `Stage B`: YAML-Template mit `custom_fcstd` Referenz auf die Quellgeometrie
- `Stage A` bleibt der robuste Standardpfad: Maße, Height, Origin-Metadaten und erkannte Mounting-Holes werden in das YAML geschrieben
- `Stage B` speichert zusätzlich die FCStd-Datei, das Referenzobjekt oder die Referenzfläche sowie Origin- und Rotationsdaten als Base-Geometry-Referenz
- Beide Modi speichern ein Template im User-Templates-Ordner und machen es anschließend in der Template-Auswahl sichtbar
- Nach dem Import öffnet sich der Template Inspector für die Nachbearbeitung
- Bestehende Standard-Templates bleiben unverändert nutzbar; `custom_fcstd` ist nur eine zusätzliche optionale Template-Variante

## Template Inspector

- Der Inspector trennt bewusst zwischen `Imported raw template` und `Edited / validated template`
- Prüfe und bearbeite dort mindestens:
  - `Template ID`
  - `Name`
  - `Description`
  - `Width`, `Depth`, `Height`
  - `Rotation`
  - `Offset X`, `Offset Y`
  - rudimentäre `Zones`
  - `Mounting Holes`
- Der Inspector zeigt zusätzlich:
  - `Surface / Geometry`
  - deklarierte `Parameters`
  - verfügbare Template-Presets
  - `Resolved Parameters`
  - `Resolved Preview`
- `Source Metadata` zeigt die importierte FCStd-Herkunft an und dient als Referenz
- Der Parameter-Editor rendert passende Controls direkt aus dem Template-Schema
- `Apply Template Preset` belegt Parameterwerte vor und erlaubt danach manuelle Overrides
- `Apply` aktualisiert nur die Inspector-Vorschau im Speicher und speichert noch nichts
- `Reset All` setzt die Parameter auf die aktuell im Template gespeicherten Defaults zurück
- `Validate` prüft offensichtliche Feldfehler und zeigt Fehler oder Warnungen ohne Speichern an
- `Save Template` schreibt zurück in dieselbe User-Template-Datei
- `Save As User Template` schreibt ein validiertes User-Template in den User-Templates-Ordner
- Existiert bereits ein User-Template mit derselben ID, ist ein Overwrite nur mit aktivierter Overwrite-Option erlaubt
- Nach dem Speichern wird die Template Registry neu geladen, damit das bearbeitete Template direkt im Create-Flow verfügbar ist
- Wichtig: Inspector-Parameteränderungen werden beim Speichern als neue Template-Defaults gesichert. Sie sind nicht dasselbe wie projektspezifische Parameterwerte in einem konkreten Controller-Dokument.

## FCStd Stage A Vs Stage B

- `Stage A` erzeugt ein normales YAML-Template mit abgeleiteten Maßen und Quell-Metadaten, aber ohne direkte FCStd-Abhängigkeit im Builder
- `Stage B` erzeugt ebenfalls ein YAML-Template, referenziert jedoch zusätzlich die Quell-`FCStd` als `custom_fcstd` Base-Geometry
- `Stage B` ist mächtiger, aber bewusst enger gekapselt:
  - Die logische Controller-Surface, Bounds-Checks und die bestehenden Overlay-/Layout-Workflows bleiben template-basiert
  - Die FCStd-Geometrie wird nur beim Build der Base-Top-Plate geladen und dort als Ausgangsform verwendet
- Wenn die referenzierte Datei, das Objekt oder die Referenzfläche fehlen, schlägt der Build mit einer klaren Fehlermeldung fehl, statt einen halbinitialisierten Zustand zu hinterlassen

## Begriffe

- Controller
- Component
- Cutout
- Keepout

## Status

Noch Early Stage – Fokus aktuell auf Dev & Architektur
