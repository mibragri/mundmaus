# MundMaus — Technische Referenz

Ergaenzung zur [README.md](README.md). Hier stehen Hardware-Details, Protokolle,
Firmware-Interna und Raspberry-Pi-Setup die fuer Entwickler und fortgeschrittene
Einrichtung relevant sind.

---

## Pin-Belegung

Die Firmware erkennt das Board automatisch (`config.py` / `config.h`).

| Funktion | ESP32-WROOM (V4) | ESP32-S3 (N16R8) | Hinweis |
|----------|-------------------|-------------------|---------|
| Joystick VRX | **GPIO33** | GPIO1 | ADC1 |
| Joystick VRY | **GPIO35** | GPIO2 | ADC1 |
| Joystick SW | **GPIO21** | GPIO42 | Digital, Pull-Up |
| Puff DATA | **GPIO32** | GPIO4 | Digital (HX710B) |
| Puff CLK | **GPIO25** | GPIO5 | Digital (HX710B) |
| Display A0 | **GPIO2** | GPIO6 | Data/Command |
| Display RST | GPIO14 | GPIO14 | Reset |
| Display CS | GPIO17 | GPIO17 | SPI CS |
| Display SCK | GPIO18 | GPIO18 | SPI CLK |
| Display SDA | GPIO23 | GPIO23 | SPI MOSI |

> ESP32-S3 hat keine GPIO33-39. Board-Erkennung via `sys.implementation._machine`.

### Komplettes Pinout (ESP32-WROOM DevKitC V4)

```
                 ESP32-WROOM-32 DevKitC V4
                 +----------------------+
                 |     [USB Micro-B]    |
                 +----------------------+
           3.3V -| 3V3              GND |- GND (alle GND)
                 |                      |
                 | GPIO33         GPIO21|- Joystick SW
                 | (Joystick VRx)       |
                 | GPIO35         GPIO23|- Display SDA
                 | (Joystick VRy)       |
                 | GPIO32         GPIO18|- Display SCK
                 | (Puff DATA)          |
                 | GPIO25         GPIO17|- Display CS
                 | (Puff CLK)           |
                 | GPIO2          GPIO14|- Display RST
                 | (Display A0)         |
                 | ...             ...  |
                 +----------------------+

Stromversorgung:
  3.3V ──┬── KY-023 "+5V" (Label ignorieren, 3.3V reicht!)
         ├── HX710B VCC
         └── ST7735 VCC (optional)
  GND ──┬── KY-023 GND
        ├── HX710B GND
        └── ST7735 GND (optional)
```

---

## Verkabelung

### Joystick KY-023

```
KY-023          ESP32-WROOM
---------       -----------
GND      ────── GND
+5V      ────── 3.3V  (NICHT 5V — 3.3V reicht, ADC-Werte passen)
VRx      ────── GPIO33
VRy      ────── GPIO35
SW       ────── GPIO21
```

### Drucksensor MPS20N0040D-S + HX710B

```
HX710B Board    ESP32-WROOM
------------    -----------
VCC      ────── 3.3V
GND      ────── GND
DATA     ────── GPIO32
CLK      ────── GPIO25
```

Silikonschlauch (ID 4mm) vom Mundstueck → seitlich am Gehaeuse entlang → auf
den Barb (Nippel) des Drucksensors stecken.

### Display ST7735 (optional)

```
ST7735          ESP32-WROOM
------          -----------
VCC      ────── 3.3V
GND      ────── GND
SDA      ────── GPIO23 (MOSI)
SCK      ────── GPIO18 (SCK)
CS       ────── GPIO17
A0/DC    ────── GPIO2
RESET    ────── GPIO14
```

---

## Mundstueck

Das Mundstueck wird separat in OnShape verwaltet:

**CAD-Modell:** <https://cad.onshape.com/documents/95d3a4d6faad26c25a2f7521/w/612dd5f1a9d3cf74ba406bb7/e/fc37b7a7abf844a33ef56714>

Es sitzt auf dem Joystick-Stift und hat einen seitlichen Schlauch-Abgang
(Richtung +X / links vom Patienten). Der Silikonschlauch laeuft aussen am
Gehaeuse zum Drucksensor. Der Schlauch darf nicht stark gebogen werden — das
zieht am Joystick und beeintraechtigt die Navigation.

---

## Firmware-Architektur

Zwei gleichwertige Firmware-Varianten mit identischem Feature-Set:

### MicroPython (asyncio)

```
asyncio.run(async_main)
  ├── sensor_loop()    – 50 Hz, Joystick + Puff → WebSocket
  ├── server_loop()    – 100 Hz, HTTP accept + WS accept + WS read
  └── display_loop()   – 0.2 Hz, ST7735 TFT update (optional)
```

Module: `boot.py`, `main.py`, `config.py`, `sensors.py`, `server.py`,
`wifi_manager.py`, `updater.py`, `display.py`

### Arduino C++ (FreeRTOS)

```
Core 0: AsyncTCP + HTTP Server + WebSocket + OTA
Core 1: Sensor-Task (50 Hz Joystick + Puff) + WDT-Heartbeat
```

Quellen: `firmware/arduino/src/`

### Klassen / Module

#### CalibratedJoystick (`sensors.py` / `sensors.cpp`)

ADC-basierter Joystick mit Drift-Kompensation.

- `calibrate(samples=50)` — Mittelwert bei Ruheposition → echte Mitte
- `read_centered()` → `(dx, dy)` relativ zur Mitte, Deadzone angewendet
- `get_direction()` → `left|right|up|down|None`
- `poll_navigation()` — mit Repeat-Timer (konfigurierbar)
- `is_idle()` → True wenn nahe Mitte (triggert Auto-Rekalibrierung nach 10s)

**Drift-Problem:** Billige KY-023 haben thermischen ADC-Drift. Geloest durch
Auto-Kalibrierung beim Boot + Auto-Rekalibrierung nach Idle.

#### PuffSensor (`sensors.py` / `sensors.cpp`)

HX710B 24-bit ADC Bit-Bang-Reader fuer MPS20N0040D-S.

- `calibrate_baseline(samples=30)` — Ruhedruck-Kalibrierung
- `read_normalized()` → `0.0` bis `1.0`, gleitender Durchschnitt
- `detect_puff()` → True bei Threshold + Cooldown
- `get_level()` → aktueller Pegel fuer UI-Anzeige

**Limitierung:** Nur Pusten (Ueberdruck), kein Saugen. Fuer Sip-and-Puff
waere ein Differenzdrucksensor (MPXV7002DP) noetig.

#### WiFiManager (`wifi_manager.py` / `wifi_manager.cpp`)

```
Boot-Flow:
  load_credentials()     → liest wifi.json / NVS
       │
       ├─ Credentials da → connect_station(timeout=10s)
       │                         │
       │                    ├─ OK → Station-Modus (Router-IP)
       │                    └─ Fail → start_ap()
       │
       └─ Keine Credentials → start_ap()

AP-Modus:
  SSID: "MundMaus"  |  Pass: "mundmaus1"  |  IP: 192.168.4.1
```

#### MundMausServer (`server.py` / `web_server.cpp`)

Kombinierter HTTP File-Server + WebSocket Server.

---

## Konfigurationsparameter

Definiert in `config.py` (MicroPython) / `config.h` (Arduino). Zur Laufzeit
aenderbar ueber die Settings-Seite im Browser (⚙ im Portal).

| Parameter | Default | Beschreibung |
|-----------|---------|-------------|
| `DEADZONE` | 150 | ADC-Einheiten um Joystick-Mitte ignorieren |
| `NAV_THRESHOLD` | 450 | ADC-Wert ab dem Richtung erkannt wird |
| `NAV_REPEAT_MS` | 400 | Wiederholrate bei gehaltenem Joystick |
| `PUFF_RAW_THRESHOLD` | 75000 | Rohwert ab dem Puff erkannt wird |
| `PUFF_COOLDOWN_MS` | 400 | Mindestzeit zwischen zwei Puffs |
| `SENSOR_POLL_MS` | 20 | Sensor-Abtastintervall (50 Hz) |
| `USE_DISPLAY` | False | ST7735 TFT ein/ausschalten |
| `RECAL_IDLE_MS` | 10000 | Auto-Rekalibrierung nach Idle |

---

## HTTP API

Beide Firmware-Varianten implementieren dieselben Endpoints.

| Endpunkt | Methode | Beschreibung |
|----------|---------|-------------|
| `/` | GET | Spiele-Portal (listet alle Spiele, WiFi-Status, Updates) |
| `/www/<datei>` | GET | Spieldatei aus www/ (gzip-komprimiert auf LittleFS) |
| `/api/info` | GET | `{board, version, free_ram, ...}` |
| `/api/wifi` | GET | WiFi-Status `{mode, ssid, ip, connected}` |
| `/api/wifi` | POST | Credentials speichern `{ssid, password}` → Reboot |
| `/api/scan` | GET | WLAN-Scan `{networks: ["SSID1", ...]}` |
| `/api/settings` | GET | Aktuelle Konfig-Werte (Deadzone, Threshold, ...) |
| `/api/reboot` | GET | ESP32 Neustart |
| `/api/updates` | GET | Verfuegbare OTA-Updates `{available, games, firmware}` |
| `/api/updates/check` | POST | Update-Check erzwingen |
| `/api/update/start` | POST | OTA-Update starten |
| `/favicon.ico` | GET | 204 No Content |

---

## WebSocket-Protokoll

WebSocket laeuft auf Port **81** (separater Listener).
Alle Nachrichten sind JSON.

### ESP32 → Browser

```json
{"type": "nav",          "dir": "left|right|up|down"}
{"type": "action",       "kind": "puff|press"}
{"type": "puff_level",   "value": 0.0-1.0}
{"type": "wifi_status",  "mode": "station|ap", "ssid": "...", "ip": "..."}
{"type": "wifi_networks","networks": ["SSID1", "SSID2"]}
{"type": "config_values","deadzone": 150, "nav_threshold": 450, ...}
{"type": "config_saved", "ok": true}
{"type": "update_progress", "current": 2, "total": 5, "file": "chess.html.gz"}
{"type": "update_complete", "message": "..."}
```

### Browser → ESP32

```json
{"type": "wifi_config",    "ssid": "...", "password": "..."}
{"type": "wifi_scan"}
{"type": "config_preview", "deadzone": 200, ...}
{"type": "config_save",    "deadzone": 200, ...}
{"type": "config_reset"}
```

### In Spielen (Browser-seitig)

Spiele verbinden sich zu `ws://${location.hostname}:81` und reagieren auf
`nav`- und `action`-Events. Tastatur-Fallback funktioniert ohne WebSocket.

```
Joystick / Pfeiltasten:
  ◀▶  Spalte/Element wechseln
  ▲▼  Innerhalb einer Spalte navigieren

Pusten / Leertaste / Enter:
  Auswaehlen / Ablegen / Bestaetigen

Joystick-Button / Backspace:
  Rueckgaengig (Undo)

N = Neues Spiel  |  K = Kiosk-Modus  |  F = Vollbild
```

---

## OTA-Update-System

Beide Firmware-Varianten pruefen beim Boot `mundmaus.de/ota/manifest.json`
(Basic Auth). Das Portal zeigt verfuegbare Updates an — der User klickt
"Installieren".

- **Arduino**: ESP-IDF Dual-Partition + `markBootOk()` → automatischer Rollback
  bei fehlgeschlagenem Firmware-Update
- **MicroPython**: `.bak`-Dateien + `boot.py` Counter + Recovery-AP

Deploy-Workflow: siehe README.md ("Neues Spiel hinzufuegen" Checkliste).

---

## Flash-Speicher

### ESP32-WROOM-32 (4 MB)

```
MicroPython Firmware:     ~1.5 MB
Python-Dateien (*.py):    ~0.05 MB
www/ Verzeichnis:         ~2.4 MB verfuegbar
```

### Arduino (4 MB, Dual-Partition)

```
App Partition 0:          ~1.5 MB
App Partition 1:          ~1.5 MB  (OTA Rollback)
LittleFS (www/):          ~1.0 MB
```

### ESP32-S3 N16R8 (16 MB)

~14 MB fuer www/ verfuegbar. Kein Platzproblem.

---

## Raspberry Pi Kiosk-Setup

Fuer den Dauerbetrieb am TV/Monitor: Raspberry Pi als dedizierter Browser-Client.

### 1. WiFi-Verbindung zum ESP32-Hotspot

```bash
# /etc/wpa_supplicant/wpa_supplicant.conf
network={
    ssid="MundMaus"
    psk="mundmaus1"
    priority=10
}
```

Oder: `sudo raspi-config` → System Options → Wireless LAN

### 2. Browser im Kiosk-Modus (Autostart)

```bash
#!/bin/bash
# /home/pi/start-mundmaus.sh

# Warte bis ESP32 erreichbar
echo "Warte auf MundMaus WiFi..."
while ! ping -c 1 -W 2 192.168.4.1 > /dev/null 2>&1; do
    sleep 2
done
echo "ESP32 erreichbar!"

# Cursor ausblenden
unclutter -idle 0 &

# Browser starten
chromium-browser \
    --kiosk \
    --no-first-run \
    --disable-infobars \
    --noerrdialogs \
    --disable-translate \
    --disable-features=TranslateUI \
    --check-for-update-interval=31536000 \
    http://192.168.4.1
```

```bash
chmod +x /home/pi/start-mundmaus.sh
echo "@/home/pi/start-mundmaus.sh" >> /etc/xdg/lxsession/LXDE-pi/autostart
```

### 3. Bildschirmschoner deaktivieren

```bash
sudo apt install xscreensaver
# GUI: Bildschirmschoner → Deaktivieren

# Oder via xset:
xset s off && xset -dpms && xset s noblank
```

### 4. Pakete

```bash
sudo apt install unclutter chromium-browser
```

---

## Troubleshooting

| Problem | Ursache | Loesung |
|---------|---------|--------|
| ESP32 wird nicht erkannt | Nur Ladekabel (2 Adern) | **Datenkabel** verwenden (4 Adern) |
| Joystick driftet | Thermischer Drift KY-023 | Deadzone erhoehen (Settings ⚙) |
| Kein Puff erkannt | Schlauch undicht / Threshold zu hoch | Schlauch pruefen, Empfindlichkeit erhoehen (Settings ⚙) |
| WiFi "MundMaus" nicht sichtbar | ESP32 nicht gestartet | USB-Kabel pruefen, Serial Monitor |
| Spiele laden langsam | Erste Uebertragung (gzip) | Normal — danach schneller |
| WebSocket trennt sich | WiFi-Reichweite | ESP32 naeher an Client |
| ESP32-S3: ADC liest 0 | GPIO33-39 gibt es nicht | Firmware-Update mit Board-Erkennung |
| Display bleibt schwarz | SPI-Pins vertauscht | Verkabelung pruefen (A0/RST) |
| OTA-Update schlaegt fehl | Kein Internet im AP-Modus | ESP32 muss im Station-Modus sein |

---

## MicroPython-Version

Empfohlen: **v1.27.0+**

| Feature | ab Version | Nutzen |
|---------|-----------|--------|
| asyncio ausgereift | v1.25+ | Nicht-blockierende Hauptschleife |
| Auto-detect SPIRAM | v1.24+ | PSRAM auf S3 automatisch erkannt |
| ROMFS | v1.27 | HTML aus Flash ohne RAM-Kopie |
| Dynamic USB Device (S3) | v1.25+ | Zukuenftig: USB-HID Maus-Modus |

Download: [micropython.org/download/ESP32_GENERIC](https://micropython.org/download/ESP32_GENERIC/)
