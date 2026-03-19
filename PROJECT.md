# MundMaus — Projekt-Kontext

## Hardware
- **Board**: ESP32-WROOM-32 DevKitC V4 (AZDelivery) — 54.4×28.0×1.2mm, Pin-Row 25.4mm
- **Joystick**: KY-023 (AZDelivery) — 34×26mm PCB, Loch-Grid 26.67×20.32mm (1.05"×0.80"), M4
- **Drucksensor**: MPS20N0040D-S + HX710B — 20×15×5mm
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
- **Papa** ist der Endnutzer — Tetraplegie, kann nur Gesichtsmuskulatur nutzen
- UX muss extrem simpel und zuverlaessig sein
- Kein Loeten, nur Breadboard + DuPont-Jumper
- **Mundsteuerung**: Joystick mit Mundstück, Lippen/Zunge fuer Navigation
- **Drucksensor**: Pusten/Saugen ins Mundstück → Silikonschlauch geht seitlich ab nach links (+X) → läuft AUSSEN am Gehäuse → wird von aussen auf Sensor-Barb gesteckt
- **Schlauch-Constraint**: Darf nicht stark gebogen sein (zieht am Joystick, beeinträchtigt Navigation)
- **Sichtfeld**: Joystick am oberen Rand (+Y) des Gehäuses, Gehäuse erstreckt sich unterhalb → maximale Sichtfreiheit

## 3D-Gehäuse (v5.5)
- **CadQuery** — `enclosure/mundmaus_v55_enclosure.py`
- **Validierung** — `enclosure/validate_enclosure.py` (Maße, Clearances, Druckbarkeit, Nut-Insertion)
- **Ausgabe** — `enclosure/output/` (STL, PNG, Report)
- **Maße**: 136×50×39mm, 2mm Wände (5 Perimeter @ 0.4mm)
- **Layout** (−X → +X): Mic-Mount → Joystick-Säulen(X=8) → Sensor(X=42) → ESP32(X=35)
- **Joystick**: 4 Säulen (Ø8mm, Ø11mm Flare-Basis) statt Massiv-Sockel — USB-Kabel läuft zwischen den Füßen
- **Generieren**: `/home/ai/.local/share/mamba/envs/cadquery/bin/python enclosure/mundmaus_v55_enclosure.py --outdir enclosure/output`

## 3D-Drucker (Bambu Lab P2S)
- **Details**: siehe [`enclosure/BAMBU.md`](enclosure/BAMBU.md)
- **Generisches Druck-Tool**: `tools/bambu-print.sh` (projektübergreifend, Config in `tools/bambu-profiles/`)
- **MundMaus drucken**: `enclosure/print-p2s.sh base` / `enclosure/print-p2s.sh lid`
- **AMS Slot 4**: Grau PETG

## Kontakt
- **E-Mail**: mbraig@gmail.com

## Agent-Flow
- **micropython-Agent** direkt, kein Coordinator
- 3D-Gehaeuse: **3d-Agent** (CadQuery)
