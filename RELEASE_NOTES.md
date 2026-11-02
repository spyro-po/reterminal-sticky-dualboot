# v1.0.0 — Stage 4 source release

CrossPoint EPUB reading and factory Seeedash 1.2.0 share a Seeed reTerminal Sticky with ESP32-S3 and 32 MiB Flash. CrossPoint is the default. Select **Settings → System → Switch to Seeedash** to restart into Seeedash; physical Reset without Up returns to CrossPoint.

The owner reports the Stage 4 update and menu switching on battery working on their physical device. Up+Reset is confirmed with USB only. Newly rebuilt firmware has not been tested on hardware by the release preparer. Read `docs/VALIDATION.md` for actual offline results and limits.

**Public assets are source, patches, documentation, manifests, licenses and SHA256SUMS only.** There is no precompiled installation/update BIN in this release. Seeedash binary redistribution permission is unresolved; CrossPoint's combined-library binary compliance also requires further work. Do not mirror the vendor BIN or upload a locally merged image.

Build locally using `docs/BUILD.md`. Choose destructive Fresh Install or a checked two-segment Update / Preserve Data for an already compatible device. Keep a verified full backup and establish ROM recovery before writing. Never install a loader/application from different pairs. Updates are not power-fail atomic.

**All standard OTA, Seeedash firmware/resource/child-device updates and CrossPoint OTA are unsupported and forbidden.** Keep Seeedash offline and unpaired. Battery Up+Reset, broad sleep/wake behavior, runtime stack high-water and other hardware revisions remain unverified.

SHA-256 manifests detect corruption, not publisher identity. No artifact in this release contains device credentials, private backups or user books.
