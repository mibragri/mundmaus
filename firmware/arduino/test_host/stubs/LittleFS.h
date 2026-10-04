#pragma once
#include <Arduino.h>
#include <set>
#include <string>
extern std::set<std::string> g_files;  // existing paths on the fake LittleFS
class File {
 public:
  File() = default; explicit File(bool ok) : ok_(ok) {}
  explicit operator bool() const { return ok_; }
  size_t write(const uint8_t*, size_t n) { return n; }
  void close() {}
 private: bool ok_ = false;
};
struct FakeFS {
  bool exists(const String& p) { return g_files.count(p.c_str()) > 0; }
  bool exists(const char* p) { return g_files.count(p) > 0; }
  bool mkdir(const String& p) { g_files.insert(p.c_str()); return true; }
  File open(const String& p, const char*) { g_files.insert(p.c_str()); return File(true); }
  bool remove(const String& p) { return g_files.erase(p.c_str()) > 0; }
  bool rename(const String& a, const String& b) { if (!g_files.erase(a.c_str())) return false; g_files.insert(b.c_str()); return true; }
};
extern FakeFS LittleFS;
