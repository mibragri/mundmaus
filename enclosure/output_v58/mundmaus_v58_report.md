# MundMaus v5.8 Enclosure — Schraub-Verschluss (Spax 3.5x20)
## Summary
v5.8 ersetzt den Detent-Klick-Verschluss aus v5.7 durch eine echte Schraub-
verbindung mit 4 Spax 3.5x20 Senkkopf-Spanplattenschrauben in den Eck-
Innenbereichen. Detent-Ridges/Grooves vollständig entfernt.

Geometrie:
- 4 Schraubsäulen im Base bei (±58, ±18.0), D=6.0mm,
  Vorbohr-Loch 2.5mm.
- 4 hängende Säulen im Lid (gleiche XY-Position) mit Durchgangsloch 4.0mm
  und Senkung 7.5mm × 2.1mm tief an der Lid-Außenseite.
- ESP-Side-Guide-Rails von ESP_L*0.4 (21.8mm) auf 14.0mm gekürzt — Rails standen
  sonst im Weg der +X- und +Y-Eck-Säulen.
- Lip (3.0mm) bleibt zur Zentrierung beim Zusammenbau und für Staubdichtigkeit.

## Schrauben-Tiefenrechnung
| Strecke | Wert |
|---|---:|
| Schraubenlänge gesamt | 20.0 mm |
| Senkung im Lid (Kopf bündig) | 2.1 mm |
| Lid-Korpus durchquert (Decke + Lip-Hänger) | 12.0 mm |
| Eindringtiefe in Base-Säule | 8.0 mm |
| Summe | 22.1 mm |
| Säulenoberkante Z (base coords) | 26.8 mm |
| Spiel Säulen-Top zu Lid-Hänger-Boden | 0.2 mm |
| Boden-Reserve unter Bohrung | 16.8 mm |
| Säulen-Kollisions-Abstand zur Eckkurve | 1.61 mm |

## Komponenten-Layout (unverändert von v5.7)
- Mic mount collar: -X wall (internal, -58.1 inner edge)
- Joystick center: X=-19.0 (platform -37.5 to -0.5)
- ESP32 center: X=35.0 (PCB 7.8 to 62.2, USB at -X end)
- Sensor shelf: +X inner wall, shelf X=61.0 to 66.0, Z=5.5 to 25.5

## Clearance Analysis
| Item | Value |
|---|---:|
| Lip zone bottom | 27.0 mm |
| Sensor PCB top to lip zone | 1.5 mm |
| Mic collar to joystick platform | 20.60 mm |
| ESP32 right edge to +X inner wall | 3.80 mm |
| Sensor bottom Z to ESP32 PCB top Z | -0.7 mm |
| Hold-down wall gap (lid closed) | 1.0 mm |
| Barb hole diameter | 2.8 mm (press-fit) |
| Pressure barb wall | +X |
| Lid attachment | 4 Schrauben Spax 3.5x20 Senkkopf |

## Changes vs v5.7
| Feature | v5.7 | v5.8 |
|---|---|---|
| Verschluss | Detent-Klick (7 Ridges/Grooves) | 4× Schraube Spax 3.5x20 |
| RIDGE_H/GROOVE_D | 0.6 / 0.55 mm | entfallen |
| Base-Säulen | — | 4× D=6mm, h=24.8mm, Bohrung 2.5mm |
| Lid-Säulen-Hänger | — | 4× D=6mm, h=10.0mm, Senkung 7.5/2.1 |
| ESP-Side-Rails | 21.8 mm | 14.0 mm |
| Base STL | v5.6 unchanged | NEU (Säulen + kürzere Rails) |
| Lid STL | v5.7 | NEU (Hänger + Senkungen, ohne Detents) |

## External Dimensions
- Base footprint: 136.0 x 50.0 mm
- Closed enclosure height: 39.0 mm
- Joystick protrusion above lid: 2.6 mm

## Print Notes
- Material: PETG preferred, PLA acceptable for quick fit checks
- Base orientation: floor-down, no support intended
- Lid orientation: flip 180 deg, ceiling-down. Senkungen liegen damit an der Druckplatte;
  die 40°-Konuswand druckt support-frei (Material drumherum, nicht darüber).
- Schrauben: 4× Spax/Spanplattenschraube 3.5×20 mm Senkkopf, Torx oder Kreuzschlitz.
  In PETG selbstschneidend — kein Brass-Insert nötig.
- Anzugsmoment: handfest, nicht überdrehen (PETG-Säulenwand 1.75mm).
- USB cable: plug Micro-USB with lid off, route cable to -Y wall notch, close lid.
- External hose path: mouthpiece -> +X wall barb (straight run, minimal bending).
- Pressure sensor: place PCB flat against +X inner wall, nipple through barb hole, lid retains from above.
- The -X collar remains internal-only; the outer -X wall stays flat for the mic stand.
- Suggested slicer baseline: 0.2 mm layer height, 4 walls, 25% gyroid, 240 C nozzle, 75 C bed, 40% fan.
