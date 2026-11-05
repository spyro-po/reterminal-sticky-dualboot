# Validation record and limits

## v1.1.0 Docker builder audit

The [final audit](V1.1_FINAL_AUDIT.md) records the owner-reported successful Ubuntu
Docker/reproducibility/verification run and independent checks of its actual
local bundles. Windows execution and new firmware hardware tests remain pending.
The native v1.0.0 evidence below is historical and has different artifact hashes.

## Hardware evidence

`manifests/hardware-test-report.json` records the owner's Stage 4 observations on one physical Sticky: CrossPoint default/EPUB reading, Seeedash menu switching, plain physical Reset return, Up+Reset with USB, battery menu switching, and successful Stage 4 installation. The original tested segment identities are retained in `manifests/stage4-validated-artifacts.json` for provenance, not as publicly bundled binaries.

No new hardware test, battery measurement, sleep/wake stress test or recovery flash was performed during release preparation. A newly compiled image is not the exact tested artifact merely because its runtime sources are retained.

## Offline gates

The release preparation runs the following checks and records the final build result in `manifests/release-validation.json`:

- The eight-file CrossPoint patch applies at the exact upstream commit; its whole SHA-256 and the FreeInk commit are verified.
- Host-compiled real policy and menu code: reset classes, button qualification, menu diagnostics, journal failures and all 33 partial-write cut points, sequence exhaustion and image fallback.
- NVS mocks and real isolation/Flash wrappers: default and named NVS routing, erase denial, boundary/overflow rejection and forbidden filesystem operations.
- Real IDF native OTA target/pre-erase decision functions from bootloader and application SDK sources, with hardware stubs. This is not a full OTA simulation or permission to run Seeedash OTA.
- Production loader layout/image validation functions extracted with IDF I/O mocks; malformed offsets, flags, subtypes, extra records, wrong digest/header/length rejected.
- Independent partition generator versus ESP-IDF generator, table MD5 and canonical SHA-256, all factory physical extents preserved.
- Synthetic corruption, mismatched pair/manifest, sector-write preservation and publication-audit negative cases.
- Target CrossPoint build, final ELF/map guard coverage and Wi-Fi NVS callback; custom pinned loader build and SDK configuration.
- Local complete-image assembly validates the official firmware, every protected factory extent and exactly 32 MiB length. No private device backup is used to build it.
- Same-path clean rebuild comparison when recorded as passed; cross-host reproducibility is not claimed.
- Git-index and source-archive publication allowlist, text-only content, size/path limits, secret patterns and manual provenance review. No scanner alone can prove the absence of every possible secret.

Standalone native-build logs stay in ignored `.local/logs/<run-id>/`. Installer builds persist private logs in the output bind directory, `out/diagnostics/<run-id>/` by default, outside the six-file firmware bundle. Public manifests contain results and hashes, not local paths, serial numbers, network credentials or device dumps. Missing checks must be recorded as missing, never described as passed.

## Rebuild cache issue resolved during preparation

An initial clean comparison retrieved ELF/BIN from upstream's SCons cache without recreating the map file. The required ELF/map audit rejected that output and no update package was generated. The isolated release profile now disables this cache so a clean build genuinely recompiles and links. The integrity gate was retained. Final comparison results are recorded in the release manifest.

## Final preparation outcome

The first and final independent source compilations produced byte-identical bootloader and CrossPoint BINs on the same host/path, with the fixed source epoch. Final compilation did not restore objects or ELF from SCons cache. The independently assembled local32MiB image also matched. Target builds, host fault tests, ELF/map checks, native/independent table validation and private fresh-image preflight passed. Exact hashes and limits are in `manifests/release-validation.json`. This is not a cross-host reproducibility or new hardware claim.

## Known residual risks

- All OTA paths remain forbidden; unmodified Seeedash raw/resource update code cannot be sandboxed by this loader.
- Code-pair installation is not power-fail atomic; an interrupted loader write can require ROM recovery.
- Battery Up+Reset and broad deep-sleep/wake behavior remain unconfirmed on hardware.
- Panic reset classification may resume a journal-selected system; physical Reset is the return gesture.
- Journal write/readback errors can leave a committed request; use physical Reset before retrying/sleeping.
- Corrupt CrossPoint NVS recovery may lose protected-book keys even though vendor NVS remains isolated.
- SHA-256/ABI markers are compatibility and corruption checks, not authenticated Secure Boot or protection against malicious firmware.
- Runtime stack high-water, full SDK call-chain peak and other hardware revisions are not measured by the host tests.
- Public binary-license compliance remains incomplete; this release ships source only.
