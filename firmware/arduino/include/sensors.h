#pragma once
// sensors.h -- CalibratedJoystick + PuffSensor (HX710B 24-bit)
// Direct port of MicroPython sensors.py to Arduino/ESP32.

#include <Arduino.h>

class CalibratedJoystick {
public:
    CalibratedJoystick(int pinX, int pinY, int pinSW);

    /// Calibrate center position (blocking). samples=0 uses Config default.
    void calibrate(int samples = 0);

    /// Poll for navigation event. Returns "left","right","up","down" or nullptr.
    const char* pollNavigation();

    /// Poll button (debounced, active LOW). Returns true on press edge.
    bool pollButton();

    /// True if both axes within 2x DEADZONE of center.
    bool isIdle();

    int centerX;
    int centerY;

    /// Continuous state: direction + intensity (0-1). Returns nullptr if idle.
    const char* getState(float& outIntensity);

private:
    int _pinX, _pinY, _pinSW;
    const char* _lastDir;
    float _lastIntensity = 0.0f;
    unsigned long _lastNavTime;
    bool _navRepeating;
    unsigned long _dirLostTime;
    int _swLast;
    unsigned long _swDebounceTime;

    void _readCentered(int& dx, int& dy);
    const char* _getDirection();
};

class PuffSensor {
public:
    PuffSensor(int dataPin, int clkPin);

    /// Calibrate baseline (blocking, ~600ms). samples=0 uses default 30.
    void calibrateBaseline(int samples = 30);

    /// Non-blocking read. Call every poll cycle.
    void poll();

    /// Normalized puff level 0.0-1.0 relative to baseline.
    float getLevel();

    /// Detect puff/sip as sudden delta. Includes cooldown to prevent rebounds.
    bool detectPuff();

    int32_t baseline;

private:
    int _dataPin, _clkPin;
    int32_t _maxRange;
    unsigned long _lastPuffTime;
    int32_t _previousRaw;
    int32_t _rawThreshold;
    int32_t _lastRaw;

    /// Read if data ready (non-blocking). Returns 0 if not ready.
    int32_t _readRawNonblocking();

    /// Wait up to ~10ms for data ready, then read (for calibration).
    int32_t _readRawBlocking();
};
