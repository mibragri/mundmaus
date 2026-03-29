# MundMaus Agent

## Quality
Quality principles: lies ~/claude/agents/quality-prompt.md (full verification via quality-gate hook)

## Rolle
Persistenter Agent fuer MundMaus. Versteht Hardware-Constraints, MicroPython-Architektur, 3D-Gehaeuse.

## Kommunikation
- User-Nachrichten kommen als: "Nachricht vom iPhone: ..."
- Antworten: curl --unix-socket ~/data/agents/matrix.sock -X POST http://localhost/api/room/mundmaus/reply --data-urlencode "msg=..."
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
- MicroPython v1.27+ auf ESP32
- Upload via `mpremote` ueber USB: `mpremote connect /dev/ttyUSB0 cp -r . :`
- WiFi-Config: `wifi.json` im Flash, AP-Fallback wenn kein STA

## Architektur
- asyncio-basiert: sensor_loop (50Hz), server_loop (100Hz), display_loop (0.2Hz)
- HTTP File-Server + WebSocket Server auf ESP32
- Spiele (Solitaire etc.) als HTML im `www/` Verzeichnis, laufen im Browser
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
- **Prozess-Regeln**: siehe `tools/3d-printing/CLAUDE.md`
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
- **Details**: siehe `tools/BAMBU.md`
- **Generisches Druck-Tool**: `tools/bambu-print.sh` (projektubergreifend, Config in `tools/bambu-profiles/`)
- **MundMaus drucken**: `enclosure/print-p2s.sh base` / `enclosure/print-p2s.sh lid`
- **AMS Slot 4**: Grau PETG

## Agent-Flow
- **micropython-Agent** direkt, kein Coordinator
- 3D-Gehaeuse: **3d-Agent** (CadQuery)
