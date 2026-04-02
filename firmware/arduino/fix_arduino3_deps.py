# fix_arduino3_deps.py -- PlatformIO pre-build script
# ESP32 Arduino v3.x internal libraries (WiFi, WebServer, FS, Network)
# don't declare cross-dependencies in their library.properties files.
# This script:
#   1. Adds internal library include paths globally (CPPPATH)
#   2. Force-builds internal libraries that PIO can't discover via LDF
#      (e.g. "Network" dir vs "Networking" lib name)

import os
Import("env")

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
