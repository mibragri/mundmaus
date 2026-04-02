# MundMaus

Assistive Mundsteuerung fuer Tetraplegiker. Ein ESP32 mit Joystick und Drucksensor steuert browserbasierte Spiele ueber WebSocket — ohne Installation, ohne App, nur WLAN und Browser.

Pusten statt Klicken. Joystick statt Maus.

## Features

- **Mundsteuerung** — KY-023 Joystick fuer Navigation, MPS20N0040D-S Drucksensor fuer Aktionen (Pusten = Klick)
- **3 Spiele** — Solitaire, Schach, Memo — alle per Joystick+Pusten spielbar
- **Kabellos** — ESP32 eroeffnet eigenen WLAN-Hotspot oder verbindet sich mit bestehendem Netzwerk
- **Browser-Spiele** — HTML5 wird direkt vom ESP32 ausgeliefert (gzip-komprimiert), kein Internet noetig
- **OTA Updates** — Firmware + Spiele ueber WiFi aktualisierbar, mit Rollback + Recovery-AP
- **Settings UI** — Joystick/Puff-Empfindlichkeit live im Browser einstellen
- **Barrierefreiheit** — Farbenblind-sichere Markierungen, Audio-Feedback, Kiosk-Modus
- **Captive Portal** — WLAN-Konfiguration direkt im Browser
- **Erweiterbar** — HTML-Dateien in `www/` ablegen, erscheinen automatisch im Portal

## Architektur

```
                        WebSocket :81
┌──────────────┐◄────────────────────────────►┌──────────────┐
│    ESP32     │         HTTP :80              │   Browser    │
│              │                               │   (TV/PC)    │
│  Joystick ───┤  ┌────────────────────────┐   │              │
│  Puff-Sensor─┤  │ Portal (/)             │──►│  Solitaire   │
│  WiFiManager │  │ Games (/www/*.html.gz) │   │  Schach      │
│  WS-Server   │  │ Settings (/www/settings│   │  Memo        │
│  OTA Updater │  │ REST API (/api/*)      │   │  Settings    │
└──────────────┘  └────────────────────────┘   └──────────────┘
```

**Datenfluss:** Firmware pollt Sensoren (50 Hz) → erkennt Richtung/Puff → sendet JSON ueber WebSocket → Browser fuehrt Spielaktion aus.

## Hardware

| Komponente | Typ | Zweck | ca. Preis |
|------------|-----|-------|-----------|
| Microcontroller | ESP32-WROOM-32 DevKitC V4 | WiFi + Firmware | ~8 EUR |
| Joystick | KY-023 | 2-Achsen-Navigation + Button | ~3 EUR |
| Drucksensor | MPS20N0040D-S + HX710B | Puff-Erkennung (24-bit ADC) | ~5 EUR |
| Silikonschlauch | 4mm ID | Mundstueck → Sensor | ~3 EUR |
| Display (optional) | ST7735 1.8" TFT | Status-Anzeige | ~5 EUR |

**Gesamtkosten: ~25 EUR** (ohne Display, ohne Gehaeuse). Kein Loeten — alle Verbindungen ueber DuPont-Kabel auf Breadboard.

**Alternative:** ESP32-S3 (N16R8) — 8MB PSRAM, USB-C, USB-HID moeglich. Firmware erkennt das Board automatisch.

### Pin-Belegung

```
ESP32-WROOM DevKitC V4                ESP32-S3-DevKitC-1 (N16R8)
┌─────────────────────┐               ┌─────────────────────┐
│                 3V3 ├─ KY-023 +5V   │                 3V3 ├─ KY-023 +5V
│                 GND ├─ KY-023 GND   │                 GND ├─ KY-023 GND
│                     │   HX710B GND  │                     │   HX710B GND
│                     │               │                     │
│  GPIO33 (ADC1_CH5) ├─ KY-023 VRX   │  GPIO1  (ADC1_CH0) ├─ KY-023 VRX
│  GPIO35 (ADC1_CH7) ├─ KY-023 VRY   │  GPIO2  (ADC1_CH1) ├─ KY-023 VRY
│  GPIO21            ├─ KY-023 SW    │  GPIO42            ├─ KY-023 SW
│                     │               │                     │
│  GPIO32            ├─ HX710B DATA  │  GPIO4             ├─ HX710B DATA
│  GPIO25            ├─ HX710B CLK   │  GPIO5             ├─ HX710B CLK
│                     │               │                     │
│  5V / VIN          ├─ HX710B VCC   │  5V / VIN          ├─ HX710B VCC
│                     │               │                     │
│         USB ────────┤               │      USB-C ─────────┤
└─────────────────────┘               └─────────────────────┘
```

### Verkabelung

```
KY-023 Joystick          ESP32-WROOM         HX710B Drucksensor
┌───────────┐            ┌───────────┐       ┌───────────┐
│ GND ──────┼────────────┤ GND       │       │ GND ──────┼──── GND
│ +5V ──────┼────────────┤ 3V3       │       │ VCC ──────┼──── 5V/VIN
│ VRX ──────┼────────────┤ GPIO33    │       │ DATA ─────┼──── GPIO32
│ VRY ──────┼────────────┤ GPIO35    │       │ CLK ──────┼──── GPIO25
│ SW  ──────┼────────────┤ GPIO21    │       │           │
└───────────┘            └───────────┘       └───────────┘
                              │
                    MPS20N0040D-S Sensor
                    (auf HX710B Board)
                    Silikonschlauch 4mm
                    vom Mundstueck
```

> **Hinweis:** Joystick VRX/VRY muessen an ADC1-faehige Pins (GPIO32-39 bei WROOM). ADC2 ist bei aktivem WiFi nicht nutzbar. ESP32-S3 verwendet andere Pins — siehe Tabelle oben.

Detaillierte Pin-Tabelle mit Display-Pins: siehe [MUNDMAUS-SETUP.md](MUNDMAUS-SETUP.md).

## Firmware-Varianten

Zwei Firmware-Optionen — gleiche Features, gleiche HTML-Spiele:

| | MicroPython | Arduino C++ |
|---|---|---|
| Sprache | Python | C++ (PlatformIO) |
| RAM frei | ~80 KB | ~188 KB |
| Dev-Zyklus | 2-5s (mpremote) | 10-30s (compile+flash) |
| OTA | Dateibasiert (.py/.html) | Dual-Partition + LittleFS |
| Verzeichnis | `*.py` (Root) | `firmware/arduino/` |

## Setup

### Option A: MicroPython flashen

```bash
pip3 install esptool mpremote mpy-cross

esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 \
  write_flash -z 0x1000 ESP32_GENERIC-20251209-v1.27.0.bin
```

Firmware: [micropython.org/download/ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/)
Fuer ESP32-S3: [micropython.org/download/ESP32_GENERIC_S3](https://micropython.org/download/ESP32_GENERIC_S3/) (SPIRAM-Build waehlen)

### 2. Dateien hochladen

```bash
# Alles kompilieren, minifyen, hochladen und rebooten:
tools/upload-esp32.sh
```

Oder manuell:
```bash
mpremote connect /dev/ttyUSB0 cp boot.py main.py config.py :/
mpremote connect /dev/ttyUSB0 mkdir :www
mpremote connect /dev/ttyUSB0 cp games/solitaire.html :/www/
mpremote connect /dev/ttyUSB0 cp games/chess.html :/www/
mpremote connect /dev/ttyUSB0 cp games/memo.html :/www/
```

### Option B: Arduino C++ flashen

```bash
cd firmware/arduino
pip install platformio

# Firmware kompilieren + flashen:
pio run -e esp32 -t upload

# Spieledateien (LittleFS) flashen:
pio run -e esp32 -t uploadfs
```

Beim ersten Boot ohne WiFi: Credentials per Serial senden (`SSID:PASSWORD`) oder ueber den MundMaus-Hotspot konfigurieren.

### 3. Verbinden und spielen

1. Handy/PC mit WLAN **MundMaus** verbinden (Passwort: `mundmaus1`)
2. Browser oeffnen: `http://192.168.4.1`
3. Spiel im Portal auswaehlen
4. Joystick + Pusten zum Spielen

## Projektstruktur

```
mundmaus/
├── boot.py              # Rollback-Logik, Recovery-AP, Board-Erkennung
├── main.py              # Async Event-Loop, WDT, Sensor/Server Tasks
├── config.py            # Board-Detection, Pins, Konfiguration, Runtime-Settings
├── sensors.py           # CalibratedJoystick + PuffSensor (HX710B)
├── server.py            # HTTP/WS Server, Portal, File-Serving (gzip)
├── updater.py           # OTA Manifest-Check + Download
├── wifi_manager.py      # STA/AP-Modus, Credentials, Reconnect
├── display.py           # ST7735 TFT (optional)
├── games/
│   ├── solitaire.html   # Klondike Solitaire
│   ├── chess.html        # Schach (vs AI, 4 Schwierigkeitsstufen)
│   ├── memo.html         # Memory/Memo (4 Feldgroessen)
│   ├── settings.html     # Einstellungen (Slider + Experten-Modus)
│   └── STANDARDS.md      # Game Design Standards
├── tools/
│   ├── upload-esp32.sh   # Kompilieren + Minify + Upload + Reboot
│   ├── minify_gzip.py    # HTML minifyen + gzip fuer ESP32
│   ├── update_manifest.py # OTA Manifest-Versionierung
│   ├── provision-esp32.sh # Erstinstallation (Flash + Upload)
│   ├── deploy-ota.sh     # OTA-Dateien auf Server deployen
│   └── test-esp32.sh     # Syntax-Check + Boot-Test + E2E
├── firmware/
│   └── arduino/          # Arduino C++ Firmware (PlatformIO)
│       ├── platformio.ini
│       ├── include/      # Header files
│       ├── src/          # C++ Implementation
│       └── data/www/     # LittleFS Game-Dateien
├── enclosure/            # 3D-Gehaeuse (CadQuery)
├── site/                 # mundmaus.de Website
├── MUNDMAUS.md           # Technische Dokumentation
├── MUNDMAUS-SETUP.md     # Hardware-Setup-Anleitung
└── manifest.json         # OTA Versions-Manifest
```

Auf dem ESP32:
```
/
├── boot.py              # Rollback + Recovery (bleibt .py)
├── main.py              # Event-Loop (bleibt .py)
├── config.py            # Konfiguration (bleibt .py, globals()-Zugriff)
├── sensors.mpy          # Pre-compiled Bytecode
├── server.mpy           #   (spart RAM gegenueber .py)
├── updater.mpy
├── wifi_manager.mpy
├── display.mpy
├── versions.json        # Installierte OTA-Versionen
├── wifi.json            # Gespeicherte WLAN-Credentials
├── settings.json        # Benutzerdefinierte Einstellungen
└── www/
    ├── solitaire.html.gz  # Spiele (gzip-komprimiert, ~4-5x kleiner)
    ├── chess.html.gz
    ├── memo.html.gz
    └── settings.html.gz
```

## Konfiguration

Alle Parameter in `config.py`, live aenderbar ueber die Settings-Seite im Browser:

| Parameter | Default | Beschreibung |
|-----------|---------|-------------|
| `DEADZONE` | 150 | Joystick-Totzone (ADC-Einheiten) |
| `NAV_THRESHOLD` | 800 | Schwelle fuer Richtungserkennung |
| `NAV_REPEAT_MS` | 300 | Wiederholrate bei gehaltenem Joystick |
| `PUFF_THRESHOLD` | 0.25 | Puff-Empfindlichkeit (0.0–1.0) |
| `PUFF_COOLDOWN_MS` | 400 | Mindestabstand zwischen Puffs |
| `PUFF_SAMPLES` | 5 | Glaettung des Drucksensor-Signals |
| `SENSOR_POLL_MS` | 20 | Sensor-Abtastrate (50 Hz) |

WLAN-Zugangsdaten + Einstellungen koennen zur Laufzeit ueber den Browser konfiguriert werden und ueberleben Neustarts.

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
{"type": "config_preview", "key": "DEADZONE", "value": 100}
{"type": "config_save"}
{"type": "calibrate"}
```

## Lizenz

AGPL-3.0 — basiert auf [mibragri/mouthMouse](https://github.com/mibragri/mouthMouse).
