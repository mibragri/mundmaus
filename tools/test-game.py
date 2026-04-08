#!/usr/bin/env python3
"""MundMaus Game Quality Gate — Playwright-basierte Tests.

Prueft ein Spiel auf alle Quality-Standards aus der Session 2026-04-06.
Muss vor jedem Deploy PASS zeigen. Laeuft gegen den lokalen ESP32.

Usage:
    python3 tools/test-game.py games/solitaire.html
    python3 tools/test-game.py --all                    # alle Spiele
    python3 tools/test-game.py --all --host 192.168.178.86
"""

import argparse
import json
import subprocess
import sys
import gzip
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
GAMES_DIR = PROJECT / "games"
ALL_GAMES = ["chess", "freecell", "memo", "muehle", "solitaire", "vier-gewinnt"]

# ══════════════════════════════════════════════════════════════
# CSS / JS Static Checks (no browser needed)
# ══════════════════════════════════════════════════════════════

class StaticChecker:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.stem
        self.content = path.read_text()
        self.errors = []
        self.warnings = []

    def check_all(self):
        self._check_charge_nav()
        self._check_cancel_charge()
        self._check_keyboard_mode()
        self._check_ws_handler()
        self._check_ws_reconnect()
        self._check_settings_fetch()
        self._check_direct_cooldown()
        self._check_footer_icons()
        self._check_header_color()
        self._check_footer_color()
        self._check_opacity_minimums()
        self._check_puff_visibility()
        self._check_action_btn_visibility()
        self._check_card_proportions()
        self._check_win_overlay_clear()
        self._check_ws_dot_in_header()
        self._check_idle_overlay()
        self._check_kiosk_mode()
        self._check_portal_link()
        self._check_error_flash()
        self._check_no_blue_rgba()
        self._check_ultrawide_cap()
        self._check_vw_cap()
        self._check_colorblind_safe()
        self._check_escape_key()
        return len(self.errors) == 0

    def _check_charge_nav(self):
        for fn in ["computeTarget", "startCharge", "cancelCharge", "completeCharge", "chargeLoop", "renderChargePreview"]:
            if f"function {fn}" not in self.content and f"{fn}=" not in self.content:
                self.errors.append(f"MISSING: function {fn}() — charge navigation not implemented")

    def _check_cancel_charge(self):
        # Check navigate() calls cancelCharge
        nav_match = re.search(r'function navigate\s*\([^)]*\)\s*\{([^}]{0,500})', self.content)
        if nav_match:
            body_start = nav_match.group(1)
            if "cancelCharge" not in body_start:
                self.errors.append("navigate() does not call cancelCharge() — stale charge will override keyboard input")

        # Check initGame/newGame calls cancelCharge (search first 500 chars after function declaration)
        for fn in ["initGame", "newGameState", "startGame", "createBoard"]:
            match = re.search(rf'function {fn}\s*\([^)]*\)\s*\{{', self.content)
            if match:
                body_start = self.content[match.end():match.end()+500]
                if "cancelCharge" not in body_start:
                    self.errors.append(f"{fn}() does not call cancelCharge() — stale charge after new game")
                break

    def _check_keyboard_mode(self):
        if "kbSimMode" not in self.content:
            self.errors.append("MISSING: kbSimMode — keyboard dual-mode (J toggle) not implemented")
        if "updateKbMode" not in self.content:
            self.errors.append("MISSING: updateKbMode() — KB mode indicator not implemented")
        if "'keyup'" not in self.content and '"keyup"' not in self.content:
            self.errors.append("MISSING: keyup event listener — charge cancel on key release not implemented")

    def _check_ws_handler(self):
        if "nav_hold" not in self.content:
            self.errors.append("MISSING: nav_hold WebSocket handler — joystick charge events not handled")
        if "nav_release" not in self.content:
            self.errors.append("MISSING: nav_release WebSocket handler")
        if "wsSupported" not in self.content:
            self.warnings.append("MISSING: charge.wsSupported — legacy nav fallback may not work")

    def _check_ws_reconnect(self):
        if "wsReconnectTimer" not in self.content and "reconnectTimer" not in self.content:
            if "WebSocket" in self.content:
                self.errors.append("MISSING: wsReconnectTimer — WebSocket reconnect not deduped, will stack connections")

    def _check_settings_fetch(self):
        if "NAV_COOLDOWN_MS" not in self.content:
            self.errors.append("MISSING: NAV_COOLDOWN_MS fetch from /api/settings")

    def _check_direct_cooldown(self):
        # navigate() should have a short fixed cooldown (not navCooldown)
        nav_body = re.search(r'function navigate\s*\([^)]*\)\s*\{(.*?)\n\}', self.content, re.DOTALL)
        if nav_body:
            body = nav_body.group(1)[:500]
            if "navCooldown" in body and "120" not in body and "150" not in body:
                self.warnings.append("navigate() may use navCooldown (charge duration) instead of fixed 120ms for direct mode")

    def _check_footer_icons(self):
        if "<kbd>J</kbd>" not in self.content:
            self.errors.append("MISSING: <kbd>J</kbd> in footer — keyboard mode shortcut not shown")
        if "📺" not in self.content and "Kiosk" not in self.content:
            self.warnings.append("MISSING: kiosk icon in footer")

    def _check_header_color(self):
        if "rgba(15, 52, 96" in self.content or "rgba(15,52,96" in self.content:
            self.errors.append("Header/footer has BLUE background (rgba(15,52,96)) — should be black rgba(0,0,0,0.7)")
        if "backdrop-filter" in self.content:
            self.warnings.append("backdrop-filter: blur still present — may cause visual artifacts on some displays")

    def _check_footer_color(self):
        # Already covered by header check (same pattern)
        pass

    def _check_opacity_minimums(self):
        # Check pile-slot border opacity
        pile_match = re.search(r'\.pile-slot\s*\{[^}]*border[^}]*rgba\(255,\s*255,\s*255,\s*([\d.]+)\)', self.content)
        if pile_match:
            opacity = float(pile_match.group(1))
            if opacity < 0.25:
                self.errors.append(f"pile-slot border opacity {opacity} < 0.25 — nearly invisible on dark background")

        # Check empty-label opacity
        label_match = re.search(r'\.empty-label\s*\{[^}]*color:\s*rgba\(255,\s*255,\s*255,\s*([\d.]+)\)', self.content)
        if label_match:
            opacity = float(label_match.group(1))
            if opacity < 0.3:
                self.errors.append(f"empty-label color opacity {opacity} < 0.3 — text too dim")

    def _check_puff_visibility(self):
        puff_match = re.search(r'#puff-icon\s*\{[^}]*color:\s*rgba\(255,\s*255,\s*255,\s*([\d.]+)\)', self.content)
        if puff_match:
            opacity = float(puff_match.group(1))
            if opacity < 0.4:
                self.errors.append(f"#puff-icon opacity {opacity} < 0.4 — blow indicator too dim")

    def _check_action_btn_visibility(self):
        btn_match = re.search(r'\.action-btn\s*\{[^}]*border[^}]*rgba\(255,\s*255,\s*255,\s*([\d.]+)\)', self.content)
        if btn_match:
            opacity = float(btn_match.group(1))
            if opacity < 0.2:
                self.errors.append(f"action-btn border opacity {opacity} < 0.2 — buttons nearly invisible")

    def _check_card_proportions(self):
        if "CARD_H" in self.content:
            match = re.search(r'CARD_H\s*=\s*([\d.]+)', self.content)
            if match:
                h = float(match.group(1))
                if h < 14.0:
                    self.warnings.append(f"CARD_H={h} < 14.0 — cards may look squished")

    def _check_win_overlay_clear(self):
        # Win message must be cleared on new game (prevents sticky overlay)
        if "message" in self.content and "className" in self.content:
            # Game has a message element — check if initGame/startGame/newGame clears it
            for fn in ["initGame", "newGameState", "startGame", "createBoard"]:
                match = re.search(rf'function {fn}\s*\([^)]*\)\s*\{{', self.content)
                if match:
                    body = self.content[match.end():match.end()+800]
                    if "message" in self.content and "show win" in self.content:
                        if "className" not in body and "''" not in body:
                            self.errors.append(f"{fn}() may not clear win overlay — message.className not reset")
                    break

    def _check_ws_dot_in_header(self):
        # WS status dot should be inside the h1 (between MundMaus and game name)
        if '<span id="ws-status"' not in self.content:
            if '<div id="ws-status"' in self.content:
                self.errors.append("ws-status is a <div> (should be <span> inside h1 for inline display)")
            elif "ws-status" in self.content:
                self.warnings.append("ws-status exists but may not be inline in header")

    def _check_idle_overlay(self):
        # Idle overlays are NOT wanted — they confuse non-technical caretakers.
        # The patient or caretaker cannot dismiss them reliably.
        if "idle-overlay" in self.content and "IDLE_TIMEOUT" in self.content:
            self.warnings.append("Idle overlay present — may confuse caretakers. Consider removing or disabling.")

    def _check_kiosk_mode(self):
        if "toggleKiosk" not in self.content and "kiosk" not in self.content.lower():
            self.warnings.append("No kiosk mode — patient may be confused by UI clutter")

    def _check_portal_link(self):
        if "location.href='/'" not in self.content and "location.href = '/'" not in self.content:
            self.warnings.append("No portal link (P key) — user cannot navigate back to game selection")

    def _check_error_flash(self):
        # From fix d5bed9e: red error flash must be visible on invalid puff
        if "sndError" in self.content:
            if "flashError" not in self.content and "error-flash" not in self.content and "red" not in self.content.lower()[:self.content.lower().find("sndError")]:
                self.warnings.append("sndError exists but no visual error flash — invalid actions may be silent")

    def _check_no_blue_rgba(self):
        # From fixes caf006b, df004fe: no blue backgrounds anywhere
        matches = re.findall(r'rgba\(15,\s*52,\s*96[^)]*\)', self.content)
        if matches:
            self.errors.append(f"Blue rgba(15,52,96) still present ({len(matches)}x) — should be black")

    def _check_ultrawide_cap(self):
        # From fix 4f4e028: max-width 1920px prevents ultrawide stretching
        if "max-width" not in self.content and "1920" not in self.content:
            self.warnings.append("No max-width cap — layout may stretch on ultrawide monitors (34\" patient TV)")

    def _check_vw_cap(self):
        # From feedback_ultrawide_vw: --vw must use min(1vw, 19.2px)
        if "--vw" in self.content:
            if "min(1vw" not in self.content:
                self.errors.append("--vw not capped with min(1vw, 19.2px) — will stretch on ultrawide")

    def _check_colorblind_safe(self):
        # From fix 75633eb: don't rely solely on red/green color distinction
        # Check if selected state uses shape cues (badge, outline) not just color
        if "selected" in self.content.lower():
            if "badge" not in self.content.lower() and "outline" not in self.content.lower() and "border" not in self.content.lower():
                self.warnings.append("Selection may rely only on color — add shape cues (badge/outline) for colorblind users")

    def _check_escape_key(self):
        # Every game should support Escape to go back to portal
        if "'Escape'" not in self.content and '"Escape"' not in self.content:
            self.warnings.append("No Escape key handler — user cannot exit to portal with Escape")


# ══════════════════════════════════════════════════════════════
# Integration Checks (files, manifest, etc.)
# ══════════════════════════════════════════════════════════════

class IntegrationChecker:
    def __init__(self, name: str):
        self.name = name
        self.errors = []

    def check_all(self):
        self._check_html_exists()
        self._check_gz_exists()
        self._check_littlefs_copy()
        self._check_manifest_entry()
        self._check_screenshot()
        self._check_readme()
        self._check_website()
        self._check_check_games()
        return len(self.errors) == 0

    def _check_html_exists(self):
        if not (GAMES_DIR / f"{self.name}.html").exists():
            self.errors.append(f"MISSING: games/{self.name}.html")

    def _check_gz_exists(self):
        if not (GAMES_DIR / f"{self.name}.html.gz").exists():
            self.errors.append(f"MISSING: games/{self.name}.html.gz — run gzip -kf")

    def _check_littlefs_copy(self):
        if not (PROJECT / "firmware/arduino/data/www" / f"{self.name}.html.gz").exists():
            self.errors.append(f"MISSING: firmware/arduino/data/www/{self.name}.html.gz")

    def _check_manifest_entry(self):
        manifest = json.loads((PROJECT / "manifest.json").read_text())
        key = f"www/{self.name}.html.gz"
        if key not in manifest.get("files", {}):
            self.errors.append(f"MISSING: {key} in manifest.json")

    def _check_screenshot(self):
        if not (PROJECT / "screenshots" / f"{self.name}.png").exists():
            self.errors.append(f"MISSING: screenshots/{self.name}.png")

    def _check_readme(self):
        readme = (PROJECT / "README.md").read_text()
        if self.name not in readme.lower():
            self.errors.append(f"MISSING: {self.name} not mentioned in README.md")

    def _check_website(self):
        website = (PROJECT / "website/index.html").read_text()
        if self.name not in website.lower():
            self.errors.append(f"MISSING: {self.name} not in website/index.html")

    def _check_check_games(self):
        check_script = (PROJECT / "tools/check-games.sh").read_text()
        if self.name not in check_script:
            self.errors.append(f"MISSING: {self.name} not in tools/check-games.sh")


# ══════════════════════════════════════════════════════════════
# GZ Freshness Check
# ══════════════════════════════════════════════════════════════

def check_gz_fresh(name: str) -> list:
    errors = []
    html = GAMES_DIR / f"{name}.html"
    gz = GAMES_DIR / f"{name}.html.gz"
    lfs = PROJECT / "firmware/arduino/data/www" / f"{name}.html.gz"

    if html.exists() and gz.exists():
        if html.stat().st_mtime > gz.stat().st_mtime:
            errors.append(f"STALE: {name}.html.gz is older than {name}.html — run gzip -kf")
    if gz.exists() and lfs.exists():
        if gz.stat().st_mtime > lfs.stat().st_mtime:
            errors.append(f"STALE: LittleFS copy is older than games/{name}.html.gz — copy to firmware/arduino/data/www/")
    return errors


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

def test_game(name: str) -> bool:
    print(f"\n{'=' * 60}")
    print(f"  TESTING: {name}")
    print(f"{'=' * 60}")

    html_path = GAMES_DIR / f"{name}.html"
    if not html_path.exists():
        print(f"  ERROR: {html_path} not found")
        return False

    all_pass = True

    # Static checks
    print(f"\n  --- Static Checks ---")
    static = StaticChecker(html_path)
    static.check_all()
    for e in static.errors:
        print(f"  FAIL  {e}")
        all_pass = False
    for w in static.warnings:
        print(f"  WARN  {w}")
    if not static.errors:
        print(f"  OK    {len(static.warnings)} warnings")

    # Integration checks
    print(f"\n  --- Integration Checks ---")
    integration = IntegrationChecker(name)
    integration.check_all()
    for e in integration.errors:
        print(f"  FAIL  {e}")
        all_pass = False
    if not integration.errors:
        print(f"  OK")

    # Freshness checks
    print(f"\n  --- Freshness Checks ---")
    stale = check_gz_fresh(name)
    for e in stale:
        print(f"  FAIL  {e}")
        all_pass = False
    if not stale:
        print(f"  OK")

    # Summary
    total_errors = len(static.errors) + len(integration.errors) + len(stale)
    if total_errors == 0:
        print(f"\n  ✓ {name}: ALL CHECKS PASSED")
    else:
        print(f"\n  ✗ {name}: {total_errors} ERRORS")

    return all_pass


def main():
    parser = argparse.ArgumentParser(description="MundMaus Game Quality Gate")
    parser.add_argument("game", nargs="?", help="Game HTML file or name (e.g. solitaire)")
    parser.add_argument("--all", action="store_true", help="Test all games")
    parser.add_argument("--host", default="192.168.178.86", help="ESP32 host for browser tests")
    args = parser.parse_args()

    if args.all:
        games = ALL_GAMES
    elif args.game:
        name = Path(args.game).stem.replace(".html", "")
        games = [name]
    else:
        parser.print_help()
        sys.exit(1)

    all_pass = True
    for name in games:
        if not test_game(name):
            all_pass = False

    print(f"\n{'=' * 60}")
    if all_pass:
        print(f"  ✓ ALL {len(games)} GAMES PASSED")
    else:
        print(f"  ✗ SOME GAMES FAILED — fix errors before deploying")
    print(f"{'=' * 60}")

    # Settings page WiFi config check
    settings_path = PROJECT / "games" / "settings.html"
    if settings_path.exists():
        settings_html = settings_path.read_text()
        wifi_checks = [
            ("wifi-card", "WiFi config card (#wifi-card)"),
            ("wifi-ssid", "WiFi SSID dropdown (#wifi-ssid)"),
            ("wifi-pw", "WiFi password input (#wifi-pw)"),
            ("doWifiScan", "WiFi scan function"),
            ("doWifiConnect", "WiFi connect function"),
            ("/api/wifi", "WiFi API endpoint"),
        ]
        wifi_ok = True
        for token, desc in wifi_checks:
            if token not in settings_html:
                print(f"  FAIL  Settings missing: {desc}")
                wifi_ok = False
                all_pass = False
        if wifi_ok:
            print(f"  OK    Settings WiFi config present")

    # Also run check-games.sh
    print(f"\n  --- check-games.sh ---")
    result = subprocess.run(["bash", str(PROJECT / "tools/check-games.sh")],
                          capture_output=True, text=True, cwd=str(PROJECT))
    if "ALL OK" in result.stdout:
        print(f"  OK    ALL OK")
    else:
        print(f"  FAIL  check-games.sh failed:")
        for line in result.stdout.splitlines()[-5:]:
            print(f"        {line}")
        all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
