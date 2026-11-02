# Update / Preserve Data

Only for a device already using the exact **protected-reference** table. This is not a factory-device migration. The current table must contain `app1` subtype **test (0x20)** at `0x690000`, private `cp_nvs` and `bootstate`, and all vendor data extents unchanged. A valid MD5 alone does not prove layout compatibility.

Build a new matched pair using [BUILD.md](BUILD.md). There is no public precompiled CrossPoint asset in this source release. Retain your last verified working **pair** for rollback. Do not install the bootloader alone.

Use esptool **4.12.0** and the path/port variables from [INSTALL.md](INSTALL.md). Establish ROM access, inspect `get_security_info` and `flash_id`, and stop if the device is not the supported unrestricted 32 MiB model. Keep the chip in ROM/stub with `--after no_reset` until readback is finished so application writes cannot change data between captures.

```sh
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset read_flash 0x0 0x2000000 /private/path/sticky-before.bin
sha256sum /private/path/sticky-before.bin
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset verify_flash 0x0 /private/path/sticky-before.bin
.venv/bin/python scripts/preflight.py --bundle .local/out/build1/update --backup /private/path/sticky-before.bin
```

The offline preflight checks both manifest hashes, image checksums and appended SHA-256, paired digest, selector ABI, installed Seeedash 1.2.0, the exact table, full sector erase ranges and unchanged protected bytes in a simulated update. It neither opens a serial device nor flashes anything. A standalone 3072/4096-byte table can be checked using `--table file.bin`, but that is not a replacement for the full backup.

After a successful full-backup preflight, write **exactly two segments**, with stable USB power:

```sh
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 .local/out/build1/update/bootloader.bin 0x690000 .local/out/build1/update/crosspoint.bin
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset verify_flash 0x0 .local/out/build1/update/bootloader.bin 0x690000 .local/out/build1/update/crosspoint.bin
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset read_flash 0x0 0x2000000 /private/path/sticky-after-before-boot.bin
.venv/bin/python scripts/preflight.py --bundle .local/out/build1/update --backup /private/path/sticky-before.bin --after /private/path/sticky-after-before-boot.bin
```

Do not erase the chip or add table, `boot_app0`, OTA metadata, NVS, `bootstate` or filesystem images. This update writes only code sectors; all other partitions are preserved. Normal application writes after startup remain possible and are outside this promise.

Two code writes are **not power-fail atomic**. If interrupted, restore the exact verified backup through ROM download, or complete the same matched pair if recovery remains possible. A loader rejecting a mismatched CrossPoint and falling back to Seeedash does not mean the update succeeded. Do not disable integrity pins.

Reset without Up, then test EPUB reading, menu switching on USB and battery, Reset return and separate sleep/wake. Keep OTA disabled. See [recovery](RECOVERY.md) for exact-state and factory restoration.
