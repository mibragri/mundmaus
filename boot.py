# boot.py - MundMaus ESP32/ESP32-S3
# Runs before main.py

import esp
esp.osdebug(None)

import gc
gc.collect()

import sys
_m = getattr(sys.implementation, '_machine', '?')
print(f"MundMaus v3.0 booting... ({_m})")

