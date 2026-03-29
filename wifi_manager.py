# wifi_manager.py — WiFi station/AP management with credential persistence

import json
import os
import time

import network

from config import AP_PASS, AP_SSID, WIFI_CONFIG_FILE


class WiFiManager:
    def __init__(self):
        self.sta = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)
        self.ssid = None
        self.password = None
        self.mode = None
        self.ip = None

    def load_credentials(self):
        try:
            with open(WIFI_CONFIG_FILE) as f:
                data = json.load(f)
                self.ssid = data.get('ssid', '').strip()
                self.password = data.get('password', '').strip()
                if self.ssid:
                    print(f"  Gespeicherte SSID: '{self.ssid}'")
                    return True
                return False
        except OSError:
            print("  Keine wifi.json vorhanden")
            return False
        except Exception as e:
            print(f"  wifi.json Fehler: {e}")
            return False

    def save_credentials(self, ssid, password):
        self.ssid = ssid.strip()
        self.password = password.strip()
        try:
            with open(WIFI_CONFIG_FILE, 'w') as f:
                json.dump({'ssid': self.ssid, 'password': self.password}, f)
            print(f"  Credentials gespeichert: '{self.ssid}'")
            return True
        except Exception as e:
            print(f"  Speicherfehler: {e}")
            return False

    def delete_credentials(self):
        try:
            os.remove(WIFI_CONFIG_FILE)
        except:
            pass
        self.ssid = None
        self.password = None

    def connect_station(self, timeout_ms=10000):
        if not self.ssid:
            return None
        self.ap.active(False)
        self.sta.active(True)
        if self.sta.isconnected():
            self.ip = self.sta.ifconfig()[0]
            self.mode = 'station'
            return self.ip
        print(f"  Verbinde mit '{self.ssid}'...")
        try:
            self.sta.connect(self.ssid, self.password)
        except Exception as e:
            print(f"  Fehler: {e}")
            return None
        start = time.ticks_ms()
        while not self.sta.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                print(f"  Timeout ({timeout_ms}ms)")
                self.sta.active(False)
                return None
            time.sleep_ms(250)
        self.ip = self.sta.ifconfig()[0]
        self.mode = 'station'
        print(f"  Verbunden: {self.ip}")
        return self.ip

    def start_ap(self):
        self.sta.active(False)
        self.ap.active(True)
        self.ap.config(essid=AP_SSID, password=AP_PASS,
                       authmode=network.AUTH_WPA_WPA2_PSK)
        while not self.ap.active():
            time.sleep_ms(100)
        self.ip = self.ap.ifconfig()[0]
        self.mode = 'ap'
        return self.ip

    def scan_networks(self):
        try:
            was_active = self.sta.active()
            self.sta.active(True)
            time.sleep_ms(100)
            results = self.sta.scan()
            if not was_active and self.mode == 'ap':
                self.sta.active(False)
            seen = set()
            ssids = []
            for r in sorted(results, key=lambda x: x[3], reverse=True):
                name = r[0].decode('utf-8', 'ignore').strip()
                if name and name not in seen:
                    seen.add(name)
                    ssids.append(name)
            return ssids[:15]
        except Exception as e:
            print(f"  Scan Fehler: {e}")
            return []

    def get_status(self):
        return {
            'mode': self.mode or 'disconnected',
            'ssid': self.ssid or '',
            'ip': self.ip or '',
            'ap_ssid': AP_SSID,
            'connected': self.sta.isconnected() if self.mode == 'station' else False
        }

    def startup(self):
        has_creds = self.load_credentials()
        if has_creds:
            ip = self.connect_station()
            if ip:
                return ip, 'station'
            print("  WLAN fehlgeschlagen -> Hotspot")
        else:
            print("  Keine Daten -> Hotspot")
        ip = self.start_ap()
        return ip, 'ap'
