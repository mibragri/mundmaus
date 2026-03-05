# MundMaus -- Setup & Hardware Guide

## Board: ESP32-WROOM-32 DevKitC V4

Das Projekt verwendet einen **ESP32-WROOM-32 DevKitC V4** (z.B. AZ-Delivery). Guenstiger, weit verbreitet, USB Micro-B.

**Preis:** ~8 EUR | **Kein Loeten noetig -- Board mit vorverloeteten Pins waehlen!**

Eigenschaften:

- **Dual-Core Xtensa LX6 240MHz**
- **4MB Flash** -- reicht fuer Firmware + Solitaire-HTML + weitere Spiele
- **520 KB SRAM** -- genuegt fuer HTTP/WebSocket Server
- **USB Micro-B** -- Daten + Strom ueber ein Kabel
- **WiFi 802.11 b/g/n** -- Hotspot oder Station-Modus
- Vorverloeotete Pins bei DevKitC V4

### Alternative: ESP32-S3 (N16R8 DevKitC-1)

Die Firmware erkennt ESP32-S3 Boards automatisch. Vorteile:

- 16MB Flash, 8MB PSRAM -- mehr Platz fuer Spiele
- Dual USB-C (UART + native USB)
- USB-HID Maus-Modus moeglich (Zukunft)

Fuer den Grundbetrieb ist der ESP32-S3 nicht noetig. Die Firmware unterstuetzt beide Boards.

### Pin-Mapping: ESP32-WROOM vs. ESP32-S3

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

**Hinweis:** ESP32-S3 hat keine GPIO33-39. Die Firmware erkennt das Board automatisch.

---

## Board-Erkennung in der Firmware

Die Firmware erkennt das Board automatisch und setzt die Pins:

```python
import sys

if 'ESP32S3' in sys.implementation._machine:
    # ESP32-S3 Pin-Belegung
    PIN_VRX = 1;  PIN_VRY = 2;  PIN_SW = 42
    PIN_PUFF_DATA = 4;  PIN_PUFF_CLK = 5
    DISPLAY_A0 = 6
    BOARD = "ESP32-S3"
else:
    # Klassischer ESP32 (WROOM/DevKitC V4)
    PIN_VRX = 33;  PIN_VRY = 35;  PIN_SW = 21
    PIN_PUFF_DATA = 32;  PIN_PUFF_CLK = 25
    DISPLAY_A0 = 2
    BOARD = "ESP32-WROOM"

print(f"Board erkannt: {BOARD}")
```

---

## Verdrahtung (kein Loeten!)

> **Philosophie:** Alles wird mit DuPont-Jumperkabeln auf ein Breadboard gesteckt.
> Kein Loeten noetig. Fuer den Dauerbetrieb koennen Schraubklemmen-Adapter verwendet werden.

### Benoetigtes Zubehoer (zusaetzlich zu den Komponenten)

| Zubehoer | Preis |
|---------|-------|
| Breadboard 830 Kontakte | ~3 EUR |
| DuPont Jumper-Kabel Set (M-F, M-M, F-F je 40 Stk) | ~7 EUR |
| USB Micro-B Datenkabel | ~3 EUR |

### Joystick KY-023

```
KY-023          ESP32-WROOM
---------       -----------
GND      ------ GND
+5V      ------ 3.3V  ! NICHT 5V! (3.3V reicht, siehe mouthMouse README)
VRx      ------ GPIO33
VRy      ------ GPIO35
SW       ------ GPIO21
```

**Achtung:** Der KY-023 ist mit "5V" beschriftet, funktioniert aber korrekt an 3.3V. Die ADC-Werte passen zu den Kalibrierungseinstellungen in der Firmware.

### Drucksensor MPS20N0040D-S + HX710B

```
HX710B Board    ESP32-WROOM
------------    -----------
VCC      ------ 3.3V
GND      ------ GND
DATA     ------ GPIO32
CLK      ------ GPIO25

Sensor-Seite:
Silikonschlauch (ID 5mm) -> T-Stueck (Gardena) -> Sensor-Eingang
                             |
                        Mundstueck
```

### Display ST7735 (optional)

```
ST7735          ESP32-WROOM
------          -----------
VCC      ------ 3.3V
GND      ------ GND
SDA      ------ GPIO23 (MOSI)
SCK      ------ GPIO18 (SCK)
CS       ------ GPIO17
A0/DC    ------ GPIO2
RESET    ------ GPIO14
```

### Komplettes Pinout-Diagramm

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
  3.3V --+-- KY-023 +5V (Label ignorieren!)
         +-- HX710B VCC
         +-- ST7735 VCC
  GND --+-- KY-023 GND
         +-- HX710B GND
         +-- ST7735 GND
```

---

## Netzwerk-Architektur

### Konzept: ESP32 als selbstaendiger Hotspot

Der ESP32 startet immer als **eigener WiFi-Hotspot**. Das ist die zuverlaessigste Loesung:

- Kein fremdes WLAN noetig
- Funktioniert ueberall (Krankenhaus, Pflegeheim, zuhause)
- Keine Router-Konfiguration
- Feste, vorhersagbare IP-Adresse

```
+---------------------------------------------------------+
|                  WiFi "MundMaus"                        |
|                  PW: mundmaus1                          |
|                                                         |
|   +---------------+         +----------------------+    |
|   |   ESP32       |  WiFi   |   Raspberry Pi       |   |
|   |   WROOM-32    |<------->|   (oder PC/Laptop)   |   |
|   |               |         |                      |   |
|   |  IP: 192.168.4.1       |                      |   |
|   |  HTTP :80     |         |   Browser oeffnet:   |   |
|   |  WS   :81     |         |   http://192.168.4.1 |   |
|   |               |         |                      |   |
|   |  Joystick     |         |   +--------------+   |   |
|   |  Puff-Sensor  | --WS--> |   |solitaire.html|   |   |
|   |  Display      |         |   | (vom ESP32)  |   |   |
|   +---------------+         |   +--------------+   |   |
|                              |          |           |   |
|                              |   TV/Monitor via HDMI|   |
|                              +----------------------+   |
+---------------------------------------------------------+
```

### Netzwerk-Modi

#### Modus 1: Hotspot (Standard, empfohlen)

```
ESP32 startet als Access Point:
  SSID:     MundMaus
  Passwort: mundmaus1
  IP:       192.168.4.1
  Subnet:   255.255.255.0

Raspberry Pi verbindet sich mit "MundMaus" WiFi
Browser oeffnet: http://192.168.4.1
WebSocket:       ws://192.168.4.1:81
```

#### Modus 2: Bestehendes WLAN (optional)

Falls Internet auf dem Pi gewuenscht ist (Updates etc.):

```
Ueber WiFi-Panel im Solitaire-Spiel:
  -> SSID + Passwort eingeben -> ESP32 startet neu

ESP32 verbindet sich mit dem Router:
  IP: wird vom Router vergeben (z.B. 192.168.1.42)

Pi verbindet sich ebenfalls mit dem Router:
  Browser oeffnet: http://192.168.1.42 (oder mDNS, falls konfiguriert)

Nachteil: IP nicht vorhersagbar, DHCP kann sich aendern
Bei Fehlschlag: automatischer Fallback auf Hotspot-Modus
```

### Raspberry Pi Einrichtung

#### 1. WiFi-Verbindung zum ESP32-Hotspot

```bash
# /etc/wpa_supplicant/wpa_supplicant.conf
network={
    ssid="MundMaus"
    psk="mundmaus1"
    priority=10
}
```

Oder ueber raspi-config:

```bash
sudo raspi-config
# -> System Options -> Wireless LAN
# SSID: MundMaus
# Passwort: mundmaus1
```

#### 2. Browser im Kiosk-Modus (Autostart)

```bash
# /etc/xdg/autostart/mundmaus-kiosk.desktop
[Desktop Entry]
Type=Application
Name=MundMaus Solitaire
Exec=chromium-browser --kiosk --no-first-run --disable-infobars --disable-session-crashed-bubble http://192.168.4.1
```

Oder alternativ mit einem Autostart-Script:

```bash
# /home/pi/start-mundmaus.sh
#!/bin/bash

# Warte bis WiFi verbunden ist
echo "Warte auf MundMaus WiFi..."
while ! ping -c 1 -W 2 192.168.4.1 > /dev/null 2>&1; do
    sleep 2
done
echo "ESP32 erreichbar!"

# Starte Browser im Kiosk-Modus
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
# In Autostart eintragen:
echo "@/home/pi/start-mundmaus.sh" >> /etc/xdg/lxsession/LXDE-pi/autostart
```

#### 3. Bildschirmschoner deaktivieren

```bash
sudo apt install xscreensaver
# Dann ueber GUI: Bildschirmschoner -> Deaktivieren

# Oder via xset:
echo "xset s off && xset -dpms && xset s noblank" >> ~/.xinitrc
```

#### 4. Cursor ausblenden

```bash
sudo apt install unclutter
echo "unclutter -idle 0 &" >> /home/pi/start-mundmaus.sh
```

---

## ESP32 Mini-Webserver (Spiele-Portal)

Der ESP32 kann die Solitaire-HTML und weitere Spiele direkt servieren. Kein separater Webserver noetig.

### Dateistruktur auf dem ESP32

```
/                       (ESP32 Flash Root)
+-- boot.py
+-- main.py             (Firmware)
+-- wifi.json           (gespeicherte WLAN-Credentials)
+-- www/                (Webseiten)
    +-- solitaire.html  (Solitaire-Spiel)
    +-- memory.html     (Memory-Spiel -- zukuenftig)
    +-- settings.html   (Einstellungen -- zukuenftig)
```

### Spiele-Portal

Wird vom ESP32 auf `http://192.168.4.1/` ausgeliefert. Zeigt:

- Spielauswahl (grosse Kacheln, mundmaus-bedienbar)
- WiFi-Status
- Firmware-Version
- Link zu Einstellungen

### Spiel-Deployment

Neue Spiele auf den ESP32 laden:

```bash
# Per rshell (USB-Kabel am ESP32):
rshell --buffer-size=30 -p /dev/ttyUSB0

# Datei hochladen:
cp solitaire.html /pyboard/www/solitaire.html

# Oder ganzen www-Ordner synchronisieren:
rsync -m www/ /pyboard/www/
```

### Flash-Speicher (ESP32-WROOM-32)

```
4 MB Flash total:
  MicroPython Firmware:     ~1.5 MB
  Python-Dateien (*.py):    ~0.05 MB
  www/ Verzeichnis:         ~2.4 MB verfuegbar

  solitaire.html:           ~0.04 MB (36 KB)
  -> Platz fuer ~60 Spiele dieser Groesse
```

> **ESP32-S3 N16R8:** 16 MB Flash -> ~14 MB fuer www/ verfuegbar.

---

## Erste Inbetriebnahme (Schritt fuer Schritt)

### 1. ESP32 flashen

```bash
# esptool installieren
pip3 install esptool rshell

# ESP32 per USB Micro-B verbinden
# Flash loeschen
esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash

# MicroPython Firmware flashen
# Download: https://micropython.org/download/ESP32_GENERIC/
esptool.py --chip esp32 --port /dev/ttyUSB0 \
  --baud 460800 write_flash -z 0x1000 \
  ESP32_GENERIC-20251209-v1.27.0.bin
```

> **ESP32-S3:** `--chip esp32s3`, Offset `0x0`, Firmware `ESP32_GENERIC_S3-SPIRAM_OCT-*.bin`
> Download: https://micropython.org/download/ESP32_GENERIC_S3/

### 2. Dateien hochladen

```bash
rshell --buffer-size=30 -p /dev/ttyUSB0

# Verzeichnis erstellen
mkdir /pyboard/www

# Dateien kopieren
cp boot.py /pyboard/boot.py
cp main.py /pyboard/main.py
cp solitaire.html /pyboard/www/solitaire.html
```

### 3. Hardware verkabeln

1. Joystick KY-023 an 3.3V, GND, GPIO33, GPIO35, GPIO21
2. Drucksensor HX710B an 3.3V, GND, GPIO32, GPIO25
3. Silikonschlauch an Sensor anschliessen
4. (Optional) Display an SPI-Pins

### 4. Testen

```bash
# Serial Monitor oeffnen
screen /dev/ttyUSB0 115200

# Erwartete Ausgabe:
# ========================================
#   MUNDMAUS v3.0
#   Board: ESP32-WROOM
# ========================================
# Joystick Kalibrierung...
# Kalibriert: center=(1847,1923) deadzone=+/-150
# Drucksensor MPS20N0040D-S: OK
# Puff baseline=834521 range=417260
# Keine wifi.json vorhanden
# Keine WLAN-Daten -> Starte Hotspot
# ========================================
#   HOTSPOT AKTIV
#   SSID: MundMaus
#   Passwort: mundmaus1
#   IP: 192.168.4.1
# ========================================
# HTTP Server auf :80
# WebSocket Server auf :81
```

### 5. Verbinden und Spielen

1. Handy/Laptop: WiFi "MundMaus" verbinden (PW: mundmaus1)
2. Browser oeffnen: `http://192.168.4.1`
3. Spiele-Portal erscheint -> Solitaire starten
4. Joystick bewegen -> Karten navigieren
5. Pusten -> Karte auswaehlen/ablegen

### 6. Raspberry Pi einrichten (fuer Dauerbetrieb)

1. Raspbian installieren
2. WiFi "MundMaus" konfigurieren (siehe oben)
3. Autostart-Script einrichten
4. Cursor ausblenden, Bildschirmschoner deaktivieren
5. TV/Monitor per HDMI anschliessen
6. Fertig -- Pi bootet direkt ins Solitaire

---

## MicroPython

### Empfohlene Version: v1.27.0 (Dezember 2025)

Download: https://micropython.org/download/ESP32_GENERIC/

**Relevante Features fuer MundMaus:**

| Feature | Version | Nutzen fuer MundMaus |
|---------|---------|-------------------|
| `asyncio` ausgereift | v1.25+ | Nicht-blockierende Hauptschleife |
| `network.ipconfig()` neue API | v1.25+ | Sauberere WiFi-Konfiguration |
| `Pin.toggle()` | v1.25+ | Vereinfacht HX710B Clock |
| Compressed error messages | v1.25+ | Weniger RAM fuer Fehlerstrings |
| Auto-detect SPIRAM | v1.24+ | PSRAM wird automatisch erkannt (S3) |
| TLS Memory Management | v1.25+ | Stabiler bei WiFi-Reconnects |
| ROMFS | v1.27 | HTML-Dateien direkt aus Flash |
| Dynamic USB Device (S3) | v1.25+ | USB-HID Maus-Modus (nur ESP32-S3) |

### USB-HID Maus-Modus (nur ESP32-S3)

MicroPython v1.25+ unterstuetzt auf dem ESP32-S3 dynamische USB-Konfiguration. Der ESP32-S3 kann sich als **USB-HID-Maus** am PC/TV anmelden -- ganz ohne WiFi. Das waere ein alternativer Betriebsmodus: ESP32-S3 direkt per USB-C an den PC/TV, erscheint als Maus.

---

## Troubleshooting

| Problem | Ursache | Loesung |
|---------|---------|--------|
| Joystick driftet | Thermischer Drift des KY-023 | Deadzone erhoehen: `DEADZONE = 200` |
| Kein Puff erkannt | Schlauch undicht oder Threshold zu hoch | `PUFF_THRESHOLD = 0.15` senken |
| WiFi "MundMaus" nicht sichtbar | ESP32 nicht gestartet oder AP-Fehler | USB-Kabel pruefen, Serial Monitor |
| Browser zeigt nichts | www/ Ordner fehlt auf ESP32 | `rshell` -> Dateien hochladen |
| WebSocket trennt sich | WiFi-Reichweite | ESP32 naeher am Pi platzieren |
| Solitaire reagiert nicht | WS nicht verbunden | WiFi-Panel -> Status pruefen |
| ESP32-S3: ADC liest immer 0 | Falsche Pins (GPIO33-39 gibt es nicht auf S3) | Firmware-Update mit Board-Erkennung |
| Display bleibt schwarz | SPI-Pins oder A0/RST vertauscht | Verkabelung pruefen |
