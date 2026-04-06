# MundMaus Quality Session — 2026-04-06

## Kontext
Assistive Gaming Controller fuer einen tetraplegischen Patienten. ESP32 + Mundjoystick + Drucksensor. 6 Browser-Spiele auf dem Fernseher. Zero Defects Anforderung — die Spiele sind die einzige Abwechslung.

---

## Neue Features

### Charge-Navigation (alle 6 Spiele)
- **Unsichtbarer Cooldown ersetzt durch sichtbare Ladeanzeige**: SVG-Rahmen zeichnet sich im Uhrzeigersinn um das Zielfeld
- **Joystick-Intensitaet**: analog 0.0–1.0, staerker = schneller laden
- **Keyboard Dual-Mode**: "J" toggelt zwischen Direkt (Pfleger, sofort) und Joystick-Sim (Patient-Test, Charge)
- **NAV_COOLDOWN_MS**: Konfigurierbarer Default 1000ms, Range 50–3000ms, live preview in Settings

### Muehle (neues Spiel)
- 24-Position Board mit 3 AI-Schwierigkeitsgraden (Minimax + Alpha-Beta)
- Multiplayer-Toggle ("M"), Setzphase + Zugphase, Mill-Erkennung mit Glow
- Grosse Spielsteine (r=5.0) mit Highlight-Layer ueber den Steinen

### Multiplayer-Modus
- Vier gewinnt + Muehle: "M" toggelt zwischen KI und Pfleger-Gegner
- Gleiche Eingabeformen fuer beide Spieler

### Firmware v3.9
- Joystick-Axis-Hysterese (1.4x Faktor gegen Diagonal-Flipping)
- Stabilitaetsbasierter Drift-Guard (auto-rekalibriert nach 30s stabiler Drift)
- WiFi-Reconnect in Background-Task (kein WDT-Crash mehr)
- OTA Rollback-Schutz (pending_fw in NVS, erst bei erfolgreichem Boot promoted)
- Async WiFi-Scan (blockiert AsyncTCP nicht mehr)

---

## Bugs gefixt (nach Kategorie)

### Firmware (8 Bugs)
| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Joystick friert ein | ADC-Rauschen flippt X/Y 50x/s bei Diagonal | Axis-Hysterese 1.4x |
| Auto-Rekal waehrend Nutzung | isIdle() Gap (DEADZONE*2 vs NAV_THRESHOLD) | isIdle() auf DEADZONE gesenkt |
| Joystick driftet | Center verschiebt sich ueber Zeit | Stabilitaets-Drift-Guard (30s) |
| WDT-Crash bei WiFi-Reconnect | connectStation() blockiert 49s, WDT=30s | Background-Task |
| Truncated OTA silently installiert | Kein Size-Check nach Download | contentLen + write Validierung |
| _updateResult Race Condition | Background-Task vs AsyncTCP | FreeRTOS Mutex |
| Stale Firmware nach Rollback | Version in NVS vor Boot gespeichert | pending_fw Pattern |
| Config-Werte ungeranged | Korrupte NVS-Werte nicht geklemmt | constrain() in load() |

### Games — Logik (9 Bugs)
| Bug | Spiel | Root Cause | Fix |
|-----|-------|-----------|-----|
| Karte nicht ablegbar | Solitaire | isSamePos() vergleicht stale cardIdx | Nur Zone+Spalte |
| Karte nicht ablegbar | Freecell | Gleicher isSamePos Bug | Nur Zone+Spalte |
| Figur nicht abwaehlbar | Chess | Re-select statt deselect bei gleicher Pos | Same-pos = deselect |
| AI crasht bei Neu | Muehle/Chess/VG | setTimeout nicht cancelable | Handle + re-check guards |
| autoComplete stackt | Solitaire | setInterval lokal, kein Guard | Globaler Handle + reentry |
| computeTarget falsch | Solitaire | navZone statt z Variable | Variable gefixt |
| Win-Overlay bleibt | Solitaire+Freecell | message.className nicht gecleart | Clear in initGame() |
| WS-Reconnect stackt | Solitaire+Freecell | Kein Timer-Dedup | Handle + clearTimeout |
| Memo stale Callbacks | Memo | setTimeout captures stale refs | Generation-Counter |

### Games — Visuell (7 Fixes)
| Problem | Spiel | Fix |
|---------|-------|-----|
| Karten gequetscht (Wert geht in Symbol) | Solitaire+Freecell | Kartenhöhe 13.3→14.5vw, Center-Font 4.5→3.5vw, Padding |
| Gestapelte Karten verschmelzen | Solitaire+Freecell | Dynamischer FUO (3.8vw normal, 1.2vw minimum bei langen Stapeln) |
| Karten laufen aus Viewport | Solitaire+Freecell | FUO basiert auf tatsaechlicher Viewport-Hoehe |
| Foundation-Slots unsichtbar | Solitaire+Freecell | Border 0.15→0.3, Label 0.2→0.4, Font 2.5→3.5vw |
| Header blau statt schwarz | Solitaire+Freecell | rgba(15,52,96) → rgba(0,0,0,0.7) |
| Footer blau statt schwarz | Solitaire+Freecell | Gleiches Fix wie Header |
| Action-Buttons fast unsichtbar | Alle 6 | Border 0.12→0.25, Background 0.06→0.1 |

### Konsistenz (6 Fixes)
| Problem | Fix |
|---------|-----|
| Footer Sprache Mix (DE/EN) | Icon-Sprache ueberall (↻ ↩ 💡 ⌨ 👥 📺 🏠) |
| KB-Mode nur in 2 Spielen | Alle 6 Spiele haben J-Taste + ⌨ Indicator |
| Charge-Nav nur in 2 Spielen | Alle 6 Spiele haben Charge-Mechanik |
| navigate() cancelt Charge nicht | Alle 6 Spiele: cancelCharge() in navigate() |
| initGame() cancelt Charge nicht | Alle 6 Spiele: cancelCharge() in initGame() |
| Puff-Icon kaum sichtbar | Alle 6 Spiele: 0.25→0.5 Opacity |

---

## Quality Gates (automatisiert)

### Firmware
- **cppcheck + clang-tidy**: `--fail-on-defect=low`, 8 Check-Kategorien
- **Pre-Build Lint**: Automatisch vor jedem `pio run`, gecacht via `.lint_passed` Marker
- **Null-Guards**: Alle Pointer im sensorTask geprueft (joystick, server, puffSensor)
- **Volatile Config**: Cross-Core Globals als `volatile int`
- **Atomic Flags**: `std::atomic<bool>` fuer TOCTOU-sichere Scan/Update Guards
- **Single ADC Read**: `sampleRaw()` einmal pro Iteration, alle Methoden nutzen Cache
- **Safe Broadcast**: `_broadcastText()` via makeBuffer + shared_ptr

### Games
- **cancelCharge()** in navigate() und initGame() — verhindert stale Charge State
- **AI Timer cancelable** — clearTimeout + re-check Guards in Callback
- **autoComplete guarded** — globaler Handle + reentry Prevention
- **WS-Reconnect deduped** — Timer Handle + clearTimeout
- **Generation Counter** (Memo) — invalidiert stale setTimeout Callbacks
- **Dynamic Card Stacking** — FUO skaliert mit Viewport-Hoehe

### OTA
- **Fresh-Flash Marker** (`.ota_marker`) — erkennt USB-Flash, cleared stale NVS
- **Firmware Version Seeding** — MUNDMAUS_FW_VERSION Build-Flag
- **Truncation Validation** — contentLen + write Return-Value Check
- **Rollback Protection** — pending_fw in NVS, nur bei erfolgreichem Boot promoted

---

## Test-Methodologie

### Playwright Deep-Tests (alle 6 Spiele)
1. **Win-State erzwingen** → Overlay erscheint → neues Spiel → Overlay weg, State clean
2. **Deselect-Zyklus** → Karte auswaehlen → wegnavigieren → zurueck → gleiche Position = Abwahl
3. **Undo-Kette** → Zuege machen → undo bis leer → kein Crash
4. **Rapid New-Game** → 10x schnell hintereinander → kein State-Leak
5. **AI-Cancel** → Zug machen → waehrend AI denkt "N" → Menu erscheint, kein Crash
6. **Multiplayer-Toggle** → M druecken → beide Seiten spielbar
7. **Zone-Navigation** → Alle Uebergaenge (Tableau↔Top, Board↔Buttons)
8. **Volle Spalte** (Vier gewinnt) → Drop auf volle Spalte → abgelehnt

### Visuelle Tests (Playwright Screenshots)
1. **Normal-Spiel** bei 1920x1080 → Proportionen, Lesbarkeit
2. **Max-Stack** (13 face-up Solitaire) → Dynamischer FUO → alle Karten + Cursor sichtbar
3. **Ultrawide** (3440x1440) → max-width Cap funktioniert
4. **Opacity-Audit** → Alle rgba() < 0.3 auf Lesbarkeit geprueft

### Firmware-Tests
1. **Lint**: cppcheck + clang-tidy bei jedem Build
2. **Boot-Verify**: Serial Monitor "Bereit." + Heap-Check
3. **API-Test**: `/api/settings`, `/api/updates` korrekte JSON-Antworten
4. **WebSocket**: Connect + wifi_status Message empfangen
5. **OTA-Verify**: Manifest + MD5 Server vs Lokal
6. **WDT**: WiFi-Reconnect ueberlebt 30s Timeout (Background-Task)

---

## Versions-Stand nach Session

| Datei | Version | Aenderungen |
|-------|---------|-------------|
| firmware.bin | v40 (3.9) | Hysterese, Drift-Guard, volatile, atomic, safe broadcast |
| solitaire | v27 | Charge-Nav, Deselect, autoComplete, dynamic FUO, Slot-Visibility |
| freecell | v19 | Charge-Nav, Deselect, dynamic FUO, Slot-Visibility, WS-Dedup |
| chess | v15 | Charge-Nav, Deselect, AI-Cancel, Visibility |
| memo | v14 | Charge-Nav, Gen-Counter, Visibility |
| muehle | v4 | Neues Spiel, grosse Steine, Board-Border, Visibility |
| vier-gewinnt | v13 | Multiplayer, Charge-Nav, checkWinAt, AI-Cancel, Visibility |
| settings | v5 | NAV_COOLDOWN_MS Anzeige (ms pro Sprung) |

## Bekannte Defekte: 0
