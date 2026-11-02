#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum { BOOT_SEEEDASH = 0, BOOT_CROSSPOINT = 1, BOOT_NONE = -1 } boot_target_t;
typedef enum { BOOT_COLD, BOOT_SOFTWARE, BOOT_DEEP_SLEEP, BOOT_FAULT } boot_reset_t;
typedef enum {
  BOOT_OK,
  BOOT_NO_IMAGE,
  BOOT_READ_ERROR,
  BOOT_ERASE_ERROR,
  BOOT_WRITE_ERROR,
  BOOT_VERIFY_ERROR,
  BOOT_SEQUENCE_EXHAUSTED
} boot_status_t;

typedef struct {
  uint32_t seq;
  uint8_t label[20];
  uint32_t state;
  uint32_t crc;
} boot_record_t;

typedef struct {
  void* context;
  bool (*read)(void*, unsigned, boot_record_t*);
  bool (*erase)(void*, unsigned);
  bool (*write)(void*, unsigned, const boot_record_t*);
  bool (*validate)(void*, boot_target_t);
  bool private_journal;
} boot_ops_t;

typedef struct {
  boot_target_t target;
  bool fallback;
  bool wrote_selection;
} boot_result_t;

/* One tick is 10 ms. A qualified hold must end with a debounced release. */
typedef struct {
  unsigned low_ticks, release_ticks, wait_ticks;
  bool held, done, select_seeedash;
} boot_button_t;
/* Physical Up is a recovery gesture only at a cold/fault reset, not at wake/restart. */
bool boot_accept_physical_up(boot_reset_t reset);
void boot_button_tick(boot_button_t* button, bool low);
uint32_t boot_seq_crc(uint32_t seq);
bool boot_record_valid(const boot_record_t* record);
boot_status_t boot_choose(const boot_ops_t* ops, boot_reset_t reset, bool up_held, boot_result_t* result);
