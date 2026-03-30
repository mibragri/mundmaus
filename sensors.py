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
        try:
            self.adc_x.width(machine.ADC.WIDTH_12BIT)
            self.adc_y.width(machine.ADC.WIDTH_12BIT)
        except:
            pass  # Neuere MicroPython brauchen das evtl. nicht

        self.sw = machine.Pin(pin_sw, machine.Pin.IN, machine.Pin.PULL_UP)
        self.deadzone = deadzone
        self.center_x = 2048
        self.center_y = 2048
        self.last_dir = None
        self.last_nav_time = 0
        self.sw_last = 1
        self.sw_debounce_time = 0
        self.calibrate()

    def calibrate(self, samples=CALIBRATION_SAMPLES):
        print("  Joystick Kalibrierung...")
        for _ in range(10):
            self.adc_x.read(); self.adc_y.read()
            time.sleep_ms(5)
        sx, sy = 0, 0
        for _ in range(samples):
            sx += self.adc_x.read(); sy += self.adc_y.read()
            time.sleep_ms(10)
        self.center_x = sx // samples
        self.center_y = sy // samples
        print(f"  Center=({self.center_x},{self.center_y}) dz=±{self.deadzone}")

    def read_centered(self):
        dx = self.adc_x.read() - self.center_x
        dy = self.adc_y.read() - self.center_y
        if abs(dx) < self.deadzone: dx = 0
        if abs(dy) < self.deadzone: dy = 0
        return dx, dy

    def get_direction(self):
        dx, dy = self.read_centered()
        if abs(dx) > abs(dy):
            if dx < -NAV_THRESHOLD: return 'left'
            elif dx > NAV_THRESHOLD: return 'right'
        else:
            if dy < -NAV_THRESHOLD: return 'up'
            elif dy > NAV_THRESHOLD: return 'down'
        return None

    def poll_navigation(self):
        now = time.ticks_ms()
        d = self.get_direction()
        if d is None:
            self.last_dir = None
            return None
        if d != self.last_dir or time.ticks_diff(now, self.last_nav_time) > NAV_REPEAT_MS:
            self.last_dir = d
            self.last_nav_time = now
            return d
        return None

    def poll_button(self):
        now = time.ticks_ms()
        val = self.sw.value()
        if val == 0 and self.sw_last == 1:
            if time.ticks_diff(now, self.sw_debounce_time) > 200:
                self.sw_debounce_time = now
                self.sw_last = val
                return True
        self.sw_last = val
        return False

    def is_idle(self):
        dx, dy = self.read_centered()
        return abs(dx) < self.deadzone * 2 and abs(dy) < self.deadzone * 2


class PuffSensor:
    def __init__(self, data_pin, clk_pin, threshold=PUFF_THRESHOLD):
        self.data = machine.Pin(data_pin, machine.Pin.IN)
        self.clk = machine.Pin(clk_pin, machine.Pin.OUT)
        self.clk.value(0)
        self.threshold = threshold
        self.baseline = 0
        self.max_range = 1
        self.last_puff_time = 0
        self.samples_buf = [0] * PUFF_SAMPLES
        self.sample_idx = 0
        time.sleep_ms(100)
        self.calibrate_baseline()

    def _read_raw(self):
        timeout = 0
        while self.data.value() == 1:
            timeout += 1
            if timeout > 100000: return 0
        value = 0
        for i in range(24):
            self.clk.value(1); time.sleep_us(1)
            value = (value << 1) | self.data.value()
            self.clk.value(0); time.sleep_us(1)
        self.clk.value(1); time.sleep_us(1)
        self.clk.value(0); time.sleep_us(1)
        if value & 0x800000: value -= 0x1000000
        return value

    def calibrate_baseline(self, samples=30):
        print("  Drucksensor Kalibrierung...")
        readings = []
        for _ in range(samples):
            r = self._read_raw()
            if r != 0: readings.append(r)
            time.sleep_ms(20)
        if readings:
            self.baseline = sum(readings) // len(readings)
            self.max_range = abs(self.baseline) * 0.5 if self.baseline != 0 else 100000
        print(f"  Baseline={self.baseline} range={self.max_range}")

    def read_normalized(self):
        raw = self._read_raw()
        if raw == 0: return 0.0
        delta = abs(raw - self.baseline)
        n = min(1.0, delta / self.max_range)
        self.samples_buf[self.sample_idx] = n
        self.sample_idx = (self.sample_idx + 1) % PUFF_SAMPLES
        return sum(self.samples_buf) / PUFF_SAMPLES

    def detect_puff(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_puff_time) < PUFF_COOLDOWN_MS: return False
        if self.read_normalized() >= self.threshold:
            self.last_puff_time = now
            return True
        return False

    def get_level(self):
        return self.read_normalized()
