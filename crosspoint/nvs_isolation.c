/* Default NVS and internal flash writes for the dedicated Sticky test profile. */
#include <stdbool.h>
#include <string.h>
#ifdef BOOT_HOST_TEST
#include "test_nvs_api.h"
#else
#include "esp_partition.h"
#include "nvs.h"
#include "nvs_flash.h"
#if !defined(CROSSPOINT_STICKY_DUALBOOT) || !FREEINK_DEVICE_STICKY
#error "NVS isolation must only be linked into the dedicated Sticky dual boot profile"
#endif
#if !CONFIG_ESPTOOLPY_FLASHSIZE_32MB
#error "CrossPoint dual boot requires a 32 MiB SDK build"
#endif
#if CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE || CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK
#error "Fixed-image dual boot requires rollback disabled in the application SDK"
#endif
#if CONFIG_NVS_ENCRYPTION
#error "The experimental deployment does not support NVS encryption"
#endif
#endif

#define CP_NVS "cp_nvs"

esp_err_t __real_nvs_flash_init_partition(const char*);
esp_err_t __real_nvs_flash_init_partition_ptr(const esp_partition_t*);
esp_err_t __real_nvs_flash_deinit_partition(const char*);
esp_err_t __real_nvs_flash_erase_partition(const char*);
esp_err_t __real_nvs_flash_erase_partition_ptr(const esp_partition_t*);
esp_err_t __real_nvs_open_from_partition(const char*, const char*, nvs_open_mode_t, nvs_handle_t*);
esp_err_t __real_esp_partition_erase_range(const esp_partition_t*, size_t, size_t);
esp_err_t __real_esp_partition_write(const esp_partition_t*, size_t, const void*, size_t);

static const esp_partition_t* cp_partition(void) {
  const esp_partition_t* p =
      esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, CP_NVS);
  return p && p->address == 0x89000 && p->size == 0x5000 && !p->encrypted ? p : NULL;
}

static bool cp_label(const char* label) { return label && strcmp(label, CP_NVS) == 0; }

const char sticky_dualboot_build_contract[] =
    "STICKY-DUALBOOT-ABI3;cp_nvs=0x89000:0x5000;bootstate=0x8e000:0x2000;OTA=FORBIDDEN";

bool sticky_dualboot_write_allowed(uint32_t address, size_t size) {
  const uint64_t end = (uint64_t)address + size;
  return end >= address &&
         ((address >= 0x86000 && end <= 0x88000) || (address >= 0x89000 && end <= 0x90000) ||
          (address >= 0x1fc0000 && end <= 0x2000000));
}

esp_err_t __wrap_nvs_flash_init(void) {
  return cp_partition() ? __real_nvs_flash_init_partition(CP_NVS) : ESP_ERR_NOT_FOUND;
}
esp_err_t __wrap_nvs_flash_deinit(void) { return __real_nvs_flash_deinit_partition(CP_NVS); }
esp_err_t __wrap_nvs_flash_erase(void) {
  return cp_partition() ? __real_nvs_flash_erase_partition(CP_NVS) : ESP_ERR_NOT_FOUND;
}
esp_err_t __wrap_nvs_flash_init_partition(const char* label) {
  if (!cp_label(label)) return ESP_ERR_NOT_ALLOWED;
  return __wrap_nvs_flash_init();
}
esp_err_t __wrap_nvs_flash_init_partition_ptr(const esp_partition_t* p) {
  const esp_partition_t* cp = cp_partition();
  return cp && p == cp ? __real_nvs_flash_init_partition_ptr(cp) : ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_nvs_flash_secure_init(nvs_sec_cfg_t* cfg) { return ESP_ERR_NOT_ALLOWED; }
esp_err_t __wrap_nvs_flash_secure_init_partition(const char* label, nvs_sec_cfg_t* cfg) {
  return ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_nvs_flash_deinit_partition(const char* label) {
  return cp_label(label) ? __real_nvs_flash_deinit_partition(CP_NVS) : ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_nvs_flash_erase_partition(const char* label) {
  if (!cp_label(label)) return ESP_ERR_NOT_ALLOWED;
  return __wrap_nvs_flash_erase();
}
esp_err_t __wrap_nvs_flash_erase_partition_ptr(const esp_partition_t* p) {
  const esp_partition_t* cp = cp_partition();
  return cp && p == cp ? __real_nvs_flash_erase_partition_ptr(cp) : ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_nvs_open(const char* name, nvs_open_mode_t mode, nvs_handle_t* handle) {
  return cp_partition() ? __real_nvs_open_from_partition(CP_NVS, name, mode, handle) : ESP_ERR_NOT_FOUND;
}
esp_err_t __wrap_nvs_open_from_partition(const char* label, const char* name, nvs_open_mode_t mode,
                                         nvs_handle_t* h) {
  return cp_label(label) ? __wrap_nvs_open(name, mode, h) : ESP_ERR_NOT_ALLOWED;
}

static bool writable(const esp_partition_t* p, size_t offset, size_t size) {
  if (!p || p->type != ESP_PARTITION_TYPE_DATA || offset > p->size || size > p->size - offset || p->encrypted)
    return false;
  return (p == cp_partition()) ||
         (p->address == 0x86000 && p->size == 0x2000 && p->subtype == 0 && !strcmp(p->label, "otadata")) ||
         (p->address == 0x8e000 && p->size == 0x2000 && p->subtype == 64 && !strcmp(p->label, "bootstate")) ||
         (p->address == 0x1fc0000 && p->size == 0x40000 && p->subtype == 3 && !strcmp(p->label, "coredump"));
}

esp_err_t __wrap_esp_partition_erase_range(const esp_partition_t* p, size_t offset, size_t size) {
  return writable(p, offset, size) ? __real_esp_partition_erase_range(p, offset, size) : ESP_ERR_NOT_ALLOWED;
}
esp_err_t __wrap_esp_partition_write(const esp_partition_t* p, size_t offset, const void* data, size_t size) {
  return writable(p, offset, size) ? __real_esp_partition_write(p, offset, data, size) : ESP_ERR_NOT_ALLOWED;
}
