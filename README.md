# MundMaus

**Mundgesteuerte Spieleplattform fuer Menschen mit Tetraplegie.**

Ein ESP32 mit Joystick und Drucksensor steuert browserbasierte Spiele — pusten statt klicken, Joystick statt Maus. Kein Internet, keine App. Nur WLAN und ein Browser.

Kosten: ~25 EUR | Aufbauzeit: ~30 Minuten | Nur der Drucksensor muss geloetet werden

![Solitaire](screenshots/solitaire.png) ![Chess](screenshots/chess.png) ![Memo](screenshots/memo.png)

![Portal](screenshots/portal.png) ![Settings](screenshots/settings.png)

## So funktioniert es

1. ESP32 liest Joystick (Lippe/Zunge) + Drucksensor (Pusten)
2. Sendet Befehle per WebSocket an den Browser
3. Browser zeigt Kartenspiele auf TV/Monitor
4. Alles laeuft lokal — kein Internet noetig

```
   Joystick ──┐
               ├── ESP32 ──── WiFi ──── Browser (TV/Monitor)
Drucksensor ──┘                          Solitaire / Schach / Memo
```

## Spiele

| Spiel | Beschreibung |
|-------|-------------|
| **Solitaire** | Klondike mit Undo, Auto-Solve, 3 Schwierigkeitsstufen |
| **Schach** | Gegen Computer, 4 Schwierigkeitsstufen |
| **Memo** | Memory-Spiel, 4 Feldgroessen |

Alle Spiele sind barrierefrei: farbenblind-sichere Markierungen, Audio-Feedback, Kiosk-Modus fuer den Patienten, Keyboard-Fallback fuer Pfleger.

### Portal & Einstellungen

Das **Spiele-Portal** erscheint automatisch wenn man die ESP32-Adresse im Browser oeffnet — alle Spiele auf einen Blick, WiFi-Status, Software-Updates.

Die **Einstellungen** (⚙) erlauben Pflegern, Joystick-Empfindlichkeit, Puste-Staerke und Geschwindigkeit per Slider anzupassen — ohne technische Kenntnisse.

### OTA Auto-Update

Neue Spiele und Firmware-Updates werden automatisch ueber WiFi heruntergeladen. Beim Einschalten prueft der ESP32 ob Updates verfuegbar sind — ein Klick im Portal installiert sie. Bei fehlgeschlagenem Update: automatischer Rollback auf die vorherige Version.

## Was du brauchst

### Einkaufsliste

| # | Komponente | ca. Preis | Beispiel |
|---|-----------|-----------|----------|
| 1 | ESP32-WROOM-32 DevKit (mit Pins!) | ~8 EUR | AZ-Delivery ESP32 DevKitC V4 |
| 2 | KY-023 Joystick Modul | ~3 EUR | AZ-Delivery KY-023 |
| 3 | Drucksensor MPS20N0040D-S + HX710B | ~5 EUR | eBay/AliExpress "MPS20N0040D HX710B" |
| 4 | DuPont Jumper-Kabel (M-M + M-F) | ~3 EUR | 40 Stueck Set |
| 5 | Micro-USB Kabel (Daten, nicht nur Laden!) | ~3 EUR | Beliebig |
| 6 | Silikonschlauch 4mm Innendurchmesser | ~3 EUR | Aquarium-Zubehoer |

**Gesamtkosten: ~25 EUR** — DuPont-Kabel zusammenstecken. Nur der Drucksensor (HX710B) muss geloetet werden.

> **Gehaeuse:** Ein 3D-druckbares Gehaeuse ist enthalten (`enclosure/`). Ohne 3D-Drucker: Komponenten einfach mit DuPont-Kabeln verbinden — fertig.

![Gehaeuse](enclosure/mundmaus_v55_assembly.png)

### Halterung

Das Gehaeuse wird in eine handelsueblliche **Mikrofonklemme** auf einem **Mikrofon-Bodenstaender** eingespannt (wie fuer Musiker). Der Staender steht neben dem Bett und positioniert den Joystick vor dem Mund des Patienten. Alternative: ein **Schwanenhals-Tischstaender** fuer kleinere Aufbauten.

> **Wichtig:** Das USB-Kabel muss ein **Datenkabel** sein, nicht nur ein Ladekabel! Datenkabel haben 4 Adern (2 Strom + 2 Daten), Ladekabel nur 2. Im Zweifel: wenn der Computer das ESP32 nicht erkennt, anderes Kabel probieren.

### Verkabelung

```
ESP32 DevKitC V4          KY-023 Joystick         HX710B + Drucksensor
┌─────────────────┐       ┌─────────────┐         ┌─────────────┐
│                 │       │             │         │             │
│  3V3 ───────────┼───────┤ +5V         │         │             │
│  GND ───────────┼───┬───┤ GND         │    ┌────┤ GND         │
│                 │   │   │             │    │    │             │
│  GPIO33 ────────┼───┼───┤ VRX         │    │    │             │
│  GPIO35 ────────┼───┼───┤ VRY         │    │    │             │
│  GPIO21 ────────┼───┼───┤ SW          │    │    │             │
│                 │   │   └─────────────┘    │    │             │
│  GPIO32 ────────┼───┼──────────────────────┼────┤ DATA        │
│  GPIO25 ────────┼───┼──────────────────────┼────┤ CLK         │
│  5V/VIN ────────┼───┼──────────────────────┼────┤ VCC         │
│                 │   └──────────────────────┘    │             │
│       USB ──────┤                               │   Schlauch  │
│  (Strom+Daten)  │                               │   zum Mund  │
└─────────────────┘                               └─────────────┘
```

**Schlauch-Anschluss:** Silikonschlauch auf den Barb (Nippel) des Drucksensors stecken. Das andere Ende haelt der Patient im Mund. Leichtes Pusten = Klick.

> Detaillierte Pin-Tabelle (inkl. ESP32-S3 und optionales Display): siehe [MUNDMAUS-SETUP.md](MUNDMAUS-SETUP.md)

## Firmware aufspielen

Zwei Firmware-Optionen — gleiche Features, gleiche Spiele:

| | MicroPython | Arduino C++ |
|---|---|---|
| Fuer wen | Einsteiger, schnelles Testen | Fortgeschrittene, mehr Performance |
| RAM frei | ~80 KB | ~188 KB |
| Verzeichnis | `*.py` (Root) | `firmware/arduino/` |

### Option A: MicroPython (empfohlen fuer Einsteiger)

**Schritt 1:** Software installieren (einmalig, am Computer)
```bash
pip3 install esptool mpremote mpy-cross
```

**Schritt 2:** MicroPython auf den ESP32 flashen (einmalig)
```bash
# Firmware von micropython.org herunterladen:
# https://micropython.org/download/ESP32_GENERIC/
# Datei: ESP32_GENERIC-20251209-v1.27.0.bin

# ESP32 per USB anschliessen, dann:
esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 \
  write_flash -z 0x1000 ESP32_GENERIC-20251209-v1.27.0.bin
```

> **Windows:** Statt `/dev/ttyUSB0` den COM-Port verwenden (z.B. `COM3`). Im Geraetemanager nachschauen.

**Schritt 3:** MundMaus-Dateien hochladen
```bash
tools/upload-esp32.sh
```

Oder manuell:
```bash
mpremote connect /dev/ttyUSB0 cp boot.py main.py config.py :/
mpremote connect /dev/ttyUSB0 cp sensors.py server.py updater.py wifi_manager.py display.py :/
mpremote connect /dev/ttyUSB0 mkdir :www
mpremote connect /dev/ttyUSB0 cp games/solitaire.html games/chess.html games/memo.html games/settings.html :/www/
```

### Option B: Arduino C++ (mehr RAM, schneller)

```bash
cd firmware/arduino
pip install platformio

# Firmware kompilieren + flashen:
pio run -e esp32 -t upload

# Spieledateien flashen:
pio run -e esp32 -t uploadfs
```

## Erste Inbetriebnahme

1. **ESP32 per USB an Strom anschliessen** (USB-Ladegeraet oder Computer)
2. **Mit dem WLAN "MundMaus" verbinden** (Passwort: `mundmaus1`)
3. **Browser oeffnen:** `http://192.168.4.1`
4. **WLAN konfigurieren:** Im Portal das Heim-WLAN auswaehlen und Passwort eingeben
5. **ESP32 startet neu** und verbindet sich mit dem Heim-WLAN
6. **Beliebiges Geraet im gleichen WLAN** kann jetzt die Spiele oeffnen (IP-Adresse wird im Seriell-Monitor angezeigt)

> **Fuer den TV:** Einen guenstigen Android-Stick (z.B. Xiaomi Mi TV Stick, ~30 EUR) an den TV anschliessen, Browser oeffnen, IP-Adresse eingeben. Oder einen alten Laptop/Tablet per HDMI an den TV.

## Einstellungen anpassen

Ueber das Portal (Zahnrad-Symbol ⚙) koennen Pfleger die Empfindlichkeit anpassen:

- **Joystick-Empfindlichkeit** — wie weit der Joystick bewegt werden muss
- **Puste-Staerke** — wie stark gepustet werden muss fuer einen Klick
- **Geschwindigkeit** — wie schnell der Cursor bei gehaltenem Joystick wandert

Aenderungen wirken sofort (Live-Preview). "Save" speichert dauerhaft, "Cancel" verwirft.

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

## Projektstruktur

```
mundmaus/
├── boot.py, main.py, config.py, ...  # MicroPython Firmware
├── sensors.py           # Joystick + Drucksensor (HX710B)
├── server.py            # HTTP/WebSocket Server + Portal
├── games/
│   ├── solitaire.html   # Klondike Solitaire
│   ├── chess.html        # Schach
│   ├── memo.html         # Memory/Memo
│   └── settings.html     # Einstellungen
├── firmware/arduino/     # Arduino C++ Firmware (Alternative)
├── enclosure/            # 3D-Gehaeuse (CadQuery, druckfertig)
├── tools/                # Deploy- und Build-Scripts
├── website/              # mundmaus.de Webseite (separat)
├── MUNDMAUS.md           # Detaillierte technische Dokumentation
└── MUNDMAUS-SETUP.md     # Hardware-Setup-Anleitung mit Pin-Tabellen
```

## FAQ

**Das ESP32 wird nicht erkannt (kein COM-Port):**
Anderes USB-Kabel versuchen! Viele Kabel sind reine Ladekabel ohne Datenleitungen.

**Die Spiele laden langsam:**
Normal beim ersten Laden — die Dateien werden komprimiert uebertragen (gzip). Danach schneller.

**Der Puff-Sensor reagiert nicht:**
Schlauch pruefen — ist er richtig auf dem Sensor-Nippel? Kein Knick im Schlauch? In den Einstellungen (⚙) die Puste-Empfindlichkeit erhoehen.

**Der Joystick springt:**
In den Einstellungen (⚙) die Empfindlichkeit reduzieren. Bei starkem WiFi-Ruckeln: ESP32 naeher an den Router stellen.

**Wie komme ich auf das ESP32 wenn ich die IP vergessen habe?**
ESP32 aus- und wieder einstecken. Wenn es kein WLAN findet, startet es automatisch den Hotspot "MundMaus" (Passwort: `mundmaus1`). Dann: `http://192.168.4.1`

## Mitmachen

Neue Spiele? Bug gefunden? Pull Requests willkommen! Alle Spiele sind einzelne HTML-Dateien in `games/` — HTML + CSS + JS in einer Datei, keine Build-Tools noetig.

Spiel-Design-Richtlinien: [games/STANDARDS.md](games/STANDARDS.md)

## Lizenz

AGPL-3.0 — siehe [LICENSE](LICENSE)

Basiert auf [mibragri/mouthMouse](https://github.com/mibragri/mouthMouse).
