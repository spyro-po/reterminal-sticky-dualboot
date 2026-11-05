# Troubleshooting

| Symptom | Checks / safe action |
| --- | --- |
| Menu reports a layout mismatch | Read the actual table/backup and run preflight. `app1` must be test, not ota_1. Do not flash a generic reference table. |
| Loader ABI or integrity mismatch | Check whole-segment hashes and the matched pair; never substitute the PlatformIO loader or disable the pin. |
| Seeedash integrity mismatch | Only official 1.2.0 is accepted. Restore using a verified backup or the destructive factory procedure. |
| Journal read/erase/write/readback/exhausted error | Do not repeatedly retry or sleep; use physical Reset. Preserve a private backup for diagnosis. An error can coexist with a committed request. |
| New loader falls back to Seeedash | CrossPoint may be missing, corrupt or not match the loader's pin. A fallback is not a successful update. Restore/complete the matched pair via ROM. |
| Up+Reset works on USB but not battery | Use the menu (reported working on battery). Compare actual button response after unplugging USB; a retained e-paper image proves nothing about CPU power. Measure supply, CHIP_PU, GPIO45/46 and GPIO5 on the actual board if needed. |
| Unexpected app after a crash | Some panic resets look like software resets. Physical Reset without Up restores the default policy. |
| Protected books fail after CP NVS recovery | CP NVS may have lost keys; restore your own verified backup. Book files alone may be insufficient. |
| ROM download fails | Check cable, CH343 driver, port and DTR/RTS. Up is not BOOT. See RECOVERY.md before touching board pads. |
| Build fails on SDK/tool versions | Use the exact lock and isolated caches; inspect ignored local logs. Do not relax write/integrity guards to get a build. |

## Battery fault isolation

Separate selection failures from power loss. Confirm CrossPoint remains interactive after USB removal and plain Reset on battery. Start Seeedash through the known USB gesture, unplug without resetting and check interaction again. Then compare the menu on battery with Up+Reset on battery at the same charge level. If only a reset gesture fails, the latch/reset interval is a stronger suspect; if Seeedash dies after unplugging without reset, investigate its battery/load path. Neither observation alone identifies a component fault.

A qualified person can capture UART0 using a **3.3 V adapter, RX-only plus common ground**; do not connect VCC/VBUS, TX, DTR or RTS, which can change power/reset behavior. Identify pads from the actual schematic revision. The software tests cannot reproduce power rails or GPIO timing.

## Sleep/wake checks for a new build

Test each system entering sleep and waking on USB and battery. Confirm the same system resumes and that holding Up across a software restart or sleep wake does not change it. Then test plain physical Reset and qualified Up+Reset separately. The owner reports basic sleep/wake and emergency selection PASS for the [exact v1.1.0 image](VALIDATION.md). Held-button wake, long-term stress and battery power specifically for emergency Up+Reset were not supplied; repeat checks for future builds/devices.
