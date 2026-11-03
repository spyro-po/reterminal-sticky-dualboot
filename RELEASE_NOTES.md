# v1.1.0 — Docker-based Firmware Builder & Installer (unreleased)

Build the approved reTerminal Sticky Dual Boot source combination locally without manually installing ESP-IDF/PlatformIO on the host. The Bash launcher uses Docker Engine or Docker Desktop + WSL2. It offers list, build, verify, info and read-only check-updates commands. No command flashes a device.

The sole stable source combination is CrossPoint2.0.0 at the approved commit plus factory Seeedash1.2.0 and the Stage4 loader/layout. Stable records the owner's prior device observations; a new Docker-generated artifact has no new physical validation. Unknown upstream versions remain experimental.

Local builds download the official Seeedash artifact at runtime and verify its SHA-256, apply the pinned patch, compile the paired application/loader and run the existing integrity, NVS/Flash, link and partition gates. Output contains the local fresh32MiB image, paired segments, version report and SHA256SUMS. Preserve Data instructions require a real full-device backup, canonical table verification and explicit layout acknowledgement.

Public distribution remains source-only. No Seeedash BIN, complete Flash image, compiled CrossPoint BIN, device dump or prebuilt container image is included or automatically published. See docs/LICENSING.md. All standard OTA remains unsupported and forbidden; paired updates remain non-atomic.

Docker execution, repeat compilation and physical validation are separate checks. Read the v1.1 validation record for actual available/unavailable results. This is a prepared development release: no v1.1.0 tag, merge or GitHub Release is authorized yet.
