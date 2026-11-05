# Changelog

## v1.1.0 — 2026-11-05

- Record owner-reported Preserve Data/flash/protected-readback verification and 9/9 hardware tests for exact image e4dcb8…f073 on one Sticky; retain untested defaults for future rebuilds/devices and all OTA/distribution restrictions.

- Complete final artifact/layout audit of the owner-tested Ubuntu Docker output; document source-only release readiness, retain Windows/hardware limits and harden manual installation/recovery commands against failed checks and backup overwrite.

- Bootstrap and verify the application ESP-IDF5.5.5 Python environment with a separate fully pinned, hashed package lock; keep PlatformIO and bootloader IDF5.4 environments separate and reject missing imports before compilation.

- Initialize the pinned PlatformIO environment before the first clean; check framework source metadata and ESP32-S3 SDK files on cold and warm caches without bypassing CrossPoint pre-scripts.

- Preserve build diagnostics in unique output-volume directories after container removal; record actual exit codes/signals and show final stdout/stderr on failure. Never reuse an earlier host log or infer success from text.

- Fix the ESP-IDF5.4 tool-selector no-op, explicitly create tool/constraints paths and check the installed compiler before dependency validation; add build/runtime path-order regressions.

- Fix APT dependency conflicts by pinning main, updates and security streams to the same snapshot; preserve signature/dependency checks and add regression coverage.

- Add a locally built Docker tools image with pinned Python/base digest, ESP-IDF/toolchain and Python dependencies.
- Add list/build/verify/info/check-updates CLI commands and explicit Preserve Data backup/layout validation.
- Export locally checked fresh images, matched code pairs, hashes and component reports; offer clean repeat-build comparison.
- Add a versioned compatibility gate for the sole approved CrossPoint2.0.0 + Seeedash1.2.0 source combination.
- Add Windows11/WSL2/PowerShell installation and recovery documentation.
- Add read-only upstream monitoring and offline/container smoke CI; no automatic promotion, firmware upload or release.
- Preserve Stage4 runtime, partitions, NVS/OTA protections and source-only distribution policy. New Docker output is not hardware certified.

## v1.0.0 — 2026-11-02

- First source release of the Stage 4 reTerminal Sticky Dual Boot integration.
- Custom pinned-image bootloader; CrossPoint default, private-journal menu switching to Seeedash, physical Reset return and emergency Up selection.
- Separate CrossPoint NVS, link-time/write guards and forbidden standard OTA paths.
- Protected 32 MiB layout, pinned upstream patch and isolated build tooling.
- Local official firmware downloader, checked fresh-image assembly and paired code-update preflight.
- English installation, recovery, architecture, troubleshooting and licensing documentation.
- Stage 4 device results are reported by the project owner. Release rebuilds have separate offline validation; no new hardware test is claimed.
- Source-only public assets: Seeedash and complete images excluded; combined CrossPoint binary redistribution remains pending dependency-license compliance.
