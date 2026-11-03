# Docker Firmware Builder & Installer (v1.1.0)

This development version wraps the existing Stage 4 build and verification pipeline. It does **not** flash devices. The currently released version remains v1.0.0 until the owner approves a new release.

## Requirements

Use Linux with a working Docker Engine, or Windows 11 with Docker Desktop's **Linux containers / WSL2** backend. The launcher runs in Bash on Linux or WSL2. No host ESP-IDF, PlatformIO or compiler installation is needed. The initial supported container platform is **linux/amd64**; ARM/emulated hosts are not validated. Allow at least 20 GiB free disk space, several GiB RAM and a reliable network connection. Download/build time depends on network and CPU and can be substantial.

Docker Desktop has its own licensing terms; check [Docker's Windows installation documentation](https://docs.docker.com/desktop/setup/install/windows-install/). See [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) for the complete Windows path.

## APT snapshot consistency

The tools image uses `docker/apt.sources`: both the `debian` archive (`bookworm` and `bookworm-updates`) and the separate `debian-security` archive (`bookworm-security`) are pinned to **20261102T000000Z**. The base image digest and Python version are unchanged. The source file hash and required suites are recorded in `manifests/builder.lock.json` and checked offline.

The pinned amd64 base image, created on 2026-10-28, already contains security-updated runtime packages. Replacing its sources with `bookworm main` alone removed the matching development/runtime dependencies:

| Package family | Installed base runtime | Main-only snapshot | Matching security snapshot |
| --- | --- | --- | --- |
| OpenSSL | libssl3 3.0.22-1~deb12u2 | libssl-dev 3.0.20-1~deb12u2 | libssl-dev/libssl3 3.0.22-1~deb12u2 |
| Perl | perl-base 5.36.0-7+deb12u4 | perl 5.36.0-7+deb12u3 | perl/perl-base 5.36.0-7+deb12u4 |

Those versions were checked against the digest-verified official base layers and Debian's snapshot package indexes. This metadata check is not a successful Docker build or complete APT solver test. APT still verifies Debian signatures through the archive keyring. Only historical `Valid-Until` expiry is disabled, as [Debian's snapshot documentation](https://snapshot.debian.org/) requires for old snapshots. Live mirrors, unsigned/trusted sources, forced downgrades and ignored APT errors are not used.

For the reported Ubuntu Docker Engine failure, pull this branch update and run from the repository root:

```sh
git pull --ff-only origin feature/docker-installer
./sticky-installer.sh build --reproducibility-check
```

The changed source `COPY` invalidates the APT layer automatically. To isolate the tools-image test without compiling firmware, run:

```sh
docker build --no-cache --platform linux/amd64 --tag reterminal-sticky-dualboot-builder:1.1.0 .
```

The patch was prepared in an environment without a Docker daemon; its image build/run remains unverified locally. APT failure must stop the build. Do not bypass it or change the stable firmware combination to make installation proceed.

## ESP-IDF tool installation and paths

The pinned SDK commit `67c1de1eebe095d554d281952fde63c16ee2dca0` has a tool-selection issue: `idf_tools.py install xtensa-esp-elf@esp-14.2.0_20241119` is filtered against bare tool names before version parsing. It returns0 with an empty installation list and can leave the tools directory absent. This was reproduced against the real pinned script on the host; creating the directory alone would not verify that a compiler was installed.

The image now creates `IDF_TOOLS_PATH` explicitly, calls `install --targets esp32s3 xtensa-esp-elf`, checks the compiler at the exact versioned path and runs its `--version`, then copies constraints to a complete filename and runs the dependency check. The selected recommended version remains `esp-14.2.0_20241119`, fixed by the unchanged SDK commit/tool metadata and checked by the compiler path. The tool archive SHA-256 and all dependency version pins are unchanged. No upstream SDK source is patched.

| Setting | Image construction | Unprivileged runtime |
| --- | --- | --- |
| IDF_PATH / IDF54_PATH | `/opt/esp/idf` | Same immutable SDK |
| IDF_PYTHON_ENV_PATH | `/opt/esp/idf-python` | Same Python environment |
| IDF54_PYTHON | `/opt/esp/idf-python/bin/python` | Same interpreter for SDK actions |
| IDF_TOOLS_PATH | `/opt/esp/tools` | `$HOME/.espressif`, writable metadata and constraints |
| Compiler | `/opt/esp/tools/tools/xtensa-esp-elf/esp-14.2.0_20241119/xtensa-esp-elf/bin/xtensa-esp-elf-gcc` | Reached through the runtime `tools` symlink |
| Constraints | `/opt/esp/tools/espidf.constraints.v5.4.txt` | `$HOME/.espressif/espidf.constraints.v5.4.txt` |

See [ESP-IDF5.4 tool documentation](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32/api-guides/tools/idf-tools.html). The dependency check uses the explicit SDK Python environment and the pinned constraints file; it is not disabled. The custom environment is installed from exact package locks rather than downloading a new Python dependency set.

The remaining Dockerfile order was reviewed: Docker `COPY` creates lock/source destination directories, venv creation precedes SDK tool invocations, Git checkout/pin checks precede installation, compiler/constraints checks precede the final source audit, and privilege drop occurs last. The entrypoint checks immutable prerequisites and creates its writable workspace/metadata/helper parents before copying or linking. Static regressions reject broken paths and reordered steps.

Real tool installation and Python dependency checks passed in isolated host directories, including the runtime symlink/metadata layout. The owner subsequently reported a successful tools-image build on Ubuntu, followed by a runtime build failure. A Docker daemon is still unavailable in the preparation environment; no local container execution or new hardware test is claimed.

## Build failure diagnostics

Each installer build prints a unique diagnostic directory under the output mount:
`/output/diagnostics/<UTC-timestamp>-<random-id>/`, available on the host as
`out/diagnostics/<same-id>/` (or under your `--output` directory). It survives
`docker run --rm` even if the build fails. These private logs are outside the
six-file firmware bundle; do not upload the whole output directory.

`installer-first-driver.log` captures the native builder, while
`installer-first-clean.log` captures the actual PlatformIO clean command.
Each has a matching `.status.json` with command, working directory, PID, run ID,
UTC start/end times and actual `returncode`. Repeat builds use `installer-repeat`.
Zero means success; negative values indicate POSIX signals. A spawn failure has
`outcome: spawn_error` and no process return code. A missing completion time or
`outcome: running` means no final status was recorded (for example, abrupt container
termination); never infer success from the last output line.

On failure the console includes the bounded final stdout/stderr and exact log/status
paths. Inspect the inner tool's status as well as the driver's exit code. Files are
created exclusively and each build gets a new directory, so retries do not replace
earlier evidence. No environment dump or device backup is recorded. If the output
directory is not writable by the invoking UID/GID, diagnostics creation fails
before compilation. Fix ownership of your chosen output directory; do not run
the container privileged or weaken validation.

The earlier error referenced `.local/logs/installer-first-clean.log` inside the
disposable container workspace. The launcher does not mount the host repository
there. A same-named file in the host repository therefore cannot establish the
result of that container run. Textual PlatformIO `SUCCESS` is not an exit status:
a process can fail later or be terminated. The original runtime failure remains
unidentified until a correlated log and status are collected; no error is ignored
by this change. A native host clean returned0 in the preparation environment,
which does not reproduce or validate the Docker run.

Pull this update and retry on Ubuntu:

```sh
git pull --ff-only origin feature/docker-installer
./sticky-installer.sh build --reproducibility-check
ls -lt out/diagnostics
```

Choose the run ID printed by that invocation, then inspect its clean and driver
logs/status files. Review logs for private paths or tool messages before sharing
selected excerpts. If Docker itself is killed before the Python driver runs,
also retain the host terminal output; no subprocess logger can record a process
it never started.

## Commands

From the repository root:

```sh
./sticky-installer.sh list
./sticky-installer.sh build --combination cp-2.0.0-seeedash-1.2.0
./sticky-installer.sh verify --mode fresh
./sticky-installer.sh info --mode fresh
./sticky-installer.sh check-updates
```

`list` shows the single approved combination and the source of its hardware evidence. Metadata reports are immutable snapshots; use `check-updates --report another-name.json` when the default report already exists. `check-updates` reads metadata only; its report never grants compatibility. The launcher builds/refreshes the local tools image using Docker's layer cache before running the command. The image contains SDK/tools and reviewed source, **no Seeedash download or generated firmware**. First-time image construction requires the network. Do not assume a first-time `verify` command can run without the cached image/dependencies.

`build` downloads the pinned CrossPoint commit and FreeInk SDK, checks the patch SHA-256 and official Seeedash 1.2.0 SHA-256, compiles the application and its specifically pinned bootloader, runs the existing host/link/partition tests, and verifies the fresh image. Output appears only after all gates pass:

```text
out/cp-2.0.0-seeedash-1.2.0/
  fresh-32MiB.bin
  bootloader.bin
  crosspoint.bin
  segments.json
  build-report.json
  SHA256SUMS.txt
```

The report records source pins, component/Python versions, builder/compatibility lock hashes, test results and **hardware_tested_this_build: false**. Existing output is never overwritten. Use `--directory another-name` for another run, and the same option for verification/info. Use `--output /path/to/output-root` to choose the host bind directory. Avoid commas/newlines in bind paths. Output cannot be the repository root or an ancestor.

For an independently recompiled same-environment comparison:

```sh
./sticky-installer.sh build --directory repeat-check --reproducibility-check
./sticky-installer.sh verify --directory repeat-check
```

The builder performs two clean application links and a fresh bootloader project for the repeat, compares both code segments, and refuses export on a mismatch. A reproducibility result must not be inferred from a single successful compilation. Different absolute paths or hosts may change binary hashes.

## Preserve Data

This is only for an existing compatible Dual Boot device. Make and verify a **full 33554432-byte backup from that chip** with host esptool while keeping it in ROM/stub. Then:

```sh
./sticky-installer.sh verify --mode preserve --backup /private/sticky-before.bin --confirm-layout protected-reference
./sticky-installer.sh info --mode preserve --backup /private/sticky-before.bin --confirm-layout protected-reference
```

The backup is mounted as one **read-only file**; it is not copied into the bundle, report or image. Verification checks its exact partition table, installed Seeedash 1.2.0 and full erase-sector boundaries in a simulated paired-code update. The acknowledgement alone is insufficient. A table hash alone is insufficient. The actual backup must pass. See [UPDATE.md](UPDATE.md) for manual paired writes at `0x0` and `0x690000` and protected-byte readback before first boot. Never erase for Preserve Data.

## Manual Linux installation from a Docker bundle

The native `.venv` and `.local/out/build1` paths in the original native-build guides are **not created by Docker**. Use the exported bundle paths below. This separate host Python/esptool environment is only for the manual serial operation; no host ESP-IDF/PlatformIO is required. Install your distribution's Python3 and venv support if missing. Use Bash and run each stage deliberately; `set -e` and the function's exit check stop on command failure.

From the repository root, after a successful Docker build:

```sh
set -e
umask 077
BUNDLE=$(realpath out/cp-2.0.0-seeedash-1.2.0)
PRIVATE="$HOME/sticky-private"
mkdir -p "$PRIVATE"
python3 -m venv "$PRIVATE/esptool-env"
ESP_PY="$PRIVATE/esptool-env/bin/python"
"$ESP_PY" -m pip install esptool==4.12.0
STICKY_PORT=/dev/ttyACM0  # Replace with this device's actual UART port.
sticky_esptool() {
  "$ESP_PY" -m esptool --chip esp32s3 --port "$STICKY_PORT" "$@" || return "$?"
}
sticky_esptool get_security_info
sticky_esptool flash_id
BEFORE="$PRIVATE/before-32MiB.bin"
sticky_esptool --after no_reset read_flash 0x0 0x2000000 "$BEFORE"
test "$(wc -c < "$BEFORE")" -eq 33554432
sticky_esptool --after no_reset verify_flash 0x0 "$BEFORE"
sha256sum "$BEFORE"
./sticky-installer.sh verify --mode fresh
(cd "$BUNDLE" && sha256sum -c SHA256SUMS.txt)
```

Stop unless ROM access is reliable, Flash is32MiB, security/encryption/download restrictions are absent and the backup/readback succeeds. Backups contain private calibration, credentials and possibly keys; keep them outside Git. Never use `--force` or burn eFuses. Use stable USB power. The following two paths are alternatives, not a sequence.

### Fresh Install — destructive

After confirming the complete backup and accepting loss of existing Flash data:

```sh
set -e
sticky_esptool --after no_reset erase_flash
sticky_esptool --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 "$BUNDLE/fresh-32MiB.bin"
sticky_esptool --after no_reset verify_flash 0x0 "$BUNDLE/fresh-32MiB.bin"
```

Reset without Up only after verification. Follow the physical test checklist in [INSTALL.md](INSTALL.md); use the Docker bundle path above rather than its native-build example path.

### Preserve Data — existing compatible Dual Boot only

Do **not** erase. With the same freshly captured backup:

```sh
set -e
./sticky-installer.sh verify --mode preserve --backup "$BEFORE" --confirm-layout protected-reference
./sticky-installer.sh info --mode preserve --backup "$BEFORE" --confirm-layout protected-reference
sticky_esptool --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 "$BUNDLE/bootloader.bin" 0x690000 "$BUNDLE/crosspoint.bin"
sticky_esptool --after no_reset verify_flash 0x0 "$BUNDLE/bootloader.bin" 0x690000 "$BUNDLE/crosspoint.bin"
AFTER="$PRIVATE/after-before-boot.bin"
sticky_esptool --after no_reset read_flash 0x0 0x2000000 "$AFTER"
docker run --rm --platform linux/amd64 --network none --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges --mount "type=bind,src=$BUNDLE,dst=/bundle,readonly" --mount "type=bind,src=$BEFORE,dst=/before.bin,readonly" --mount "type=bind,src=$AFTER,dst=/after.bin,readonly" --entrypoint /opt/sticky/python/bin/python reterminal-sticky-dualboot-builder:1.1.0 /opt/sticky/source/scripts/preflight.py --bundle /bundle --backup /before.bin --after /after.bin
```

Only reset after the offline readback comparison passes. The container receives just the bundle and two read-only files, no serial device. Do not add table, OTA, NVS or filesystem images. `0xe000` is factory NVS. As [UPDATE.md](UPDATE.md) explains, code-pair writes are not power-fail atomic and later application writes are outside the preservation promise.

### Linux recovery

For exact-state recovery, write the verified full backup from **this chip** at0x0, then verify it:

```sh
set -e
sticky_esptool --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 "$BEFORE"
sticky_esptool --after no_reset verify_flash 0x0 "$BEFORE"
```

For destructive official factory defaults without a suitable factory backup, use the standalone host esptool Python to download the fixed official file; no native builder environment is needed. Check its complete size and hash before erasing:

```sh
set -e
VENDOR="$PRIVATE/seeedash-1.2.0.bin"
"$ESP_PY" - "$VENDOR" <<'PY_VENDOR_RECOVERY'
import hashlib, pathlib, sys, urllib.request
url='https://raw.githubusercontent.com/Seeed-Projects/reterminal-sticky-playground-registry/f0479400594d8f9a3d7fd7b282f2d7b2a1bdbd0e/firmwares/sticky-factory/firmware/1.2.0/reterminal_sticky_1_2_0.bin'
data=urllib.request.urlopen(url, timeout=120).read(33292289)
if len(data)!=33292288 or hashlib.sha256(data).hexdigest()!='5cd55031ddee26cf32ed9e01dd89ed8d820bdbfe752d0140b136177fab26a2a2':
    raise SystemExit('Official firmware integrity mismatch: STOP')
path=pathlib.Path(sys.argv[1])
if path.exists() and path.read_bytes()!=data:
    raise SystemExit('Existing vendor file differs: STOP')
path.write_bytes(data)
PY_VENDOR_RECOVERY
sticky_esptool --after no_reset erase_flash
sticky_esptool --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 "$VENDOR"
sticky_esptool --after no_reset verify_flash 0x0 "$VENDOR"
```

The whole-chip erase also clears the final256KiB absent from the vendor file. Reset and provision factory Seeedash after verification. If ROM access fails, follow the board-specific physical guidance in [RECOVERY.md](RECOVERY.md); Up is not a ROM BOOT strap. Do not guess test pads. These manual instructions have not been executed against a device during this work.

## Isolation and licensing

The host runs `docker build/run`. The container receives no Docker socket, serial device, host source mount, credentials or privileged flag. Runtime capabilities are dropped and `no-new-privileges` is set. It runs as the host UID/GID, copies image source into an ephemeral private workspace and writes only its output bind directory. Immutable SDK/tool binaries stay in the tools image; PlatformIO's mutable Python helper environment is separately seeded in the disposable workspace with pinned constraints. No existing container is inspected or changed.

The image pins Python by image digest, ESP-IDF by commit, the compiler archive by IDF's checked tool metadata, Python packages by exact versions, and Debian dependency resolution by a dated snapshot. GitHub Actions are pinned by full commit. This is not a promise of a fully hermetic, cross-host bit-identical build.

**Local outputs contain Seeedash and must not be publicly uploaded.** Do not publish a running container snapshot with `docker commit/export`, any output bundle, or an image into which runtime output was copied. SDK test fixtures/tool binaries are distinct from the forbidden Seeedash/CrossPoint application and complete Flash artifacts. No prebuilt Docker image is published by this project. [LICENSING.md](LICENSING.md) remains authoritative.

All standard OTA paths remain unsupported and forbidden. New Docker outputs have no new hardware validation. Physical power/reset/wake risks and the non-atomic paired update remain unchanged.
