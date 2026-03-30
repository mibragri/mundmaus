# Tasks — Mundmaus

## Backlog
- [ ] USB-HID Mouse Mode — ESP32-S3 Dynamic USB, Maussteuerung ohne WiFi (#high)
- [ ] Sip-and-Puff — Differenzdrucksensor MPXV7002DP als Alternative zum Joystick (#medium)
- [ ] Weitere Spiele — Snake, weitere Kartenspiele (#medium)
- [ ] Settings Panel — Threshold/Deadzone über Browser-UI einstellen (#medium)
- [ ] Input-Profile — Puff/Sip/Wangenluft konfigurierbar je Behinderungsgrad, Action-Mapping im Portal (#high)
- [ ] Solitaire Ultrawide-Skalierung — vw-Einheiten vs Container-basiert (#low)
- [ ] mDNS — `mundmaus.local` statt IP-Adresse (#medium)
- [ ] Housing — Mikrofon-Schwenkarm-Halterung für Joystick (#low)
- [ ] Raspberry Pi Kiosk — Auto-Start-Script für Kiosk-Modus (#low)

## In Progress
- [ ] Gehäuse v5.5 Lid drucken — Grau PETG, Slot 4
- [ ] Input-Profile Design — Brainstorming + Spec für konfigurierbare Eingabe-Profile

## Next
- [ ] Gehäuse v5.6 — Cantilever-Clips statt Schrauben (Daumen-lösbar, selten geöffnet)
- [ ] Gehäuse v5.6 — Joystick-PCB Niederhalter (Druckstege im Lid-Inneren, ~0.5mm Spiel)
- [ ] Gehäuse v5.6 — Schraubbosses entfernen (durch Clips ersetzt)

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
