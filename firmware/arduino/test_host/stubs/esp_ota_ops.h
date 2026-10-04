#pragma once
#include <cstdint>
#include "esp_system.h"
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1
enum { ESP_PARTITION_SUBTYPE_APP_FACTORY = 0x00, ESP_PARTITION_SUBTYPE_APP_OTA_0 = 0x10, ESP_PARTITION_SUBTYPE_APP_OTA_15 = 0x1f };
typedef struct { int subtype; const char* label; } esp_partition_t;
typedef enum { ESP_OTA_IMG_NEW = 0, ESP_OTA_IMG_PENDING_VERIFY = 1, ESP_OTA_IMG_VALID = 2, ESP_OTA_IMG_INVALID = 3 } esp_ota_img_states_t;
const esp_partition_t* esp_ota_get_running_partition();
const esp_partition_t* esp_ota_get_next_update_partition(const esp_partition_t*);
esp_err_t esp_ota_get_state_partition(const esp_partition_t*, esp_ota_img_states_t*);
esp_err_t esp_ota_set_boot_partition(const esp_partition_t*);
esp_err_t esp_ota_mark_app_valid_cancel_rollback();
