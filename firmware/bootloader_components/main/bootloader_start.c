/* SPDX-License-Identifier: Apache-2.0
 * SPDX-FileCopyrightText: 2015-2022 Espressif Systems (Shanghai) CO LTD
 * Adapted from ESP-IDF v5.4 bootloader startup (Espressif Systems).
 * Dual-boot integration changes: 2026 reTerminal Sticky Dual Boot contributors.
 */
/* Experimental second-stage bootloader. No device writes are authorized by building it. */
#include <string.h>

#include "boot_contract.h"
#include "boot_policy.h"
#include "bootloader_common.h"
#include "bootloader_flash.h"
#include "bootloader_flash_priv.h"
#include "bootloader_init.h"
#include "bootloader_utility.h"
#include "esp_flash_encrypt.h"
#include "esp_image_format.h"
#include "esp_rom_gpio.h"
#include "esp_rom_sys.h"
#include "esp_secure_boot.h"
#include "hal/gpio_ll.h"
#include "hal/rtc_io_ll.h"
#include "sdkconfig.h"
#include "soc/gpio_struct.h"
#include "soc/rtc_cntl_reg.h"

#if CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE || CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK || \
    CONFIG_BOOTLOADER_SKIP_VALIDATE_IN_DEEP_SLEEP
#error "The prototype requires fixed-image selection without rollback or deep-sleep validation bypass"
#endif

static const uint8_t seeedash_sha[32] = {0xb7, 0x18, 0x44, 0x69, 0xaa, 0x47, 0xa6, 0x80, 0xc2, 0x93, 0x84,
                                         0x8b, 0x26, 0x43, 0x42, 0x70, 0x5c, 0xc8, 0x17, 0x68, 0x9f, 0x4f,
                                         0x76, 0x93, 0xd2, 0xe6, 0x74, 0xf0, 0xab, 0x23, 0xee, 0xc7};
#include "crosspoint_pin.h"
static const uint8_t crosspoint_sha[32] = CROSSPOINT_IMAGE_SHA_BYTES;
typedef struct {
  const bootloader_state_t* bs;
  uint32_t offset;
} flash_context_t;

static void early_power_latch(void) {
  /* U3 is a D flip-flop: D=GPIO45 must be high before the rising CP=GPIO46 edge. */
  esp_rom_gpio_pad_select_gpio(45);
  gpio_ll_set_level(&GPIO, 45, 1);
  gpio_ll_output_enable(&GPIO, 45);
  gpio_ll_hold_dis(&GPIO, 45);
  esp_rom_gpio_pad_select_gpio(46);
  gpio_ll_set_level(&GPIO, 46, 0);
  gpio_ll_output_enable(&GPIO, 46);
  gpio_ll_hold_dis(&GPIO, 46);
  gpio_ll_deep_sleep_hold_dis(&GPIO);
  esp_rom_delay_us(2);
  gpio_ll_set_level(&GPIO, 46, 1);
}

static bool sample_up(bool allow_selection) {
  /* Seeedash may have isolated this RTC-capable pad while sleeping. */
  rtcio_ll_force_hold_disable(5);
  rtcio_ll_function_select(5, RTCIO_LL_FUNC_DIGITAL);
  esp_rom_gpio_pad_select_gpio(5);
  gpio_ll_sleep_sel_dis(&GPIO, 5);
  gpio_ll_output_disable(&GPIO, 5);
  gpio_ll_input_enable(&GPIO, 5);
  gpio_ll_pullup_en(&GPIO, 5);
  gpio_ll_pulldown_dis(&GPIO, 5);
  /* R60/C47 is 10 kohm/100 nF. Allow a released input to charge before sampling. */
  esp_rom_delay_us(10000);
  esp_rom_printf("Sticky Up: initial_low=%d\n", gpio_ll_get_level(&GPIO, 5) == 0);
  if (!allow_selection) {
    esp_rom_printf("Sticky Up: selection ignored for software/deep-sleep reset\n");
    return false;
  }
  boot_button_t button = {0};
  while (!button.done) {
    esp_rom_delay_us(10000);
    boot_button_tick(&button, gpio_ll_get_level(&GPIO, 5) == 0);
  }
  esp_rom_printf("Sticky Up: qualified=%d low_ticks=%u release_ticks=%u wait_ticks=%u\n",
                 button.select_seeedash, button.low_ticks, button.release_ticks, button.wait_ticks);
  return button.select_seeedash;
}

static bool read_record(void* ctx, unsigned sector, boot_record_t* record) {
  const flash_context_t* flash = ctx;
  return sector < 2 &&
         bootloader_flash_read(flash->offset + sector * 4096, record, sizeof(*record), false) == ESP_OK;
}
static bool erase_record(void* ctx, unsigned sector) {
  const flash_context_t* flash = ctx;
  return sector < 2 && bootloader_flash_erase_sector(flash->offset / 4096 + sector) == ESP_OK;
}
static bool write_record(void* ctx, unsigned sector, const boot_record_t* record) {
  const flash_context_t* flash = ctx;
  /* Check the host-tested CRC implementation against IDF's native helper. */
  esp_ota_select_entry_t native;
  memcpy(&native, record, sizeof(native));
  if (native.crc != bootloader_common_ota_select_crc(&native)) return false;
  return sector < 2 &&
         bootloader_flash_write(flash->offset + sector * 4096, &native, sizeof(native), false) == ESP_OK;
}

static bool validate_image(void* ctx, boot_target_t target) {
  const flash_context_t* flash = ctx;
  if (flash->offset == 0x86000 && target != BOOT_SEEEDASH) return false;
  if (target == BOOT_CROSSPOINT) {
    uint8_t provisioned = 0;
    for (unsigned i = 0; i < sizeof(crosspoint_sha); ++i) provisioned |= crosspoint_sha[i];
    if (!provisioned) return false;
  }
  const bootloader_state_t* bs = flash->bs;
  const esp_partition_pos_t* part = target == BOOT_SEEEDASH ? &bs->ota[0] : &bs->test;
  esp_image_metadata_t metadata = {0};
  if (esp_image_verify(ESP_IMAGE_VERIFY, part, &metadata) != ESP_OK || metadata.image.spi_size != 5)
    return false;
  const uint8_t* sha = target == BOOT_SEEEDASH ? seeedash_sha : crosspoint_sha;
  if (metadata.image_len != (target == BOOT_SEEEDASH ? 3261088 : CROSSPOINT_IMAGE_LEN)) return false;
  return metadata.image.hash_appended == 1 && !memcmp(metadata.image_digest, sha, 32);
}

static bool supported_layout(const bootloader_state_t* bs) {
  /* Only the protected experimental layout is accepted; vendor data addresses stay fixed. */
  const uint32_t offsets[10] = {0x9000,  0x86000,  0x88000,  0x89000,   0x8e000,
                                0x90000, 0x690000, 0xc90000, 0x15c0000, 0x1fc0000};
  const uint32_t sizes[10] = {0x7d000,  0x2000,   0x1000,   0x5000,   0x2000,
                              0x600000, 0x600000, 0x930000, 0xa00000, 0x40000};
  const uint8_t types[10] = {1, 1, 1, 1, 1, 0, 0, 1, 1, 1};
  const uint8_t subtypes[10] = {2, 0, 1, 2, 64, 16, 32, 131, 131, 3};
  static const char* const labels[10] = {"nvs",  "otadata", "phy_init",    "cp_nvs",      "bootstate",
                                         "app0", "app1",    "sys_storage", "usr_storage", "coredump"};
  esp_partition_info_t entry;
  for (unsigned i = 0; i < 10; ++i) {
    if (bootloader_flash_read(0x8000 + i * 32, &entry, sizeof(entry), false) != ESP_OK ||
        entry.magic != ESP_PARTITION_MAGIC || entry.type != types[i] || entry.subtype != subtypes[i] ||
        entry.pos.offset != offsets[i] || entry.pos.size != sizes[i] || entry.flags != 0 ||
        strncmp((const char*)entry.label, labels[i], 16))
      return false;
  }
  /* The next record must be the MD5 trailer, not an additional OTA destination. */
  if (bootloader_flash_read(0x8000 + 10 * 32, &entry, sizeof(entry), false) != ESP_OK ||
      entry.magic != 0xebeb)
    return false;
  return bs->app_count == 1 && bs->ota_info.offset == 0x86000 && bs->ota_info.size == 0x2000 &&
         bs->ota[0].offset == 0x90000 && bs->test.offset == 0x690000;
}

void __attribute__((noreturn)) call_start_cpu0(void) {
  early_power_latch();
  if (bootloader_init() != ESP_OK) bootloader_reset();
  esp_rom_printf("Sticky selector: %s\n", STICKY_BOOT_CONTRACT);
  if (esp_flash_encryption_enabled() || esp_secure_boot_enabled()) {
    esp_rom_printf("Prototype refuses encrypted/secure-boot deployments\n");
    bootloader_reset();
  }
  bootloader_state_t bs = {0};
  if (!bootloader_utility_load_partition_table(&bs) || !supported_layout(&bs)) bootloader_reset();
  const int reason = esp_rom_get_reset_reason(0);
  boot_reset_t reset = BOOT_FAULT;
  if (reason == RESET_REASON_CHIP_POWER_ON || reason == RESET_REASON_CHIP_BROWN_OUT)
    reset = BOOT_COLD;
  else if (reason == RESET_REASON_CORE_DEEP_SLEEP)
    reset = BOOT_DEEP_SLEEP;
  else if (reason == RESET_REASON_CORE_SW || reason == RESET_REASON_CPU0_SW)
    reset = BOOT_SOFTWARE;
  esp_rom_printf("Sticky reset: raw=%d class=%d; latch D45 then CLK46 asserted\n", reason, reset);
  flash_context_t context = {&bs, 0x8e000};
  const boot_ops_t ops = {&context, read_record, erase_record, write_record, validate_image, true};
  boot_result_t result;
  const bool physical_up = sample_up(boot_accept_physical_up(reset));
  const boot_status_t status = boot_choose(&ops, reset, physical_up, &result);
  esp_rom_printf("Dual boot prototype: status=%d target=%d fallback=%d wrote=%d\n", status, result.target,
                 result.fallback, result.wrote_selection);
  if (status != BOOT_OK) bootloader_reset();
  if (result.target == BOOT_SEEEDASH) {
    /* Initialise/rebind native OTA metadata to the sole OTA slot for Seeedash's own APIs. */
    flash_context_t ota_context = {&bs, 0x86000};
    const boot_ops_t ota_ops = {&ota_context, read_record, erase_record, write_record, validate_image, false};
    boot_result_t ota_result;
    if (boot_choose(&ota_ops, BOOT_COLD, true, &ota_result) != BOOT_OK || ota_result.target != BOOT_SEEEDASH)
      bootloader_reset();
  }
  /* Prevent IDF's generic fallback from loading any image that was not pinned above. */
  bootloader_state_t isolated = {0};
  isolated.app_count = 1;
  isolated.ota_info = bs.ota_info;
  if (result.target == BOOT_CROSSPOINT)
    isolated.test = bs.test;
  else
    isolated.ota[0] = bs.ota[0];
  bootloader_utility_load_boot_image(&isolated, result.target == BOOT_CROSSPOINT ? TEST_APP_INDEX : 0);
  bootloader_reset();
  while (true) {
  }
}

struct _reent* __getreent(void) { return _GLOBAL_REENT; }
