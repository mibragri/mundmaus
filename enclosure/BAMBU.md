# Bambu Lab P2S — Druckdokumentation

## Drucker
- **Modell**: Bambu Lab P2S
- **IP**: 192.168.178.135
- **Seriennummer**: 22E8BA581100579
- **Developer Mode**: aktiviert (erforderlich für lokale API)
- **AMS 2 Pro**: Slot 1 Schwarz, Slot 2 Rot, Slot 3 Weiß, **Slot 4 Grau** (alle PETG)

## Lokale API
Der P2S wird ohne Bambu Cloud direkt über das LAN angesteuert:
- **MQTT** (Port 8883, TLS) — Druckbefehle, Status, AMS-Info
- **FTPS** (Port 990) — nicht zuverlässig für Uploads (553-Fehler)
- **Workaround**: Datei wird per temporärem HTTP-Server bereitgestellt, Drucker holt sie per URL

### Authentifizierung
- User: `bblp`
- Passwort: Access Code aus Drucker-Einstellungen
- Config: `tools/bambu-profiles/printer.env` (in `.gitignore`, nicht committed)

## Druckablauf

### 1. Generisches Tool (für alle Projekte)
```bash
# Beliebige STL-Datei slicen und drucken
bambu-print.sh model.stl --slot 4

# Nur slicen, nicht drucken
bambu-print.sh model.stl --slot 4 --no-start

# Mit eigenen Profilen
bambu-print.sh model.stl --slot 2 --profile /pfad/zu/profiles/
```

**Pfad**: `tools/bambu-print.sh`

### 2. MundMaus-spezifisch
```bash
# Base drucken (Grau PETG, Slot 4)
enclosure/print-p2s.sh base

# Lid drucken
enclosure/print-p2s.sh lid
```

### 3. Workflow intern
```
STL → BambuStudio CLI (headless slice) → .gcode.3mf
    → HTTP-Server auf 192.168.178.2:9994 (temporär)
    → MQTT-Befehl an P2S → Drucker holt Datei per HTTP
    → Druck startet automatisch
```

## Slicer-Profile

### Default-Profile (generisch)
```
tools/bambu-profiles/
├── printer.env              # IP, Access Code, Serial
├── machine-resolved.json    # P2S 0.4mm Nozzle (voll aufgelöst)
├── filament-resolved.json   # Generic PETG HF
└── process-resolved.json    # 0.20mm Standard
```

### MundMaus-Profile (projektspezifisch)
```
enclosure/bambu-profiles/
├── machine-resolved.json    # P2S 0.4mm, Textured PEI Plate
├── filament-resolved.json   # Generic PETG HF
└── process-resolved.json    # 0.20mm, 5 Wände, 25% Gyroid, 5 Top/Bottom
```

**Wichtig**: Profile sind **voll aufgelöst** (keine Vererbung). BambuStudio CLI kann vererbte Profile nicht aus dem Profilverzeichnis nachladen. Bei Updates: `validate_enclosure.py` enthält die Referenzwerte.

### MundMaus Druckeinstellungen
| Parameter | Wert |
|-----------|------|
| Material | PETG (AMS Slot 4, Grau) |
| Layer | 0.20mm |
| Wände | 5 (= 2.0mm) |
| Top/Bottom | 5 Layers |
| Infill | 25% Gyroid |
| Nozzle | 240°C |
| Bett | 70°C (Textured PEI) |
| Support | Keiner |
| Druckausrichtung Base | Boden nach unten |
| Druckausrichtung Lid | Bereits geflippt im STL |

## AMS-Belegung auslesen
```bash
python3 -c "
import ssl, json, time
import paho.mqtt.client as mqtt

def on_connect(c, ud, flags, rc, props=None):
    c.subscribe('device/22E8BA581100579/report')
def on_message(c, ud, msg):
    data = json.loads(msg.payload)
    if 'print' in data and 'ams' in data['print'].get('ams', {}):
        for unit in data['print']['ams']['ams']:
            for tray in unit.get('tray', []):
                print(f'Slot {int(tray[\"id\"])+1}: {tray.get(\"tray_type\")} #{tray.get(\"tray_color\",\"\")[:6]}')
        c.disconnect()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set('bblp', '8dc21963')
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)
client.on_connect = on_connect
client.on_message = on_message
client.connect('192.168.178.135', 8883, 10)
client.loop_start()
time.sleep(10)
client.loop_stop()
"
```

## Monitoring
Das Print-Script startet automatisch `bambu-monitor.py` im Hintergrund:
- Pollt alle 30s den Drucker-Status via MQTT
- Sendet iPhone-Notification bei **Fertigstellung** oder **Fehler**
- Loggt Fortschritt alle 10% in `/tmp/bambu-monitor.log`
- Beendet sich automatisch nach Druckende

Manuell starten:
```bash
python3 tools/bambu-monitor.py
```

## Profil-Validierung
Vor jedem Druck prüft `validate-profiles.sh` automatisch:
- Start-GCode enthält `P2S start gcode` Marker (kein generischer Code)
- Bed Type ist PETG-kompatibel
- Nozzle-Temperatur realistisch
- Smoke Test: sliced einen Test-Cube und prüft den Output-GCode

Manuell:
```bash
tools/bambu-profiles/validate-profiles.sh
```

## Thumbnail
BambuStudio CLI kann auf headless Linux keine OpenGL-Thumbnails rendern.
Das Print-Script injiziert automatisch CadQuery-Renders (512x512 PNG) als
`Metadata/plate_1.png` in die 3MF-Datei → Vorschaubild auf dem P2S Display.

## Firewall
Port 9994 muss für den Drucker offen sein (temporärer HTTP-Server für Dateitransfer):
```bash
sudo ufw allow from 192.168.178.135 to any port 9994 proto tcp comment 'bambu P2S file download'
```

## Tools
```
tools/
├── bambu-print.sh          # Slice + Upload + Print + Monitor
├── bambu-monitor.py        # Hintergrund-Monitoring mit iPhone-Notification
└── bambu-profiles/
    ├── printer.env          # IP, Access Code, Serial
    ├── machine-resolved.json    # P2S 0.4mm + Template-GCodes
    ├── filament-resolved.json   # Generic PETG HF
    ├── process-resolved.json    # 0.20mm, 5 Wände, 25% Gyroid
    └── validate-profiles.sh     # Pre-Print Validierung
```

## Abhängigkeiten
- `BambuStudio.AppImage` → `~/.local/bin/BambuStudio.AppImage`
- `libwebkit2gtk-4.1-0` (apt)
- `mosquitto-clients` (apt)
- `paho-mqtt` (pip)
- `Pillow` (pip, für Thumbnail-Injection)
