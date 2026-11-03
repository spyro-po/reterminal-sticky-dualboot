# Changelog

## v1.1.0 — Unreleased

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
