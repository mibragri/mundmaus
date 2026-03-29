# config.py — MundMaus shared configuration
# Board detection + constants used by all modules

import sys

# ============================================================
# BOARD DETECTION
# ============================================================

_machine_id = getattr(sys.implementation, '_machine', '')

if 'ESP32S3' in _machine_id:
    BOARD = 'ESP32-S3'
    PIN_VRX       = 1
    PIN_VRY       = 2
    PIN_SW        = 42
    PIN_PUFF_DATA = 4
    PIN_PUFF_CLK  = 5
    PIN_DISP_A0   = 6
    PIN_DISP_RST  = 14
    PIN_DISP_CS   = 17
    PIN_DISP_SCK  = 18
    PIN_DISP_SDA  = 23
else:
    BOARD = 'ESP32-WROOM'
    PIN_VRX       = 33
    PIN_VRY       = 35
    PIN_SW        = 21
    PIN_PUFF_DATA = 32
    PIN_PUFF_CLK  = 25
    PIN_DISP_A0   = 2
    PIN_DISP_RST  = 14
    PIN_DISP_CS   = 17
    PIN_DISP_SCK  = 18
    PIN_DISP_SDA  = 23

# ============================================================
# CONFIGURATION
# ============================================================

VERSION = '3.1'

WS_PORT = 81
HTTP_PORT = 80

# AP Hotspot
AP_SSID = 'MundMaus'
AP_PASS = 'mundmaus1'
AP_IP = '192.168.4.1'

# Credentials file
WIFI_CONFIG_FILE = 'wifi.json'

# Joystick
DEADZONE = 150
NAV_THRESHOLD = 800
NAV_REPEAT_MS = 300
CALIBRATION_SAMPLES = 50

# Puff
PUFF_THRESHOLD = 0.25
PUFF_COOLDOWN_MS = 400
PUFF_SAMPLES = 5

# Display
USE_DISPLAY = False

# File serving
WWW_DIR = 'www'

# Timing
RECAL_IDLE_MS = 10000
PUFF_SEND_INTERVAL_MS = 100
SENSOR_POLL_MS = 20
GC_INTERVAL = 500

# OTA
OTA_BASE_URL = 'https://mundmaus.de/ota'
VERSIONS_FILE = 'versions.json'
UPDATE_STATE_FILE = 'update_state.json'
