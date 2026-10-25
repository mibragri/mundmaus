#pragma once
#include "FreeRTOS.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <mutex>
// Real mutexes, so a test can run OTA calls from two threads and see whether they overlap.
// A portMAX_DELAY wait that lasts 5 s aborts the test: on the device it would be a deadlock.
inline SemaphoreHandle_t xSemaphoreCreateMutex() { return new std::timed_mutex; }
inline BaseType_t xSemaphoreTake(SemaphoreHandle_t h, TickType_t ms) {
  auto* m = static_cast<std::timed_mutex*>(h);
  if (ms != portMAX_DELAY) return m->try_lock_for(std::chrono::milliseconds(ms)) ? pdTRUE : pdFALSE;
  if (m->try_lock_for(std::chrono::seconds(5))) return pdTRUE;
  std::fprintf(stderr, "Deadlock: Mutex seit 5 s belegt\n");
  std::abort();
}
inline BaseType_t xSemaphoreGive(SemaphoreHandle_t h) {
  static_cast<std::timed_mutex*>(h)->unlock();
  return pdTRUE;
}
