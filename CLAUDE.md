# MundMaus Agent
Persistenter Agent fuer MundMaus. Versteht Hardware-Constraints, MicroPython/Arduino-Architektur, 3D-Gehaeuse.

## Verbindliche Regeln & Quality
- Core Rules: `~/claude/agents/core-rules.md` (Think Before / Simplicity / Surgical / Goal-Driven)
- Quality: `~/claude/agents/quality-prompt.md` (Quality-Gate Hook erzwingt zusätzlich)

## Kommunikation
- User-Nachrichten kommen als: "Nachricht vom iPhone: ..."
- Antworten: `agentctl reply "..."` (Projekt wird aus PWD erkannt)
- Eskalation an Orchestrator: `agentctl message orchestrator "..."`

## Delegation
- `agentctl spawn micropython|3d|ci|auditor --project mundmaus --briefing <datei>`
- Status: `agentctl status`

---

## Wo das Wissen steht
- **PROJECT.md** — Hardware, Firmware-Varianten, Endnutzer-Kontext, Gehaeuse, Drucker,
  interner Betrieb. **Nur lokal** (gitignored): interne Hostnamen und Pfade gehoeren
  dorthin, nicht in diese oeffentliche Datei.
- **TECHNICAL.md** — Pinout, Verkabelung, HTTP-API, WebSocket-Protokoll, OTA inkl. Deploy-Workflow, Flash-Layout
- **README.md** — Setup, Einkaufsliste, Inbetriebnahme, Shortcuts, FAQ
- **games/STANDARDS.md** — Visual + Interaction Standards der Spiele

## Unverhandelbare Nutzer-Constraints
Die beiden Saetze entscheiden mehr Designfragen als jede technische Vorgabe:
- **Der Patient ist taub.** Rueckmeldung immer visuell — nie nur akustisch.
- **Die Pflege wechselt und hat keine IT-Kenntnisse.** Jede Fehlermeldung muss
  ohne Vorwissen handlungsfaehig machen. Nichts bauen, das Neustarten,
  Konfigurieren oder Nachschlagen verlangt.

Mechanische Constraints (Schlauchfuehrung, Sichtfeld) in PROJECT.md, "Endnutzer-Kontext".

## 3D: CadQuery-Koordinatenregel
Bei JEDER Geometrie-Operation absolute Position als Variable + Kommentar berechnen
BEVOR die Workplane erstellt wird:
```python
wall_x_start = ESP_POS_X - wall_len / 2  # = 23.0 (ESP32-Bereich, +X)
# Workplane("YZ").workplane(offset=wall_x_start)  ← Vorzeichen pruefen
```
Vorzeichen-Fehler bei Workplane-Offsets sind der haeufigste 3D-Bug.

## Spiele — Definition of Done
- **Success**: `tools/check-games.sh` zeigt ALL OK, Playwright-Test besteht (start → spielen → gewinnen → neues Spiel → kein State-Leak, Undo bis leer crasht nicht), Screenshot in mid-game (nicht leerer Start), 1920x1080 ohne Overflow
- **Vorlage**: bestehendes Spiel klonen (z.B. `games/freecell.html`) — Charge-Navigation, WS-Reconnect mit Backoff, Keyboard-Dual-Mode (`J`-Toggle), AI-cancelable, Settings-Fetch (`/api/settings` fuer `NAV_COOLDOWN_MS`) wandern automatisch mit
- **Invarianten** (beim Refactoring nicht brechen): `navigate()` und `newGame()` rufen als ERSTES `cancelCharge()`; AI-`setTimeout`-Handles speichern + `clearTimeout` in `newGame`/`showMenu`; WS-Reconnect via *einem* `wsReconnectTimer`-Handle (nicht stacken); Direct-Mode-Cooldown 120ms (nicht `navCooldown`)
- **Integration** (von `check-games.sh` geprueft): screenshot, README, manifest, website, LittleFS-`.gz`, Anzeigename in `tools/check-games.sh DISPLAY_NAMES`
