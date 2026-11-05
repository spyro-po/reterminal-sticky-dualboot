# v1.1.0 — Docker Firmware Builder & Installer

**Proposed release notes. This version has not been merged, tagged or published.**

Build the approved reTerminal Sticky Dual Boot firmware locally using Docker
Engine on Linux or Docker Desktop with WSL2. Host installation of ESP-IDF and
PlatformIO is no longer needed. The Stage 4 runtime, firmware versions, partition
layout, book storage and OTA restrictions are unchanged.

## Features

- `sticky-installer.sh list`, `build`, `verify`, `info` and `check-updates`.
- Pinned tooling with separate Python environments for PlatformIO, application
  ESP-IDF5.5.5 and bootloader ESP-IDF5.4.
- Official Seeedash download and SHA-256 verification at local build time,
  followed by the pinned patch, compilation and integrity/partition audits.
- Local six-file bundle: `fresh-32MiB.bin`, matched `bootloader.bin` and
  `crosspoint.bin`, `segments.json`, `build-report.json` and `SHA256SUMS.txt`.
- `--reproducibility-check` compares two clean builds before export; failed
  builds retain private diagnostics under the output volume.
- Preserve Data preflight checks the full device backup, protected layout,
  installed Seeedash and code-sector boundaries before printing instructions.
- Read-only upstream monitoring never promotes versions or publishes firmware.

## Approved combination and validation

Only `cp-2.0.0-seeedash-1.2.0` is supported: pinned CrossPoint2.0.0,
Seeedash1.2.0 and the Stage 4 bootloader/protected 32 MiB layout.

The owner reports a successful full Ubuntu Docker build, reproducibility check
and artifact verification. The supplied local bundles also passed independent
checks of integrity, layout bounds, factory extents and simulated Preserve Data
writes. Their fresh-image SHA-256 is:

```text
e4dcb8b45d07cdc367ef03517c19c4f59aab839aae4041dfcd3c50ad4c43f073
```

This identifies the audited local output, not a public download or a universal
cross-host build hash. Verify your own bundle using its checksums and the CLI.
See [the final audit](docs/V1.1_FINAL_AUDIT.md) for segment identities and evidence
limits. Offline tests and the existing PR's tools-image smoke CI passed.

## Installation and upgrade

Start with [Docker setup](docs/DOCKER_INSTALL.md) or the
[Windows11/WSL2 guide](docs/WINDOWS_INSTALL.md). The installer **never flashes a
device**; `info` prints instructions for a separate manual esptool operation.

Fresh Install destroys existing Flash data. Preserve Data requires an already
compatible Dual Boot device and writes the matched pair at `0x0` and `0x690000`.
Keep a verified private full backup and establish ROM recovery first. Existing
v1.0.0 devices need no reflashing merely to use the new builder.

## Limits and distribution

- Public assets are source only. No Seeedash, application/bootloader BIN, complete
  Flash image, device dump or prebuilt tools image is distributed. Local output
  must not be uploaded; see [LICENSING.md](docs/LICENSING.md).
- All standard OTA and Seeedash resource/child updates remain forbidden. The
  unmodified factory application cannot be sandboxed by this bootloader.
- Paired updates are not power-fail atomic. See [Recovery](docs/RECOVERY.md).
- Windows installation has been reviewed but not executed. New Docker-built
  firmware has not been tested on hardware; historical Stage 4 results do not
  validate these new binaries.
- Battery Up+Reset and broad sleep/wake behavior remain unconfirmed. Menu
  switching on battery belongs to the owner's historical Stage 4 observations.
- Same-environment repeat builds passed; cross-host bit identity is not promised.

Publication and merge still require the owner's approval.
