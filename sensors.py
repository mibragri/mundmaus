# sensors.py — CalibratedJoystick + PuffSensor (HX710B 24-bit)

import time

import machine

from config import (
    CALIBRATION_SAMPLES,
    DEADZONE,
    NAV_REPEAT_MS,
    NAV_THRESHOLD,
    PUFF_COOLDOWN_MS,
    PUFF_SAMPLES,
    PUFF_THRESHOLD,
)


class CalibratedJoystick:
    def __init__(self, pin_x, pin_y, pin_sw, deadzone=DEADZONE):
        self.adc_x = machine.ADC(machine.Pin(pin_x))
        self.adc_y = machine.ADC(machine.Pin(pin_y))
        self.adc_x.atten(machine.ADC.ATTN_11DB)
        self.adc_y.atten(machine.ADC.ATTN_11DB)
        self.btn = machine.Pin(pin_sw, machine.Pin.IN, machine.Pin.PULL_UP)
        self.deadzone = deadzone
        self.center_x = 2048
        self.center_y = 2048
        self.last_nav = None
        self.last_nav_time = 0
        self.last_btn = 1
        self.last_btn_time = 0
        self.calibrate()

    def calibrate(self, samples=CALIBRATION_SAMPLES):
        sx, sy = 0, 0
        for _ in range(samples):
            sx += self.adc_x.read()
            sy += self.adc_y.read()
            time.sleep_ms(5)
        self.center_x = sx // samples
        self.center_y = sy // samples
        print(f"  Joystick cal: {self.center_x}, {self.center_y}")

    def read_centered(self):
        x = self.adc_x.read() - self.center_x
        y = self.adc_y.read() - self.center_y
        if abs(x) < self.deadzone: x = 0
        if abs(y) < self.deadzone: y = 0
        return x, y

    def get_direction(self):
        x, y = self.read_centered()
        if abs(x) > abs(y):
            if x > NAV_THRESHOLD: return 'right'
            if x < -NAV_THRESHOLD: return 'left'
        else:
            if y > NAV_THRESHOLD: return 'down'
            if y < -NAV_THRESHOLD: return 'up'
        return None

    def poll_navigation(self):
        d = self.get_direction()
        now = time.ticks_ms()
        if d is None:
            self.last_nav = None
            return None
        if d != self.last_nav or time.ticks_diff(now, self.last_nav_time) > NAV_REPEAT_MS:
            self.last_nav = d
            self.last_nav_time = now
            return d
        return None

    def poll_button(self):
        val = self.btn.value()
        now = time.ticks_ms()
        if val == 0 and self.last_btn == 1 and time.ticks_diff(now, self.last_btn_time) > 200:
            self.last_btn = 0
            self.last_btn_time = now
            return True
        if val == 1:
            self.last_btn = 1
        return False

    def is_idle(self):
        x, y = self.read_centered()
        return x == 0 and y == 0


class PuffSensor:
    def __init__(self, data_pin, clk_pin, threshold=PUFF_THRESHOLD, samples=PUFF_SAMPLES):
        self.data = machine.Pin(data_pin, machine.Pin.IN)
        self.clk = machine.Pin(clk_pin, machine.Pin.OUT)
        self.clk.value(0)
        self.threshold = threshold
        self.baseline = 0
        self.last_puff_time = 0
        self._buf = [0] * samples
        self._idx = 0
        self._samples = samples
        self.calibrate_baseline()

    def _read_raw(self):
        timeout = time.ticks_ms() + 200
        while self.data.value() == 1:
            if time.ticks_diff(time.ticks_ms(), timeout) > 0:
                return None
        result = 0
        for _ in range(24):
            self.clk.value(1)
            self.clk.value(0)
            result = (result << 1) | self.data.value()
        self.clk.value(1)
        self.clk.value(0)
        if result & 0x800000:
            result -= 0x1000000
        return result

    def calibrate_baseline(self, n=30):
        vals = []
        for _ in range(n):
            v = self._read_raw()
            if v is not None:
                vals.append(v)
            time.sleep_ms(10)
        if vals:
            self.baseline = sum(vals) // len(vals)
            print(f"  Puff-Baseline: {self.baseline}")
        else:
            print("  Puff: Sensor antwortet nicht")

    def read_normalized(self):
        raw = self._read_raw()
        if raw is None:
            return 0.0
        diff = abs(raw - self.baseline)
        self._buf[self._idx] = diff
        self._idx = (self._idx + 1) % self._samples
        return sum(self._buf) / (self._samples * max(abs(self.baseline), 1))

    def detect_puff(self):
        level = self.read_normalized()
        now = time.ticks_ms()
        if level > self.threshold and time.ticks_diff(now, self.last_puff_time) > PUFF_COOLDOWN_MS:
            self.last_puff_time = now
            return True
        return False

    def get_level(self):
        return self.read_normalized()
