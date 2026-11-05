# Fresh Install — destructive

Docker builders can create the complete local image using [DOCKER_INSTALL.md](DOCKER_INSTALL.md); Windows users should follow [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md).

This path replaces all Flash configuration, books/resources stored in Flash and credentials. It does not preserve existing user data. For an existing compatible Dual Boot installation use [Update](UPDATE.md). Backups can contain passwords and keys; store them outside the repository and never upload them.

First establish [ROM recovery](RECOVERY.md), verify 32 MiB Flash and unrestricted/unencrypted operation, and make and verify a complete backup from this chip. Do not burn eFuses, use `--force`, or change the Flash layout to force a failed preflight to pass.

Build locally as [BUILD.md](BUILD.md) describes, including the validated official Seeedash download and the custom paired bootloader. Assemble `.local/out/build1/fresh-32MiB.bin`; it must be exactly **33554432 bytes**. Check the adjacent `.sha256` file against the generated output. This file is local-only, not a public Release asset.

The manual commands below use **esptool 4.12.0**, whose syntax uses underscores. Install it in a separate environment so the firmware builder's toolchain is unaffected. Set `ESP_PY` to that environment's Python and `STICKY_PORT` to the actual device port. esptool 5 has different command spelling; do not blindly mix versions.

```sh
set -eu
umask 077
export ESP_PY=/path/to/esptool-4.12-env/bin/python
export STICKY_PORT=/dev/ttyACM0
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" get_security_info
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" flash_id
test ! -e /private/path/sticky-before.bin
test ! -e /private/path/sticky-before.bin.sha256
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset read_flash 0x0 0x2000000 /private/path/sticky-before.bin
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset verify_flash 0x0 /private/path/sticky-before.bin
sha256sum /private/path/sticky-before.bin > /private/path/sticky-before.bin.sha256
```

Only after checking that backup and accepting data loss, with stable USB power:

```sh
set -eu
(cd .local/out/build1 && sha256sum --check fresh-32MiB.sha256)
test "$(wc -c < .local/out/build1/fresh-32MiB.bin)" -eq 33554432
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset erase_flash
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 .local/out/build1/fresh-32MiB.bin
"$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" --after no_reset verify_flash 0x0 .local/out/build1/fresh-32MiB.bin
```

Reset without Up: CrossPoint should start. Open an EPUB, select Switch to Seeedash, check Seeedash interaction, then Reset back to CrossPoint. Repeat the menu test on battery. Keep Seeedash offline and unpaired; all OTA paths remain forbidden. Check each application's sleep/wake separately. A retained e-paper page is not evidence that the CPU still has power.

No script in this repository performs these hardware commands. Recheck recovery access before installing a newly built pair.
