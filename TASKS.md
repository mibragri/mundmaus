# Tasks — Mundmaus

## Backlog
- [ ] USB-HID Mouse Mode — ESP32-S3 Dynamic USB, Maussteuerung ohne WiFi (#high)
- [ ] Sip-and-Puff — Differenzdrucksensor MPXV7002DP als Alternative zum Joystick (#medium)
- [ ] Weitere Spiele — Snake, weitere Kartenspiele (#medium)
- [ ] Input-Profile — Puff/Sip/Wangenluft konfigurierbar je Behinderungsgrad, Action-Mapping im Portal (#high)
- [ ] mDNS — `mundmaus.local` statt IP-Adresse (#medium)
- [ ] Housing — Mikrofon-Schwenkarm-Halterung für Joystick (#low)
- [ ] Raspberry Pi Kiosk — Auto-Start-Script für Kiosk-Modus (#low)

## In Progress

## Next
- [ ] Input-Profile Design — Brainstorming + Spec für konfigurierbare Eingabe-Profile

## Done (2026-04-02)
- [x] Arduino C++ Firmware v3.2 — PlatformIO, ESPAsyncWebServer, FreeRTOS, 188KB free RAM
- [x] Settings UI — Browser-Config für Joystick/Puff-Empfindlichkeit (Pfleger-Slider + Expert)
- [x] ESP32 Robustheit — Smart WDT (30s), faster OTA (1 retry), RAM protection (503 <20KB)
- [x] GC-Optimierung — gc.threshold() + post-HTTP collect (71KB steady statt 30KB)
- [x] Gzip-Serving — Pre-komprimierte .html.gz, 4-5x schnellere Seitenauslieferung
- [x] Upload-Tooling — upload-esp32.sh mit auto mpy-cross + minify + gzip
- [x] HX710B Sensor-Fix — disable_irq + PULL_DOWN, Rauschen 300k→3.8k
- [x] Puff-Detection — Adaptive Delta (Original mouthMouse), Cooldown auf Rebounds
- [x] Non-blocking Sensor-Read — Joystick 50Hz ohne HX710B-Blockade
- [x] Joystick-Navigation — Jitter-Hold 100ms, Initial-Delay 1.5x, TCP_NODELAY
- [x] Portal-Fixes — Offline-Updates verborgen, .html.gz Scan, Settings-Link
- [x] Ultrawide-Fix — --vw: min(1vw, 19.2px) auf allen Spielen
- [x] Puff-Indicator — Im Header statt Footer, in allen Spielen
- [x] Portal-Button — 🏠 in Win/Game-Over-Screens (Chess, Memo)
- [x] README.md — Komplett neu mit Pin-Diagrammen, v3.1 Architektur
- [x] 3x Code Review — Zero Defects auf MicroPython + Arduino

## Done (2026-03-30)
- [x] OTA Auto-Update — Manifest auf mundmaus.de, atomare Installation, Rollback, Recovery-AP
- [x] Firmware-Modularisierung — main.py (1009 Zeilen) → 8 Module + .mpy Pre-Compilation
- [x] Portal Joystick-Navigation — Spiele per Joystick+Puff wählbar
- [x] Portal Status-Chips — WiFi-RSSI, Sensor-Status, WS-Verbindung
- [x] Portal Auto-Reconnect — Seite lädt neu nach ESP32-Reboot
- [x] Robustheit — Hardware-Watchdog, WiFi-Reconnect, SSL vor asyncio
- [x] Zurück-zum-Portal — 🏠 Button + P-Taste in allen Spielen
- [x] Kiosk-Button — ↖↗↙↘ per Joystick navigierbar in allen Spielen
- [x] Icon UI — Universelle Icons statt deutsche Texte, bilingual Pfleger-Labels
- [x] Level-Menü — 🏋️ Gewichtheber-Icons statt Text
- [x] Schach Zuganzeige — ⚪/⚫ Farbpunkt + Spinner statt Text
- [x] Full HD Layout — max-width 1920px für TV-Ausgang
- [x] Solitaire Layout — Engere Kartenstapelung, rechts-bündige Buttons
- [x] Memory → Memo — Ravensburger-Marke vermieden
- [x] Favicon — Goldenes M auf allen Seiten
- [x] Playwright E2E Tests — 66 Tests gegen echten ESP32
- [x] OTA Basic Auth — mundmaus.de/ota passwortgeschützt
- [x] Upload-Tool — tools/upload-esp32.sh mit Auto-Reset+Reboot
- [x] Deploy-Tools — deploy-ota.sh, test-esp32.sh, provision-esp32.sh

## Done (2026-03-19)
- [x] Solitaire: Key-Repeat-Bug behoben (e.repeat Guard)
- [x] Solitaire: Navigierbare Action-Buttons (Hilfe/Neu) rechts vom Tableau
- [x] Solitaire: UI-Cleanup — Hint-Toggle entfernt, WiFi-Icon in Statusbar, Puff-Indicator mit Icon
- [x] Solitaire: Tableau-Cursor als einzelner Bar unter den Karten
- [x] Solitaire-Service: systemd User-Unit mit uv-Env (mundmaus-solitaire.service)
- [x] UFW: Port 9993 für LAN freigegeben
- [x] Gehäuse v5.5: ESP32-Maße korrigiert (54.4mm, Espressif Spec)
- [x] Gehäuse v5.5: Joystick Pin-Grid korrigiert (26.67×20.32mm)
- [x] Gehäuse v5.5: 2mm Wände (optimiert für Bambu P2S, 5 Perimeter)
- [x] Gehäuse v5.5: Neues Layout — Joystick-Säulen zentriert auf ESP32 USB-Port
- [x] Gehäuse v5.5: 4 Säulen statt Massiv-Sockel (USB-Kabel-Zugang)
- [x] Gehäuse v5.5: Mic-Nut Insertion Clearance Check im Validator
- [x] Gehäuse v5.5: Validierung komplett (Maße, Clearances, Druckbarkeit)
- [x] P2S: MQTT-Verbindung hergestellt, AMS ausgelesen, Seriennummer ermittelt
- [x] Bambu Studio CLI: P2S-Profile korrekt aufgelöst (Templates statt generisch)
- [x] Bambu Print: Profil-Validierung vor jedem Druck (validate-profiles.sh)
- [x] Bambu Print: Thumbnail-Injection (CadQuery-Render → 3MF)
- [x] Bambu Print: iPhone-Notification bei Start/Fertig/Fehler (bambu-monitor.py)
- [x] Gehäuse v5.5 Base gedruckt — Grau PETG, Slot 4, ~1h33m (2026-03-20)
- [x] Gehäuse v5.5 Lid gedruckt — Grau PETG, Slot 4
