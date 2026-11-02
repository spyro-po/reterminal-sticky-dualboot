#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef int esp_err_t;
typedef int nvs_open_mode_t;
typedef struct {
  int unused;
} nvs_sec_cfg_t;
typedef uint32_t nvs_handle_t;
typedef struct {
  int type, subtype;
  uint32_t address, size;
  char label[17];
  bool encrypted;
} esp_partition_t;
#define ESP_OK 0
#define ESP_ERR_NOT_FOUND 1
#define ESP_ERR_NOT_ALLOWED 2
#define ESP_ERR_NVS_NO_FREE_PAGES 3
#define ESP_PARTITION_TYPE_DATA 1
#define ESP_PARTITION_SUBTYPE_DATA_NVS 2
const esp_partition_t* esp_partition_find_first(int, int, const char*);
esp_err_t __wrap_nvs_flash_init(void);
esp_err_t __wrap_nvs_flash_erase(void);
esp_err_t __wrap_nvs_flash_init_partition(const char*);
esp_err_t __wrap_nvs_flash_erase_partition(const char*);
esp_err_t __wrap_nvs_open(const char*, nvs_open_mode_t, nvs_handle_t*);
esp_err_t __wrap_nvs_open_from_partition(const char*, const char*, nvs_open_mode_t, nvs_handle_t*);
esp_err_t __wrap_esp_partition_erase_range(const esp_partition_t*, size_t, size_t);
esp_err_t __wrap_esp_partition_write(const esp_partition_t*, size_t, const void*, size_t);

esp_err_t __wrap_nvs_flash_init_partition_ptr(const esp_partition_t*);
esp_err_t __wrap_nvs_flash_erase_partition_ptr(const esp_partition_t*);
esp_err_t __wrap_nvs_flash_secure_init(nvs_sec_cfg_t*);
esp_err_t __wrap_nvs_flash_secure_init_partition(const char*, nvs_sec_cfg_t*);
