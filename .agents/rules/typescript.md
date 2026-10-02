---
description: Erzwingt die Namenskonventionen und Best Practices für unsere TypeScript-Dateien.
trigger:
  type: glob
  pattern: "**/*.{ts,tsx}"
---

# TypeScript Guidelines

1. Verwende immer `const` anstelle von `let`, es sei denn, die Variable wird zwingend neu zugewiesen.
2. Typisiere alle Funktionsrückgabewerte explizit.
3. Nutze `camelCase` für Variablen und Funktionen sowie `PascalCase` für Interfaces und Typen.
4. Vermeide `any` – nutze präzise Types oder Generics.
5. Halte React-Komponenten und Hooks modular, sauber typisiert und wiederverwendbar.
