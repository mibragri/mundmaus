# fix_arduino3_deps.py -- PlatformIO pre-build script
# ESP32 Arduino v3.x internal libraries (WiFi, WebServer, FS, Network)
# don't declare cross-dependencies in their library.properties files.
# This script:
#   1. Adds internal library include paths globally (CPPPATH)
#   2. Force-builds internal libraries that PIO can't discover via LDF
#      (e.g. "Network" dir vs "Networking" lib name)

import os
import sys
Import("env")

# ── Guard: OTA_AUTH_B64 must be set ──────────────────────────────────
# PlatformIO resolves ${sysenv.*} BEFORE pre-scripts run, so we
# can't rely on setting os.environ. Instead we inject the -D flag
# directly into CPPDEFINES from the pre-script.
ota_auth = os.environ.get("OTA_AUTH_B64", "")
if not ota_auth:
    # Try loading from ota_auth.py in project root
    ota_file = os.path.join(env.subst("$PROJECT_DIR"), "..", "..", "ota_auth.py")
    if os.path.exists(ota_file):
        with open(ota_file) as f:
            for line in f:
                if line.startswith("OTA_AUTH"):
                    ota_auth = line.split("=", 1)[1].strip().strip("'\"")
                    print(f"  OTA_AUTH_B64 loaded from {ota_file}")
                    break
if not ota_auth:
    print("\n" + "=" * 60)
    print("  FATAL: OTA_AUTH_B64 not set!")
    print("  Firmware without OTA auth cannot download updates.")
    print("  Set OTA_AUTH_B64 env var or create ../../ota_auth.py")
    print("=" * 60 + "\n")
    sys.exit(1)
env.Append(CPPDEFINES=[('OTA_AUTH_B64', env.StringifyMacro(ota_auth))])

# ── Guard: lint check before build ───────────────────────────────────
# Run cppcheck + clang-tidy. Fail build on any defects.
import shutil
import subprocess
_lint_marker = os.path.join(env.subst("$BUILD_DIR"), ".lint_passed")
_src_dir = os.path.join(env.subst("$PROJECT_DIR"), "src")
_pio_bin = shutil.which("pio") or os.path.expanduser("~/.platformio/penv/bin/pio")

def _src_newer_than_marker():
    if not os.path.exists(_lint_marker):
        return True
    marker_mtime = os.path.getmtime(_lint_marker)
    for f in os.listdir(_src_dir):
        if f.endswith((".cpp", ".h")):
            if os.path.getmtime(os.path.join(_src_dir, f)) > marker_mtime:
                return True
    return False

if _src_newer_than_marker() and "PIOTEST" not in os.environ and "_MUNDMAUS_LINT" not in os.environ:
    print("  Running lint (cppcheck + clang-tidy)...")
    lint_env = os.environ.copy()
    lint_env["_MUNDMAUS_LINT"] = "1"
    result = subprocess.run(
        [_pio_bin, "check", "-e", env.subst("$PIOENV"), "--fail-on-defect=low"],
        cwd=env.subst("$PROJECT_DIR"),
        env=lint_env,
    )
    if result.returncode != 0:
        print("\n" + "=" * 60)
        print("  FATAL: Lint check failed! Fix defects before building.")
        print("=" * 60 + "\n")
        sys.exit(1)
    # Touch marker so we don't re-lint until source changes
    os.makedirs(os.path.dirname(_lint_marker), exist_ok=True)
    with open(_lint_marker, "w") as f:
        f.write("passed")
    print("  Lint passed ✓")

framework_dir = env.PioPlatform().get_package_dir("framework-arduinoespressif32")
libs_dir = os.path.join(framework_dir, "libraries")

# Internal framework libraries whose headers are needed by other libraries
internal_libs = [
    "Network",
    "WiFi",
    "FS",
    "WebServer",
    "Preferences",
    "LittleFS",
    "NetworkClientSecure",
    "DNSServer",
    "Ticker",
    "HTTPClient",
]

for lib in internal_libs:
    src_dir = os.path.join(libs_dir, lib, "src")
    if os.path.isdir(src_dir):
        env.Append(CPPPATH=[src_dir])

# NOTE: Network library used to be force-built here because PIO couldn't
# discover it (dir "Network" vs library.properties name "Networking").
# Since Phase 7 (OTA) added HTTPClient, PIO's deep+ LDF discovers Network
# automatically through HTTPClient's dependency chain. Force-building it
# here would cause duplicate symbols. The CPPPATH entry above still ensures
# Network.h is findable during compilation.
