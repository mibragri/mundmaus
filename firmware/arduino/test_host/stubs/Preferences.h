#pragma once
#include <Arduino.h>
#include <map>
#include <string>
extern std::map<std::string, std::map<std::string, std::string>> g_nvs;  // namespace -> key -> value
extern bool g_nvsWritesFail;  // simulates a full or failing NVS partition
class Preferences {
 public:
  bool begin(const char* ns, bool ro = false) { ns_ = ns; ro_ = ro; return true; }
  void end() {}
  bool clear() { g_nvs[ns_].clear(); return true; }
  bool remove(const char* k) { return g_nvs[ns_].erase(k) > 0; }
  bool isKey(const char* k) { return g_nvs[ns_].count(k) > 0; }
  int32_t getInt(const char* k, int32_t d = 0) { auto& m = g_nvs[ns_]; return m.count(k) ? (int32_t)std::stol(m[k]) : d; }
  size_t putInt(const char* k, int32_t v) { if (!writable()) return 0; g_nvs[ns_][k] = std::to_string(v); return 4; }
  uint32_t getUInt(const char* k, uint32_t d = 0) { auto& m = g_nvs[ns_]; return m.count(k) ? (uint32_t)std::stoul(m[k]) : d; }
  size_t putUInt(const char* k, uint32_t v) { if (!writable()) return 0; g_nvs[ns_][k] = std::to_string(v); return 4; }
  uint8_t getUChar(const char* k, uint8_t d = 0) { return (uint8_t)getUInt(k, d); }
  size_t putUChar(const char* k, uint8_t v) { return putUInt(k, v); }
  String getString(const char* k, const String& d = String()) { auto& m = g_nvs[ns_]; return m.count(k) ? String(m[k].c_str()) : d; }
  size_t putString(const char* k, const String& v) { if (!writable()) return 0; g_nvs[ns_][k] = v.c_str(); return v.length(); }
  size_t putString(const char* k, const char* v) { return putString(k, String(v)); }
 private:
  bool writable() const { return !ro_ && !g_nvsWritesFail; }
  std::string ns_; bool ro_ = false;
};
