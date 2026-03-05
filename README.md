# MundMaus

Assistive Mundsteuerung fuer Tetraplegiker. Ein ESP32-S3 mit Joystick und Drucksensor steuert browserbasierte Spiele ueber WebSocket — ohne Installation, ohne App, nur WLAN und Browser.

Pusten statt Klicken. Joystick statt Maus.

## Features

- **Mundsteuerung** — KY-023 Joystick fuer Navigation, MPS20N0040D-S Drucksensor fuer Aktionen (Pusten = Klick)
- **Kabellos** — ESP32-S3 eroeffnet eigenen WLAN-Hotspot oder verbindet sich mit bestehendem Netzwerk
- **Browser-Spiele** — HTML5-Spiele werden direkt vom ESP32 ausgeliefert, kein Internet noetig
- **Klondike Solitaire** — Vollstaendiges Kartenspiel mit Undo, Auto-Solve, Scoring und Kiosk-Modus
- **Barrierefreiheit** — Farbenblind-sichere Markierungen (Cyan/Magenta + Symbole), Audio-Feedback via Web Audio API
- **Captive Portal** — WLAN-Konfiguration direkt im Browser, kein Serial-Zugang noetig
- **Erweiterbar** — HTML-Dateien in `www/` ablegen, erscheinen automatisch im Spiele-Portal

## Architektur

```
┌──────────────┐         WebSocket :81         ┌──────────────┐
│   ESP32-S3   │◄────────────────────────────►│   Browser     │
│              │         HTTP :80              │              │
│  Joystick ───┤  ┌──────────────────────┐    │  Solitaire   │
│  Puff-Sensor─┤  │ Spiele-Portal (/)    │───►│  (HTML5)     │
│  WiFiManager │  │ Static Files (/www/) │    │              │
│  WS-Server   │  │ REST API (/api/*)    │    │  WiFi-Panel  │
└──────────────┘  └──────────────────────┘    └──────────────┘
```

**Datenfluss:** Firmware pollt Sensoren mit 50 Hz → erkennt Richtung oder Puff → sendet JSON ueber WebSocket → Browser fuehrt Spielaktion aus.

## WebSocket-Protokoll

ESP32 → Browser:
```json
{"type": "nav", "dir": "left|right|up|down"}
{"type": "action", "kind": "puff|press|new_game"}
{"type": "puff_level", "value": 0.42}
```

Browser → ESP32:
```json
{"type": "wifi_config", "ssid": "...", "password": "..."}
{"type": "wifi_scan"}
```

## Hardware

| Komponente | Typ | Zweck | ca. Preis |
|------------|-----|-------|-----------|
| Microcontroller | ESP32-S3-DevKitC-1 N16R8 | WiFi + Firmware | ~12 EUR |
| Joystick | KY-023 | 2-Achsen-Navigation + Button | ~3 EUR |
| Drucksensor | MPS20N0040D-S + HX710B | Puff-Erkennung (24-bit ADC) | ~5 EUR |
| Silikonschlauch | 4mm ID | Mundstueck → Sensor | ~3 EUR |
| Display (optional) | ST7735 1.8" TFT | Status-Anzeige | ~5 EUR |

**Gesamtkosten: ~25 EUR** (ohne Display, ohne Gehaeuse). Kein Loeten noetig — alle Verbindungen ueber DuPont-Kabel.

### Pin-Belegung (ESP32-S3)

| Funktion | GPIO | Typ |
|----------|------|-----|
| Joystick VRX | 1 | ADC |
| Joystick VRY | 2 | ADC |
| Joystick SW | 42 | Digital |
| Puff DATA | 4 | Digital |
| Puff CLK | 5 | Digital |

ESP32-WROOM wird ebenfalls unterstuetzt (automatische Board-Erkennung, andere Pins).

## Tech Stack

- **Firmware:** MicroPython v1.24+ (empfohlen v1.27) mit asyncio
- **Hardware-Abstraktion:** `machine.ADC`, `machine.Pin`, Bit-Bang fuer HX710B
- **Netzwerk:** HTTP/1.1 Server (Port 80) + WebSocket Server (Port 81), beide async
- **Frontend:** Vanilla HTML5/CSS/JS, keine Build-Tools, keine externen Dependencies
- **Audio:** Web Audio API (synthetische Toene, kein Laden von Dateien)

## Setup

### 1. MicroPython flashen

```bash
pip3 install esptool rshell

esptool.py --chip esp32s3 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32s3 --port /dev/ttyUSB0 --baud 460800 \
  write_flash -z 0x0 ESP32_GENERIC_S3-SPIRAM_OCT-20251209-v1.27.0.bin
```

Firmware-Download: [micropython.org/download/ESP32_GENERIC_S3](https://micropython.org/download/ESP32_GENERIC_S3/) — Variante **SPIRAM_OCT** fuer N16R8.

### 2. Dateien hochladen

```bash
rshell --buffer-size=30 -p /dev/ttyUSB0
> mkdir /pyboard/www
> cp boot.py main.py /pyboard/
> cp solitaire.html /pyboard/www/
```

### 3. Verbinden und spielen

1. Handy/PC mit WLAN **MundMaus** verbinden (Passwort: `mundmaus1`)
2. Browser oeffnen: `http://192.168.4.1`
3. Solitaire im Spiele-Portal auswaehlen
4. Joystick + Pusten zum Spielen

## Projektstruktur

```
mundmaus/
├── boot.py              # Board-Erkennung, GC init
├── main.py              # Firmware v3.0 (~950 Zeilen)
│                        #   WiFiManager, CalibratedJoystick,
│                        #   PuffSensor, MundMausServer
├── solitaire.html       # Klondike Solitaire (~1100 Zeilen)
├── MUNDMAUS.md          # Technische Dokumentation
├── MUNDMAUS-SETUP.md    # Hardware-Aufbau & Setup-Anleitung
└── pyproject.toml       # Ruff Linter-Konfiguration
```

Auf dem ESP32:
```
/
├── boot.py
├── main.py
├── wifi.json            # Gespeicherte WLAN-Credentials (auto-generiert)
└── www/
    └── solitaire.html
```

## Konfiguration

Alle Parameter stehen am Anfang von `main.py`:

| Parameter | Default | Beschreibung |
|-----------|---------|-------------|
| `DEADZONE` | 150 | Joystick-Totzone (ADC-Einheiten) |
| `NAV_THRESHOLD` | 800 | Schwelle fuer Richtungserkennung |
| `PUFF_THRESHOLD` | 0.25 | Puff-Empfindlichkeit (0.0–1.0) |
| `PUFF_COOLDOWN_MS` | 400 | Mindestabstand zwischen Puffs |
| `USE_DISPLAY` | False | ST7735 TFT aktivieren |
| `AP_SSID` | MundMaus | Hotspot-Name |
| `AP_PASS` | mundmaus1 | Hotspot-Passwort |

WLAN-Zugangsdaten koennen zur Laufzeit ueber den Browser konfiguriert werden.

## Lizenz

AGPL-3.0 — basiert auf [mibragri/mouthMouse](https://github.com/mibragri/mouthMouse).
