#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <atomic>
#include <chrono>
#include <map>
#include <string>
#include <thread>
#include <utility>
enum followRedirects_t { HTTPC_DISABLE_FOLLOW_REDIRECTS, HTTPC_STRICT_FOLLOW_REDIRECTS, HTTPC_FORCE_FOLLOW_REDIRECTS };
extern std::map<std::string, std::pair<int, std::string>> g_http;  // url without query -> (code, body)
// Faults and bookkeeping for the tests, defined in fakes.cpp and cleared by resetFakes().
extern std::atomic<int> g_httpFailNext;    // the next n GETs fail like an unreachable server (-1)
extern std::atomic<bool> g_httpCertFails;  // a GET on a certificate-checked connection fails (-1)
extern std::atomic<int> g_httpGetMs;       // each GET keeps its connection open this long
extern std::atomic<int> g_httpGets, g_httpOpen, g_httpMaxOpen;  // GETs made; connections open now, at most
class HTTPClient {
 public:
  ~HTTPClient() { end(); }
  void setConnectTimeout(int32_t) {} void setTimeout(uint16_t) {} void setFollowRedirects(followRedirects_t) {}
  bool begin(const String& url) { std::string u = url.c_str(); url_ = u.substr(0, u.find('?')); checked_ = false; return true; }
  bool begin(const String& url, const char*) { begin(url); checked_ = true; return true; }
  void setUserAgent(const String&) {} void addHeader(const String&, const String&) {}
  int GET() {
    ++g_httpGets;
    if (!open_) {
      open_ = true;
      const int now = ++g_httpOpen;
      int most = g_httpMaxOpen;
      while (now > most && !g_httpMaxOpen.compare_exchange_weak(most, now)) {}
    }
    if (g_httpGetMs > 0) std::this_thread::sleep_for(std::chrono::milliseconds(g_httpGetMs.load()));
    int left = g_httpFailNext;
    while (left > 0 && !g_httpFailNext.compare_exchange_weak(left, left - 1)) {}
    if (left > 0) return -1;
    if (checked_ && g_httpCertFails) return -1;
    const auto it = g_http.find(url_);
    return it != g_http.end() ? it->second.first : 404;
  }
  String getString() { const auto it = g_http.find(url_); return String(it != g_http.end() ? it->second.second.c_str() : ""); }
  void end() { if (open_) { open_ = false; --g_httpOpen; } }
  int getSize() { const auto it = g_http.find(url_); return it != g_http.end() ? (int)it->second.second.size() : 0; }
  WiFiClient* getStreamPtr() { return &c_; } bool connected() { return false; }
 private: std::string url_; bool checked_ = false; bool open_ = false; WiFiClient c_;
};
