#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <map>
#include <string>
#include <utility>
enum followRedirects_t { HTTPC_DISABLE_FOLLOW_REDIRECTS, HTTPC_STRICT_FOLLOW_REDIRECTS, HTTPC_FORCE_FOLLOW_REDIRECTS };
extern std::map<std::string, std::pair<int, std::string>> g_http;  // url without query -> (code, body)
class HTTPClient {
 public:
  void setConnectTimeout(int32_t) {} void setTimeout(uint16_t) {} void setFollowRedirects(followRedirects_t) {}
  bool begin(const String& url) { std::string u = url.c_str(); url_ = u.substr(0, u.find('?')); return true; }
  void setUserAgent(const String&) {} void addHeader(const String&, const String&) {}
  int GET() { return g_http.count(url_) ? g_http[url_].first : 404; }
  String getString() { return String(g_http[url_].second.c_str()); }
  void end() {} int getSize() { return (int)g_http[url_].second.size(); }
  WiFiClient* getStreamPtr() { return &c_; } bool connected() { return false; }
 private: std::string url_; WiFiClient c_;
};
