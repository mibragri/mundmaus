#pragma once
#include <Arduino.h>
struct UpdateClass { bool begin(size_t) { return true; } size_t write(uint8_t*, size_t n) { return n; } bool end(bool = false) { return true; } void abort() {} const char* errorString() { return ""; } };
extern UpdateClass Update;
