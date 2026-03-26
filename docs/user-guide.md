
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
- Der Import erzeugt zunächst ein rohes YAML-Template im User-Templates-Ordner und macht es anschließend in der Template-Auswahl sichtbar
- Nach dem Import öffnet sich der Template Inspector für die Nachbearbeitung

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
- `Source Metadata` zeigt die importierte FCStd-Herkunft an und dient als Referenz
- `Validate` prüft offensichtliche Feldfehler und zeigt Fehler oder Warnungen ohne Speichern an
- `Save As User Template` schreibt ein validiertes User-Template in den User-Templates-Ordner
- Existiert bereits ein User-Template mit derselben ID, ist ein Overwrite nur mit aktivierter Overwrite-Option erlaubt
- Nach dem Speichern wird die Template Registry neu geladen, damit das bearbeitete Template direkt im Create-Flow verfügbar ist

## Begriffe

- Controller
- Component
- Cutout
- Keepout

## Status

Noch Early Stage – Fokus aktuell auf Dev & Architektur
