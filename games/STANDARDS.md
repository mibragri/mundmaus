# MundMaus Spiele — Design-Standards

## Zielgruppe
Tetraplegie-Patient, steuert mit Joystick (4 Richtungen) + Pusten (1 Aktion).
Kein Keyboard, keine Maus, kein Touch.

## Eingabe
- Joystick: Navigation (hoch/runter/links/rechts)
- Puff: Aktion (auswaehlen, aufdecken, platzieren)
- Keyboard als Fallback fuer Entwicklung/Test (Pfeiltasten + Space/Enter)

## Visuelles Theme
- **Hintergrund**: Dark Navy #1a1a2e
- **Header**: Frosted glass (rgba, backdrop-filter blur), oben, zeigt Spielname + Status
- **Footer**: Hint-Leiste unten mit Steuerungshilfe (optional, in Kiosk-Mode versteckt)
- **Schrift**: System sans-serif, hell auf dunkel

## Cursor / Highlight
- **Farbe**: Gold #FFD700
- **Stil**: Goldener Rahmen (2-3px solid) UND goldener Hintergrund (rgba(255, 215, 0, 0.25))
- **Glow**: Optional box-shadow mit Gold-Ton
- **Konsistenz**: Identischer Stil in ALLEN Spielen

## Selection (ausgewaehltes Element)
- **Farbe**: Magenta #e040fb
- **Stil**: Magenta Rahmen + Hintergrund-Overlay (rgba(224, 64, 251, 0.25))

## Buttons (Neu, Zurueck, Hilfe)
- **Position**: RECHTS neben dem Spielfeld, vertikal gestapelt
- **Navigation**: Joystick rechts vom Spielfeld-Rand wechselt zu den Buttons
- **Cursor**: Gold-Highlight wenn Cursor auf Button
- **Pflicht-Buttons**: "Neu" (neues Spiel) in JEDEM Spiel. "Zurueck" (Undo) wo sinnvoll.
- **Disabled-Stil**: opacity 0.3 wenn nicht verfuegbar

## Spielfiguren (Schach)
- **Alle Figuren**: Ausgefuellte (filled) Unicode-Zeichen, NICHT Outline
- **Weiss**: CSS color weiss + dicker dunkler Stroke (text-shadow)
- **Schwarz**: CSS color schwarz/sehr dunkel + subtiler Stroke
- **Brett**: Mittlere Helligkeits-Toene (kein reines Weiss, kein tiefes Schwarz)

## Farben / Barrierefreiheit
- **WCAG AA Minimum**: 4.5:1 Kontrast fuer Text, 3:1 fuer grosse Elemente
- **CVD-safe**: Nie nur auf Farbe verlassen — immer zusaetzlich Form, Text oder Position
- **Triple-Encoding** (Memory): Symbol + Farbe + Text-Label

## WebSocket
- Verbindung zu ws://{host}:81
- Fallback: ws://192.168.4.1:81 (ESP32 AP-Mode)
- Exponential Backoff: 3s -> 6s -> 12s -> 24s -> max 30s
- Status-Dot: gruen=verbunden, grau=getrennt (oben rechts)

## Kiosk-Mode (K)
- Taste K oder WS action "kiosk"
- Kombiniert Vollbild + vereinfachte Ansicht:
  1. Browser-Fullscreen (requestFullscreen API)
  2. Footer/Hints versteckt
  3. Idle-Screen nach 2min Inaktivitaet ("Pusten zum Starten")
- KEIN separater Vollbild-Modus (F) — alles ueber K

## Layout-Reihenfolge
1. Header (oben): Spielname links, Puff-Indicator mitte, Stats rechts, WS-Indikator rechts
2. Spielfeld (mitte): So gross wie moeglich
3. Buttons (rechts): Neben dem Spielfeld, nicht darunter
4. Footer (unten): Keyboard-Hints fuer Betreuer

## Ultrawide / Skalierung
- **body**: `max-width: 1920px; width: 100%` (nicht 100vw!)
- **Keine rohen vw-Einheiten**: Alle `vw`-Werte als `calc(X * var(--vw))` mit `--vw: min(1vw, 19.2px)` in `:root`
- **Grund**: Auf Ultrawide (3440px) wuerden vw-Werte den 1920px-Body sprengen
- **JS Inline-Styles**: Ebenfalls `calc(X * var(--vw))` verwenden, nicht `X + 'vw'`

## Footer-Hints (konsistent in ALLEN Spielen)
Format mit kbd-Tags fuer Tastatur-Shortcuts:
- `←↑→↓` Navigieren
- `Leertaste` [spielspezifische Aktion]
- `N` Neues Spiel
- `K` Kiosk
- Spielspezifisch: `U` Rueckgaengig (Chess), `F` Vollbild etc.
Hinweise dienen Betreuern (wechselnde Pfleger, keine Schulung).
Der Nutzer selbst braucht nur Joystick + Pusten.

## Puff-Indicator
- **Position**: Im Header, zwischen Titel und Stats
- **Aufbau**: Emoji (💨) + schmaler Balken (8vw breit, 0.6vh hoch)
- **Balken**: Gold-Farbe (--highlight/--cursor-color), Breite = puff_level (0-100%)
- **Pflicht**: JEDES Spiel muss den Puff-Indicator im Header haben
- **JS**: WebSocket `puff_level` Event setzt `puff-bar` Breite
- **NICHT** als fixed-Element unten positionieren (kollidiert mit Footer)

## Header-Stats
- Stat-Werte in Gold (#FFD700), Labels in heller Schrift
- Tabular-Nums fuer Zahlen (kein Springen)
- Konsistentes Format: "Label: Wert"

## WebSocket-Verbindungsindikator
- Position: oben rechts, fixed
- Gruener Punkt = verbunden, grauer Punkt = getrennt
- Identisch in ALLEN Spielen (gleiche CSS-Klasse, gleiche Position)

## Betreuer-Hinweise
Wechselnde Pfleger muessen die Spiele ohne Schulung bedienen koennen:
- Footer zeigt alle Tastatur-Shortcuts (Pfeiltasten, Leertaste, N, K)
- Buttons (Neu, Zurueck) sind gross und beschriftet
- Kiosk-Mode (K) vereinfacht die Ansicht fuer den Nutzer
- WiFi-Setup ueber 📶 Symbol im Header (Solitaire) erreichbar
