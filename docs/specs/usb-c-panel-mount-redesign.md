# USB-C Panel Mount Redesign — Design Proposal

**Status:** Draft
**Betrifft:** Enclosure v5.2 → v5.3
**Datum:** 2026-03-06

---

## 1. Problemanalyse

### Ist-Zustand (v5.2)

- **Board:** ESP32-WROOM-32 DevKitC V4, USB Micro-B auf der kurzen Seite (+X Ende)
- **Board-Position:** Zentrum X=28, Y=-2, USB-Ende bei X≈53.75
- **USB-Oeffnung:** Rechteckiger Kabel-Durchlass 8×3.5mm auf +Y Wand bei X=45, Z=5.5 (ueber Boden)
- **Kabel-Notch:** 8×4mm Kerbe in Oberkante der +Y Wand + Lip fuer Kabelauslass
- **Nutzung:** USB-Kabel wird von innen eingesteckt, durch die Oeffnung nach aussen gefuehrt. Gehaeuse muss zum Anstecken geoeffnet werden.

### Probleme

1. **Mechanische Belastung:** Pfleger brechen wiederholt den USB Micro-B Stecker am ESP32. Micro-B ist konstruktionsbedingt fragil (asymmetrisch, kleine Kontakte, kurzer Hebelarm)
2. **Falsch einstecken:** Micro-B hat eine Orientierung — Pfleger versuchen es verkehrt herum und biegen den Port
3. **Kein Austausch moeglich:** Wenn der Micro-B Port am ESP32 bricht, muss das gesamte Board ersetzt werden (~8 EUR + Neuverkabelung + Firmware-Flash)
4. **Gehaeuse oeffnen:** Zum USB-Anstecken muss das Gehaeuse geoeffnet werden (4 Schrauben)

### Nutzungshaeufigkeit

USB wird benoetigt fuer:
- **Stromversorgung** — permanent, ESP32 laeuft ueber USB 5V (wahrscheinlich immer eingesteckt)
- **Firmware-Update** — selten, nur bei Software-Aenderungen (via rshell/esptool)
- **Serial-Debugging** — nur Entwicklung

Da der ESP32 permanent Strom ueber USB braucht, ist das Kabel **dauerhaft angeschlossen**. Pfleger muessen es nur bei Standortwechsel oder Reinigung ab-/anstecken.

---

## 2. Loesungsvorschlag: USB-C Panel Mount mit internem Adapterkabel

### Konzept

```
AUSSEN                  WAND (3mm)              INNEN
                        +------+
USB-C Kabel  ------>   | Panel |  ---[USB-C-to-Micro-B Kabel 10cm]---> ESP32
(Pfleger)              | Mount |                                       Micro-B
                        +------+
                        Mutter
```

Drei Komponenten:
1. **USB-C Panel-Mount-Buchse** (Bulkhead-Adapter, Gewindezylinder) — in der Gehaeusewand montiert
2. **Kurzes USB-C-auf-Micro-B Kabel** (10cm) — verbindet Panel-Mount innen mit ESP32
3. **Gehaeuse-Ausschnitt** — runde Bohrung statt bisherigem Rechteck-Ausschnitt

### Vorteile

| Aspekt | Bisher (Micro-B direkt) | Neu (USB-C Panel Mount) |
|--------|------------------------|------------------------|
| Einstecken | Muss Orientierung treffen | Beidseitig einsteckbar |
| Robustheit | Fragiler Micro-B Port | Massiver Panel-Mount in Wand |
| Bei Bruch | ESP32 ersetzen (~8 EUR + Arbeit) | Panel-Mount tauschen (~4 EUR, schrauben) |
| Gehaeuse oeffnen | Ja, fuer jeden USB-Zugang | Nein, USB von aussen erreichbar |
| Kabelzug | Direkt auf ESP32-Port | Wand faengt Kraft ab, Kabel innen lose |
| Zukunft (ESP32-S3) | Anderer Port (USB-C) | Nur internes Kabel tauschen (C-auf-C) |

---

## 3. Komponentenauswahl

### 3.1 Panel-Mount USB-C Buchse (Bulkhead)

**Empfehlung: Gewindezylinder-Typ (Female-to-Female Pass-Through)**

```
Aussen           Innen
+------+    +-----------+    +------+
| USB-C|----| Gewinde   |----|USB-C |
|female|    | M8/custom |    |female|
+------+    +-----------+    +------+
                    ^
                  Mutter (Innensechskant oder raendel)
```

Spezifikation:
- **Typ:** USB-C Female-to-Female Bulkhead Pass-Through
- **Gewinde:** M8-aehnlich oder proprietaer (~8mm Aussendurchmesser)
- **Bohrung im Gehaeuse:** 8.5mm Durchmesser (mit 0.2mm Toleranz)
- **Befestigung:** Sechskant-Mutter von innen (11-12mm Schluesselweite)
- **Durchgangslaenge:** 15-20mm (mehr als genug fuer 3mm Wandstaerke)
- **Uebertragung:** USB 2.0 (reicht fuer Daten + 5V/2A Strom)
- **Preis:** ~3-5 EUR (Amazon/eBay, Suchbegriff: "USB-C Einbaubuchse Panel Mount Bulkhead")

**Warum Gewindezylinder statt Flansch:**
- Nur eine runde Bohrung noetig (einfacher zu drucken als Rechteck + Schraubenloecher)
- Selbstzentrierend
- Mutter-Klemmung haelt ohne Kleber
- Austauschbar ohne Werkzeug (raendelmutter)

### 3.2 Internes Kabel: USB-C auf Micro-B

**Empfehlung: Kurzes USB-C-auf-Micro-B Datenkabel (10-15cm)**

Spezifikation:
- **Typ:** USB 2.0 USB-C Male auf Micro-B Male
- **Laenge:** 10cm (kuerzeste gaengige Laenge). 15cm geht auch.
- **Anforderung:** Daten + Strom (nicht nur Ladekabel!)
- **Preis:** ~2-3 EUR
- **Suchbegriff:** "USB C auf Micro B Kabel kurz 10cm"

**Kabelweg intern:** Panel-Mount (innen) → ~25mm bis ESP32 USB-Port. 10cm Kabel gibt genug Slack fuer Gehaeuseoefffnung und Wartung.

### 3.3 Stueckliste (zusaetzlich)

| Teil | Typ | Preis |
|------|-----|-------|
| USB-C Panel Mount | Female-to-Female Bulkhead, Gewinde | ~4 EUR |
| USB-C auf Micro-B Kabel | 10cm, Daten+Strom | ~3 EUR |
| **Gesamt** | | **~7 EUR** |

---

## 4. Positionierung am Gehaeuse

### Position: +Y Wand (obere Laengsseite)

```
+Y wall (TOP)
+------------------------------------------------------+
|    [Panel-Mount USB-C]                                |
|        X=45  Z=14                                     |
| [Sensor]  [Joystick]       [ESP32--->USB]             |mount(+X)
+------------------------------------------------------+
-Y wall (BOTTOM — Patienten-Seite)
```

**Koordinaten der Panel-Mount-Bohrung:**
- **Wand:** +Y (obere Laengsseite, weg vom Patienten)
- **X = 45mm** (gleiche Position wie bisheriger USB-Auslass, nahe ESP32 USB-Ende)
- **Z = 14mm** (von Basis-Unterkante, mittig in der Wandhoehe)
- **Bohrung:** 8.5mm Durchmesser, durch 3mm Wand

### Begruendung der Position

| Kriterium | Bewertung |
|-----------|-----------|
| Abstand zum Patienten | Maximal — +Y ist die patientenferne Seite |
| Kabelweg intern | Kurz — ESP32 USB-Ende (X≈54) ist ~25mm entfernt |
| Konflikt mit Mount (+X) | Keiner — andere Wand |
| Konflikt mit Tube (-X) | Keiner — andere Wand |
| Konflikt mit Vents (-Y) | Keiner — andere Wand |
| Zugang fuer Pfleger | Gut — Kabel haengt nach hinten/oben, nicht ins Gesicht |
| Schraubboss-Konflikt | Keiner — naechster Boss bei (59, 16), Bohrung bei (45, 22) |

### Clearance-Analyse

- **Mutter innen:** ~12mm Durchmesser. Freiraum zur Kavitaetswand: OK (Kavitaet ist 44mm breit, Mutter sitzt an +Y Innenwand)
- **Mutter-Hoehe:** ~5mm. Ragt nicht in ESP32-Bereich (ESP32 Board-Oberkante bei Z≈7mm, Mutter-Unterkante bei Z≈9mm)
- **Externe Buchse:** Ragt ~2-3mm aus der Wand heraus. Kein Konflikt mit Deckel (Deckel hat Lip, aber an dieser Stelle sitzt keine Lip-Struktur nach aussen)

---

## 5. Befestigung und Montage

### Panel-Mount Einbau

1. Gewindezylinder von **aussen** durch die Bohrung stecken
2. Von **innen** Mutter aufschrauben und handfest anziehen
3. Optional: Gummi-O-Ring zwischen Buchse und Aussenwand fuer Vibrationsdaempfung

### Internes Kabel anschliessen

1. USB-C Male Ende in die innere Seite der Panel-Mount-Buchse stecken
2. Kabel durch Kabelclip(s) fuehren
3. Micro-B Ende in den ESP32 stecken
4. Kabel-Ueberschuss lose in der Kavitaet verstauen

### Wartung / Austausch

- **Panel-Mount defekt:** Mutter loesen, von aussen herausziehen, neue einsetzen. ESP32 bleibt unberuehrt.
- **Kabel defekt:** Gehaeuse oeffnen (4 Schrauben), Kabel tauschen. Panel-Mount bleibt montiert.
- **ESP32 defekt:** Gehaeuse oeffnen, Micro-B abstecken, Board tauschen. Panel-Mount + Kabel bleiben.

---

## 6. Kabelmanagement und Zugentlastung

### Problem

Ohne Kabelmanagement haengt das interne Kabel lose und uebertraegt externe Zugkraefte auf den ESP32 Micro-B Port — genau das was wir vermeiden wollen.

### Loesung: Kabelclips + Zugentlastung

```
+Y Wand (innen)
|                                                        |
|   [Clip 2]----Kabel----[Clip 1]                        |
|     bei Panel-Mount       bei ESP32                    |
|                                                        |
|         [ESP32===================>USB]                 |
|                              ^ Micro-B                 |
```

**Clip 1 — Zugentlastung am ESP32 (kritisch):**
- Position: Direkt neben dem ESP32 USB-Ende, auf dem Boden
- Typ: Offener Bogen (C-Clip), 5mm hoch, 4mm Oeffnung
- Funktion: Kabel wird eingedrueckt, Clip haelt es fest. Jeder Zug am externen Kabel wird vom Clip aufgefangen, nicht vom Micro-B Port
- Angeformt am Gehaeuse-Boden (Teil der CadQuery-Geometrie, kein separates Teil)

**Clip 2 — Kabelfuehrung an der +Y Wand:**
- Position: Neben der Panel-Mount-Mutter, auf der Innenseite der +Y Wand
- Typ: Kleiner Bogen oder Steg auf dem Boden
- Funktion: Verhindert dass sich das Kabel um andere Bauteile wickelt
- Weniger kritisch als Clip 1

### Kabel-Routing

```
Seitenansicht (Y-Z Schnitt bei X=45):

Z ^
  |     [Panel-Mount]=====[Mutter]
  |         Z=14           |
  |                       Kabel
  |                        |
  |         [Clip 2]------'
  |                \
  |                 '-------[Clip 1]--->[ESP32 Micro-B]
  |                           Z≈6
  +-------------------------------------> Y
     +Y Wand (aussen)            ESP32
```

---

## 7. Aenderungen an der CadQuery-Datei (v5.2 → v5.3)

### Entfernen

| Feature | Funktion | Begruendung |
|---------|----------|-------------|
| Rechteck-USB-Oeffnung (+Y Wand) | `_cut_usb_opening()` | Ersetzt durch runde Panel-Mount-Bohrung |
| USB-Kabel-Notch (+Y Wand, Basis) | Teil von `_cut_cable_notches()` | Kein Kabel mehr ueber Wandkante, geht durch Panel-Mount |
| USB-Lip-Notch (+Y Wand, Deckel) | Teil von `make_lid()` | Kein Kabel mehr ueber Wandkante |

### Aendern

| Feature | Alt | Neu |
|---------|-----|-----|
| `_cut_usb_opening()` | Rechteck 8×3.5mm, X=45, Z=5.5 | **Kreisbohrung 8.5mm**, X=45, Z=14 |
| `_cut_cable_notches()` | USB-Notch + Tube-Notch | **Nur Tube-Notch** (USB-Notch entfaellt) |
| `make_lid()` USB lip notch | USB-Kerbe in Lip | **Entfaellt** |

### Hinzufuegen

| Feature | Beschreibung |
|---------|-------------|
| Panel-Mount-Bohrung | Kreis 8.5mm auf +Y Wand, X=45, Z=14. Durchstich durch 3mm Wand |
| Mutter-Freiraum (optional) | Senkung innen, 12mm Durchmesser, 2mm tief — damit Mutter buendig sitzt |
| Kabelclip 1 (ESP32-seitig) | C-Bogen auf Boden, X≈52, Y≈5, H=5mm, Oeffnung 4mm |
| Kabelclip 2 (+Y-Wand-seitig) | C-Bogen auf Boden, X≈45, Y≈18, H=5mm, Oeffnung 4mm |

### Parameter (neu)

```python
# USB-C Panel Mount (Bulkhead, +Y wall)
USBC_MOUNT_HOLE_D = 8.5     # Bohrung fuer Gewindezylinder
USBC_MOUNT_X = 45.0          # X-Position auf +Y Wand (wie bisher)
USBC_MOUNT_Z = 14.0          # Z-Position (Mitte Wandhoehe)
USBC_NUT_D = 12.0            # Innensechskant-Mutter Durchmesser
USBC_NUT_RECESS = 2.0        # Senkung fuer Mutter (optional)

# Cable Clips
CLIP_H, CLIP_W, CLIP_OPENING = 5.0, 3.0, 4.0
CLIP1_X, CLIP1_Y = 52.0, 5.0   # Nahe ESP32 USB-Ende
CLIP2_X, CLIP2_Y = 45.0, 18.0  # Nahe Panel-Mount
```

### Parameter (entfallen)

```python
# Diese werden nicht mehr benoetigt:
# USB_W, USB_H, USB_CHAMFER, USB_POS_Z = 8.0, 3.5, 0.8, 5.5
# USB_EXIT_X = 45.0  # Wird ersetzt durch USBC_MOUNT_X
```

---

## 8. UX-Bewertung (fuer Pfleger)

### Verbesserungen

| Aspekt | Bisher | Neu | Bewertung |
|--------|--------|-----|-----------|
| Einstecken | Micro-B, einseitig, fummelig | USB-C, beidseitig, robust | Deutlich besser |
| Gehaeuse oeffnen | Fuer jeden USB-Zugang | Nie (USB von aussen) | Deutlich besser |
| Kraft auf ESP32 | Direkt am fragilen Port | Wand faengt Kraft ab | Kernproblem geloest |
| Reparatur bei Bruch | ESP32 tauschen, neu flashen | Panel-Mount aufschrauben | Viel einfacher |
| Kabel-Typ | USB Micro-B Kabel | Standard USB-C Kabel | Zukunftssicher, ueberall erhaeltlich |
| Kosten bei Bruch | ~8 EUR + 30 Min Arbeit | ~4 EUR + 2 Min Arbeit | Guenstiger |

### Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Panel-Mount loest sich | Gering (Mutter klemmt) | Schraubensicherung (Loctite) oder Raendelmutter |
| Internes Kabel loest sich | Gering (statisch, kein Bewegen) | Kabelclips halten Kabel, kein Zug auf Stecker |
| Wasser/Speichel dringt ein | Mittel (Panel-Mount ist offen) | O-Ring zwischen Buchse und Wand; Positionierung oben (+Y) statt unten |
| Kabel zu kurz/zu lang | Keine (10cm Standard) | 10cm ist ideal fuer ~30mm internen Weg |

---

## 9. ESP32-S3 Zukunftskompatibilitaet

Falls spaeter auf ESP32-S3 gewechselt wird (hat bereits USB-C):

- **Panel-Mount bleibt identisch** — keine Gehaeuse-Aenderung
- **Nur internes Kabel tauschen:** USB-C-auf-Micro-B → USB-C-auf-USB-C (10cm)
- **Kosten:** ~3 EUR fuer neues Kabel
- Die Panel-Mount-Loesung ist also Board-agnostisch

---

## 10. Zusammenfassung

### Empfehlung

USB-C Female-to-Female Bulkhead Pass-Through auf der +Y Wand, verbunden mit einem kurzen USB-C-auf-Micro-B Kabel zum ESP32. Zwei angeformte Kabelclips im Gehaeuse-Inneren fuer Zugentlastung.

### Naechste Schritte

1. **Panel-Mount beschaffen** — USB-C Bulkhead F/F, Gewindezylinder, Amazon/eBay bestellen
2. **Kabel beschaffen** — USB-C auf Micro-B, 10cm, Datenkabel (nicht nur Lade)
3. **Gehaeuse v5.3** — CadQuery-Datei anpassen (Aenderungen siehe Abschnitt 7)
4. **Prototyp drucken** — Bohrung pruefen, Panel-Mount einsetzen, Kabel testen
5. **Praxistest** — Pfleger USB-C ein-/ausstecken lassen, Belastungstest

### Kosten

| Position | Einmalig | Bei Bruch |
|----------|----------|-----------|
| Panel-Mount + Kabel | ~7 EUR | ~4 EUR (nur defektes Teil) |
| Neuer Gehaeuse-Druck | ~2 EUR Filament | — |
| **Gesamt** | **~9 EUR** | **~4 EUR** |

Verglichen mit ESP32-Ersatz bei Micro-B-Bruch (~8 EUR + 30 Min) amortisiert sich die Loesung beim ersten verhinderten Defekt.
