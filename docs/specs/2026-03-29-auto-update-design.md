# ESP32 Auto-Update mit Firmware-Modularisierung

**Datum:** 2026-03-29
**Status:** Design approved

---

## Ziel

ESP32 prüft beim Boot auf Updates (Manifest auf mundmaus.de), zeigt verfügbare Updates im Web-Portal an, und ermöglicht manuellen Update-Start mit Fortschrittsanzeige. Firmware-Rollback schützt gegen fehlerhafte Updates. Voraussetzung: Aufspaltung der monolithischen `main.py` in Module.

## Endnutzer-Kontext

- **Patient:** Tetraplegie, bedient Gerät mit Mund (Joystick + Pusten)
- **Pfleger:** Keine technische Schulung, kann kein USB-Recovery
- **Nutzungsmuster:** Paar Stunden spielen → Gerät wird ausgesteckt → Reboot passiert natürlich

---

## Phase 1: Firmware-Modularisierung

Aufspaltung der monolithischen `main.py` (~1000 Zeilen) in Module:

```
/                          (ESP32 Flash Root)
├── boot.py                (~50 Zeilen, Rollback-Logik + Recovery-AP)
├── main.py                (~80 Zeilen, Startup + asyncio Loop)
├── config.py              (~40 Zeilen, Board-Detection + alle Konstanten)
├── wifi_manager.py        (~120 Zeilen)
├── server.py              (~300 Zeilen, HTTP + WebSocket + Portal-HTML)
├── sensors.py             (~200 Zeilen, CalibratedJoystick + PuffSensor/HX710B)
├── updater.py             (~150 Zeilen, Manifest-Check + Download)
├── display.py             (~80 Zeilen, optional ST7735)
├── wifi.json              (auto-generiert, WLAN-Credentials — NIE OTA)
├── versions.json          (auto-generiert, lokale Datei-Versionen — NIE OTA)
├── update_state.json      (auto-generiert, Rollback-State — NIE OTA)
└── www/
    ├── solitaire.html
    ├── chess.html
    └── memory.html
```

### `config.py` — Shared Konfiguration

Enthält Board-Detection und alle Konstanten die von mehreren Modulen gebraucht werden:
- Board-Detection (ESP32 vs ESP32-S3) + alle PIN_* Definitionen
- VERSION, WS_PORT, HTTP_PORT, AP_SSID, AP_PASS, AP_IP
- Joystick-Thresholds, Puff-Thresholds, Timing-Konstanten
- OTA_BASE_URL (z.B. `https://mundmaus.de/ota`)

Alle Module importieren aus config: `from config import *` oder selektiv.

### .mpy Pre-compilation: auf Phase 2 verschoben

Erst wenn RAM auf ESP32-WROOM tatsächlich eng wird. Grund: mpy-cross Version muss exakt zur MicroPython-Firmware-Version passen — bei Firmware-Update ohne passendes mpy-cross sind alle .mpy-Dateien inkompatibel.

---

## Phase 2: Auto-Update-System

### Hosting: mundmaus.de

OTA-Dateien werden auf mundmaus.de gehostet (eigener Server, Caddy HTTPS):
- Manifest: `https://mundmaus.de/ota/manifest.json`
- Dateien: `https://mundmaus.de/ota/<dateiname>`
- Vorteile: Volle Kontrolle, kein CDN-Caching, kein SNI-Risiko, HTTPS via Caddy

Deployment der OTA-Dateien auf mundmaus.de wird in `deploy.sh` integriert oder als eigenes `tools/deploy-ota.sh` Script.

### Manifest (`manifest.json`)

```json
{
  "manifest_version": 1,
  "files": {
    "boot.py":            { "version": 1, "firmware": true },
    "main.py":            { "version": 5, "firmware": true },
    "config.py":          { "version": 3, "firmware": true },
    "wifi_manager.py":    { "version": 2, "firmware": true },
    "server.py":          { "version": 3, "firmware": true },
    "sensors.py":         { "version": 2, "firmware": true },
    "updater.py":         { "version": 1, "firmware": true },
    "display.py":         { "version": 1, "firmware": true },
    "www/solitaire.html": { "version": 3 },
    "www/chess.html":     { "version": 2 },
    "www/memory.html":    { "version": 1 }
  }
}
```

- `firmware: true` — Dateien die einen Reboot brauchen (alle `.py` im Root)
- Games (`www/`) — wirken sofort beim nächsten Seitenaufruf
- Versionsnummer pro Datei — ESP32 vergleicht mit lokaler `versions.json`
- `dest` entfällt — Pfad im Manifest = Pfad auf ESP32

### Ausschlüsse (NIE im Manifest)

- `wifi.json` — User-Credentials
- `versions.json` — lokal verwaltet durch updater.py
- `update_state.json` — lokal verwaltet durch boot.py/updater.py

### `versions.json` (auf ESP32-Flash)

```json
{
  "boot.py": 1,
  "main.py": 5,
  "config.py": 3,
  "wifi_manager.py": 2,
  "server.py": 3,
  "sensors.py": 2,
  "updater.py": 1,
  "display.py": 1,
  "www/solitaire.html": 3,
  "www/chess.html": 2,
  "www/memory.html": 1
}
```

### Boot-Ablauf (erweitert)

```
boot.py:
  1. Rollback-Check (update_state.json)
  2. GC, Board-Detection

main.py:
  3. Module importieren (config, wifi_manager, server, sensors, updater, display)
  4. WiFi connect (WiFiManager)
  5. Server starten (HTTP + WebSocket) — SOFORT, nicht warten
  6. Wenn update_state "pending" war und Boot erfolgreich: status → "ok"
  7. asyncio Event-Loop starten:
     - sensor_loop (50 Hz)
     - server_loop (100 Hz)
     - display_loop (0.2 Hz)
     - update_check (einmalig, async) — Manifest von mundmaus.de fetchen,
       Ergebnis im RAM merken, Portal per WebSocket benachrichtigen
```

**Wichtig:** Server startet VOR dem Manifest-Check. User kann sofort spielen. Update-Badge erscheint asynchron sobald der Check fertig ist. Bei langsamer Verbindung oder Timeout (5s) zeigt das Portal einfach keinen Update-Hinweis.

### Portal-Erweiterungen

**Status-Anzeige im Portal:**
- Beim Laden: kein Update-Hinweis (Check läuft noch im Hintergrund)
- Updates da (WS-Push): **"X Updates verfügbar"** (Badge) + Update-Button
- Alles aktuell (WS-Push): **"Aktuell"**
- AP-Modus / kein Internet: **"Offline — keine Update-Prüfung"**
- Nach Rollback (recovery Flag): **"Update fehlgeschlagen, alte Version wiederhergestellt"**

**Update-Prozess (User klickt Button):**
1. Fortschrittsanzeige via WebSocket: "Datei 2/5: chess.html..."
2. Games zuerst (kein Reboot nötig, best-effort — Fehler bei einem Game stoppt nicht den Rest)
3. Firmware zuletzt (ALL-OR-NOTHING — Fehler bei einer Firmware-Datei → alle verwerfen)
4. Abschluss-Meldung:
   - Nur Games: "Update fertig"
   - Mit Firmware: "Update fertig, wird beim nächsten Start aktiv"
   - Teilfehler: "3 von 5 Updates installiert, 2 fehlgeschlagen: ..."

### API-Endpoints (neu)

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/updates` | GET | `{available: [{file, from_ver, to_ver}], offline: bool}` |
| `/api/update/start` | POST | Startet Update-Prozess, Fortschritt via WebSocket |

**WebSocket-Messages (neu):**
| Type | Richtung | Payload |
|------|----------|---------|
| `update_status` | Server→Browser | `{available: [...], offline: bool}` — nach Manifest-Check |
| `update_progress` | Server→Browser | `{file: "chess.html", current: 2, total: 5}` |
| `update_complete` | Server→Browser | `{firmware_updated: bool, message: "..."}` |
| `update_error` | Server→Browser | `{file: "...", error: "..."}` |

### Datei-Download

- Quelle: `https://mundmaus.de/ota/<datei>`
- Streaming-Download mit raw `socket` + `ssl` (2KB Buffer, chunk-weise in Datei)
- Nicht `urequests` (puffert ganze Response im RAM → 52KB chess.html sprengt den Speicher)
- Nacheinander, nicht parallel (RAM-Schonung)
- `await asyncio.sleep_ms(0)` zwischen Chunks — gibt Server-Loop Zeit für WS-Progress-Updates

### Atomarer Download-Prozess

Zu keinem Zeitpunkt darf das System in einem inkonsistenten Zustand sein:

```
1. DOWNLOAD-PHASE: Alle Dateien als .new herunterladen
   - main.py.new, config.py.new, www/chess.html.new, ...
   - Bei Fehler einer Firmware-Datei: ALLE .new löschen → abbrechen
   - Bei Fehler einer Game-Datei: .new löschen, Rest weitermachen

2. INSTALL-PHASE (nur wenn Downloads erfolgreich):
   Firmware (atomar):
   a) Für jede Firmware-Datei: original → .bak kopieren
   b) Für jede Firmware-Datei: .new → final (os.rename)
   c) update_state.json = {"status": "pending", "attempts": 0}

   Games (einzeln):
   d) Für jedes Game: .new → final (os.rename) — atomar pro Datei

3. CLEANUP:
   e) versions.json aktualisieren (ERST JETZT, nach allen Renames)
   f) Gelöschte Dateien entfernen (in versions.json aber nicht im Manifest)
```

**Warum os.rename für Games:** Wenn ein Game gerade per HTTP ausgeliefert wird während es aktualisiert wird, würde direktes Schreiben korrupte Daten liefern. `os.rename()` ist atomar auf FAT.

### Gelöschte Dateien

Dateien die in `versions.json` existieren aber nicht mehr im Manifest: werden beim Update gelöscht. Verhindert stale Games auf dem ESP32. Nur im Rahmen eines aktiven Update-Prozesses, nicht beim Boot.

---

## Rollback-Mechanismus

### `update_state.json`

Zwei Zustände:

```json
{"status": "ok"}
{"status": "pending", "attempts": 0}
```

Optional nach Rollback:
```json
{"status": "ok", "recovery": true}
```

`recovery: true` wird von main.py gelesen und im Portal als Warnung angezeigt. Wird beim nächsten erfolgreichen Update oder manuell entfernt.

### Ablauf bei Firmware-Update

```
Update-Prozess (updater.py):
  1. Alle Dateien als .new herunterladen
  2. Firmware: original → .bak kopieren
  3. Alle: .new → final (rename)
  4. update_state.json = {"status": "pending", "attempts": 0}
  5. versions.json aktualisieren
  6. Portal: "Update fertig, wird beim nächsten Start aktiv"

--- User steckt Gerät aus und wieder ein ---

boot.py liest update_state.json:
├── "ok" / fehlt → normal, main.py starten
├── "pending" + attempts < 2:
│     attempts++ speichern → main.py starten
│     main.py bei erfolgreicher Init → status "ok"
│     main.py crasht → ESP32 hängt → User steckt aus/ein → nächster Boot
└── "pending" + attempts >= 2:
      ROLLBACK:
      ├── .bak-Dateien existieren → alle zurückkopieren → status "ok" + recovery: true
      │   → main.py (alte Version) startet normal, Portal zeigt Warnung
      └── .bak fehlt → Recovery-AP direkt in boot.py
```

### Recovery-AP (Notfall, in boot.py)

Aktiviert wenn Rollback nicht möglich ist (keine `.bak`-Dateien). Minimaler AP-Hotspot mit Upload-Seite:

- SSID: "MundMaus-Recovery"
- IP: 192.168.4.1
- Simple HTML-Seite mit File-Upload
- Upload-Mechanismus: JavaScript `FileReader` liest Datei, sendet rohen Inhalt per `POST /upload/<filename>` — vermeidet komplexes Multipart-Parsing in boot.py
- ~60 Zeilen Code in boot.py
- Letzte Rettung bevor USB-Recovery nötig wird

### boot.py Update-Risiko

`boot.py` ist die Sicherheitsbasis. Updates sind möglich aber selten und müssen besonders getestet werden. Wenn ein `boot.py`-Update fehlschlägt, greift kein Software-Rollback → USB-Recovery nötig. Akzeptabel weil boot.py minimal ist und sich kaum ändert.

---

## Test & Deployment Pipeline

### Zwei ESP32-Geräte

| Gerät | Anschluss | Rolle |
|-------|-----------|-------|
| **Test-ESP32** | Server (USB) | Automatisierte Integration-Tests vor OTA-Deploy |
| **Produktions-ESP32** | Laptop (SSH) | Erstbetankung neuer Geräte für Patient oder Versand |

Damit wird MundMaus reproduzierbar: neuer ESP32 → remote flashen → verschicken → OTA-Updates automatisch.

### Test-Pipeline (`tools/test-esp32.sh`)

Voraussetzung: Test-ESP32 per USB am Server angeschlossen.

```
1. PRE-CHECK (schnell, ohne Hardware):
   - mpy-cross: alle .py-Dateien kompilieren → MicroPython-Syntax valide?
   - manifest.json parsebar, alle referenzierten Dateien existieren
   - Versionen nur aufwärts (Vergleich mit deployed Manifest auf mundmaus.de)

2. UPLOAD auf Test-ESP32:
   - mpremote connect /dev/ttyUSB0 cp boot.py main.py config.py ... :
   - mpremote cp games/*.html :www/

3. BOOT-VERIFIZIERUNG (Serial Console):
   - mpremote/rshell: Serial Output monitoren
   - Warten auf "Bereit." Message (Timeout 30s)
   - IP-Adresse aus Output extrahieren
   - Prüfen: keine Exceptions, kein Crash, kein Reboot-Loop

4. WEB-INTERFACE-TEST (Playwright):
   - http://<esp-ip>/ — Portal lädt, Games aufgelistet
   - Jedes Game einzeln öffnen — kein JS-Error
   - WebSocket-Verbindung wird aufgebaut
   - Update-UI Elemente rendern korrekt (Badge, Button)
   - Während Playwright: Serial Console auf Errors prüfen

5. ERGEBNIS:
   - Alles grün → deploy-ota.sh freigegeben
   - Fehler → Abbruch, Fehler-Report
```

### Erstbetankung neuer Geräte (`tools/provision-esp32.sh`)

Für neue ESP32s die per USB am Laptop hängen (Zugriff via SSH):

```
1. MicroPython-Firmware flashen (esptool.py, einmalig)
2. Alle Dateien uploaden (mpremote)
3. Boot verifizieren (Serial Console)
4. WiFi-Credentials: User verbindet sich mit MundMaus-Hotspot und konfiguriert WLAN
5. Ab dann: OTA-Updates automatisch via mundmaus.de
```

### Manifest-Pflege: `tools/update-manifest.py`

- Scannt Firmware-Dateien (`*.py` im Root, ohne `wifi.json` etc.) und Games (`games/*.html`)
- Berechnet SHA256 pro Datei, vergleicht mit `.manifest-state.json`
- Bei Änderung: Versionsnummer automatisch bumpen
- Schreibt `manifest.json` im Repo-Root
- `.manifest-state.json` in `.gitignore` (lokaler State)
- Kann als Pre-Commit-Hook oder manuell laufen

### Deployment: `tools/deploy-ota.sh`

```
1. tools/test-esp32.sh ausführen → bei Fehler: Abbruch
2. manifest.json + alle Firmware/Game-Dateien nach mundmaus.de:/ota/ kopieren (rsync + SSH)
3. Verify: manifest.json auf mundmaus.de erreichbar und parsebar
```

### Kompletter Release-Ablauf

```
Code ändern (Firmware oder Games)
  → tools/update-manifest.py        Manifest aktualisieren
  → git commit + push               Code versionieren
  → tools/deploy-ota.sh             Test auf ESP32 → Deploy auf mundmaus.de
                                     (test-esp32.sh läuft automatisch als Gate)
  → ESP32-Geräte im Feld bekommen Updates beim nächsten Boot
```

---

## Offline-Verhalten

- AP-Modus oder kein Internet: Portal zeigt "Offline — keine Update-Prüfung"
- Manifest-Fetch Timeout: 5 Sekunden
- Alles funktioniert normal mit lokalen Dateien
- Keine Fehler, keine Blockade — Update-Check ist best-effort
- Server ist bereits gestartet bevor der Check läuft
