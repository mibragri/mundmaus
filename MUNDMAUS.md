# MundMaus – Projektdokumentation v3.0

## Überblick

Assistive-Technology-Projekt: eine mundgesteuerte Spieleplattform für Menschen mit Tetraplegie. Basiert auf dem Open-Source-Projekt [mibragri/mouthMouse](https://github.com/mibragri/mouthMouse) und erweitert es um ein kartenspielbasiertes Interface mit barrierefreier Navigation.

**Zielgruppe:** Menschen die nur Gesichtsmuskulatur, Mund und Zunge nutzen können. Im Extremfall künstlich beatmet – können nicht pusten, sondern nur Wangenluft zusammenpressen.

**Kostenpunkt:** ~30 EUR für alle Komponenten (ohne Display, ohne Löten).

**Designprinzip:** Kein Löten, nur zusammenstecken. Alle Kabel sind DuPont-Jumper auf Breadboard. Jeder soll das nachbauen können.

---

## Systemarchitektur

```
┌──────────────────────────────────────────────────────────┐
│                   BROWSER (TV/Monitor)                    │
│                                                           │
│   http://<ESP-IP>/www/solitaire.html                     │
│   ┌──────────────────────────────────────────────────┐   │
│   │  Klondike Solitaire Engine (JS)                  │   │
│   │  ├── Kartenlogik + Spielregeln                   │   │
│   │  ├── Accessible Rendering (CVD-safe)             │   │
│   │  ├── Audio-Feedback (Web Audio API)              │   │
│   │  ├── Kiosk-Modus                                 │   │
│   │  └── WiFi-Setup-Panel                            │   │
│   └───────────────────────┬──────────────────────────┘   │
│                           │ WebSocket :81                  │
│                           │ HTTP :80                       │
└───────────────────────────┼──────────────────────────────┘
                            │
                ┌───────────┴────────────┐
                │  ESP32-S3 DevKitC-1    │
                │  MicroPython v1.27+    │
                │  (asyncio)             │
                │                        │
                │  ┌──────────────────┐  │
                │  │ WiFiManager      │  │  wifi.json (Flash)
                │  │ ├ STA-Modus      │  │
                │  │ └ AP-Fallback    │  │
                │  ├──────────────────┤  │
                │  │ HTTP File-Server │  │  www/*.html → Spiele
                │  │ WebSocket Server │  │  Joystick/Puff Events
                │  ├──────────────────┤  │
                │  │ CalibratedJoy    │──┼── KY-023 (S3: G1,G2,G42)
                │  │ + AutoCal        │  │
                │  ├──────────────────┤  │
                │  │ PuffSensor       │──┼── MPS20N0040D-S + HX710B
                │  │ (HX710B 24-bit)  │  │   (S3: G4,G5)
                │  ├──────────────────┤  │
                │  │ Display (opt.)   │──┼── ST7735 1.8" TFT
                │  └──────────────────┘  │
                └────────────────────────┘

Datenfluss (asyncio):
  sensor_loop (50Hz) ──→ WebSocket ──→ Browser
  server_loop (100Hz) ← HTTP/WS ←── Browser
  display_loop (0.2Hz) ──→ ST7735 TFT
```

---

## Dateien

| Datei | Ort auf ESP32 | Beschreibung | Zeilen |
|-------|---------------|-------------|--------|
| `main.py` | `/main.py` | Firmware v3.0 (asyncio, Board-Erkennung, File-Server) | ~750 |
| `boot.py` | `/boot.py` | Boot-Script (debug off, GC, Board-Info) | ~10 |
| `solitaire.html` | `/www/solitaire.html` | Klondike Solitaire (HTML+CSS+JS, single-file) | ~1070 |
| `wifi.json` | `/wifi.json` | Gespeicherte WLAN-Credentials (auto-generiert) | – |
| `mundmaus-gehaeuse.scad` | – (lokal) | 3D-Gehäuse (OpenSCAD, parametrisch) | ~290 |
| `MUNDMAUS.md` | – (lokal) | Diese Dokumentation | – |
| `MUNDMAUS-SETUP.md` | – (lokal) | Setup-Anleitung (Hardware, Pins, Netzwerk) | – |

### Verzeichnisstruktur auf dem ESP32

```
/                       (ESP32 Flash Root)
├── boot.py             (Board-Erkennung, GC)
├── main.py             (Firmware v3.0)
├── wifi.json           (auto-generiert nach WiFi-Setup)
└── www/
    ├── solitaire.html  (Klondike, ~36 KB)
    ├── memory.html     (zukünftig)
    └── ...             (weitere Spiele)
```

---

## Hardware

### Stückliste (BOM) – Kein Löten!

| Komponente | Modell | Preis | Bezugsquelle |
|-----------|--------|-------|--------------|
| ⭐ Mikrocontroller | Waveshare ESP32-S3-DEV-KIT-N16R8-**M** (mit Pins) | ~16 EUR | [Amazon.de B0DKSZ7J3S](https://www.amazon.de/dp/B0DKSZ7J3S) |
| Alternative | Heemol ESP32-S3 N16R8 DevKitC-1 (mit Pins + IPEX-Antenne) | ~14 EUR | [Amazon.de B0FKFXC6F8](https://www.amazon.de/dp/B0FKFXC6F8) |
| Joystick | KY-023 Thumb Joystick | ~2 EUR | Amazon/eBay |
| Drucksensor | MPS20N0040D-S + HX710B 24-bit ADC | ~4,30 EUR | [eBay 284856729901](https://ebay.de/itm/284856729901) |
| Display (optional) | ST7735 1.8" TFT SPI | ~7,50 EUR | Amazon/eBay |
| Silikonschlauch | ID 5-7mm, ~50cm | ~3 EUR | Baumarkt/Amazon |
| Breadboard | 830 Kontakte | ~3 EUR | Amazon |
| Kabel | DuPont Jumper Wires (M-F, M-M, F-F) | ~7 EUR | Amazon (Elegoo 120er Set) |
| USB-C Kabel | Daten + Strom | ~5 EUR | – |

**Gesamt: ~40 EUR** (mit Breadboard/Kabel, ohne Display) | **~26 EUR** (nur Kernkomponenten)

> ⚠️ **Wichtig beim ESP32-S3:** Unbedingt die Variante **mit vorverlöteten Pins** kaufen (Waveshare: "-M" Suffix, Heemol: steht in der Beschreibung). Sonst muss man selbst löten!

> ❌ **Nicht empfohlen:** AZ-Delivery DevKitC V4 (ESP32-WROOM-32) – nur 4MB Flash, kein PSRAM, Micro-USB. Funktioniert mit der Firmware (auto-erkannt), aber für das Open-Source-Projekt sollte ESP32-S3 empfohlen werden.

### Pin-Belegung

Die Firmware erkennt automatisch das Board und setzt die Pins:

| Funktion | ESP32-WROOM (V4) | ESP32-S3 (N16R8) | Hinweis |
|----------|-------------------|-------------------|---------|
| Joystick VRX | GPIO33 | **GPIO1** | ADC1 |
| Joystick VRY | GPIO35 | **GPIO2** | ADC1 |
| Joystick SW | GPIO21 | **GPIO42** | Digital, Pull-Up |
| Puff DATA | GPIO32 | **GPIO4** | Digital (HX710B) |
| Puff CLK | GPIO25 | **GPIO5** | Digital (HX710B) |
| Display A0 | GPIO2 | **GPIO6** | Data/Command |
| Display RST | GPIO14 | GPIO14 | Reset |
| Display CS | GPIO17 | GPIO17 | SPI CS |
| Display SCK | GPIO18 | GPIO18 | SPI CLK |
| Display SDA | GPIO23 | GPIO23 | SPI MOSI |

**ESP32-S3: GPIO33-39 existieren NICHT.** ADC1-Kanäle liegen auf GPIO1-10.

### Board-Erkennung in der Firmware

```python
import sys
if 'ESP32S3' in sys.implementation._machine:
    BOARD = 'ESP32-S3'
    PIN_VRX = 1; PIN_VRY = 2; PIN_SW = 42
    PIN_PUFF_DATA = 4; PIN_PUFF_CLK = 5
else:
    BOARD = 'ESP32-WROOM'
    PIN_VRX = 33; PIN_VRY = 35; PIN_SW = 21
    PIN_PUFF_DATA = 32; PIN_PUFF_CLK = 25
```

### Drucksensor (MPS20N0040D-S + HX710B)

Ersetzt den Water Flow Sensor aus dem Original-Projekt. Vorteile:

- 24-bit ADC-Auflösung → erkennt feinsten Munddruck
- 0-40 kPa Messbereich, typischer Munddruck 1-5 kPa
- Kein mechanisches Verschleißteil
- Digital-Ausgang (kein separater ADC nötig)
- 3,3V Betriebsspannung

**Anschluss:** Silikonschlauch vom Mundstück → T-Stück → Schlauch zum Sensor-Eingang. Der HX710B sitzt direkt auf dem Sensor-Board.

**Limitierung:** Nur Pusten (Überdruck), kein Saugen. Für Sip-and-Puff: Differenzdrucksensor MPXV7002DP.

### Joystick (KY-023) – Drift-Problem

Billige KY-023 haben häufig ADC-Drift (Zentrum wandert thermisch). Gelöst durch:

1. **Auto-Kalibrierung beim Boot:** 50 Samples bei Ruheposition → echte Mitte berechnen
2. **Deadzone:** ±150 ADC-Einheiten um die Mitte werden ignoriert
3. **Auto-Rekalibrierung:** Nach 10s Idle automatisch neu kalibrieren
4. Parameter einstellbar: `DEADZONE`, `NAV_THRESHOLD`, `CALIBRATION_SAMPLES`

---

## ESP32 Firmware (main.py v3.0)

### Architektur: asyncio

v3.0 nutzt MicroPython `asyncio` statt synchroner Polling-Loop:

```
asyncio.run(async_main)
  ├── sensor_loop()    – 50 Hz, Joystick + Puff → WebSocket
  ├── server_loop()    – 100 Hz, HTTP accept + WS accept + WS read
  └── display_loop()   – 0.2 Hz, ST7735 TFT update (optional)
```

**Vorteile gegenüber v2.1:**
- Sensor-Loop und Server blockieren sich nicht gegenseitig
- HTTP-Request für große HTML-Datei unterbricht Joystick-Abfrage nicht
- WiFi-Reconnect blockiert nicht die Puff-Erkennung
- Saubere Task-Trennung, einfacher erweiterbar

### Klassen

#### `WiFiManager`

Verwaltet die Netzwerkverbindung mit persistenter Speicherung.

```
Boot-Flow:
  load_credentials()     → liest wifi.json
       │
       ├─ Credentials da → connect_station(timeout=10s)
       │                         │
       │                    ├─ OK → Station-Modus (Router-IP)
       │                    └─ Fail → start_ap()
       │
       └─ Keine Credentials → start_ap()

start_ap():
  SSID: "MundMaus"
  Pass: "mundmaus1"
  IP:   192.168.4.1
```

Methoden:

- `load_credentials()` → liest `wifi.json`
- `save_credentials(ssid, pw)` → schreibt `wifi.json`, überlebt Reboot
- `delete_credentials()` → löscht `wifi.json`
- `connect_station(timeout_ms)` → verbindet mit gespeichertem WLAN
- `start_ap()` → startet Hotspot
- `scan_networks()` → scannt WLANs, sortierte SSID-Liste
- `get_status()` → Dict mit mode, ssid, ip, connected
- `startup()` → kompletter Boot-Flow, gibt `(ip, mode)` zurück

#### `CalibratedJoystick`

ADC-basierter Joystick mit Drift-Kompensation.

- `calibrate(samples=50)` → Mittelwert-Kalibrierung
- `read_centered()` → `(dx, dy)` relativ zur Mitte, Deadzone angewendet
- `get_direction()` → `'left'|'right'|'up'|'down'|None`
- `poll_navigation()` → mit Repeat-Timer (300ms)
- `poll_button()` → Entprellt, fallende Flanke
- `is_idle()` → True wenn nahe Mitte

#### `PuffSensor`

HX710B 24-bit ADC Bit-Bang-Reader für MPS20N0040D-S.

- `calibrate_baseline(samples=30)` → Ruhedruck-Kalibrierung
- `read_normalized()` → `0.0` bis `1.0`, gleitender Durchschnitt (5 Samples)
- `detect_puff()` → `True` bei Threshold + Cooldown (400ms)
- `get_level()` → aktueller Pegel für UI-Anzeige

#### `MundMausServer`

Kombinierter HTTP File-Server + WebSocket Server.

**HTTP (:80):**

| Endpunkt | Methode | Beschreibung |
|----------|---------|-------------|
| `/` | GET | Spiele-Portal (listet alle www/*.html) |
| `/www/<datei>` | GET | Statische Datei aus www/ servieren |
| `/api/wifi` | GET | WiFi-Status als JSON |
| `/api/wifi` | POST | Credentials speichern `{ssid, password}` |
| `/api/scan` | GET | WLAN-Scan `{networks: [...]}` |
| `/api/info` | GET | Board, Version, RAM |
| `/api/reboot` | GET | ESP32 Neustart |
| (alles andere) | GET | WiFi-Setup-Seite (Captive Portal) |

**File-Server Features:**
- Content-Type-Erkennung (.html, .js, .css, .json, .png, .jpg, .svg)
- Chunk-weise Übertragung (2048 Byte Buffer)
- Cache-Control Header (max-age=3600)
- 404-Handling
- Path-Traversal-Schutz (`..` blockiert)

**Spiele-Portal (GET /):**
- Scannt `www/` Ordner nach `.html` Dateien
- Generiert klickbare Buttons für jedes Spiel
- Zeigt IP, Board-Typ, Firmware-Version, freien RAM

**WebSocket (:81) – Ausgehend (ESP32 → Browser):**

```json
{"type": "nav", "dir": "left|right|up|down"}
{"type": "action", "kind": "puff|press|new_game"}
{"type": "puff_level", "value": 0.0-1.0}
{"type": "wifi_status", "mode": "station|ap", "ssid": "...", "ip": "..."}
{"type": "wifi_networks", "networks": ["SSID1", "SSID2"]}
```

**WebSocket (:81) – Eingehend (Browser → ESP32):**

```json
{"type": "wifi_config", "ssid": "...", "password": "..."}
{"type": "wifi_scan"}
```

### Konfigurierbare Parameter (oben in main.py)

| Parameter | Default | Beschreibung |
|-----------|---------|-------------|
| `DEADZONE` | 150 | ADC-Einheiten um Joystick-Mitte ignorieren |
| `NAV_THRESHOLD` | 800 | ADC-Wert ab dem Richtung erkannt wird |
| `NAV_REPEAT_MS` | 300 | Wiederholrate bei gehaltenem Joystick |
| `PUFF_THRESHOLD` | 0.25 | Normalisierter Wert ab dem Puff erkannt |
| `PUFF_COOLDOWN_MS` | 400 | Mindestzeit zwischen zwei Puffs |
| `SENSOR_POLL_MS` | 20 | Sensor-Abtastintervall (50 Hz) |
| `USE_DISPLAY` | False | ST7735 TFT ein/ausschalten |

---

## Solitaire-App (solitaire.html)

Single-File HTML-Anwendung (~1070 Zeilen). Kein Build-Tool, kein Framework, direkt vom ESP32 serviert oder lokal im Browser öffnen.

### Spiellogik

Klondike-Solitaire mit Standardregeln:

- 7 Tableau-Spalten, 4 Foundation-Stapel (♠♥♦♣)
- Stock/Waste (Nachziehstapel)
- Selektion über Puff (kein Mauszeiger nötig)
- Undo-Stack (max 50 Züge)
- Auto-Solve wenn alle Karten aufgedeckt und Stock leer
- Punktesystem: +10 Foundation, +5 Aufdecken, -10 Foundation→Tableau, -20 Stock recyclen

### Navigation (ohne Maus)

```
Joystick/Pfeiltasten:
  ◀▶  Spalte/Stapel wechseln
  ▲▼  Karte innerhalb Spalte wählen (nur aufgedeckte)
  ▲   Von Tableau zu oberer Reihe springen
  ▼   Von oberer Reihe zu Tableau

Pusten / Leertaste / Enter:
  1. Auf Stock → Karte aufdecken
  2. Auf aufgedeckte Karte (nichts selektiert) → Karte auswählen
  3. Auf gleiche Karte → Abwählen
  4. Auf anderes Feld (Karte selektiert) → Ablegen versuchen

Joystick-Button / Backspace:
  Rückgängig (Undo)
```

### Barrierefreiheit / Accessibility

**Farbsehschwäche (CVD-safe):**

Das System nutzt drei unabhängige visuelle Kanäle:

| Zustand | Farbe | Form-Cue | Animation |
|---------|-------|----------|-----------|
| Navigation (wo bin ich) | Karte hellcyan (#c8f0ff) | – | – |
| Ausgewählt (was halte ich) | Karte kräftig cyan (#00d4ff) | ✓ Badge | Puls |
| Gültiges Ziel | Karte hellmagenta (#ffe0ff) | ↓ Badge | Puls |
| Leerer Zielstapel | Magenta-Rahmen + Hintergrund | ↓ Badge | Puls |

**Designentscheidung:** Kartenfarbe ändern statt Rahmen. Farbänderung der gesamten Karte ist auf TV-Distanz sofort erkennbar. Cyan vs Magenta maximal unterscheidbar bei Protanopie, Deuteranopie, Tritanopie. Badges (✓/↓) als zusätzlicher nicht-farbbasierter Cue.

### Kiosk-Modus

Aktivierung: Taste `K` oder per WebSocket `{type:'action', kind:'kiosk'}`.

- Hilfetext ausgeblendet, kein Mauszeiger
- ESP32-Verbindungsstatus oben rechts (grüner/grauer Punkt)
- Idle-Screen nach 2 Minuten: dunkles Overlay mit "Pusten zum Starten"
- Jede Eingabe resettet Idle-Timer
- Taste `F` für Vollbild

### WiFi-Setup-Panel

Unten links: 📶-Toggle-Button.

- Im AP-Modus: blinkt orange, Panel öffnet automatisch
- Netzwerk-Scan: sendet `{type:'wifi_scan'}` per WS oder `GET /api/scan`
- Dropdown mit gefundenen Netzwerken
- SSID + Passwort Felder
- Verbinden-Button: sendet `{type:'wifi_config', ssid, password}` → ESP32 speichert + Reboot

### Tastenbelegung

| Taste | Funktion |
|-------|----------|
| Pfeiltasten | Navigation |
| Leertaste / Enter | Pusten (Auswählen/Ablegen) |
| Backspace | Rückgängig |
| N | Neues Spiel |
| K | Kiosk-Modus toggle |
| F | Vollbild toggle |

### Audio

Web Audio API Beeps (kein externes Audio nötig):

| Event | Frequenz | Dauer |
|-------|---------|-------|
| Navigation | 600 Hz | 60ms |
| Auswählen | 800+1000 Hz | 100ms |
| Ablegen | 1000+1200 Hz | 80ms |
| Fehler | 200 Hz | 200ms |
| Undo | 400 Hz | 100ms |
| Stock ziehen | 500 Hz | 80ms |
| Gewonnen | 523→659→784→1047 Hz | Melodie |

---

## 3D-Gehäuse (mundmaus-gehaeuse.scad)

Parametrisches OpenSCAD-Design. Alle Maße als Variablen.

### Teile

1. **Unterteil** (`bottom_case()`): Wanne mit Montagepfosten, USB-Ausschnitt, Schlauch-Durchführung, Belüftungsschlitze
2. **Deckel** (`lid()`): Display-Fenster, Joystick-Öffnung (Ø20mm), Schraubenlöcher, "MundMaus"-Schriftzug
3. **Schlauch-Adapter** (`tube_adapter()`): Barb-Fitting für Silikonschlauch

### Maße (anpassbar)

- Innen: 100 × 70 × 40 mm
- Wandstärke: 2,5 mm
- Druckempfehlung: 0,2mm Schichthöhe, 20-30% Infill, PLA/PETG

---

## Netzwerk-Architektur

### Empfohlen: ESP32 als Hotspot (kein Router nötig)

```
WiFi "MundMaus" (PW: mundmaus1)
  ESP32-S3: 192.168.4.1 (HTTP :80 + WS :81)
  Raspberry Pi: verbindet sich, öffnet Chromium im Kiosk
  TV/Monitor: HDMI am Pi
```

### Alternativ: ESP32 im bestehenden WLAN

- WiFi-Panel im Spiel: SSID + Passwort eingeben
- ESP32 speichert in wifi.json, startet neu
- IP vom Router vergeben
- Bei Fehler: automatischer Fallback auf Hotspot

---

## MicroPython

### Empfohlene Version: v1.27.0 (Dezember 2025)

Download: https://micropython.org/download/ESP32_GENERIC_S3/

Für ESP32-S3 N16R8 die **SPIRAM_OCT** Variante verwenden (Octal PSRAM).

### Relevante Features für MundMaus

| Feature | Version | Nutzen |
|---------|---------|--------|
| asyncio ausgereift | v1.25+ | Nicht-blockierende Hauptschleife |
| Auto-detect SPIRAM | v1.24+ | PSRAM wird automatisch erkannt |
| `Pin.toggle()` | v1.25+ | Vereinfacht HX710B Clock |
| Dynamic USB Device (S3) | v1.25+ | Zukunft: USB-HID Maus-Modus |
| ROMFS | v1.27 | HTML aus Flash ohne RAM-Kopie |
| network.ipconfig() | v1.25+ | Sauberere WiFi-Konfiguration |

### Flashen

```bash
# ESP32-S3 mit Octal PSRAM (N16R8):
esptool.py --chip esp32s3 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32s3 --port /dev/ttyUSB0 --baud 460800 \
  write_flash -z 0x0 ESP32_GENERIC_S3-SPIRAM_OCT-20251209-v1.27.0.bin

# Dateien hochladen:
rshell -p /dev/ttyUSB0
mkdir /pyboard/www
cp boot.py /pyboard/
cp main.py /pyboard/
cp solitaire.html /pyboard/www/
```

---

## Entwicklung

### Lokales Testen (ohne ESP32)

`solitaire.html` direkt im Browser öffnen. Tastatur-Steuerung funktioniert ohne WebSocket. WS-Reconnect läuft im Hintergrund und stört nicht.

### WiFi-Konfiguration

1. ESP32 starten → Hotspot "MundMaus" erscheint
2. Mit Handy/PC verbinden (PW: `mundmaus1`)
3. Browser: `http://192.168.4.1` → Spiele-Portal
4. Alternativ: im Spiel unten links 📶 → SSID + PW eingeben → Neustart

### Neues Spiel hinzufügen

1. HTML-Datei erstellen (single-file, kein Framework nötig)
2. WebSocket-Verbindung zu `ws://${location.hostname}:81` aufbauen
3. Auf Nachrichten `{type:'nav', dir:'...'}` und `{type:'action', kind:'puff'}` reagieren
4. Datei nach `www/` auf den ESP32 kopieren: `rshell cp spiel.html /pyboard/www/`
5. Spiel erscheint automatisch im Portal unter `http://<IP>/`

### Debugging

```
# Serial Monitor:
#   MundMaus v3.0
#   Board: ESP32-S3
#   [Hardware]
#     Joystick Kalibrierung...
#     Center=(1847,1923) dz=±150
#     Drucksensor: OK
#     Baseline=834521 range=417260
#   [Netzwerk]
#     HOTSPOT: MundMaus / mundmaus1
#     IP: 192.168.4.1
#   [Server]
#     HTTP  :80
#     WS    :81
#   [Start] RAM frei: 4823040 bytes
#   Bereit.
```

---

## WebSocket-Protokoll (Referenz)

### ESP32 → Browser

```
NAV:        {"type":"nav","dir":"left|right|up|down"}
ACTION:     {"type":"action","kind":"puff|press|new_game"}
PUFF_LEVEL: {"type":"puff_level","value":0.0-1.0}
WIFI_STATE: {"type":"wifi_status","mode":"station|ap","ssid":"...","ip":"..."}
WIFI_NETS:  {"type":"wifi_networks","networks":["SSID1","SSID2"]}
```

### Browser → ESP32

```
WIFI_CFG:   {"type":"wifi_config","ssid":"...","password":"..."}
WIFI_SCAN:  {"type":"wifi_scan"}
```

---

## Changelog

### v3.0 (aktuell)

- Automatische Board-Erkennung (ESP32 vs ESP32-S3)
- asyncio-basierte Hauptschleife (drei unabhängige Tasks)
- File-Server: serviert HTML-Spiele aus `www/` Ordner
- Spiele-Portal auf `/` als Launcher
- ESP32-S3 N16R8 als empfohlene Hardware (16MB Flash, 8MB PSRAM)
- Kein Löten: nur Boards mit vorverlöteten Pins empfohlen
- Display-Pins über Board-spezifische Konstanten
- `/api/info` Endpoint für Board/Version/RAM

### v2.1

- WiFiManager mit Hotspot-Fallback und WS-basierter Konfiguration
- PuffSensor mit HX710B 24-bit ADC
- Synchrone Polling-Loop
- Inline-HTML für Setup-Seite
- Hardcodierte ESP32-WROOM Pins

---

## Offene Punkte / TODOs

- [ ] USB-HID Maus-Modus (ESP32-S3 Dynamic USB) – Maussteuerung ohne WiFi
- [ ] Sip-and-Puff: Differenzdrucksensor (MPXV7002DP)
- [ ] Weitere Spiele: Memory, Snake, Schach
- [ ] Settings-Panel: Threshold/Deadzone über Browser-UI anpassen
- [ ] OTA-Firmware-Update über WiFi
- [ ] mDNS: `mundmaus.local` statt IP-Adresse
- [ ] Gehäuse: Mikrofon-Schwenkarm-Halterung
- [ ] Raspberry Pi Kiosk-Autostart-Script

---

## Lizenz

Basiert auf [mibragri/mouthMouse](https://github.com/mibragri/mouthMouse) – AGPL-3.0.

