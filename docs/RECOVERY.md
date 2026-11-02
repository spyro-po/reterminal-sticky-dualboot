# Recovery

Prepare recovery **before** changing Flash. Use stable USB-C power and a data cable. The board's CH343 bridge supports DTR/RTS auto-download. Confirm ROM download works on your physical board; Up/GPIO5 is **not** the GPIO0 boot strap. The physical Reset controls CHIP_PU.

If auto-download fails, a qualified person must locate GPIO0 and CHIP_PU from the actual board revision and [Seeed hardware documentation](https://www.seeedstudio.com/sticky/docs/en/device-guide/hardware-overview/) before attempting manual ROM entry. GPIO0 also serves sensor I2C. Do not guess pads or assume Up+Power enters ROM. If ROM access remains unavailable, seek manufacturer service; software Reset cannot repair an invalid second-stage loader.

Commands below use esptool **4.12.0**, `ESP_PY` and `STICKY_PORT` as explained in [INSTALL.md](INSTALL.md). Stop for Secure Boot, Flash encryption, restricted download, a non-32 MiB chip, an incomplete backup or failed verification. Do not burn eFuses or use `--force`.

## Restore the exact pre-install state

Use a verified **33554432-byte backup from this chip**, stored privately with its SHA-256. A different device's backup can contain different calibration and secrets.

```sh
sha256sum /private/path/sticky-before.bin
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 /private/path/sticky-before.bin
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset verify_flash 0x0 /private/path/sticky-before.bin
```

Reset after verification. This restores bootloader, table, applications, NVS, PHY, resources and coredump bytes from the backup. It does not restore or change eFuses. If the backup was already Dual Boot, this restores Dual Boot, not factory layout. For code-only rollback, use both members of your previously verified working pair and the same protected-layout preflight/update procedure.

## Restore official Seeedash 1.2.0 defaults

**Destructive:** this restores factory firmware and defaults, not personal files or credentials. A complete erase also clears private Dual Boot state and the last 256 KiB coredump area absent from the vendor download.

```sh
.venv/bin/python scripts/fetch_seeedash.py
sha256sum .local/vendor/seeedash-1.2.0.bin
# Must be: 5cd55031ddee26cf32ed9e01dd89ed8d820bdbfe752d0140b136177fab26a2a2
# Exact vendor file length: 33292288 bytes (0x1fc0000).
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset erase_flash
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 .local/vendor/seeedash-1.2.0.bin
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset verify_flash 0x0 .local/vendor/seeedash-1.2.0.bin
```

Reset and provision Seeedash again. This is a merged ESP32-S3 factory image at **0x0**. Never write `boot_app0.bin` at `0xe000`; that address is factory NVS. The vendor BIN remains unchanged locally and must not be publicly redistributed by this project without permission.

## Emergency system selection is not recovery

With a valid Dual Boot loader/table, qualified Up+Reset selects Seeedash (USB confirmed), and Reset without Up selects CrossPoint. It does not restore the factory partition table or recover corrupted firmware. Battery menu selection is reported working; battery Up+Reset is still not established.
