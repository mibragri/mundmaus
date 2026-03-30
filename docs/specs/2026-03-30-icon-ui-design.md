# Universal Icon UI — Sprachunabhängiges Interface

**Datum:** 2026-03-30
**Status:** Design approved

---

## Ziel

Alle spielerrelevanten Texte durch universelle Icons ersetzen. Pfleger-Texte (WiFi, Updates, Recovery) zweisprachig Deutsch/Englisch. Das Projekt wird dadurch ohne Sprachkenntnisse nutzbar.

## Endnutzer-Kontext

- **Patient:** Tetraplegie, navigiert mit Joystick+Puff. Muss keine Texte lesen.
- **Pfleger:** Wechselnd, keine Schulung. Sieht WiFi-Setup, Updates, Recovery. Kurze deutsch/englische Labels reichen.

---

## Spiel-Buttons (rechte Spalte)

| Aktuell | Neu | Icon |
|---------|-----|------|
| ⬅ Portal | 🏠 | Haus — universell "Home/Zurück" |
| ↻ Neu | NEW | Badge in Gold-Rahmen, international bekannt |
| ↩ Zurück | ↩ | Bleibt — universell "Undo" |
| Hilfe | ? | Fragezeichen — universell |
| Kiosk | Kiosk | Bleibt — universelles Wort |

## Footer Keyboard-Hints

Format: `[Taste] Icon`

```
[⏎] ● [N] NEW [U] ↩ [K] Kiosk [P] 🏠
```

- Enter (⏎) als Primäraktion statt Space — universell erkennbar
- Space wird weiterhin akzeptiert, nur nicht im Footer gezeigt
- Navigationspfeile (←↑→↓) bleiben wie im Portal

## Schwierigkeits-Menü

Gehirn-Icons gestaffelt statt Text:

**Chess:**
- 🧠 (Anfänger — zufällige Züge)
- 🧠🧠 (Leicht — 2 Züge voraus)
- 🧠🧠🧠 (Mittel — 3 Züge voraus)
- 🧠🧠🧠🧠 (Schwer — 4 Züge voraus)

**Memo:**
- 🧠 (4×3 — 6 Paare)
- 🧠🧠 (4×4 — 8 Paare)
- 🧠🧠🧠 (6×4 — 12 Paare)
- 🧠🧠🧠🧠 (6×6 — 18 Paare)

Grid-Größe als kleine Zusatzinfo unter den Gehirnen (Zahlen sind universal).

## Schach Zuganzeige

Statt "Weiß am Zug" / "Computer denkt...":

- **Farbiger Punkt**: ⚪ = Weiß dran, ⚫ = Schwarz dran
- **Spinner**: Drehender Indikator wenn Computer rechnet
- **Navigation blockiert** während Computer denkt (kein versehentliches Ziehen)

## Pfleger-Texte (Deutsch/Englisch dual)

Kurze duale Labels für die wenigen Pfleger-relevanten Stellen:

**Portal WiFi-Panel:**
- "Netzwerke suchen / Scan" (oder nur 🔍 + "Scan")
- "Verbinden / Connect"
- "Neustart / Restart"
- "Passwort / Password"

**Update-Panel:**
- "Alles aktuell / Up to date" ✓
- "Offline" (gleich in beiden Sprachen)
- "Neustart / Restart"

**Recovery-AP:**
- "Update fehlgeschlagen / Update failed"
- "Hochladen / Upload"

## Texte die bleiben

- **SSID**: Technischer Term, universal
- **Kiosk**: Universelles Wort
- **MundMaus**: Produktname
- **Spielnamen**: Chess, Memo, Solitaer — international verständlich
- **Zahlen**: Züge, Punkte, Paare, Zeit — Ziffern sind universal
- **Tastenbuchstaben**: N, U, K, P — universal

## Memo Karten-Labels

Aktuell deutsche Namen (Stern, Diamant, Kreis...) — werden durch die Symbole selbst ersetzt. Die Labels sind für Screen-Reader/Accessibility, bleiben aber auf Englisch (Star, Diamond, Circle) da das universeller ist.

## Was NICHT geändert wird

- Serial-Console-Output (nur Entwickler sehen das)
- Dateinamen und API-Pfade
- Code-Kommentare
- Status-Chips (schon icon-basiert: grün/rot Punkt + Joystick/Puff)
