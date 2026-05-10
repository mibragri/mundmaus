# MundMaus Agent

## Quality
Quality principles: lies ~/claude/agents/quality-prompt.md (full verification via quality-gate hook)

## Rolle
Persistenter Agent fuer MundMaus. Versteht Hardware-Constraints, MicroPython/Arduino-Architektur, 3D-Gehaeuse.

## Kommunikation
- User-Nachrichten kommen als: "Nachricht vom iPhone: ..."
- Antworten: `agentctl reply "..."` (Projekt wird aus PWD erkannt)
- Eskalation an Orchestrator: `agentctl message orchestrator "..."`

## Delegation
- `agentctl spawn micropython|3d|ci|auditor --project mundmaus --briefing <datei>`
- Status: `agentctl status`

---

## Hardware
- **Board**: ESP32-WROOM-32 DevKitC V4 (AZDelivery) — 54.4x28.0x1.2mm, Pin-Row 25.4mm
- **Joystick**: KY-023 — 34x26mm PCB, Loch-Grid 26.67x20.32mm, M4
- **Drucksensor**: MPS20N0040D-S + HX710B
- **Display** (optional): ST7735 1.8" TFT via SPI
- **GPIOs**: Joystick GPIO33/35/21, Sensor GPIO32/25 (Firmware erkennt Board automatisch)

## Architektur & Deployment
- Zwei Firmware-Varianten: MicroPython (`*.py` im Root) und Arduino C++ (`firmware/arduino/`)
- **MicroPython**: asyncio-Loops (sensor 50Hz, server 100Hz), Upload via `tools/upload-esp32.sh`
- **Arduino**: FreeRTOS (Sensor Core 1, AsyncTCP Core 0, WDT-Heartbeat), `pio run -e esp32 -t upload` + `-t uploadfs`
- **Spiele**: `.html.gz` in `www/` auf LittleFS (Arduino) bzw. Flash (MicroPython)
- **OTA**: Manifest-Check beim Boot gegen `mundmaus.de/ota/manifest.json`. Auth: `OTA_AUTH_B64` Build-Flag (Arduino) bzw. `ota_auth.py` (MicroPython, gitignored)
- **Rollback**: Arduino Dual-Partition + `markBootOk()`; MicroPython `.bak` + `boot.py`-Counter + Recovery-AP
- **WiFi**: NVS (Arduino) / `wifi.json` (MicroPython), AP-Fallback wenn kein STA
- **Prod-Flash auf mblt**: `esptool` via `uvx`, Binaries von ai kopieren
- **Solitaire-Testserver lokal**: `systemctl --user status mundmaus-solitaire` (Port 9993)

## Endnutzer
- Tetraplegie-Patient (taub) — Mundsteuerung mit Joystick + Pusten/Saugen via MPS20-Schlauch. Kein Loeten, nur Breadboard + DuPont
- **Schlauch-Constraint**: Geht seitlich (+X) ab, AUSSEN am Gehaeuse — nicht stark gebogen (zieht sonst am Joystick)
- **Sichtfeld**: Joystick am +Y-Rand des Gehaeuses, Gehaeuse erstreckt sich nach -Y
- **Betreuer** (wechselnde Pfleger, keine Schulung): muessen Spiele per Tastatur/Maus bedienen. Footer + grosse Buttons (Neu, Zurueck) sichtbar; Kiosk-Mode (K) vereinfacht fuer Patient

## 3D-Gehaeuse (v5.5)
- **CadQuery Koordinaten-Regel**: Bei JEDER Geometrie-Operation absolute Position als Variable + Kommentar berechnen BEVOR Workplane erstellt wird:
  ```python
  wall_x_start = ESP_POS_X - wall_len / 2  # = 23.0 (ESP32-Bereich, +X)
  # Workplane("YZ").workplane(offset=wall_x_start)  ← Vorzeichen pruefen
  ```
  Vorzeichen-Fehler bei Workplane-Offsets sind der haeufigste 3D-Bug.
- **Code**: `enclosure/mundmaus_v55_enclosure.py`, Validierung: `enclosure/validate_enclosure.py`
- **Masse**: 136x50x39mm, 2mm Waende. Layout (-X→+X): Mic-Mount → Joystick-Saeulen(X=8) → ESP32(X=35) → Sensor(X=42)
- **Generieren**: `/home/ai/.local/share/mamba/envs/cadquery/bin/python enclosure/mundmaus_v55_enclosure.py --outdir enclosure/output`

## 3D-Drucker (Bambu Lab P2S)
- Generisches Tool: `projects/bambu-p2s/bambu-print.py` (siehe `projects/bambu-p2s/CLAUDE.md`)
- MundMaus drucken: `enclosure/print-p2s.sh base|lid` — AMS Slot 4 (Grau PETG)

## Spiele — neues Spiel hinzufuegen
- **Success**: `tools/check-games.sh` zeigt ALL OK, Playwright-Test besteht (start → spielen → gewinnen → neues Spiel → kein State-Leak, Undo bis leer crasht nicht), Screenshot in mid-game (nicht leerer Start), 1920x1080 ohne Overflow
- **Vorlage**: bestehendes Spiel klonen (z.B. `games/freecell.html`) — Charge-Navigation, WS-Reconnect mit Backoff, Keyboard-Dual-Mode (`J`-Toggle), AI-cancelable, Settings-Fetch (`/api/settings` fuer `NAV_COOLDOWN_MS`) wandern automatisch mit
- **Visual + Interaction Standards**: `games/STANDARDS.md` (Theme, Cursor/Selection, Layout, Puff-Indicator)
- **Invarianten** (beim Refactoring nicht brechen): `navigate()` und `newGame()` rufen als ERSTES `cancelCharge()`; AI-`setTimeout`-Handles speichern + `clearTimeout` in `newGame`/`showMenu`; WS-Reconnect via *einem* `wsReconnectTimer`-Handle (nicht stacken); Direct-Mode-Cooldown 120ms (nicht `navCooldown`)
- **Integration** (von `check-games.sh` geprueft): screenshot, README, manifest, website, LittleFS-`.gz`, Anzeigename in `tools/check-games.sh DISPLAY_NAMES`

## OTA Deploy
1. Code committen
2. `tools/update_manifest.py` — Versionen bumpen
3. Arduino: `OTA_AUTH_B64=... pio run -e esp32` → `scp firmware.bin mbs:/srv/mundmaus/ota/`
4. `tools/deploy-ota.sh` — Manifest + Dateien auf mundmaus.de deployen
5. ESP32 prueft beim naechsten Boot
