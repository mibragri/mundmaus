## MundMaus v5 — Landscape Layout Design Report
**Agent:** 3d | **Datum:** 2026-03-04 | **Projekt:** MundMaus Assistive Device

### Zusammenfassung
Komplettes Quer-Layout (Landscape) zur Reduktion der vertikalen Ausdehnung im Sichtfeld
des liegenden Patienten. Komponenten nebeneinander entlang X-Achse statt uebereinander.
Externe Y-Dimension von **71mm auf 50mm reduziert** (30% weniger Sichtfeld-Blockade).

### Problem (v4.2)
Das v4.2-Gehaeuse war "hochkant" orientiert: 96 x **71** x 41 mm.
Die 71mm Y-Dimension (Oberkante Mount bis Unterkante) blockierte zu viel Sichtfeld
des liegenden Patienten.

### Loesung (v5)
Landscape-Layout: **136 x 50 x 41 mm** (X x Y x Z).
- Komponenten horizontal verteilt (entlang X-Achse)
- Mount oben (+Y Wand = Schwanenhals-Befestigung)
- Y-Dimension minimiert: **50mm statt 71mm = 21mm weniger**

### Dimensionsvergleich v4.2 vs v5

| Dimension | v4.2 | v5 | Aenderung |
|-----------|------|------|-----------|
| Extern X (Breite) | 96 mm | 136 mm | +40 mm (breiter) |
| Extern Y (Hoehe im Sichtfeld) | **71 mm** | **50 mm** | **-21 mm (-30%)** |
| Extern Z (Tiefe) | 41 mm | 41 mm | unveraendert |
| Kavitaet X | 90 mm | 130 mm | +40 mm |
| Kavitaet Y | 65 mm | 44 mm | -21 mm |
| Wandstaerke | 3.0 mm | 3.0 mm | unveraendert |

### Anforderungen — Status

| Anforderung | Status | Nachweis |
|-------------|--------|---------|
| Quer-Layout (Landscape) | OK | EXT_X=136 > EXT_Y=50 |
| Mount oben (+Y Wand) | OK | Collar auf +Y Wand, Schwanenhals haengt von oben |
| Minimale vertikale Ausdehnung | OK | 50mm (Y) statt 71mm, 30% Reduktion |
| Komponenten nebeneinander | OK | Sensor(X=-48), Joy(X=-15), Mount(X=0), ESP(X=+35) |
| Interner Hex-Nut Collar (Option C) | OK | Identisch zu v4.2: flache Wand + interner Kragen |
| Snap-Fit Lid | OK | Lip 4mm tief, 1.8mm dick, 0.15mm Spiel |
| Joystick-Oeffnung im Deckel | OK | 17x17mm Oeffnung bei X=-15, Y=-4 |
| USB-C Cutout | OK | +X Wand, ausgerichtet auf ESP32 bei Y=-2 |
| Schlauch-Oeffnung 6.5mm | OK | -X Wand, ausgerichtet auf Drucksensor |
| Belueftungsschlitze | OK | 6 Slots auf -Y Wand + 9 Slots auf Deckel |
| FDM ohne Support | OK | Alle Features supportfrei druckbar |
| CadQuery fehlerfrei | OK | Beide STLs exportiert ohne Fehler |

### Komponenten-Layout (Draufsicht)

```
+Y Wand (OBEN — Schwanenhals-Mount)
+------------------------------------------------------+
|                    [Collar]                           |
| [Sensor]  [Joystick]  o24mmo     [ESP32 -->USB-C]    |
| X=-48     X=-15       X=0        X=+35          +X   |
+------------------------------------------------------+
-Y Wand (UNTEN — Belueftung, Richtung Patient)

Alle Komponenten bei Y ~ -2 bis -4 (versetzt von Mount-Collar)
```

### Clearance-Analyse (Kollisionspruefung)

| Komponenten-Paar | Min. Abstand | Status |
|-----------------|--------------|--------|
| ESP32 ↔ Joystick (X) | 3.3 mm | OK (Platform-Kanten) |
| ESP32 ↔ Collar (Y) | 2.15 mm | OK (ESP32-Rail bei Y=+12, Collar bei Y=+14.1) |
| Joystick ↔ Collar (Y) | 2.6 mm | OK (Platform bei Y=+11.5, Collar bei Y=+14.1) |
| Sensor ↔ Collar (X) | 24 mm | OK (kein Ueberlapp) |
| ESP32 ↔ +X Wand | 2.8 mm | OK (USB-Cutout Zugang) |
| Sensor ↔ -X Wand | 5 mm | OK (Schlauch-Routing) |

### Mic-Mount Querschnitt (+Y Wand)

```
Aussen (FLACH):  ─────────────────────
                 │    10.5mm Loch     │   ← 3/8" Schraube von aussen
Wand (3mm):      ═════════════════════
                 │  2.1mm Shelf       │   ← Mutter kann nicht durch
Interner Kragen: │  Hex SW14.7        │   ← 7.9mm tief, 24mm Kragen
                 │  (offen zur Kav.)  │   ← Mutter von innen einlegen
                 ─────────────────────
```

Identisch zu v4.2 Option C. Keine Aenderung am Mount-Design.

### Montage-Anleitung

1. Deckel abnehmen (4x M3 Schrauben loesen)
2. 3/8"-16 UNC Hex-Mutter von INNEN in den Kragen-Pocket einlegen
3. Gehaeuse mit flacher +Y Wand auf den Gooseneck-Adapter setzen
4. 3/8" Schraube von AUSSEN durch das Wandloch in die Mutter schrauben
5. Deckel aufsetzen und mit 4x M3 Schrauben befestigen

### Joystick-Erreichbarkeit

| Merkmal | Wert |
|---------|------|
| Platform-Hoehe | 15.0 mm |
| PCB auf Platform | Z = 19.6 mm |
| Stick-Spitze | Z = 36.6 mm |
| Deckel-Oberflaeche | Z = 41.0 mm |
| Stick unter Deckel | 4.4 mm |
| Oeffnung | 17 x 17 mm |

Stick-Spitze 4.4mm unter Deckeloberflaeche — komfortabel mit Mund erreichbar.

### Ausgabedateien

| Datei | Groesse | Beschreibung |
|-------|---------|-------------|
| `mundmaus_v5_enclosure.py` | CadQuery Source | Parametrisch, kommentiert |
| `mundmaus_v5_base.stl` | 1179 kB | Base mit internem Kragen |
| `mundmaus_v5_lid.stl` | 1043 kB | Deckel (gespiegelt fuer Druck) |
| `mundmaus_v5_assembly_iso.png` | 1024x768 | ISO Ansicht Base+Lid |
| `mundmaus_v5_top_view.png` | 1024x768 | Draufsicht: Landscape-Form |
| `mundmaus_v5_side_view.png` | 1024x768 | Seitenansicht: schmales Profil |
| `mundmaus_v5_mount_detail.png` | 1024x768 | Schnitt: Collar + Hex-Pocket |

### Druckhinweise

- **Base:** Bodenseite nach unten, kein Support, 25% Gyroid, 4 Waende
- **Deckel:** Deckenseite nach unten (STL bereits gespiegelt), kein Support
- **Material:** PETG, Duese 240C, Bett 75C, Luefter 40%
- **Druckzeit:** ~4-5h Base, ~2-3h Lid (P1S, Standard-Speed)
- **Kragen drucken:** Interner Kragen wachst als Zylinder vom Boden auf.
  Bridging ueber 10.5mm Bolt-Hole — bei PETG unproblematisch.

### Testdruck-Empfehlungen

1. **Landscape-Proportionen:** 136x50mm Grundflaeche pruefen — passt auf P1S Druckbett (256x256)
2. **Hex-Tasche testen:** 3/8"-16 Mutter muss in Kragen-Pocket passen
3. **Bolt-Hole testen:** 3/8" Schraube durch 10.5mm Wandloch
4. **Balance testen:** Am Schwanenhals aufhaengen — sollte nicht stark kippen
   (Mount bei X=0 = Geometrie-Zentrum, Schwerpunkt leicht rechts wegen ESP32)
5. **Sichtfeld pruefen:** 50mm Y-Ausdehnung vs. 71mm (v4.2) — deutlich weniger Blockade
