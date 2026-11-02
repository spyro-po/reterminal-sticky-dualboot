#pragma once
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <vector>

#include "HalSystem.h"
#include "boot_contract.h"
extern "C" {
#include "boot_policy.h"
}
#define LOG_ERR(...) ((void)0)
#define LOG_INF(...) ((void)0)
using esp_partition_type_t = int;
using esp_partition_subtype_t = int;
constexpr int ESP_PARTITION_TYPE_DATA = 1, ESP_PARTITION_TYPE_APP = 0, ESP_PARTITION_TYPE_ANY = 255;
constexpr int ESP_PARTITION_SUBTYPE_DATA_NVS = 2, ESP_PARTITION_SUBTYPE_DATA_OTA = 0,
              ESP_PARTITION_SUBTYPE_DATA_PHY = 1, ESP_PARTITION_SUBTYPE_APP_OTA_0 = 16,
              ESP_PARTITION_SUBTYPE_APP_OTA_1 = 17, ESP_PARTITION_SUBTYPE_APP_TEST = 32,
              ESP_PARTITION_SUBTYPE_DATA_LITTLEFS = 131, ESP_PARTITION_SUBTYPE_DATA_COREDUMP = 3,
              ESP_PARTITION_SUBTYPE_ANY = 255;
constexpr int ESP_OK = 0, ESP_FAIL = -1, ESP_IMAGE_VERIFY = 0;
struct esp_partition_t {
  const char* label;
  int type, subtype;
  uint32_t address, size;
  bool encrypted, readonly;
};
struct esp_partition_pos_t {
  uint32_t offset, size;
};
struct esp_image_metadata_t {
  struct {
    unsigned spi_size, hash_appended;
  } image;
  uint32_t image_len;
  uint8_t image_digest[32];
};
namespace BoardConfig {
constexpr struct {
  struct {
    int latch0, latch1;
  } power;
} ACTIVE = {{45, 46}};
bool isSticky();
}  // namespace BoardConfig
constexpr int GPIO_NUM_45 = 45, GPIO_NUM_46 = 46, GPIO_MODE_OUTPUT = 1;
int gpio_hold_dis(int);
int gpio_set_level(int, int);
int gpio_set_direction(int, int);
int gpio_hold_en(int);
void esp_rom_delay_us(unsigned);
int esp_reset_reason();
const esp_partition_t* esp_partition_find_first(int, int, const char*);
const esp_partition_t* esp_ota_get_running_partition();
int* esp_partition_find(int, int, const char*);
int* esp_partition_next(int*);
int esp_partition_read(const esp_partition_t*, size_t, void*, size_t);
int esp_partition_write(const esp_partition_t*, size_t, const void*, size_t);
int esp_partition_erase_range(const esp_partition_t*, size_t, size_t);
int esp_image_verify(int, const esp_partition_pos_t*, esp_image_metadata_t*);
int esp_flash_read(void*, void*, uint32_t, uint32_t);
int esp_ota_set_boot_partition(const esp_partition_t*);
struct mbedtls_sha256_context {
  unsigned bytes;
};
void mbedtls_sha256_init(mbedtls_sha256_context*);
int mbedtls_sha256_starts(mbedtls_sha256_context*, int);
int mbedtls_sha256_update(mbedtls_sha256_context*, const unsigned char*, size_t);
int mbedtls_sha256_finish(mbedtls_sha256_context*, unsigned char*);
void mbedtls_sha256_free(mbedtls_sha256_context*);
extern bool allocationFails;
template <typename T>
std::unique_ptr<T> makeUniqueNoThrow() {
  return allocationFails ? nullptr : std::unique_ptr<T>(new T{});
}
