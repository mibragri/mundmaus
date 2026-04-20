#pragma once
// wifi_log.h -- Persistent WiFi diagnostic event log on LittleFS
//
// Cold-boot WiFi failures at the patient site cannot be diagnosed without a
// log that survives USB reset / power-cycle: serial output is only available
// to caregivers if a laptop is attached, and we cannot walk them through that.
// This module persists scan/connect events to /logs/wifi.log (8KB rotating
// via a single .old archive) so we can read them later via /api/wifi-log.
//
// Timestamps come from NTP when synced, otherwise fall back to "boot=N ms=M"
// using the persistent NVS boot counter so events are still ordered across
// reboots.

#include <Arduino.h>

namespace WifiLog {

/// Initialize: mount LittleFS, increment NVS boot counter, create /logs dir,
/// allocate mutex. Must be called once from setup() before any log()/read().
void init();

/// Start the SNTP background task (Fritzbox primary, pool.ntp.org fallback,
/// UTC). Non-blocking — call right after WiFi.localIP() is valid; subsequent
/// calls are no-ops. timestamp() will use the NTP value once a sync arrives.
void startNtp();

/// Append an event line "<timestamp> <event>\n" to /logs/wifi.log. Rotates
/// to /logs/wifi.log.old when the file grows past 8 KB. Thread-safe.
void log(const String& event);

/// Read the full log (.old followed by .log). Returns "" on read failure.
/// Allocates a single String — prefer stream() for HTTP handlers to avoid
/// a 16 KB heap allocation in the AsyncTCP task.
String read();

/// Stream the full log (.old followed by .log) into a Print target. Holds
/// the log mutex during the write. Intended for AsyncResponseStream so the
/// HTTP body never materialises as a full 16 KB String in the heap.
void stream(Print& out);

/// Delete both log files. Safe to call from any context.
void clear();

/// Persistent NVS boot counter, incremented on every init() call.
uint32_t bootCount();

/// True once the SNTP background task has produced a plausibly-real time.
bool ntpSynced();

/// Current line prefix: "<ISO-8601-UTC> boot=N" if NTP synced, else
/// "boot=N ms=<millis>". Useful for the JSON status endpoint.
String timestamp();

}  // namespace WifiLog
