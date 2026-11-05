# Validation record and limits

## v1.1.0 exact-build hardware validation

The owner reports physical validation on one Seeed reTerminal Sticky (ESP32-S3,
32 MiB Flash) of CrossPoint2.0.0 + Seeedash1.2.0 with the protected-reference
layout. The [structured owner report](../manifests/v1.1-hardware-validation.json)
records **9/9 hardware tests PASS**, together with Docker build, reproducibility,
artifact verification, Preserve Data preflight, flash verification and full Flash
readback/protected-data verification PASS.

The exact generated fresh image SHA-256 is:

```text
e4dcb8b45d07cdc367ef03517c19c4f59aab839aae4041dfcd3c50ad4c43f073
```

| Owner-reported test | Result |
| --- | --- |
| Normal boot launches CrossPoint | PASS |
| EPUB opens successfully | PASS |
| CrossPoint menu switches to Seeedash | PASS |
| Seeedash launches and responds correctly | PASS |
| Reset from Seeedash returns to CrossPoint | PASS |
| Up + Reset emergency boot launches Seeedash | PASS |
| Switching works without USB power | PASS |
| Books and settings are preserved | PASS |
| Sleep and wake work in both systems | PASS |

The fresh-image hash identifies the generated reference bundle and its code pair.
It is not the expected digest of device Flash after Preserve Data, which retains
user-specific settings and books.

These are owner-reported results, not independent reviewer hardware execution.
The test execution date, cycle count and hardware revision were not supplied.
Battery menu switching is confirmed; the power source for emergency Up+Reset
was not specified. Functional sleep/wake passed, while long-term stress, held-Up
wake tests, power-cut behavior, other devices and factory Recovery remain
unverified. Preserve Data validation does not establish destructive Fresh Install
or factory Recovery execution.

Only the exact artifact and reported conditions inherit this evidence. Future
builds are untested by default, even with the same version labels. Existing
build reports retain `hardware_tested_this_build: false` from generation time;
this later report supplies the separate owner evidence. The immutable build-input
compatibility manifest remains unchanged so existing bundles still verify.
The [final audit](V1.1_FINAL_AUDIT.md) retains the independently checked segment
identities, layout/data checks and release limits. No BIN or device dump is
included. The native v1.0.0 evidence below is historical and has different hashes.

## Historical Stage 4 hardware evidence

`manifests/hardware-test-report.json` records the owner's Stage 4 observations on one physical Sticky: CrossPoint default/EPUB reading, Seeedash menu switching, plain physical Reset return, Up+Reset with USB, battery menu switching, and successful Stage 4 installation. The original tested segment identities are retained in `manifests/stage4-validated-artifacts.json` for provenance, not as publicly bundled binaries.

No reviewer hardware test, battery measurement, sleep/wake stress test or recovery flash was performed during release preparation. The later owner-reported v1.1.0 results are recorded above. A newly compiled image is not the exact tested artifact merely because its runtime sources are retained.

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
- Basic sleep/wake in both systems passed for the owner-tested v1.1.0 artifact. Battery emergency Up+Reset, long-term stress and held-button wake behavior remain unconfirmed.
- Panic reset classification may resume a journal-selected system; physical Reset is the return gesture.
- Journal write/readback errors can leave a committed request; use physical Reset before retrying/sleeping.
- Corrupt CrossPoint NVS recovery may lose protected-book keys even though vendor NVS remains isolated.
- SHA-256/ABI markers are compatibility and corruption checks, not authenticated Secure Boot or protection against malicious firmware.
- Runtime stack high-water, full SDK call-chain peak and other hardware revisions are not measured by the host tests.
- Public binary-license compliance remains incomplete; this release ships source only.
