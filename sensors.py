# sensors.py — CalibratedJoystick + PuffSensor (HX710B 24-bit)

import time

import machine

import config


class CalibratedJoystick:
    def __init__(self, pin_x, pin_y, pin_sw):
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
        self.center_x = 2048
        self.center_y = 2048
        self.last_dir = None
        self.last_nav_time = 0
        self._nav_repeating = False
        self.sw_last = 1
        self.sw_debounce_time = 0
        self.calibrate()

    def calibrate(self, samples=None):
        if samples is None:
            samples = config.CALIBRATION_SAMPLES
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
        print(f"  Center=({self.center_x},{self.center_y}) dz=±{config.DEADZONE}")

    def read_centered(self):
        dx = self.adc_x.read() - self.center_x
        dy = self.adc_y.read() - self.center_y
        if abs(dx) < config.DEADZONE: dx = 0
        if abs(dy) < config.DEADZONE: dy = 0
        return dx, dy

    def get_direction(self):
        dx, dy = self.read_centered()
        if abs(dx) > abs(dy):
            if dx < -config.NAV_THRESHOLD: return 'left'
            elif dx > config.NAV_THRESHOLD: return 'right'
        else:
            if dy < -config.NAV_THRESHOLD: return 'up'
            elif dy > config.NAV_THRESHOLD: return 'down'
        return None

    def poll_navigation(self):
        now = time.ticks_ms()
        d = self.get_direction()
        if d is None:
            self.last_dir = None
            return None
        if d != self.last_dir:
            # New direction — fire immediately, start initial delay
            self.last_dir = d
            self.last_nav_time = now
            self._nav_repeating = False
            return d
        # Same direction held — initial delay then repeat
        delay = config.NAV_REPEAT_MS if self._nav_repeating else config.NAV_REPEAT_MS * 2
        if time.ticks_diff(now, self.last_nav_time) > delay:
            self.last_nav_time = now
            self._nav_repeating = True
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
        return abs(dx) < config.DEADZONE * 2 and abs(dy) < config.DEADZONE * 2


class PuffSensor:
    def __init__(self, data_pin, clk_pin):
        self.data = machine.Pin(data_pin, machine.Pin.IN, machine.Pin.PULL_DOWN)
        self.clk = machine.Pin(clk_pin, machine.Pin.OUT)
        self.clk.value(0)
        self.baseline = 0
        self.max_range = 1
        self.last_puff_time = 0
        self.previous_raw = 0
        self._raw_threshold = 100000
        self._last_raw = 0
        time.sleep_ms(100)
        self.calibrate_baseline()

    def _read_raw_nonblocking(self):
        """Read sensor only if data ready (DATA low). Returns 0 if not ready."""
        if self.data.value() == 1:
            return 0  # Not ready — don't wait
        # Disable interrupts during bit-bang (WiFi/asyncio can corrupt timing)
        irq_state = machine.disable_irq()
        value = 0
        for i in range(24):
            self.clk.value(1)
            self.clk.value(0)
            value = (value << 1) | self.data.value()
        # 25th pulse: select next conversion (gain 128)
        self.clk.value(1)
        self.clk.value(0)
        machine.enable_irq(irq_state)
        # Sign extension
        if value > 0x7fffff:
            value -= 0x1000000
        return value

    def _read_raw_blocking(self):
        """Read sensor, waiting up to ~10ms for data ready. For calibration only."""
        timeout = 0
        while self.data.value() == 1:
            timeout += 1
            if timeout > 10000: return 0
            time.sleep_us(1)
        return self._read_raw_nonblocking()

    def calibrate_baseline(self, samples=30):
        print("  Drucksensor Kalibrierung...")
        readings = []
        for _ in range(samples):
            r = self._read_raw_blocking()
            if r != 0: readings.append(r)
            time.sleep_ms(20)
        if readings:
            self.baseline = sum(readings) // len(readings)
            self.max_range = abs(self.baseline) * 0.5 if self.baseline != 0 else 100000
            self.previous_raw = self.baseline
        print(f"  Baseline={self.baseline} range={self.max_range}")

    def poll(self):
        """Non-blocking read. Skips if sensor not ready (DATA high)."""
        raw = self._read_raw_nonblocking()
        if raw != 0:
            self._last_raw = raw

    def get_level(self):
        """Normalized level relative to fixed baseline (for puff level indicator)."""
        raw = self._last_raw
        if raw == 0: return 0.0
        delta = abs(raw - self.baseline)
        return min(1.0, delta / self.max_range)

    def detect_puff(self):
        """Detect puff/sip as sudden change from previous reading.
        Exact port of original mouthMouse hx711.py air_flow() logic:
        - Any large delta (puff or rebound) resets the cooldown timer
        - Only fires if cooldown has fully elapsed (sensor stable)
        - This prevents rebounds from triggering false events."""
        now = time.ticks_ms()
        raw = self._last_raw
        if raw == 0:
            return False
        delta = raw - self.previous_raw
        self.previous_raw = raw
        result = False
        if abs(delta) > self._raw_threshold:
            # Large change detected — only fire if cooldown elapsed
            if time.ticks_diff(now, self.last_puff_time) >= config.PUFF_COOLDOWN_MS:
                result = True
            # ALWAYS reset cooldown on any large delta (key to preventing rebounds)
            self.last_puff_time = now
        return result
