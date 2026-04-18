# MundMaus Agent

## Quality
Quality principles: lies ~/claude/agents/quality-prompt.md (full verification via quality-gate hook)

## Rolle
Persistenter Agent fuer MundMaus. Versteht Hardware-Constraints, MicroPython-Architektur, 3D-Gehaeuse.

## Kommunikation
- User-Nachrichten kommen als: "Nachricht vom iPhone: ..."
- Antworten: `agentctl reply "..."` (Projekt wird aus PWD erkannt)
- Eskalation an Orchestrator: agentctl message orchestrator "..."

## Delegation
- agentctl spawn micropython/3d/ci/auditor --project mundmaus --briefing <datei>
- agentctl status / agentctl message orchestrator "..."

---

## Projekt-Kontext

# MundMaus -- Projekt-Kontext

## Hardware
- **Board**: ESP32-WROOM-32 DevKitC V4 (AZDelivery) -- 54.4x28.0x1.2mm, Pin-Row 25.4mm
- **Joystick**: KY-023 (AZDelivery) -- 34x26mm PCB, Loch-Grid 26.67x20.32mm (1.05"x0.80"), M4
- **Drucksensor**: MPS20N0040D-S + HX710B -- 20x15x5mm
- **Display** (optional): ST7735 1.8" TFT via SPI
- **GPIOs**: Joystick GPIO33 (VRX), GPIO35 (VRY), GPIO21 (SW); Sensor GPIO32 (DATA), GPIO25 (CLK)
- Firmware erkennt Board-Typ automatisch und setzt Pins

## Deployment
- Zwei Firmware-Varianten: MicroPython (*.py im Root) und Arduino C++ (firmware/arduino/)
- **MicroPython**: Upload via `mpremote` / `tools/upload-esp32.sh`
- **Arduino**: PlatformIO `pio run -e esp32 -t upload` + `pio run -e esp32 -t uploadfs`
- **OTA**: Beide Varianten pruefen beim Boot `mundmaus.de/ota/manifest.json` (Basic Auth)
- **Arduino OTA Auth**: Build-Flag `OTA_AUTH_B64` aus Environment, MicroPython: `ota_auth.py` (gitignored)
- **Prod-Flash auf mblt**: `esptool` via `uvx` (kein PlatformIO noetig), Binaries von ai kopieren
- WiFi-Config: NVS (Arduino) / `wifi.json` (MicroPython), AP-Fallback wenn kein STA

## Architektur
- **MicroPython**: asyncio-basiert: sensor_loop (50Hz), server_loop (100Hz), display_loop (0.2Hz)
- **Arduino**: FreeRTOS: Sensor-Task (Core 1, 50Hz), AsyncTCP/HTTP (Core 0), WDT-Heartbeat
- HTTP File-Server + WebSocket Server auf ESP32
- Spiele als `.html.gz` im `www/` Verzeichnis auf LittleFS (Arduino) / Flash (MicroPython)
- OTA: Manifest-Check → Portal zeigt Updates → User klickt Install → Games + Firmware
- **Arduino Rollback**: ESP-IDF Dual-Partition + `markBootOk()`
- **MicroPython Rollback**: `.bak`-Dateien + `boot.py` Counter + Recovery-AP
- Solitaire-Testserver: `systemctl --user status mundmaus-solitaire` (Port 9993)

## Endnutzer & Bedienung
- **Endnutzer** -- Tetraplegie, kann nur Gesichtsmuskulatur nutzen
- UX muss extrem simpel und zuverlaessig sein
- Kein Loeten, nur Breadboard + DuPont-Jumper
- **Betreuer/Pfleger** -- wechselnde Pflegekraefte, KEINE Schulung moeglich
  - Muessen Spiele per Tastatur/Maus bedienen koennen (Fallback)
  - Footer in jedem Spiel zeigt Keyboard-Shortcuts (Pfeiltasten, Leertaste, N, K)
  - Grosse beschriftete Buttons (Neu, Zurueck) rechts neben dem Spielfeld
  - Kiosk-Mode (K) vereinfacht Ansicht fuer den Endnutzer
- **Mundsteuerung**: Joystick mit Mundstueck, Lippen/Zunge fuer Navigation
- **Drucksensor**: Pusten/Saugen ins Mundstueck -> Silikonschlauch geht seitlich ab nach links (+X) -> laeuft AUSSEN am Gehaeuse -> wird von aussen auf Sensor-Barb gesteckt
- **Schlauch-Constraint**: Darf nicht stark gebogen sein (zieht am Joystick, beeintraechtigt Navigation)
- **Sichtfeld**: Joystick am oberen Rand (+Y) des Gehaeuses, Gehaeuse erstreckt sich unterhalb -> maximale Sichtfreiheit

## 3D-Gehaeuse (v5.5)
- **CadQuery Koordinaten-Regel**: Bei JEDER Geometrie-Operation die absolute Position als Kommentar + benannte Variable berechnen BEVOR die Workplane erstellt wird. Beispiel:
  ```python
  wall_x_start = ESP_POS_X - wall_len / 2  # = 23.0 (ESP32-Bereich, +X)
  # Workplane("YZ").workplane(offset=wall_x_start)  ← Wert muss positiv sein fuer +X
  ```
  NIEMALS Offset-Ausdruecke inline schreiben ohne den resultierenden Wert zu pruefen. Vorzeichen-Fehler bei Workplane-Offsets sind der haeufigste 3D-Bug.
- **CadQuery** -- `enclosure/mundmaus_v55_enclosure.py`
- **Validierung** -- `enclosure/validate_enclosure.py` (Masse, Clearances, Druckbarkeit, Nut-Insertion)
- **Ausgabe** -- `enclosure/output/` (STL, PNG, Report)
- **Masse**: 136x50x39mm, 2mm Waende (5 Perimeter @ 0.4mm)
- **Layout** (-X -> +X): Mic-Mount -> Joystick-Saeulen(X=8) -> Sensor(X=42) -> ESP32(X=35)
- **Joystick**: 4 Saeulen (D8mm, D11mm Flare-Basis) statt Massiv-Sockel -- USB-Kabel laeuft zwischen den Fuessen
- **Lid-Loch**: 14mm Kreis (Offset X=+1.1, Y=-0.8 vs JOY_POS wg. Housing-Versatz), 2mm Chamfer
- **Lid-Retention**: Detent-Ridge (0.5mm) an 7 Punkten auf Lip + passende Groove (0.55mm) in Base-Wand
- **Generieren**: `/home/ai/.local/share/mamba/envs/cadquery/bin/python enclosure/mundmaus_v55_enclosure.py --outdir enclosure/output`

## 3D-Drucker (Bambu Lab P2S)
- **Details**: siehe `projects/bambu-p2s/CLAUDE.md`
- **Generisches Druck-Tool**: `projects/bambu-p2s/bambu-print.py` (projektubergreifend, Config in `projects/bambu-p2s/profiles/`)
- **MundMaus drucken**: `enclosure/print-p2s.sh base` / `enclosure/print-p2s.sh lid`
- **AMS Slot 4**: Grau PETG

## Agent-Flow
- **micropython-Agent** direkt, kein Coordinator
- **arduino-Agent**: PlatformIO Build + Flash
- 3D-Gehaeuse: **3d-Agent** (CadQuery)

## Neues Spiel hinzufuegen (Checkliste)
Wenn ein neues Spiel erstellt wird, muessen ALLE Punkte erledigt werden:

### Pflicht-Features (aus Quality Session 2026-04-06)
- [ ] **Charge-Navigation**: `computeTarget()`, `startCharge()`, `cancelCharge()`, `completeCharge()`, `chargeLoop()`, `renderChargePreview()` — SVG stroke-dasharray Animation
- [ ] **navigate() ruft cancelCharge() auf** — erste Zeile in navigate()
- [ ] **initGame()/newGame() ruft cancelCharge() auf** — verhindert stale State
- [ ] **Keyboard Dual-Mode**: `kbSimMode` + "J" Toggle + `updateKbMode()` + `⌨ Direkt`/`⌨ Sim` Indicator
- [ ] **keyup Listener** fuer Arrow-Keys (cancelCharge bei Sim-Mode)
- [ ] **WebSocket**: `nav_hold`/`nav_release`/`nav` (legacy) Handler mit `charge.wsSupported` Auto-Detect
- [ ] **WS-Reconnect deduped**: `wsReconnectTimer` Handle + clearTimeout
- [ ] **AI setTimeout cancelable** (wenn AI vorhanden): Handle speichern, clearTimeout in newGame/showMenu, re-check Guards im Callback
- [ ] **Settings-Fetch**: `fetch('/api/settings')` laedt `NAV_COOLDOWN_MS` als `navCooldown`
- [ ] **Direct-Mode Cooldown**: 120ms fester Cooldown in navigate() (nicht navCooldown!)

### Visuelles (Zero-Defects Standard)
- [ ] **Footer**: Icon-Sprache (`↻ ↩ 💡 ⌨ 👥 📺 🏠`), schwarzer Hintergrund `rgba(0,0,0,0.7)`
- [ ] **Header**: schwarzer Hintergrund `rgba(0,0,0,0.7)` (NICHT blau)
- [ ] **Action-Buttons**: Border `rgba(255,255,255,0.25)`, Background `rgba(255,255,255,0.1)`
- [ ] **Puff-Icon**: `rgba(255,255,255,0.5)`, Track `rgba(255,255,255,0.15)`
- [ ] **Pile-Slots/Leere Felder**: Border >= `rgba(255,255,255,0.3)`, Label >= `rgba(255,255,255,0.4)`
- [ ] **Karten** (falls Kartenspiel): Hoehe 14.5vw, Center-Font 3.5vw mit line-height:1 + Padding
- [ ] **Dynamischer FUO** (falls gestapelte Karten): Skaliert mit Viewport-Hoehe, min 1.2vw, max 3.8vw
- [ ] **Multiplayer-Indicator** (falls MP): `👥 Einzel`/`👥 Multi` im Footer

### Playwright-Test (vor Deploy)
- [ ] Spiel starten, spielen, gewinnen → Overlay erscheint
- [ ] Neues Spiel nach Gewinn → Overlay weg, State clean
- [ ] Select → Navigate weg → zurueck → Deselect funktioniert
- [ ] Undo bis leer → kein Crash
- [ ] "N" waehrend AI denkt → AI cancelled, kein Crash
- [ ] Rapid 10x New Game → kein State-Leak
- [ ] 1920x1080 Screenshot → alles sichtbar, kein Overflow

### Dateien + Deploy
1. `games/<name>.html` erstellen
2. `games/<name>.html.gz` erzeugen (gzip)
3. `firmware/arduino/data/www/<name>.html.gz` kopieren (LittleFS)
4. `manifest.json` — Eintrag hinzufuegen
5. `screenshots/<name>.png` — Gameplay-Screenshot (NACH Schwierigkeitswahl)
6. `README.md` — Screenshot-Zeile + Spiele-Tabelle + Projektstruktur + Upload-Befehl
7. `website/index.html` — Game-Card mit Bild + Beschreibung
8. `website/img/<name>.jpg` — Screenshot fuer Website
9. `tools/check-games.sh` ausfuehren — muss ALL OK zeigen
10. `tools/deploy-website.sh` + `tools/deploy-ota.sh` — deployen
Name-Mapping fuer deutsche Anzeigenamen: in `tools/check-games.sh` DISPLAY_NAMES pflegen.

## OTA Deploy-Workflow
1. Code aendern + committen
2. `tools/update_manifest.py` — Versionen bumpen
3. Arduino: `OTA_AUTH_B64=... pio run -e esp32` → `scp firmware.bin mbs:/srv/mundmaus/ota/`
4. `tools/deploy-ota.sh` — Manifest + Dateien auf mundmaus.de deployen
5. ESP32 prueft beim naechsten Boot automatisch
