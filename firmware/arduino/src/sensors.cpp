// sensors.cpp -- CalibratedJoystick + PuffSensor (HX710B 24-bit)
// Direct port of MicroPython sensors.py to Arduino/ESP32.

#include "sensors.h"
#include "config.h"

// ============================================================
// CalibratedJoystick
// ============================================================

CalibratedJoystick::CalibratedJoystick(int pinX, int pinY, int pinSW)
    : centerX(2048)
    , centerY(2048)
    , _pinX(pinX)
    , _pinY(pinY)
    , _pinSW(pinSW)
    , _lastDir(nullptr)
    , _lastNavTime(0)
    , _navRepeating(false)
    , _dirLostTime(0)
    , _swLast(1)
    , _swDebounceTime(0)
{
    pinMode(_pinSW, INPUT_PULLUP);
    // Arduino-ESP32 3.x only accepts per-pin attenuation changes after the
    // pin has been attached to the ADC bus. A first analogRead performs that
    // registration and avoids noisy boot-time "not configured as analog channel"
    // errors on otherwise valid ADC pins.
    analogRead(_pinX);
    analogRead(_pinY);
    analogSetPinAttenuation(_pinX, ADC_11db);
    analogSetPinAttenuation(_pinY, ADC_11db);
    calibrate();
}

void CalibratedJoystick::calibrate(int samples) {
    if (samples <= 0) {
        samples = Config::DEFAULT_CALIBRATION_SAMPLES;
    }
    Serial.println("  Joystick Kalibrierung...");

    // 10 warmup reads (5ms each)
    for (int i = 0; i < 10; i++) {
        analogRead(_pinX);
        analogRead(_pinY);
        delay(5);
    }

    // Average N samples (10ms each)
    long sx = 0, sy = 0;
    for (int i = 0; i < samples; i++) {
        sx += analogRead(_pinX);
        sy += analogRead(_pinY);
        delay(10);
    }
    centerX = (int)(sx / samples);
    centerY = (int)(sy / samples);

    Serial.printf("  Center=(%d,%d) dz=+/-%d\n", centerX, centerY, Config::DEADZONE);
}

void CalibratedJoystick::_readCentered(int& dx, int& dy) {
    dx = analogRead(_pinX) - centerX;
    dy = analogRead(_pinY) - centerY;
    if (abs(dx) < Config::DEADZONE) dx = 0;
    if (abs(dy) < Config::DEADZONE) dy = 0;
}

// Axis hysteresis: once an axis becomes dominant, it must stay dominant
// by at least HYSTERESIS_FACTOR (1.4x) to give up dominance. This prevents
// rapid X/Y flipping on diagonal joystick holds due to ADC noise.
static constexpr float HYSTERESIS_FACTOR = 1.4f;

const char* CalibratedJoystick::_getDirection() {
    int dx, dy;
    _readCentered(dx, dy);

    // Apply hysteresis to dominant axis selection
    bool xDominant;
    if (_lastAxis == 'x') {
        xDominant = abs(dx) * HYSTERESIS_FACTOR >= abs(dy);
    } else if (_lastAxis == 'y') {
        xDominant = abs(dx) >= abs(dy) * HYSTERESIS_FACTOR;
    } else {
        xDominant = abs(dx) > abs(dy);
    }

    if (xDominant) {
        if (dx < -Config::NAV_THRESHOLD) { _lastAxis = 'x'; return "left"; }
        if (dx >  Config::NAV_THRESHOLD) { _lastAxis = 'x'; return "right"; }
    } else {
        if (dy < -Config::NAV_THRESHOLD) { _lastAxis = 'y'; return "up"; }
        if (dy >  Config::NAV_THRESHOLD) { _lastAxis = 'y'; return "down"; }
    }
    if (abs(dx) == 0 && abs(dy) == 0) _lastAxis = 0;
    return nullptr;
}

const char* CalibratedJoystick::getState(float& outIntensity) {
    int dx, dy;
    _readCentered(dx, dy);

    // Apply same hysteresis as _getDirection
    bool xDominant;
    if (_lastAxis == 'x') {
        xDominant = abs(dx) * HYSTERESIS_FACTOR >= abs(dy);
    } else if (_lastAxis == 'y') {
        xDominant = abs(dx) >= abs(dy) * HYSTERESIS_FACTOR;
    } else {
        xDominant = abs(dx) > abs(dy);
    }

    const char* dir = nullptr;
    int dominant = 0;

    if (xDominant) {
        if (dx < -Config::NAV_THRESHOLD) { dir = "left";  dominant = dx; _lastAxis = 'x'; }
        else if (dx > Config::NAV_THRESHOLD) { dir = "right"; dominant = dx; _lastAxis = 'x'; }
    } else {
        if (dy < -Config::NAV_THRESHOLD) { dir = "up";    dominant = dy; _lastAxis = 'y'; }
        else if (dy > Config::NAV_THRESHOLD) { dir = "down";  dominant = dy; _lastAxis = 'y'; }
    }

    if (dir) {
        int maxTravel = 0;
        if (xDominant) {
            maxTravel = (dominant > 0) ? (4095 - centerX) : centerX;
        } else {
            maxTravel = (dominant > 0) ? (4095 - centerY) : centerY;
        }
        int usableRange = maxTravel - Config::NAV_THRESHOLD;
        if (usableRange < 1) {
            usableRange = 1;
        }
        float intensity = float(abs(dominant) - Config::NAV_THRESHOLD) / float(usableRange);
        intensity = constrain(intensity, 0.0f, 1.0f);
        _lastIntensity = intensity;
        outIntensity = intensity;
        return dir;
    }

    if (abs(dx) == 0 && abs(dy) == 0) _lastAxis = 0;
    _lastIntensity = 0;
    outIntensity = 0;
    return nullptr;
}

const char* CalibratedJoystick::pollNavigation() {
    unsigned long now = millis();
    const char* d = _getDirection();

    if (d == nullptr) {
        // Hold direction for 100ms to absorb joystick jitter at 50Hz
        if (_lastDir && _dirLostTime == 0) {
            _dirLostTime = now;
        } else if (_lastDir && (now - _dirLostTime) > 100) {
            _lastDir = nullptr;
            _navRepeating = false;
        }
        return nullptr;
    }

    _dirLostTime = 0;

    if (d != _lastDir) {
        // New direction -- fire immediately, start initial delay
        _lastDir = d;
        _lastNavTime = now;
        _navRepeating = false;
        return d;
    }

    // Same direction held -- initial delay then repeat
    unsigned long repeatDelay = _navRepeating
        ? (unsigned long)Config::NAV_REPEAT_MS
        : (unsigned long)(Config::NAV_REPEAT_MS * 3 / 2);  // 1.5x for initial

    if ((now - _lastNavTime) > repeatDelay) {
        _lastNavTime = now;
        _navRepeating = true;
        return d;
    }

    return nullptr;
}

bool CalibratedJoystick::pollButton() {
    unsigned long now = millis();
    int val = digitalRead(_pinSW);

    if (val == 0 && _swLast == 1) {
        if ((now - _swDebounceTime) > 200) {
            _swDebounceTime = now;
            _swLast = val;
            return true;
        }
    }
    _swLast = val;
    return false;
}

bool CalibratedJoystick::isIdle() {
    // Use raw (pre-deadzone) values so we can check strictly within deadzone.
    // Previously used DEADZONE*2 which created a gap between "idle" and "active"
    // where held joystick could trigger auto-recalibration while being used.
    int rawDx = analogRead(_pinX) - centerX;
    int rawDy = analogRead(_pinY) - centerY;
    return abs(rawDx) < Config::DEADZONE && abs(rawDy) < Config::DEADZONE;
}

// ============================================================
// PuffSensor (HX710B 24-bit ADC)
// ============================================================

PuffSensor::PuffSensor(int dataPin, int clkPin)
    : baseline(0)
    , _dataPin(dataPin)
    , _clkPin(clkPin)
    , _maxRange(1)
    , _lastPuffTime(0)
    , _previousRaw(0)
    , _rawThreshold(Config::PUFF_RAW_THRESHOLD)
    , _lastRaw(0)
{
    pinMode(_dataPin, INPUT_PULLDOWN);
    pinMode(_clkPin, OUTPUT);
    digitalWrite(_clkPin, LOW);

    delay(100);
    calibrateBaseline();
}

int32_t PuffSensor::_readRawNonblocking() {
    // If DATA is HIGH, sensor not ready -- don't wait
    if (digitalRead(_dataPin) == HIGH) {
        return 0;
    }

    // Disable interrupts during bit-bang (WiFi/AsyncTCP can corrupt timing)
    portDISABLE_INTERRUPTS();

    int32_t value = 0;
    for (int i = 0; i < 24; i++) {
        digitalWrite(_clkPin, HIGH);
        digitalWrite(_clkPin, LOW);
        value = (value << 1) | digitalRead(_dataPin);
    }

    // 25th clock pulse: select next conversion (gain 128)
    digitalWrite(_clkPin, HIGH);
    digitalWrite(_clkPin, LOW);

    portENABLE_INTERRUPTS();

    // Sign extension: 24-bit two's complement
    if (value > 0x7FFFFF) {
        value -= 0x1000000;
    }

    return value;
}

int32_t PuffSensor::_readRawBlocking() {
    // Wait up to ~10ms for DATA to go LOW (sensor ready)
    int timeout = 0;
    while (digitalRead(_dataPin) == HIGH) {
        timeout++;
        if (timeout > 10000) return 0;
        delayMicroseconds(1);
    }
    return _readRawNonblocking();
}

void PuffSensor::calibrateBaseline(int samples) {
    Serial.println("  Drucksensor Kalibrierung...");

    int64_t sum = 0;
    int count = 0;
    for (int i = 0; i < samples; i++) {
        int32_t r = _readRawBlocking();
        if (r != 0) {
            sum += r;
            count++;
        }
        delay(20);
    }

    if (count > 0) {
        baseline = (int32_t)(sum / count);
        _maxRange = abs(baseline) / 2;
        if (_maxRange == 0) _maxRange = 100000;
        _previousRaw = baseline;
    }

    Serial.printf("  Baseline=%d range=%d\n", (int)baseline, (int)_maxRange);
}

void PuffSensor::poll() {
    // Non-blocking read. Skip if sensor not ready (DATA high).
    int32_t raw = _readRawNonblocking();
    if (raw != 0) {
        _lastRaw = raw;
    }
}

float PuffSensor::getLevel() {
    int32_t raw = _lastRaw;
    if (raw == 0) return 0.0f;

    int32_t delta = abs(raw - baseline);
    float level = (float)delta / (float)_maxRange;
    return (level > 1.0f) ? 1.0f : level;
}

bool PuffSensor::detectPuff() {
    // Port of original mouthMouse hx711.py air_flow() logic:
    // - Any large delta (puff or rebound) resets the cooldown timer
    // - Only fires if cooldown has fully elapsed (sensor stable)
    // - This prevents rebounds from triggering false events.
    unsigned long now = millis();
    int32_t raw = _lastRaw;

    if (raw == 0) {
        return false;
    }

    int32_t delta = raw - _previousRaw;
    _previousRaw = raw;  // ALWAYS update

    bool result = false;
    if (abs(delta) > Config::PUFF_RAW_THRESHOLD) {
        // Large change detected -- only fire if cooldown elapsed
        if ((now - _lastPuffTime) >= (unsigned long)Config::PUFF_COOLDOWN_MS) {
            result = true;
        }
        // ALWAYS reset cooldown on any large delta (key to preventing rebounds)
        _lastPuffTime = now;
    }

    return result;
}
