// Test-side view of the fakes in fakes.cpp, plus a minimal check macro.
#pragma once
#include <esp_ota_ops.h>
#include <cstdio>
#include <map>
#include <set>
#include <string>

struct Restart {};  // thrown by the fake esp_restart()

extern std::map<std::string, std::map<std::string, std::string>> g_nvs;
extern bool g_nvsWritesFail;
extern std::set<std::string> g_files;
extern std::map<std::string, std::pair<int, std::string>> g_http;
extern esp_partition_t g_ota0, g_ota1;
extern const esp_partition_t* g_running;
extern std::map<const esp_partition_t*, esp_ota_img_states_t> g_state;
extern const esp_partition_t* g_bootSet;
extern esp_reset_reason_t g_resetReason;
void resetFakes();

inline int& failures() { static int n = 0; return n; }
#define CHECK(cond, what)                                                       \
  do {                                                                          \
    if (cond) { std::printf("  ok    %s\n", what); }                            \
    else { std::printf("  FAIL  %s  (%s:%d)\n", what, __FILE__, __LINE__); ++failures(); } \
  } while (0)
