# Upgrading the integration

v1.1.0 changes local build tooling, not the Stage 4 runtime. Existing v1.0.0 devices do not need reflashing to use the new builder. Keep your known working image/pair and private backup. Never combine a new bootloader with an old CrossPoint BIN.

1. Read the new changelog, compatibility manifest and license policy.
2. Build the approved combination locally; check `build-report.json` and `SHA256SUMS.txt`.
3. Select destructive Fresh Install or Preserve Data explicitly. A successful artifact check does not authorize either operation.
4. Preserve Data requires a current verified full backup, exact protected-reference table and `--confirm-layout protected-reference`. Use the two existing code offsets only; do not erase or write a table/data partition.
5. Verify paired segments and a complete protected-byte readback before first boot as [UPDATE.md](UPDATE.md) describes. Recover through ROM if interrupted; the write is not atomic.
6. Physically test a newly built pair on a suitable recoverable device before treating it as hardware verified. Check EPUB reading, USB/battery menu switching, Reset return, and each app's sleep/wake. Keep all OTA disabled.

The installer never flashes, burns eFuses, reformats filesystems or alters stable selections based on a network report. [RECOVERY.md](RECOVERY.md) provides exact-backup and destructive factory restoration.

## Upstream monitoring

`.github/workflows/upstream-check.yml` runs weekly on the default branch and manually; pull requests run offline regression tests and a tooling-image smoke build. Scheduled execution starts only after this workflow reaches the default branch. Permissions are `contents: read`. It writes a **JSON text report only**, with observed version labels, experimental candidates and outstanding source/build/hardware work. It never edits the stable manifest, creates an Issue/PR, uploads firmware, pushes a tag, publishes a container image or makes a Release.

The offline tests exercise the existing integration's image/partition, installer, promotion and Docker-launcher gates. They do **not** compile or certify unknown candidate firmware. Candidate build and hardware results remain NOT_RUN. The tooling smoke command is `list`, offline inside the built image; it does not download Seeedash. Network failure is a failed check, not proof that no upstream update exists. Maintainers can open an Issue or PR manually after reviewing the report.

This branch must not be merged or tagged/released as v1.1.0 without owner approval. Docker runtime validation and hardware testing are separate evidence, and missing checks must stay visible.
