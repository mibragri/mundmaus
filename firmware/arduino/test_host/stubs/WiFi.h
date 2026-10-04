#pragma once
#include <Arduino.h>
class WiFiClient { public: int available() { return 0; } int readBytes(uint8_t*, size_t) { return 0; } };
