#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "test_nvs_api.h"
static esp_partition_t cp = {1, 2, 0x89000, 0x5000, "cp_nvs", false};
static esp_partition_t vendor = {1, 2, 0x9000, 0x7d000, "nvs", false};
static esp_partition_t sys = {1, 131, 0xc90000, 0x930000, "sys_storage", false};
static esp_partition_t usr = {1, 131, 0x15c0000, 0xa00000, "usr_storage", false};
static esp_partition_t seeed = {0, 16, 0x90000, 0x600000, "app0", false};
static esp_partition_t crosspoint = {0, 32, 0x690000, 0x600000, "app1", false};
static esp_partition_t journal = {1, 64, 0x8e000, 0x2000, "bootstate", false};
static bool present = true;
static int erased, written, initialised, opened, init_result;
const esp_partition_t* esp_partition_find_first(int type, int subtype, const char* label) {
  assert(type == 1 && subtype == 2 && !strcmp(label, "cp_nvs"));
  return present ? &cp : NULL;
}
esp_err_t __real_nvs_flash_init_partition(const char* p) {
  assert(!strcmp(p, "cp_nvs"));
  ++initialised;
  return init_result;
}
esp_err_t __real_nvs_flash_init_partition_ptr(const esp_partition_t* p) {
  assert(p == &cp);
  ++initialised;
  return init_result;
}
esp_err_t __real_nvs_flash_deinit_partition(const char* p) {
  assert(!strcmp(p, "cp_nvs"));
  return ESP_OK;
}
esp_err_t __real_nvs_flash_erase_partition(const char* p) {
  assert(!strcmp(p, "cp_nvs"));
  ++erased;
  return ESP_OK;
}
esp_err_t __real_nvs_flash_erase_partition_ptr(const esp_partition_t* p) {
  assert(p == &cp);
  ++erased;
  return ESP_OK;
}
esp_err_t __real_nvs_open_from_partition(const char* p, const char* name, nvs_open_mode_t mode,
                                         nvs_handle_t* h) {
  assert(!strcmp(p, "cp_nvs") && !strcmp(name, "wifi"));
  ++opened;
  return ESP_OK;
}
esp_err_t __real_esp_partition_erase_range(const esp_partition_t* p, size_t o, size_t s) {
  ++erased;
  return ESP_OK;
}
esp_err_t __real_esp_partition_write(const esp_partition_t* p, size_t o, const void* d, size_t s) {
  ++written;
  return ESP_OK;
}
int main(void) {
  assert(__wrap_nvs_flash_init() == ESP_OK && initialised == 1);
  assert(__wrap_nvs_flash_init_partition_ptr(&cp) == ESP_OK && initialised == 2);
  assert(__wrap_nvs_flash_init_partition_ptr(&vendor) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_nvs_flash_erase_partition_ptr(&vendor) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_nvs_flash_secure_init(NULL) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_nvs_flash_secure_init_partition("nvs", NULL) == ESP_ERR_NOT_ALLOWED);
  init_result = ESP_ERR_NVS_NO_FREE_PAGES;
  assert(__wrap_nvs_flash_init() == ESP_ERR_NVS_NO_FREE_PAGES && !erased);
  /* The exact direct partition-erase operation attempted by Arduino initArduino(). */
  assert(__wrap_esp_partition_erase_range(&vendor, 0, vendor.size) == ESP_ERR_NOT_ALLOWED && !erased);
  for (unsigned i = 0; i < 5; ++i) {
    const esp_partition_t* p[] = {&vendor, &sys, &usr, &seeed, &crosspoint};
    assert(__wrap_esp_partition_erase_range(p[i], 0, 4096) == ESP_ERR_NOT_ALLOWED);
    assert(__wrap_esp_partition_write(p[i], 0, "x", 1) == ESP_ERR_NOT_ALLOWED);
  }
  assert(!erased && !written);
  assert(__wrap_nvs_flash_erase_partition("nvs") == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_nvs_flash_init_partition("nvs") == ESP_ERR_NOT_ALLOWED);
  nvs_handle_t h;
  assert(__wrap_nvs_open("wifi", 1, &h) == ESP_OK && opened == 1);
  assert(__wrap_nvs_open_from_partition("nvs", "wifi", 1, &h) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_esp_partition_write(&cp, 0, "x", 1) == ESP_OK && written == 1);
  assert(__wrap_esp_partition_write(&cp, cp.size, "x", 1) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_esp_partition_write(&cp, SIZE_MAX, "x", SIZE_MAX) == ESP_ERR_NOT_ALLOWED);
  assert(__wrap_esp_partition_erase_range(&journal, 0, 4096) == ESP_OK && erased == 1);
  /* NimBLE's error recovery erases only CrossPoint's own NVS through this API. */
  assert(__wrap_nvs_flash_erase() == ESP_OK && erased == 2);
  present = false;
  assert(__wrap_nvs_flash_init() == ESP_ERR_NOT_FOUND);
  assert(__wrap_nvs_open("wifi", 1, &h) == ESP_ERR_NOT_FOUND);
  present = true;
  cp.address += 4096;
  assert(__wrap_nvs_flash_init() == ESP_ERR_NOT_FOUND);
  cp.address -= 4096;
  cp.size -= 4096;
  assert(__wrap_nvs_flash_init() == ESP_ERR_NOT_FOUND);
  cp.size += 4096;
  cp.encrypted = true;
  assert(__wrap_nvs_flash_init() == ESP_ERR_NOT_FOUND);
  puts(
      "PASS: NVS isolation routes, missing/wrong/encrypted partition, Arduino erase denial, vendor storage "
      "writes denied");
  return 0;
}
