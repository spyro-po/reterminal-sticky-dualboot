/* Lower flash APIs and internal-flash filesystem entry points; SD APIs are unaffected. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef BOOT_HOST_TEST
#include "test_nvs_api.h"
typedef struct {
  int dummy;
} esp_flash_t;
extern esp_flash_t* esp_flash_default_chip;
#else
#include "esp_flash.h"
#include "esp_flash_spi_init.h"
#include "esp_partition.h"
#endif

bool sticky_dualboot_write_allowed(uint32_t address, size_t size);
esp_err_t __real_esp_flash_write(esp_flash_t*, const void*, uint32_t, uint32_t);
esp_err_t __real_esp_flash_erase_region(esp_flash_t*, uint32_t, uint32_t);
esp_err_t __real_esp_partition_write_raw(const esp_partition_t*, size_t, const void*, size_t);

static bool main_chip(esp_flash_t* chip) { return !chip || chip == esp_flash_default_chip; }

esp_err_t __wrap_esp_flash_write(esp_flash_t* chip, const void* data, uint32_t address, uint32_t size) {
  return main_chip(chip) && sticky_dualboot_write_allowed(address, size)
             ? __real_esp_flash_write(chip, data, address, size)
             : ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_esp_flash_erase_region(esp_flash_t* chip, uint32_t address, uint32_t size) {
  return main_chip(chip) && sticky_dualboot_write_allowed(address, size)
             ? __real_esp_flash_erase_region(chip, address, size)
             : ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_esp_flash_erase_chip(esp_flash_t* chip) { return ESP_ERR_NOT_ALLOWED; }
esp_err_t __wrap_esp_flash_write_encrypted(esp_flash_t* chip, uint32_t address, const void* data,
                                           uint32_t size) {
  return ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_esp_partition_write_raw(const esp_partition_t* p, size_t off, const void* data,
                                         size_t size) {
  if (!p || p->encrypted || off > p->size || size > p->size - off || (uint64_t)p->address + off > UINT32_MAX)
    return ESP_ERR_NOT_ALLOWED;
  return sticky_dualboot_write_allowed(p->address + off, size)
             ? __real_esp_partition_write_raw(p, off, data, size)
             : ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_spi_flash_write(size_t address, const void* data, size_t size) {
  if (address > UINT32_MAX || size > UINT32_MAX) return ESP_ERR_NOT_ALLOWED;
  return __wrap_esp_flash_write(NULL, data, address, size);
}
esp_err_t __wrap_spi_flash_erase_range(size_t address, size_t size) {
  if (address > UINT32_MAX || size > UINT32_MAX) return ESP_ERR_NOT_ALLOWED;
  return __wrap_esp_flash_erase_region(NULL, address, size);
}
esp_err_t __wrap_spi_flash_erase_sector(size_t sector) {
  if (sector > UINT32_MAX / 4096) return ESP_ERR_NOT_ALLOWED;
  return __wrap_esp_flash_erase_region(NULL, sector * 4096, 4096);
}
esp_err_t __wrap_spi_flash_erase_chip(void) { return ESP_ERR_NOT_ALLOWED; }
esp_err_t __wrap_spi_flash_write_encrypted(size_t address, const void* data, size_t size) {
  return ESP_ERR_NOT_ALLOWED;
}

/* Deliberately ABI-compatible opaque config pointers: no flash VFS is used by CrossPoint. */
esp_err_t __wrap_esp_vfs_spiffs_register(const void* config) { return ESP_ERR_NOT_ALLOWED; }
esp_err_t __wrap_esp_spiffs_format(const char* label) { return ESP_ERR_NOT_ALLOWED; }
esp_err_t __wrap_esp_vfs_littlefs_register(const void* config) { return ESP_ERR_NOT_ALLOWED; }
esp_err_t __wrap_esp_littlefs_format(const char* label) { return ESP_ERR_NOT_ALLOWED; }
