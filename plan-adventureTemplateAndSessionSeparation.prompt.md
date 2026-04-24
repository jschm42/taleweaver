## Plan: Adventure Template and Session Separation

Saubere Trennung in drei Ebenen: Adventure als editierbare Vorlage, Session als spielbarer Lauf, SessionState als veränderlicher Runtime-Zustand. Umsetzung über schrittweise Migration mit Dual-Write und Kompatibilitätsschicht, damit bestehende Flows funktionsfähig bleiben.

**Steps**
1. Domänenmodell explizit trennen und Begriffe fixieren. Ergebnis: AdventureTemplate (Vorlage), GameSession (Instanz), SessionState (Deltas/Runtime), optional SaveGame (Snapshot).
2. Datenverantwortung neu zuordnen, damit keine Mischzustände bleiben. AdventureTemplate enthält nur kanonische Weltdaten und Regeln; SessionState enthält Fortschritt, Inventar, NPC/Exit-Status, Chat- und Zeitfortschritt.
3. Persistenzmodell erweitern. Neue Tabellen für `adventure_templates`, `game_sessions`, `session_states` (und optional `save_games`) definieren; bestehende Adventure-Struktur bleibt in Übergangsphase lesbar. Depends on 1.
4. Keine Migration alter Adventures oder Daten. Wir fangen mit neuer DB an. Es gibt bisher keine ausgelieferte Version der App.
5. API-Fläche entkoppeln. Template-Endpunkte bleiben für Editor-Funktionen; neue Session-Endpunkte übernehmen Chat/State/Reset für Spielstände. Alte Endpunkte erhalten Shim/Fallback während Übergang. Parallel with 4 after minimal schema availability.
6. Worldeditor auf reine Template-Operationen begrenzen. Editor darf nur Vorlage ändern; laufende Sessions sehen Änderungen nur bei neuem Session-Start oder explizitem Rebase-Mechanismus.
7. Session-Erzeugung als Copy-on-Create einführen. Beim Start wird aus AdventureTemplate ein initialer SessionState erzeugt; danach keine implizite Rückschreibung ins Template.
8. Reset- und Savegame-Verhalten definieren. Reset wirkt auf SessionState, nicht auf Vorlage; optionale Snapshots ermöglichen mehrere Spielstände je Adventure.
9. Konsistenzschutz und Concurrency einbauen. Sperr-/Versionskonzept für Templates (z. B. version/checksum), Konfliktvermeidung bei gleichzeitigen Editor- und Spielaktionen.
10. Tests erweitern. Neue API- und Migrations-Tests für Trennung, Isolation, Rückwärtskompatibilität und konkurrierende Zugriffe. Depends on 5-9.

**Relevant files**
- `backend/models/adventure.py` — aktuelle Vorlage-/Laufzeitmischung als Ausgangspunkt für Entkopplung.
- `backend/models/game_state.py` — bisheriger, zu schmaler Runtime-State.
- `backend/models/avatar.py` — aktuell runtime-kritische Werte (Inventar/Stats), künftig SessionState-Kandidat.
- `backend/models/world_entity.py` — mutable Laufzeitfelder (`is_in_inventory`, `current_scene_id`, `is_locked`) identifizieren und in SessionState verschieben.
- `backend/models/chat.py` — Chat-Historie als Session-gebundene Daten.
- `backend/schemas/adventure.py` — bestehende API-Verträge, die über Shim kompatibel gehalten werden müssen.
- `backend/schemas/game_state.py` — Ausbau/Ersetzung durch Session-Schemas.
- `backend/api/routes/adventures.py` — zentrale Entkopplung: Template-Routen vs Gameplay-Routen trennen.
- `alembic/versions/` — schrittweise Migrationen für neue Tabellen + Backfill.
- `tests/test_adventures_api.py` — Template-Flow-Regressionen.
- `tests/test_avatars_api.py` — Auswirkungen der State-Verlagerung validieren.
- `tests/` (neue Session-spezifische Tests) — Isolations- und Concurrency-Coverage ergänzen.

**Verification**
1. Migrationsprüfung: Alle bestehenden Adventures wurden als Templates übernommen, inklusive Manifest-Integrität (Hash/Checksum).
2. Isolationsprüfung: Änderung im Worldeditor beeinflusst laufende Session nicht; neue Session übernimmt aktualisierte Vorlage.
3. Mehrfach-Session-Prüfung: Mehrere Sessions auf derselben Vorlage haben unabhängige Fortschritte.
4. Reset-Prüfung: Reset setzt nur SessionState zurück und verändert keine Template-Daten.
5. Kompatibilitätsprüfung: Bestehende v1-Endpunkte liefern weiterhin erwartete Felder während Übergangsphase.
6. Concurrency-Prüfung: Gleichzeitige Editor-Änderung und Chat-Aktion erzeugen keine inkonsistenten Daten.

**Decisions**
- In Scope: klare Domänentrennung, migrationsfähige Architektur, API-Kompatibilität, Teststrategie.
- Out of Scope (initial): tiefgreifender Frontend-Redesign, vollständiges Entfernen alter Endpunkte in derselben Iteration.
- Empfehlung: Dual-Write/Read-Switch statt Big-Bang, um Betriebsrisiko zu reduzieren.

**Further Considerations**
1. Session-Quelle fixieren: Soll eine Session dauerhaft an eine konkrete Template-Version gebunden sein (empfohlen), oder automatische Übernahme späterer Template-Änderungen erlauben?
2. Savegame-Scope: Reicht ein einzelner Autosave pro Session, oder sind benannte manuelle Save-Slots pro Session erforderlich?
3. Legacy-Timeline: Wie lange sollen v1-Endpunkte unterstützt werden (z. B. 4-8 Wochen), bevor sie hart deprecated werden?