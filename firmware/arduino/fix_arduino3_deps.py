# fix_arduino3_deps.py -- PlatformIO pre-build script
# ESP32 Arduino v3.x internal libraries (WiFi, WebServer, FS, Network)
# don't declare cross-dependencies in their library.properties files.
# This script:
#   1. Adds internal library include paths globally (CPPPATH)
#   2. Force-builds the "Network" library that WiFi depends on but PIO
#      can't discover (dir name "Network" vs lib name "Networking")

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
]

for lib in internal_libs:
    src_dir = os.path.join(libs_dir, lib, "src")
    if os.path.isdir(src_dir):
        env.Append(CPPPATH=[src_dir])

# Force-build the Network library (PIO can't match "Network.h" to
# the library named "Networking" in library.properties)
network_src = os.path.join(libs_dir, "Network", "src")
if os.path.isdir(network_src):
    env.BuildSources(
        os.path.join("$BUILD_DIR", "framework_Network"),
        network_src,
    )
