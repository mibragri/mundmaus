# MundMaus – Setup & Hardware Guide

## Kaufempfehlung ESP32

### ⭐ Erste Wahl: Waveshare ESP32-S3-DEV-KIT-N16R8-M (mit verlöteten Pins)

**Amazon.de:** [https://www.amazon.de/dp/B0DKSZ7J3S](https://www.amazon.de/dp/B0DKSZ7J3S)
**Preis:** ~16 EUR | **Kein Löten nötig – Pins sind vorverlötet!**

> ⚠️ Unbedingt die **"-M" Variante** kaufen (M = mit Pins). Die Version ohne M hat nur lose Pin-Leisten beigelegt, die man selbst einlöten muss.

Warum dieses Board:

- **Pre-Soldered Headers** → Auspacken, Kabel einstecken, fertig
- **Dual-Core LX7 240MHz** – ein Kern für WebSocket/HTTP, einer für Sensor-Loop
- **16MB Flash** – genug für Firmware + Solitaire-HTML + weitere Spiele direkt vom ESP32
- **8MB PSRAM** – HTML-Seiten im RAM servieren, kein Raspberry Pi nötig
- **Dual USB-C** – ein Port für UART/Flash, ein Port für native USB (kein Micro-USB-Gefummel)
- **CH343 + CH334 Chips** – zuverlässiger als der billige CH340 bei vielen No-Name-Boards
- **Pin-kompatibel** mit ESP32-S3-DevKitC-1 Layout
- **Waveshare Wiki** mit Doku, Pinout-Diagrammen, Beispielcode
- **Positive Reviews auf Amazon.de** – WiFi stabil, MicroPython getestet

### Alternative: Heemol ESP32-S3 N16R8 DevKitC-1 (mit verlöteten Pins + IPEX-Antenne)

**Amazon.de:** [https://www.amazon.de/dp/B0FKFXC6F8](https://www.amazon.de/dp/B0FKFXC6F8)
**Preis:** ~14 EUR | **Pins vorverlötet + externe Antenne mitgeliefert**

Vorteile:

- Header bereits verlötet, gute Verarbeitungsqualität lt. Reviews
- Externe 2.4G-Antenne + IPEX-Port → bessere Reichweite in schwierigen Umgebungen
- Ausführliche QR-Code-basierte Doku (gut für Einsteiger)

Nachteil: Antenne auf extern umschalten erfordert einen SMD-Widerstand umlöten (nur nötig falls man die externe Antenne nutzen will – die integrierte PCB-Antenne reicht für MundMaus-Nähdistanz).

### ❌ NICHT empfohlen: AZ-Delivery DevKitC V4 (ESP32-WROOM-32)

Das ist dein vorhandenes Board. Es funktioniert grundsätzlich, aber:

- **Nur 4MB Flash** → Solitaire-HTML (36KB) + weitere Spiele wird sofort eng
- **Kein PSRAM** → kann HTML nicht vom ESP32 servieren (Raspberry Pi nötig)
- **Micro-USB** statt USB-C
- **Kein natives USB**
- **GPIO33-39 nur Input** (kein Pull-Up, anders als beim S3)
- **ADC2 blockiert bei aktivem WiFi** (klassischer ESP32-Stolperstein)

**Fazit:** ESP32-S3 kaufen (~15€), den alten ESP32 als Ersatzteil aufheben.

### Pin-Mapping: ESP32-S3 vs. ESP32 (WROOM)

Siehe Abschnitt "Code-Anpassung" weiter oben für die vollständige Pin-Tabelle und automatische Board-Erkennung.

---

## Code-Anpassung: Was muss geändert werden?

### Ja, main.py muss angepasst werden (aber minimal)

Der aktuelle Code ist für den klassischen ESP32 (WROOM-32) geschrieben. Für den ESP32-S3 sind **drei Änderungen** nötig:

#### 1. Pin-Nummern (MUSS)

Der ESP32-S3 hat **keine GPIO33-39**. Diese Pins existieren physisch nicht. Die ADC1-Kanäle liegen auf anderen GPIOs:

```python
# === VORHER (ESP32-WROOM) ===
PIN_VRX = 33        # existiert NICHT auf S3!
PIN_VRY = 35        # existiert NICHT auf S3!
PIN_SW  = 21
PIN_PUFF_DATA = 32  # existiert NICHT auf S3!
PIN_PUFF_CLK  = 25

# === NACHHER (ESP32-S3) ===
PIN_VRX = 1         # ADC1_CH0
PIN_VRY = 2         # ADC1_CH1
PIN_SW  = 42        # freier Digital-Pin
PIN_PUFF_DATA = 4   # freier Digital-Pin
PIN_PUFF_CLK  = 5   # freier Digital-Pin
```

#### 2. Board-Erkennung (EMPFOHLEN)

Damit die gleiche Firmware auf beiden Boards läuft – ideal für ein Open-Source-Projekt:

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

#### 3. PSRAM aktivieren (ESP32-S3 mit -spiram-oct Firmware)

Für den ESP32-S3 N16R8 die **Octal-SPIRAM** Firmware verwenden:

```
Download: ESP32_GENERIC_S3-SPIRAM_OCT-v1.27.0.bin
(statt ESP32_GENERIC_S3-v1.27.0.bin)
```

Das aktiviert automatisch den 8MB PSRAM und gibt MicroPython mehr Heap.

### Was muss NICHT geändert werden?

- **WiFiManager** – identisch, `network.WLAN()` API gleich
- **WebSocket/HTTP Server** – identisch, Socket-API gleich
- **Spiellogik in solitaire.html** – komplett unverändert, läuft im Browser
- **HX710B Bit-Banging** – identisch, nutzt nur `Pin.value()` und `Pin.on()/off()`
- **Kalibrierungs-Logik** – identisch, ADC-Werte sind 12-bit auf beiden Boards

---

## MicroPython: Welche Version? Was bringt das Neueste?

### Empfohlen: MicroPython v1.27.0 (Dezember 2025)

Download: https://micropython.org/download/ESP32_GENERIC_S3/

**Relevante neue Features für MundMaus:**

| Feature | Version | Nutzen für MundMaus |
|---------|---------|-------------------|
| `asyncio` IPv6 in `start_server()` | v1.27 | Zukunftssicher |
| UART IRQ Callbacks (IRQ_RX, IRQ_RXIDLE) | v1.25+ | Effizienteres HX710B-Reading |
| `network.ipconfig()` neue API | v1.25+ | Sauberere WiFi-Konfiguration |
| `Pin.toggle()` | v1.25+ | Vereinfacht HX710B Clock |
| Dynamic USB Device (S2/S3) | v1.25+ | USB-HID Maus-Modus möglich! |
| Compressed error messages | v1.25+ | Weniger RAM für Fehlerstrings |
| Auto-detect SPIRAM | v1.24+ | PSRAM wird automatisch erkannt |
| TLS Memory Management | v1.25+ | Stabiler bei WiFi-Reconnects |
| ROMFS (Read-Only Filesystem) | v1.27 | HTML-Dateien direkt aus Flash |

### 🔑 Wichtigstes Feature: `asyncio` statt Polling-Loop

Unser aktueller Code nutzt eine synchrone Polling-Loop (`while True: ... time.sleep_ms(20)`). Das funktioniert, ist aber ineffizient. MicroPython v1.25+ hat ausgereiftes `asyncio`:

**Vorher (synchron, aktuell):**
```python
while True:
    server.poll()           # blockiert kurz
    nav = joystick.poll()   # blockiert kurz
    if puff.detect():       # blockiert kurz
        server.send('puff')
    time.sleep_ms(20)       # 50 Hz fest
```

**Nachher (asyncio, empfohlen für v2):**
```python
async def sensor_loop():
    while True:
        nav = joystick.poll()
        if nav:
            await server.send_nav(nav)
        if puff.detect():
            await server.send_action('puff')
        await asyncio.sleep_ms(20)

async def ws_loop():
    while True:
        await server.poll()  # nicht-blockierend
        await asyncio.sleep_ms(5)

async def main():
    asyncio.create_task(sensor_loop())
    asyncio.create_task(ws_loop())
    await asyncio.sleep_ms(999999999)  # forever

asyncio.run(main())
```

**Vorteile von asyncio:**
- Sensor-Loop und WebSocket laufen unabhängig
- Kein fester 20ms-Takt – Sensoren können schneller polled werden
- WiFi-Reconnect blockiert nicht die Joystick-Abfrage
- `ThreadSafeFlag` für IRQ → asyncio Brücke

**Empfehlung:** Für den ersten Release den synchronen Code belassen (funktioniert, ist getestet). Für v2 auf asyncio migrieren – das ist dann auch ein guter Community-Beitrag.

### 🔑 Zweites Highlight: USB-HID (Dynamic USB Device)

MicroPython v1.25+ unterstützt auf dem ESP32-S3 dynamische USB-Konfiguration. Das bedeutet: der ESP32-S3 kann sich als **USB-HID-Maus** am PC/TV anmelden – ganz ohne WiFi:

```python
# Zukunft: USB-HID Maus-Modus (ESP32-S3 only)
import machine
usb = machine.USBDevice()
# ... HID Mouse descriptor ...
```

Das wäre ein alternativer Betriebsmodus: ESP32 direkt per USB-C an den PC/TV, erscheint als Maus. Kein WiFi, kein Browser – aber auch kein Solitaire (nur Mauszeiger-Steuerung für beliebige Programme).

### Firmware-Download und Flash-Befehl

```bash
# ESP32-S3 mit Octal PSRAM (N16R8):
# Download von https://micropython.org/download/ESP32_GENERIC_S3/

esptool.py --chip esp32s3 --port /dev/ttyUSB0 erase_flash

esptool.py --chip esp32s3 --port /dev/ttyUSB0 \
  --baud 460800 write_flash -z 0x0 \
  ESP32_GENERIC_S3-SPIRAM_OCT-20251209-v1.27.0.bin
```

---

## Verdrahtung (kein Löten!)

> **Philosophie:** Alles wird mit DuPont-Jumperkabeln auf ein Breadboard gesteckt.
> Kein Löten nötig. Für den Dauerbetrieb können Schraubklemmen-Adapter verwendet werden.

### Benötigtes Zubehör (zusätzlich zu den Komponenten)

| Zubehör | Preis |
|---------|-------|
| Breadboard 830 Kontakte | ~3 EUR |
| DuPont Jumper-Kabel Set (M-F, M-M, F-F je 40 Stk) | ~7 EUR |
| USB-C Datenkabel | ~5 EUR |

### Joystick KY-023

```
KY-023          ESP32-S3
───────         ─────────
GND      ────── GND
+5V      ────── 3.3V  ⚠️ NICHT 5V! (3.3V reicht, siehe mouthMouse README)
VRx      ────── GPIO1
VRy      ────── GPIO2
SW       ────── GPIO42
```

**Achtung:** Der KY-023 ist mit "5V" beschriftet, funktioniert aber korrekt an 3.3V. Die ADC-Werte passen zu den Kalibrierungseinstellungen in der Firmware.

### Drucksensor MPS20N0040D-S + HX710B

```
HX710B Board    ESP32-S3
────────────    ─────────
VCC      ────── 3.3V
GND      ────── GND
DATA     ────── GPIO4
CLK      ────── GPIO5

Sensor-Seite:
Silikonschlauch (ID 5mm) → T-Stück (Gardena) → Sensor-Eingang
                           ↓
                      Mundstück
```

### Display ST7735 (optional)

```
ST7735          ESP32-S3
──────          ─────────
VCC      ────── 3.3V
GND      ────── GND
SDA      ────── GPIO23 (MOSI)
SCK      ────── GPIO18 (SCK)
CS       ────── GPIO17
A0/DC    ────── GPIO6
RESET    ────── GPIO14
```

### Komplettes Pinout-Diagramm

```
                 ESP32-S3-DevKitC-1 N16R8
                 ┌──────────────────────┐
                 │  [USB-C]    [USB-C]  │
                 │   UART       USB     │
                 ├──────────────────────┤
           3.3V ─┤ 3V3              GND ├─ GND (alle GND)
                 ┤                      ├
 Joystick VRx ──┤ GPIO1          GPIO42├── Joystick SW
 Joystick VRy ──┤ GPIO2               ├
                 ┤ GPIO3               ├
  Puff DATA ────┤ GPIO4          GPIO23├── Display SDA
  Puff CLK ─────┤ GPIO5          GPIO18├── Display SCK
  Display A0 ───┤ GPIO6          GPIO17├── Display CS
                 ┤ GPIO7          GPIO14├── Display RST
                 ┤ ...             ...  ├
                 └──────────────────────┘

Stromversorgung:
  3.3V ──┬── KY-023 +5V (Label ignorieren!)
         ├── HX710B VCC
         └── ST7735 VCC
  GND ──┬── KY-023 GND
         ├── HX710B GND
         └── ST7735 GND
```

---

## Netzwerk-Architektur

### Konzept: ESP32 als selbständiger Hotspot

Der ESP32 startet immer als **eigener WiFi-Hotspot**. Das ist die zuverlässigste Lösung:

- Kein fremdes WLAN nötig
- Funktioniert überall (Krankenhaus, Pflegeheim, zuhause)
- Keine Router-Konfiguration
- Feste, vorhersagbare IP-Adresse

```
┌─────────────────────────────────────────────────────┐
│                  WiFi "MundMaus"                      │
│                  PW: mundmaus1                        │
│                                                       │
│   ┌───────────────┐         ┌──────────────────────┐ │
│   │   ESP32-S3    │  WiFi   │   Raspberry Pi       │ │
│   │               │◄───────►│   (oder PC/Laptop)   │ │
│   │  IP: 192.168.4.1       │                      │ │
│   │  HTTP :80     │         │   Browser öffnet:    │ │
│   │  WS   :81     │         │   http://192.168.4.1 │ │
│   │               │         │                      │ │
│   │  Joystick     │         │   ┌──────────────┐   │ │
│   │  Puff-Sensor  │ ──WS──► │   │ solitaire.html│  │ │
│   │  Display      │         │   │ (vom ESP32)  │   │ │
│   └───────────────┘         │   └──────────────┘   │ │
│                              │          │            │ │
│                              │   TV/Monitor via HDMI │ │
│                              └──────────────────────┘ │
└─────────────────────────────────────────────────────┘
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
Browser öffnet: http://192.168.4.1
WebSocket:      ws://192.168.4.1:81
```

#### Modus 2: Bestehendes WLAN (optional)

Falls Internet auf dem Pi gewünscht ist (Updates etc.):

```
Über WiFi-Panel im Solitaire-Spiel:
  📶 → SSID + Passwort eingeben → ESP32 startet neu

ESP32 verbindet sich mit dem Router:
  IP: wird vom Router vergeben (z.B. 192.168.1.42)

Pi verbindet sich ebenfalls mit dem Router:
  Browser öffnet: http://192.168.1.42 (oder mDNS, falls konfiguriert)

⚠️ Nachteil: IP nicht vorhersagbar, DHCP kann sich ändern
⚠️ Bei Fehlschlag: automatischer Fallback auf Hotspot-Modus
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

Oder über raspi-config:

```bash
sudo raspi-config
# → System Options → Wireless LAN
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
# Dann über GUI: Bildschirmschoner → Deaktivieren

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

Der ESP32-S3 mit 16MB Flash kann die Solitaire-HTML und weitere Spiele direkt servieren. Kein separater Webserver nötig.

### Dateistruktur auf dem ESP32

```
/                       (ESP32 Flash Root)
├── boot.py
├── main.py             (Firmware)
├── wifi.json           (gespeicherte WLAN-Credentials)
└── www/                (Webseiten)
    ├── index.html      (Spiele-Portal / Launcher)
    ├── solitaire.html  (Solitaire-Spiel)
    ├── memory.html     (Memory-Spiel – zukünftig)
    └── settings.html   (Einstellungen – zukünftig)
```

### Spiele-Portal (index.html)

Wird vom ESP32 auf `http://192.168.4.1/` ausgeliefert. Zeigt:

- Spielauswahl (große Kacheln, mundmaus-bedienbar)
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

### Upload über Web-Interface (ohne USB)

Der ESP32-Server bietet auch einen Upload-Endpunkt:

```
POST /api/upload
Content-Type: multipart/form-data
  file: <datei>
  path: www/neues-spiel.html
```

Über den Browser:
1. `http://192.168.4.1/settings.html` öffnen
2. Datei auswählen → Hochladen
3. Spiel erscheint im Portal

### HTTP-Routing in main.py

```python
# In MundMausServer._handle_http():

if 'GET / ' in first_line or 'GET /index' in first_line:
    self._serve_file('www/index.html')
elif 'GET /solitaire' in first_line:
    self._serve_file('www/solitaire.html')
elif 'GET /settings' in first_line:
    self._serve_file('www/settings.html')
elif 'POST /api/upload' in first_line:
    self._handle_upload(client, request)
elif path.startswith('/www/'):
    self._serve_file(path[1:])  # Statische Dateien
```

### Flash-Speicher Aufteilung (ESP32-S3 N16R8)

```
16 MB Flash total:
  MicroPython Firmware:     ~1.5 MB
  Python-Dateien (*.py):    ~0.05 MB
  www/ Verzeichnis:         ~14 MB verfügbar!
  
  solitaire.html:           ~0.04 MB (36 KB)
  → Platz für ~350 Spiele dieser Größe
```

---

## Firmware-Anpassung für ESP32-S3

In `main.py` müssen die Pin-Konstanten für den S3 geändert werden. Am besten mit automatischer Board-Erkennung:

```python
import sys

# Automatische Board-Erkennung
if 'ESP32S3' in sys.implementation._machine:
    # ESP32-S3 Pin-Belegung
    PIN_VRX = 1
    PIN_VRY = 2
    PIN_SW  = 42
    PIN_PUFF_DATA = 4
    PIN_PUFF_CLK  = 5
    DISPLAY_A0 = 6
    print("Board: ESP32-S3")
else:
    # Klassischer ESP32 (WROOM) Pin-Belegung
    PIN_VRX = 33
    PIN_VRY = 35
    PIN_SW  = 21
    PIN_PUFF_DATA = 32
    PIN_PUFF_CLK  = 25
    DISPLAY_A0 = 2
    print("Board: ESP32 (Classic)")
```

### File-Server für www/ Ordner

Ergänzung in `MundMausServer`:

```python
def _serve_file(self, path):
    """Serve a static file from ESP32 flash."""
    content_types = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.png': 'image/png',
        '.ico': 'image/x-icon',
    }
    
    ext = path[path.rfind('.'):]
    ctype = content_types.get(ext, 'application/octet-stream')
    
    try:
        # Für große Dateien: chunk-weise senden
        with open(path, 'rb') as f:
            stat = os.stat(path)
            size = stat[6]
            
            client.send(f'HTTP/1.1 200 OK\r\n')
            client.send(f'Content-Type: {ctype}; charset=utf-8\r\n')
            client.send(f'Content-Length: {size}\r\n')
            client.send('Cache-Control: max-age=3600\r\n')
            client.send('\r\n')
            
            buf = bytearray(2048)
            while True:
                n = f.readinto(buf)
                if n == 0:
                    break
                client.send(buf[:n])
                
    except OSError:
        self._send_404(client, path)
```

---

## Erste Inbetriebnahme (Schritt für Schritt)

### 1. ESP32-S3 flashen

```bash
# esptool installieren
pip3 install esptool rshell

# ESP32-S3 per USB-C verbinden (linker Port = UART)
# Flash löschen
esptool.py --chip esp32s3 --port /dev/ttyUSB0 erase_flash

# MicroPython Firmware flashen
# Download: https://micropython.org/download/ESP32_GENERIC_S3/
esptool.py --chip esp32s3 --port /dev/ttyUSB0 \
  --baud 460800 write_flash -z 0x0 \
  ESP32_GENERIC_S3-20250101-v1.24.1.bin
```

### 2. Dateien hochladen

```bash
rshell --buffer-size=30 -p /dev/ttyUSB0

# Verzeichnis erstellen
mkdir /pyboard/www

# Dateien kopieren
cp boot.py /pyboard/boot.py
cp main.py /pyboard/main.py
cp solitaire.html /pyboard/www/solitaire.html
cp index.html /pyboard/www/index.html
```

### 3. Hardware verkabeln

1. Joystick KY-023 an 3.3V, GND, GPIO1, GPIO2, GPIO42
2. Drucksensor HX710B an 3.3V, GND, GPIO4, GPIO5
3. Silikonschlauch an Sensor anschließen
4. (Optional) Display an SPI-Pins

### 4. Testen

```bash
# Serial Monitor öffnen
screen /dev/ttyUSB0 115200

# Erwartete Ausgabe:
# ========================================
#   MUNDMAUS v2.1 - Solitaire Edition
#   WiFi Manager + Drucksensor
# ========================================
# Joystick Kalibrierung...
# Kalibriert: center=(1847,1923) deadzone=±150
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
2. Browser öffnen: `http://192.168.4.1`
3. Spiele-Portal erscheint → Solitaire starten
4. Joystick bewegen → Karten navigieren
5. Pusten → Karte auswählen/ablegen

### 6. Raspberry Pi einrichten (für Dauerbetrieb)

1. Raspbian installieren
2. WiFi "MundMaus" konfigurieren (siehe oben)
3. Autostart-Script einrichten
4. Cursor ausblenden, Bildschirmschoner deaktivieren
5. TV/Monitor per HDMI anschließen
6. Fertig – Pi bootet direkt ins Solitaire

---

## Troubleshooting

| Problem | Ursache | Lösung |
|---------|---------|--------|
| Joystick driftet | Thermischer Drift des KY-023 | Deadzone erhöhen: `DEADZONE = 200` |
| Kein Puff erkannt | Schlauch undicht oder Threshold zu hoch | `PUFF_THRESHOLD = 0.15` senken |
| WiFi "MundMaus" nicht sichtbar | ESP32 nicht gestartet oder AP-Fehler | USB-Kabel prüfen, Serial Monitor |
| Browser zeigt nichts | www/ Ordner fehlt auf ESP32 | `rshell` → Dateien hochladen |
| WebSocket trennt sich | WiFi-Reichweite | ESP32 näher am Pi platzieren |
| Solitaire reagiert nicht | WS nicht verbunden | 📶-Panel → Status prüfen |
| ESP32-S3: ADC liest immer 0 | Falsche Pins (GPIO33-39 gibt es nicht) | Pins auf GPIO1-10 ändern |
| Display bleibt schwarz | SPI-Pins oder A0/RST vertauscht | Verkabelung prüfen |

