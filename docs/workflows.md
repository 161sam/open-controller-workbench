
# Workflows

## Workflow 1 – Setup

- Repo klonen
- Plugin installieren
- Workbench starten

## Workflow 2 – Geometry (Python)

- Controller definieren
- Builder nutzen
- Geometrie erzeugen

## Workflow 3 – Schema Import

- YAML laden
- validieren
- Domain erzeugen
- Geometrie bauen

## Workflow 4 – UI (Ziel)

- Projekt erstellen
- Komponenten platzieren
- Constraints prüfen
- Export

## Workflow 5 – Schema Export

- controller.hw.yaml erzeugen

## Workflow 6 – KiCad Übergabe

- Outline
- Positionen
- Rotation
- Keepouts

## Workflow 7 – Validation

- fehlende Daten
- Kollisionen
- Constraints

## Workflow 8 – Import FCStd -> refine -> save

- FCStd Datei wählen
- Top Surface Referenz wählen
- YAML Template importieren
- rohes Template im Template Inspector prüfen
- ID, Name, Maße, Rotation und Origin-Offsets korrigieren
- Zonen und Mounting-Holes bei Bedarf ergänzen oder bereinigen
- Template validieren
- als User-Template speichern
- Template im Create Panel auswählen
- Controller weiter verfeinern und speichern

## Interactive Tool Lifecycle

- Only one view-interactive tool session may be active at a time.
- Tool start follows the same lifecycle: resolve view, register callbacks once, create or update overlay preview metadata, then wait for commit or cancel.
- Tool cleanup is idempotent: callback deregistration, preview metadata removal, overlay refresh, and session reset can run more than once without crashing.
- `ESC`, document close, active document change, unavailable view, and tool switching all flow through the same cancellation path.
- Successful commits clear transient preview state after the model mutation finishes.
- Failed preview updates or failed commits clear transient state and leave no active callbacks behind.

## Preview, Commit, And Undo

- Preview updates stay in metadata and overlay state only and never open a FreeCAD transaction.
- Preview validation also stays metadata-only and evaluates a hypothetical component set in memory, without a full document sync.
- Place and drag commits use one document transaction around state mutation and full sync.
- The transaction boundary is: open transaction, mutate committed project state, run full sync, close transaction.
- If the commit path raises an exception, the transaction is aborted and the previous project state is restored before control returns to the UI.
- Preview errors block place and drag commit; warning-level preview feedback remains visible but does not create undo entries on its own.
- Template Import Stage A is an external template-generation workflow: it produces a YAML file and reloads the template registry, but it does not mutate the active project document and therefore does not create a FreeCAD undo step.
