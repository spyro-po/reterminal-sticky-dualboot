#include "test_menu_api.h"
using Status = HalSystem::SeeedashBootStatus;
static esp_partition_t parts[] = {{"nvs", 1, 2, 0x9000, 0x7d000, false, false},
                                  {"otadata", 1, 0, 0x86000, 0x2000, false, false},
                                  {"phy_init", 1, 1, 0x88000, 0x1000, false, false},
                                  {"cp_nvs", 1, 2, 0x89000, 0x5000, false, false},
                                  {"bootstate", 1, 64, 0x8e000, 0x2000, false, false},
                                  {"app0", 0, 16, 0x90000, 0x600000, false, false},
                                  {"app1", 0, 32, 0x690000, 0x600000, false, false},
                                  {"sys_storage", 1, 131, 0xc90000, 0x930000, false, false},
                                  {"usr_storage", 1, 131, 0x15c0000, 0xa00000, false, false},
                                  {"coredump", 1, 3, 0x1fc0000, 0x40000, false, false}};
static boot_record_t records[2];
static uint8_t bootImage[480];
static bool board = true, badImage, badBoot, badDigest, flashReadFails, hashFails, eraseFails,
            corruptReadback;
static int entries = 10, readCount, failRead = -1, writeCount, eraseCount, writeCut = -1, powerFail = -1;
static std::vector<int> powerEvents;
bool allocationFails = false;
static const uint8_t seeedSha[] = {0xb7, 0x18, 0x44, 0x69, 0xaa, 0x47, 0xa6, 0x80, 0xc2, 0x93, 0x84,
                                   0x8b, 0x26, 0x43, 0x42, 0x70, 0x5c, 0xc8, 0x17, 0x68, 0x9f, 0x4f,
                                   0x76, 0x93, 0xd2, 0xe6, 0x74, 0xf0, 0xab, 0x23, 0xee, 0xc7};
bool BoardConfig::isSticky() { return board; }
const esp_partition_t* esp_partition_find_first(int type, int sub, const char* label) {
  for (auto& p : parts)
    if ((type == 255 || p.type == type) && (sub == 255 || p.subtype == sub) &&
        (!label || !strcmp(label, p.label)))
      return &p;
  return nullptr;
}
const esp_partition_t* esp_ota_get_running_partition() { return &parts[6]; }
int* esp_partition_find(int, int, const char*) {
  static int i;
  i = 0;
  return entries ? &i : nullptr;
}
int* esp_partition_next(int* i) { return ++*i < entries ? i : nullptr; }
int esp_partition_read(const esp_partition_t* p, size_t off, void* out, size_t size) {
  assert(p == &parts[4] && off % 4096 == 0 && off / 4096 < 2 && size == 32);
  if (++readCount == failRead) return ESP_FAIL;
  memcpy(out, &records[off / 4096], size);
  if (corruptReadback && writeCount) static_cast<boot_record_t*>(out)->crc ^= 1;
  return ESP_OK;
}
int esp_partition_write(const esp_partition_t* p, size_t off, const void* data, size_t size) {
  assert(p == &parts[4] && off % 4096 == 0 && off / 4096 < 2 && size == 32);
  ++writeCount;
  memcpy(&records[off / 4096], data, writeCut < 0 ? size : static_cast<size_t>(writeCut));
  return writeCut < 0 ? ESP_OK : ESP_FAIL;
}
int esp_partition_erase_range(const esp_partition_t* p, size_t off, size_t size) {
  assert(p == &parts[4] && off % 4096 == 0 && off / 4096 < 2 && size == 4096);
  ++eraseCount;
  if (eraseFails) return ESP_FAIL;
  memset(&records[off / 4096], 255, 32);
  return ESP_OK;
}
int esp_image_verify(int, const esp_partition_pos_t* pos, esp_image_metadata_t* out) {
  assert((pos->offset == 0 && pos->size == 0x8000) || (pos->offset == 0x90000 && pos->size == 0x600000));
  *out = {};
  out->image = {5, 1};
  if (pos->offset == 0) {
    if (badBoot) return ESP_FAIL;
    out->image_len = 512;
    memset(out->image_digest, badDigest ? 9 : 7, 32);
  } else {
    if (badImage) return ESP_FAIL;
    out->image_len = 3261088;
    memcpy(out->image_digest, seeedSha, 32);
  }
  return ESP_OK;
}
int esp_flash_read(void*, void* out, uint32_t off, uint32_t size) {
  assert(off + size <= 480);
  if (flashReadFails) return ESP_FAIL;
  memcpy(out, bootImage + off, size);
  return ESP_OK;
}
int esp_ota_set_boot_partition(const esp_partition_t*) {
  assert(false && "Native OTA must not select the custom loader");
  return ESP_FAIL;
}
int event(int n) {
  powerEvents.push_back(n);
  return static_cast<int>(powerEvents.size()) == powerFail ? ESP_FAIL : ESP_OK;
}
int gpio_hold_dis(int p) { return event(p); }
int gpio_set_level(int p, int v) { return event(p * 10 + v); }
int gpio_set_direction(int p, int) { return event(p * 100); }
int gpio_hold_en(int p) { return event(p * 1000); }
void esp_rom_delay_us(unsigned delay) {
  assert(delay == 2);
  event(2);
}
int esp_reset_reason() { return 3; }
void mbedtls_sha256_init(mbedtls_sha256_context* c) { c->bytes = 0; }
int mbedtls_sha256_starts(mbedtls_sha256_context*, int) { return hashFails ? -1 : 0; }
int mbedtls_sha256_update(mbedtls_sha256_context* c, const unsigned char*, size_t n) {
  c->bytes += n;
  return 0;
}
int mbedtls_sha256_finish(mbedtls_sha256_context* c, unsigned char* out) {
  assert(c->bytes == 480);
  memset(out, 7, 32);
  return 0;
}
void mbedtls_sha256_free(mbedtls_sha256_context*) {}
static void initial() {
  board = true;
  entries = 10;
  allocationFails = badImage = badBoot = badDigest = flashReadFails = hashFails = eraseFails =
      corruptReadback = false;
  readCount = writeCount = eraseCount = 0;
  failRead = writeCut = powerFail = -1;
  powerEvents.clear();
  memset(bootImage, 0xaa, sizeof(bootImage));
  memcpy(bootImage + 250, STICKY_BOOT_CONTRACT, sizeof(STICKY_BOOT_CONTRACT) - 1);
  memset(records, 255, sizeof(records));
  memcpy(records[0].label, "STKY-BOOT-V1", 12);
  records[0].seq = 2;
  records[0].state = 2;
  records[0].crc = boot_seq_crc(2);
}
static bool rd(void*, unsigned i, boot_record_t* r) {
  *r = records[i];
  return true;
}
static bool er(void*, unsigned i) {
  memset(&records[i], 255, 32);
  return true;
}
static bool wr(void*, unsigned i, const boot_record_t* r) {
  records[i] = *r;
  return true;
}
static bool valid(void*, boot_target_t) { return true; }
static boot_target_t boot(boot_reset_t reason, bool up) {
  boot_ops_t ops = {nullptr, rd, er, wr, valid, true};
  boot_result_t out;
  assert(boot_choose(&ops, reason, boot_accept_physical_up(reason) && up, &out) == BOOT_OK);
  return out.target;
}
int main() {
  initial();
  assert(HalSystem::checkSeeedashBoot() == Status::Ready && !eraseCount && !writeCount &&
         powerEvents.empty());
  for (auto& p : parts) {
    auto saved = p;
    p.address += 4096;
    assert(HalSystem::selectSeeedashBoot() == Status::LayoutMismatch);
    p = saved;
    p.encrypted = true;
    assert(HalSystem::checkSeeedashBoot() == Status::LayoutMismatch);
    p = saved;
    p.readonly = true;
    assert(HalSystem::checkSeeedashBoot() == Status::LayoutMismatch);
    p = saved;
  }
  entries = 11;
  assert(HalSystem::checkSeeedashBoot() == Status::LayoutMismatch);
  entries = 10;
  parts[6].subtype = 17;
  assert(HalSystem::checkSeeedashBoot() == Status::LayoutMismatch);
  parts[6].subtype = 32;
  assert(!HalSystem::firmwareUpdatesAllowed());
  initial();
  board = false;
  assert(HalSystem::checkSeeedashBoot() == Status::LayoutMismatch);
  initial();
  allocationFails = true;
  assert(HalSystem::checkSeeedashBoot() == Status::MemoryUnavailable);
  initial();
  badBoot = true;
  assert(HalSystem::checkSeeedashBoot() == Status::BootloaderMismatch);
  initial();
  badDigest = true;
  assert(HalSystem::checkSeeedashBoot() == Status::BootloaderMismatch);
  initial();
  memset(bootImage, 0xaa, sizeof(bootImage));
  assert(HalSystem::checkSeeedashBoot() == Status::BootloaderMismatch);
  initial();
  flashReadFails = true;
  assert(HalSystem::checkSeeedashBoot() == Status::BootloaderMismatch);
  initial();
  hashFails = true;
  assert(HalSystem::checkSeeedashBoot() == Status::BootloaderMismatch);
  initial();
  badImage = true;
  assert(HalSystem::checkSeeedashBoot() == Status::ImageMismatch);
  initial();
  memset(records, 255, sizeof(records));
  assert(HalSystem::checkSeeedashBoot() == Status::JournalInvalid);
  initial();
  failRead = 1;
  assert(HalSystem::selectSeeedashBoot() == Status::JournalReadFailed && powerEvents.empty());
  initial();
  powerFail = 1;
  assert(HalSystem::selectSeeedashBoot() == Status::PowerHoldFailed && !writeCount);
  initial();
  eraseFails = true;
  assert(HalSystem::selectSeeedashBoot() == Status::JournalEraseFailed && !writeCount);
  initial();
  corruptReadback = true;
  assert(HalSystem::selectSeeedashBoot() == Status::JournalVerifyFailed);
  initial();
  records[0].seq = 0xfffffffe;
  records[0].crc = boot_seq_crc(records[0].seq);
  assert(HalSystem::selectSeeedashBoot() == Status::JournalExhausted && !eraseCount);
  for (int cut = 0; cut <= 32; ++cut) {
    initial();
    auto old = records[0];
    writeCut = cut;
    assert(HalSystem::selectSeeedashBoot() == Status::JournalWriteFailed);
    assert(!memcmp(&old, &records[0], 32));
    assert(boot(BOOT_COLD, false) == BOOT_CROSSPOINT);
  }
  initial();
  assert(boot(BOOT_DEEP_SLEEP, false) == BOOT_CROSSPOINT);
  assert(boot(BOOT_DEEP_SLEEP, true) == BOOT_CROSSPOINT);
  assert(boot(BOOT_SOFTWARE, true) == BOOT_CROSSPOINT);
  assert(boot(BOOT_SOFTWARE, false) == BOOT_CROSSPOINT);
  assert(HalSystem::selectSeeedashBoot() == Status::Ready && eraseCount == 1 && writeCount == 1);
  assert((powerEvents == std::vector<int>{45, 451, 4500, 46, 460, 4600, 2, 461, 45000, 46000}));
  assert(boot(BOOT_SOFTWARE, false) == BOOT_SEEEDASH);
  assert(boot(BOOT_DEEP_SLEEP, false) == BOOT_SEEEDASH);
  assert(boot(BOOT_DEEP_SLEEP, true) == BOOT_SEEEDASH);
  assert(boot(BOOT_COLD, false) == BOOT_CROSSPOINT);
  assert(boot(BOOT_COLD, true) == BOOT_SEEEDASH);
  puts(
      "PASS: real HAL menu selector, protected layout, boot ABI/digest gates, power sequence, journal I/O/33 "
      "cuts, SW/deep/reset/Up transitions; native OTA never called");
}
