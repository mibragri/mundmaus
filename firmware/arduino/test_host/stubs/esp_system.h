// Host stub of esp_system.h. The reset reasons match ESP-IDF 5.5 (esp_system/include/esp_system.h);
// tests set the reason of the "previous" reset in g_resetReason (fakes.cpp).
#pragma once
typedef enum {
    ESP_RST_UNKNOWN,
    ESP_RST_POWERON,
    ESP_RST_EXT,
    ESP_RST_SW,
    ESP_RST_PANIC,
    ESP_RST_INT_WDT,
    ESP_RST_TASK_WDT,
    ESP_RST_WDT,
    ESP_RST_DEEPSLEEP,
    ESP_RST_BROWNOUT,
    ESP_RST_SDIO,
    ESP_RST_USB,
    ESP_RST_JTAG,
    ESP_RST_EFUSE,
    ESP_RST_PWR_GLITCH,
    ESP_RST_CPU_LOCKUP,
} esp_reset_reason_t;
#ifdef __cplusplus
esp_reset_reason_t esp_reset_reason();
void esp_restart();  // the fake throws: the real one never returns
#endif
