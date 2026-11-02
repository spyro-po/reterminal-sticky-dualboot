# Architecture

## Partition contract

All entries have flags **0**. Offsets and sizes are hexadecimal; Flash ends at `0x2000000`.

| Name | Type / subtype | Offset | Size | Owner |
| --- | --- | --- | --- | --- |
| nvs | data / nvs | 0x9000 | 0x7d000 | Seeedash; remains the first NVS partition |
| otadata | data / ota | 0x86000 | 0x2000 | Vendor/native OTA metadata; not the selector |
| phy_init | data / phy | 0x88000 | 0x1000 | Factory |
| cp_nvs | data / nvs | 0x89000 | 0x5000 | CrossPoint only |
| bootstate | data / 0x40 | 0x8e000 | 0x2000 | Private two-sector selection journal |
| app0 | app / ota_0 | 0x90000 | 0x600000 | Unmodified Seeedash 1.2.0 |
| app1 | app / test | 0x690000 | 0x600000 | CrossPoint |
| sys_storage | data / 0x83 | 0xc90000 | 0x930000 | Factory LittleFS |
| usr_storage | data / 0x83 | 0x15c0000 | 0xa00000 | Factory LittleFS |
| coredump | data / coredump | 0x1fc0000 | 0x40000 | Reserved |

Custom bootloader at `0x0` must end before `0x8000`; the partition sector is `0x8000..0x9000`. Canonical 3072-byte table SHA-256: `51fc24d4da9b5bafb4bef860874d891d6ad29044c1724e5f05882724d83be812`. Padded with 1024 erased `FF` bytes, the device sector SHA-256 is `a598360248f118f3c4ba348a2c2dd7e72839e6ead475f2b03d4ca6d1a328541b`.

The historic auxiliary IDF project's generic three-partition table was not the installed table. This release explicitly selects the custom CSV in **both** build paths, and checks output against an independent byte-level generator and ESP-IDF's generator. No automatic device repartitioning is implemented.

## Loader and selection

The ESP-IDF v5.4 loader validates the complete supported layout and checks the selected image, and any fallback, against their pinned identities. CrossPoint's digest is generated from the actual linked application before building the loader. The factory Seeedash digest and length are fixed to 1.2.0. The appended ESP image SHA-256 is explicitly checked where IDF's normal non-secure path may skip it. SHA checks are integrity gates, not signatures.

`STKY-BOOT-V1` uses two Flash sectors for tagged journal entries and readback-verified inactive-sector transactions. Cold/physical Reset and faults normally select CrossPoint; qualified Up selects Seeedash on cold/fault only. Software restart and deep-sleep wake resume the journal selection. Some panic resets can report a software reason; physical Reset is the reliable return gesture. Full power loss returns to the cold-start policy.

Up/GPIO5's RTC and digital pad state is restored on every boot. The physical selector requires 600 ms low, release within the next 2000 ms and 30 ms stable release. It is ignored during software/deep-sleep resumes. RTC RAM is not the selection store.

The power latch requires GPIO45 (D) high before GPIO46 (clock) rises. The menu prepares and individually holds these pins high before committing the private selection and calling `ESP.restart()`. It does not enter sleep, clear NVS or write native OTA metadata. Validation errors distinguish layout, Seeedash image, loader integrity/ABI, allocation, journal and power-latch failures. A journal error can leave a committed request despite an error return; use physical Reset before retrying or sleeping after such a failure.

## NVS and filesystems

Link wrappers redirect Arduino startup, Preferences, default NVS calls and Wi-Fi's NVS callback to `cp_nvs`. Named access to vendor NVS is rejected. The final ELF/map audit checks the wrappers actually survive linking. Partition and raw Flash guards deny vendor/application/filesystem writes outside the intended private scope; chip erase and filesystem registration/format are rejected. SPIFFS/LittleFS components must remain absent from the linked application. These measures are cooperative firmware integration, not a hardware sandbox for hostile code.

A library's recovery from corrupt CP NVS can still erase **cp_nvs**. That may remove protected-book encryption keys. It must not erase vendor NVS; test coverage exercises the Arduino erase-denial path. Book storage formats and paths are unchanged.

## OTA boundary

Only Seeedash `app0` is a native OTA slot. CrossPoint's `test` subtype excludes it from standard `esp_ota_get_next_update_partition` rotation. CrossPoint's higher-level updaters and lower-level write paths are blocked. A stock Seeedash custom/raw/resource updater can still overwrite arbitrary extents; the project cannot sandbox it without changing the vendor firmware. **Every OTA/update path is unsupported and forbidden**, including resource and child-device updates. Keep Seeedash offline and unpaired. Only a preflight-checked manual matched-pair update is supported by this release's instructions.

## Scope and maintenance

The eight-file patch preserves the Stage 4 runtime implementation. Reader+ supplied a conceptual validate/persist/restart reference; native `esp_ota_set_boot_partition` is not used for this selector. A complete image includes factory bytes and is built only locally. No app, key, filesystem or journal migration is hidden in release packaging.

The maintainer owns the ABI and paired image pins. Future dependency updates require a new link audit, partition/flash-boundary tests and fresh hardware verification. Fixed source/tool versions make the recipe traceable; full cross-host reproducibility is a separate claim.
