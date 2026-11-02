#include "boot_policy.h"

#include <limits.h>
#include <string.h>

_Static_assert(sizeof(boot_record_t) == 32, "OTA selection ABI");
static const uint8_t journal_label[20] = {'S', 'T', 'K', 'Y', '-', 'B', 'O', 'O', 'T', '-',
                                          'V', '1', 255, 255, 255, 255, 255, 255, 255, 255};

bool boot_accept_physical_up(boot_reset_t reset) { return reset == BOOT_COLD || reset == BOOT_FAULT; }

void boot_button_tick(boot_button_t* b, bool low) {
  if (b->done) return;
  if (!b->held) {
    if (!low) {
      b->done = true;
      return;
    }
    if (++b->low_ticks == 60) b->held = true;
    return;
  }
  ++b->wait_ticks;
  b->release_ticks = low ? 0 : b->release_ticks + 1;
  if (b->release_ticks == 3) {
    b->done = true;
    b->select_seeedash = true;
  } else if (b->wait_ticks == 200)
    b->done = true;
}

uint32_t boot_seq_crc(uint32_t seq) {
  /* esp_rom_crc32_le(UINT32_MAX, little-endian ota_seq, 4). */
  uint32_t crc = 0;
  for (unsigned i = 0; i < 4; ++i) {
    crc ^= (seq >> (8 * i)) & 255;
    for (unsigned bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320u : 0);
  }
  return ~crc;
}

bool boot_record_valid(const boot_record_t* r) {
  /* NEW/PENDING_VERIFY belong to firmware updates, not this fixed-image selector. */
  return r->seq != 0 && r->seq != UINT32_MAX && (r->state == 2 || r->state == UINT32_MAX) &&
         r->crc == boot_seq_crc(r->seq);
}

boot_status_t boot_choose(const boot_ops_t* ops, boot_reset_t reset, bool up_held, boot_result_t* out) {
  *out = (boot_result_t){.target = BOOT_NONE};
  boot_record_t records[2];
  if (!ops->read(ops->context, 0, &records[0]) || !ops->read(ops->context, 1, &records[1]))
    return BOOT_READ_ERROR;
  int active = -1;
  for (int i = 0; i < 2; ++i) {
    if (boot_record_valid(&records[i]) &&
        (!ops->private_journal || !memcmp(records[i].label, journal_label, 20)) &&
        (active < 0 || records[i].seq > records[active].seq))
      active = i;
  }
  boot_target_t target = BOOT_CROSSPOINT;
  if (up_held)
    target = BOOT_SEEEDASH;
  else if ((reset == BOOT_DEEP_SLEEP || reset == BOOT_SOFTWARE) && active >= 0)
    target = (boot_target_t)((records[active].seq - 1) % 2);

  if (!ops->validate(ops->context, target)) {
    target = target == BOOT_CROSSPOINT ? BOOT_SEEEDASH : BOOT_CROSSPOINT;
    if (!ops->validate(ops->context, target)) return BOOT_NO_IMAGE;
    out->fallback = true;
  }
  if (active >= 0 && (records[active].seq - 1) % 2 == (unsigned)target) {
    out->target = target;
    return BOOT_OK;
  }

  uint32_t seq = active < 0 ? 1 : records[active].seq + 1;
  if (seq != UINT32_MAX && (seq - 1) % 2 != (unsigned)target) ++seq;
  if (seq == UINT32_MAX || seq == 0) return BOOT_SEQUENCE_EXHAUSTED;
  boot_record_t next;
  memset(&next, 255, sizeof(next));
  if (ops->private_journal) memcpy(next.label, journal_label, 20);
  next.seq = seq;
  next.state = 2; /* ESP_OTA_IMG_VALID: selecting an already pinned image, not an OTA trial. */
  next.crc = boot_seq_crc(seq);
  const unsigned sector = active == 0 ? 1 : 0;
  if (!ops->erase(ops->context, sector)) return BOOT_ERASE_ERROR;
  if (!ops->write(ops->context, sector, &next)) return BOOT_WRITE_ERROR;
  boot_record_t readback;
  if (!ops->read(ops->context, sector, &readback) || memcmp(&readback, &next, sizeof(next)))
    return BOOT_VERIFY_ERROR;
  out->target = target;
  out->wrote_selection = true;
  return BOOT_OK;
}
