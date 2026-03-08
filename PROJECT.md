# MundMaus — Projekt-Kontext

## Hardware
- **Board**: ESP32-WROOM-32 DevKitC V4 (auch ESP32-S3 unterstuetzt, Auto-Detection)
- **Joystick**: KY-023 — GPIO33 (VRX), GPIO35 (VRY), GPIO21 (SW)
- **Drucksensor**: MPS20N0040D-S + HX710B — GPIO32 (DATA), GPIO25 (CLK)
- **Display** (optional): ST7735 1.8" TFT via SPI
- Firmware erkennt Board-Typ automatisch und setzt Pins

## Deployment
- MicroPython v1.27+ auf ESP32
- Upload via `mpremote` ueber USB: `mpremote connect /dev/ttyUSB0 cp -r . :`
- WiFi-Config: `wifi.json` im Flash, AP-Fallback wenn kein STA

## Architektur
- asyncio-basiert: sensor_loop (50Hz), server_loop (100Hz), display_loop (0.2Hz)
- HTTP File-Server + WebSocket Server auf ESP32
- Spiele (Solitaire etc.) als HTML im `www/` Verzeichnis, laufen im Browser

## Endnutzer & Bedienung
- **Papa** ist der Endnutzer — Tetraplegie, kann nur Gesichtsmuskulatur nutzen
- UX muss extrem simpel und zuverlaessig sein
- Kein Loeten, nur Breadboard + DuPont-Jumper
- **Mundsteuerung**: Joystick mit Mundstück, Lippen/Zunge fuer Navigation
- **Drucksensor**: Pusten/Saugen ins Mundstück → Silikonschlauch geht seitlich ab nach links (+X) → läuft AUSSEN am Gehäuse → wird von aussen auf Sensor-Barb gesteckt
- **Schlauch-Constraint**: Darf nicht stark gebogen sein (zieht am Joystick, beeinträchtigt Navigation)
- **Sichtfeld**: Joystick am oberen Rand (+Y) des Gehäuses, Gehäuse erstreckt sich unterhalb → maximale Sichtfreiheit

## Agent-Flow
- **micropython-Agent** direkt, kein Coordinator
- 3D-Gehaeuse: **3d-Agent** (OpenSCAD/CadQuery)
