# Agent Guidelines & Best Practices

Diese Datei enthält die grundlegenden Coding- und Architekturrichtlinien für alle (KI-gesteuerten sowie menschlichen) Entwickler, die an **TaleWeaver** arbeiten. 

Bitte halte dich bei allen Implementierungen an die folgenden Regeln, um eine hohe Code-Qualität sicherzustellen.

---

## 1. Clean Code

* **Namenskonventionen:**
  * Python: `PascalCase` für Klassen, `snake_case` für Methoden, Variablen und Module. Konstanten in `UPPER_SNAKE_CASE`.
  * JavaScript/TypeScript: `PascalCase` für Klassen/Komponenten, `camelCase` für Funktionen und Variablen.
  * Verwende immer aussagekräftige Namen (z.B. `calculate_damage` statt `calc_dmg`).
* **Single Responsibility Principle (SRP):**
  * Eine Funktion, Klasse oder ein Modul sollte exakt einen Zweck erfüllen. Wenn eine Funktion unübersichtlich lang wird, teile sie in kleinere, testbare Einheiten auf.
* **Typisierung (Type Hints):**
  * **Python:** Nutze durchgängig Type Hinting (z.B. `str`, `int`, `dict`, `list`, `Optional`). Das erleichtert das Linting (mit `mypy`) und macht den Code lesbarer.
  * **Frontend:** Verwende in JavaScript wo möglich JSDoc, oder idealerweise TypeScript für klare Interfaces.
* **Fehlerbehandlung (Error Handling):**
  * Behandle Fehler da, wo sie auftreten. 
  * Verwende in FastAPI `HTTPException`, um Fehler an das Frontend mit sinnvollen Statuscodes (400, 404, 500) und klarer Message zurückzugeben.

---

## 2. Testing

* **Prinzipien:**
  * Jeder neue Endpunkt, jede Kernfunktion (z.B. der D20-Würfel-Wurf oder das Evaluieren des LLM-Ergebnisses) muss mit automatisierten Unit-Tests abgedeckt sein.
  * Baue Tests nach dem Schema **Arrange, Act, Assert** (AAA) auf.
* **Tools & Frameworks:**
  * **Backend:** Nutze `pytest`. Für asynchrone Routen nutze `pytest-asyncio` und den `AsyncClient` von `httpx`.
* **Mocking:**
  * Netzwerkanfragen (insbesondere LLM-API-Calls zu OpenAI/Anthropic/etc.) **müssen** in Unit-Tests gemockt werden. Wir wollen keine echten API-Kosten oder Latenzen beim Ausführen der Testsuite erzeugen!
  * Datenbankzugriffe in isolierten Tests ebenfalls mocken oder eine dedizierte In-Memory-SQLite Test-Datenbank verwenden.

---

## 3. Kommentare & Dokumentation

* **Code-Dokumentation (Docstrings):**
  * Das "Warum" und "Was" ist wichtiger als das "Wie". Der Code selbst sollte das "Wie" durch gute Benennung zeigen.
  * Verwende in Python Docstrings (`"""..."""`) auf Modul-, Klassen- und Funktionsebene, idealerweise im Google- oder Sphinx-Format.
* **Inline-Kommentare:**
  * Nutze sie sparsam. Sie sind nur dann sinnvoll, wenn ein bestimmter Algorithmus extrem komplex ist, ein überraschender Fix implementiert wurde oder ein obskurer Workaround dokumentiert werden muss.
* **TODOs:**
  * Verwende `TODO: [Kurzbeschreibung]` für offene Aufgaben im Code. Die Aufgaben sollten in Issue-Trackern nachgepflegt werden.
