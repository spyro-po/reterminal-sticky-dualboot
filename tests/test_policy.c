#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

#include "boot_policy.h"

typedef struct {
  boot_record_t r[2];
  bool image[2];
  unsigned reads, erases, writes;
  int fail_read, cut_write;
  bool fail_erase, corrupt_readback;
} flash_t;
static bool read_flash(void* c, unsigned sector, boot_record_t* r) {
  flash_t* f = c;
  assert(sector < 2);
  if ((int)++f->reads == f->fail_read) return false;
  *r = f->r[sector];
  if (f->corrupt_readback && f->writes) r->crc ^= 1;
  return true;
}
static bool erase_flash(void* c, unsigned sector) {
  flash_t* f = c;
  assert(sector < 2);
  ++f->erases;
  memset(&f->r[sector], 255, sizeof(f->r[sector]));
  return !f->fail_erase;
}
static bool write_flash(void* c, unsigned sector, const boot_record_t* r) {
  flash_t* f = c;
  assert(sector < 2);
  ++f->writes;
  size_t count = f->cut_write < 0 ? sizeof(*r) : (size_t)f->cut_write;
  memcpy(&f->r[sector], r, count);
  return f->cut_write < 0;
}
static bool validate(void* c, boot_target_t target) { return ((flash_t*)c)->image[target]; }
static flash_t initial(void) {
  flash_t f = {.image = {true, true}, .fail_read = -1, .cut_write = -1};
  memset(f.r, 255, sizeof(f.r));
  return f;
}
static boot_ops_t operations(flash_t* f, bool tagged) {
  return (boot_ops_t){f, read_flash, erase_flash, write_flash, validate, tagged};
}
static void existing(flash_t* f, unsigned i, uint32_t seq, bool tagged) {
  memset(&f->r[i], 255, sizeof(f->r[i]));
  if (tagged) memcpy(f->r[i].label, "STKY-BOOT-V1", 12);
  f->r[i].seq = seq;
  f->r[i].state = 2;
  f->r[i].crc = boot_seq_crc(seq);
}

int main(void) {
  assert(boot_accept_physical_up(BOOT_COLD));
  assert(boot_accept_physical_up(BOOT_FAULT));
  assert(!boot_accept_physical_up(BOOT_DEEP_SLEEP));
  assert(!boot_accept_physical_up(BOOT_SOFTWARE));
  boot_result_t result;
  flash_t f = initial();
  boot_ops_t ops = operations(&f, true);
  assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_OK);
  assert(result.target == BOOT_CROSSPOINT && f.writes == 1 && f.r[0].seq == 2);
  assert(boot_choose(&ops, BOOT_DEEP_SLEEP, false, &result) == BOOT_OK && f.writes == 1);
  assert(boot_choose(&ops, BOOT_COLD, true, &result) == BOOT_OK && result.target == BOOT_SEEEDASH);
  assert(f.r[1].seq == 3 && f.writes == 2);
  assert(boot_choose(&ops, BOOT_DEEP_SLEEP, false, &result) == BOOT_OK && result.target == BOOT_SEEEDASH &&
         f.writes == 2);
  assert(boot_choose(&ops, BOOT_SOFTWARE, false, &result) == BOOT_OK && result.target == BOOT_SEEEDASH);
  assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_OK && result.target == BOOT_CROSSPOINT);
  assert(boot_choose(&ops, BOOT_FAULT, true, &result) == BOOT_OK && result.target == BOOT_SEEEDASH);
  assert(boot_choose(&ops, BOOT_FAULT, false, &result) == BOOT_OK && result.target == BOOT_CROSSPOINT);

  for (unsigned mask = 0; mask < 4; ++mask)
    for (unsigned hold = 0; hold < 2; ++hold) {
      f = initial();
      ops = operations(&f, true);
      f.image[0] = mask & 1;
      f.image[1] = mask & 2;
      boot_status_t status = boot_choose(&ops, BOOT_COLD, hold, &result);
      if (!mask)
        assert(status == BOOT_NO_IMAGE && result.target == BOOT_NONE && !f.writes && !f.erases);
      else {
        assert(status == BOOT_OK && f.image[result.target]);
        assert(result.fallback == !f.image[hold ? 0 : 1]);
      }
    }
  for (int cut = 0; cut <= 32; ++cut) {
    f = initial();
    ops = operations(&f, true);
    existing(&f, 0, 1, true);
    const boot_record_t old = f.r[0];
    f.cut_write = cut;
    assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_WRITE_ERROR && result.target == BOOT_NONE);
    assert(!memcmp(&old, &f.r[0], sizeof(old)));
    f.cut_write = -1;
    assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_OK && result.target == BOOT_CROSSPOINT);
  }
  f = initial();
  ops = operations(&f, true);
  existing(&f, 0, 1, true);
  f.fail_erase = true;
  assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_ERASE_ERROR && result.target == BOOT_NONE);
  f = initial();
  ops = operations(&f, true);
  f.fail_read = 1;
  assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_READ_ERROR && !f.erases);
  f = initial();
  ops = operations(&f, true);
  f.fail_read = 2;
  assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_READ_ERROR && !f.erases);
  f = initial();
  ops = operations(&f, true);
  f.fail_read = 3;
  assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_VERIFY_ERROR && result.target == BOOT_NONE);
  f = initial();
  ops = operations(&f, true);
  f.corrupt_readback = true;
  assert(boot_choose(&ops, BOOT_COLD, false, &result) == BOOT_VERIFY_ERROR && result.target == BOOT_NONE);
  f = initial();
  ops = operations(&f, true);
  existing(&f, 0, UINT32_MAX - 1, true);
  assert(boot_choose(&ops, BOOT_COLD, true, &result) == BOOT_SEQUENCE_EXHAUSTED && !f.erases);
  f = initial();
  ops = operations(&f, true);
  existing(&f, 0, 101, false);
  assert(boot_choose(&ops, BOOT_DEEP_SLEEP, false, &result) == BOOT_OK && result.target == BOOT_CROSSPOINT);
  for (unsigned state = 0; state < 5; ++state) {
    f = initial();
    existing(&f, 0, 1, true);
    f.r[0].state = state;
    assert(boot_record_valid(&f.r[0]) == (state == 2));
  }
  for (unsigned hold = 0; hold <= 260; ++hold) {
    boot_button_t b = {0};
    for (unsigned i = 0; i < hold; ++i) boot_button_tick(&b, true);
    for (unsigned i = 0; i < 3; ++i) boot_button_tick(&b, false);
    assert(b.done && b.select_seeedash == (hold >= 60 && hold <= 257));
  }
  boot_button_t b = {0};
  for (unsigned i = 0; i < 60; ++i) boot_button_tick(&b, true);
  boot_button_tick(&b, false);
  boot_button_tick(&b, true);
  boot_button_tick(&b, false);
  boot_button_tick(&b, false);
  assert(!b.done);
  boot_button_tick(&b, false);
  assert(b.done && b.select_seeedash);
  printf(
      "PASS: reset policy, tagged journal, all 33 partial-write cuts, failures, sequence limit, image "
      "fallback, button bounds\n");
}
