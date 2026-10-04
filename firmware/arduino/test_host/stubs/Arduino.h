// Host stub of Arduino.h for running real mundmaus sources off-device.
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <cstdarg>
#include <cmath>
#include <algorithm>
#include "pgmspace.h"
#include "WString.h"
using std::min; using std::max;
#ifndef constrain
#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))
#endif
unsigned long millis();
void delay(unsigned long ms);
struct FakeSerial {
  int printf(const char* fmt, ...) { va_list a; va_start(a, fmt); int n = vprintf(fmt, a); va_end(a); return n; }
  size_t println(const char* s = "") { return (size_t)::printf("%s\n", s); }
  size_t println(const String& s) { return println(s.c_str()); }
  size_t print(const char* s) { return (size_t)::printf("%s", s); }
};
extern FakeSerial Serial;
struct FakeESP { uint64_t getEfuseMac() { return 0x112233445566ULL; } };
extern FakeESP ESP;
