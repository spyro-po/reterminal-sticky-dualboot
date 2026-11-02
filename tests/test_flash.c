#include <assert.h>
#include <stdio.h>

#include "test_nvs_api.h"
typedef struct {
  int dummy;
} esp_flash_t;
static esp_flash_t chip;
esp_flash_t* esp_flash_default_chip = &chip;
static int writes, erases;
bool sticky_dualboot_write_allowed(uint32_t, size_t);
esp_err_t __real_esp_flash_write(esp_flash_t* c, const void* d, uint32_t a, uint32_t s) {
  ++writes;
  return ESP_OK;
}
esp_err_t __real_esp_flash_erase_region(esp_flash_t* c, uint32_t a, uint32_t s) {
  ++erases;
  return ESP_OK;
}
esp_err_t __real_esp_partition_write_raw(const esp_partition_t* p, size_t o, const void* d, size_t s) {
  ++writes;
  return ESP_OK;
}
esp_err_t __wrap_esp_flash_write(esp_flash_t*, const void*, uint32_t, uint32_t);
esp_err_t __wrap_esp_flash_erase_region(esp_flash_t*, uint32_t, uint32_t);
esp_err_t __wrap_esp_flash_erase_chip(esp_flash_t*);
esp_err_t __wrap_esp_flash_write_encrypted(esp_flash_t*, uint32_t, const void*, uint32_t);
esp_err_t __wrap_esp_partition_write_raw(const esp_partition_t*, size_t, const void*, size_t);
esp_err_t __wrap_spi_flash_write(size_t, const void*, size_t);
esp_err_t __wrap_spi_flash_erase_sector(size_t);
esp_err_t __wrap_esp_vfs_spiffs_register(const void*);
esp_err_t __wrap_esp_vfs_littlefs_register(const void*);
esp_err_t __wrap_esp_spiffs_format(const char*);
esp_err_t __wrap_esp_littlefs_format(const char*);
int main(void) {
  const uint32_t denied[] = {0,        0x8000,   0x9000,    0x85000,   0x88000,   0x90000,
                             0x690000, 0xc90000, 0x15c0000, 0x2000000, UINT32_MAX};
  for (unsigned i = 0; i < sizeof(denied) / sizeof(*denied); ++i) {
    assert(__wrap_esp_flash_write(NULL, "x", denied[i], 1) == ESP_ERR_NOT_ALLOWED);
    assert(__wrap_esp_flash_erase_region(NULL, denied[i], 4096) == ESP_ERR_NOT_ALLOWED);
  }
  assert(!writes && !erases);
  assert(__wrap_esp_flash_write(NULL, "x", 0x89000, 1) == ESP_OK && writes == 1);
  assert(__wrap_esp_flash_erase_region(&chip, 0x89000, 0x5000) == ESP_OK && erases == 1);
  assert(__wrap_esp_flash_erase_region(NULL, 0x89000, 0x8000) == ESP_ERR_NOT_ALLOWED);
  esp_flash_t other;
  assert(__wrap_esp_flash_write(&other, "x", 0x89000, 1) == ESP_ERR_NOT_ALLOWED);
  assert(!sticky_dualboot_write_allowed(0x89000, SIZE_MAX));
  assert(!sticky_dualboot_write_allowed(0x87000, 0x2000));
  assert(__wrap_esp_flash_erase_chip(NULL) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_esp_flash_write_encrypted(NULL, 0x89000, "x", 1) == ESP_ERR_NOT_ALLOWED);
  esp_partition_t p = {1, 2, 0xfffff000, 0x20000, "overflow", false};
  assert(__wrap_esp_partition_write_raw(&p, 0x8a000, "x", 1) == ESP_ERR_NOT_ALLOWED);
  p = (esp_partition_t){1, 2, 0x9000, 0x7d000, "nvs", false};
  assert(__wrap_esp_partition_write_raw(&p, 0, "x", 1) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_spi_flash_write(UINT32_MAX, "x", 2) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_spi_flash_erase_sector(SIZE_MAX) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_esp_vfs_spiffs_register(NULL) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_esp_vfs_littlefs_register(NULL) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_esp_spiffs_format(NULL) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_esp_littlefs_format("sys_storage") == ESP_ERR_NOT_ALLOWED);
  assert(writes == 1 && erases == 1);
  puts("PASS: lower flash API boundaries, overflow, encryption/chip erase and FS mount/format denial");
}
