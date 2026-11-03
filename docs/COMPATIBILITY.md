# Compatibility manifest

`manifests/compatibility.json` schema 1 / manifest version 1.1.0 is the user-facing selection policy. `manifests/dependencies.lock.json` remains the unchanged v1.0.0 runtime baseline. `manifests/builder.lock.json` pins the new tooling. The CLI verifies these contracts before building or checking bundles.

| ID | Channel | CrossPoint | Seeedash | Loader / layout | Hardware evidence |
| --- | --- | --- | --- | --- | --- |
| cp-2.0.0-seeedash-1.2.0 | stable | 2.0.0, e8299b5f126817282939059d6505f90429489276 | 1.2.0 | Stage 4, STKY-BOOT-V1 / protected-reference-32m | Owner-reported Stage 4 tests on one device; newly generated and Docker-built artifacts are untested |

Seeedash's approved full-image SHA-256 is `5cd55031ddee26cf32ed9e01dd89ed8d820bdbfe752d0140b136177fab26a2a2`. The CSV/table, eight-file patch, boot policy/entry/header/config and build profile have integrity pins. Six factory-extent hashes allow fresh-image verification without publishing or bundling a separate factory BIN. All original factory data extents must match.

`stable` identifies the owner-approved **source combination**, not a new Docker-image, operating-system or hardware certification. The loader pins the application compiled in that build; it is never paired by filename alone. Root builder version 1.1.0 is separate from CrossPoint's retained UI string, Stage 4 loader protocol and `segments.json` format version 1.0.0. No migration of the journal or partition schema is introduced.

Exactly one stable default is allowed. Unknown IDs fail. An entry marked `experimental` cannot be selected by this builder as stable. There is no `latest`, `--force` or automatic stable-promotion option. Currently no experimental firmware is offered for installation.

## Adding a version

Upstream release discovery only records experimental, **NOT_VALIDATED** candidates. Even a tag with the same version label does not prove that its commit is the approved patched develop revision. A maintainer must inspect the exact source and license changes, patch applicability, NVS/FS/OTA paths, layout/image bounds, loader integration and build reproducibility; then obtain new physical tests. CrossPoint and Seeedash updater behavior must be re-audited.

Only after explicit approval should the manifest, locks, source pins, documentation and hardware-evidence record be changed together. Preserve old evidence as historical evidence. Never change `new_build_tested` to true merely because a build, CI job or menu mock passed. SHA-256 is an integrity check, not publisher authentication or a hardware sandbox.
