# Pinned local build

For the Docker path without manual host SDK installation, use [DOCKER_INSTALL.md](DOCKER_INSTALL.md). The native path below remains supported for development.

Run from the repository root on Linux with Git, Python 3.12, a C/C++ host compiler (or the pinned Zig package), and ESP-IDF v5.4's supported build prerequisites. Several GiB of downloads and free disk space are needed. Initial dependency installation requires the network; verification after caching can run offline. The recipe pins source revisions and principal tools; it is not a complete cross-host hermetic dependency lock.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python scripts/prepare_crosspoint.py
.venv/bin/python scripts/fetch_seeedash.py
```

Install ESP-IDF **v5.4**, exact commit `67c1de1eebe095d554d281952fde63c16ee2dca0`, in a separate tools directory with its required submodules, Python environment and ESP32-S3 toolchain (`esp-14.2.0_20241119`). Follow [Espressif's v5.4 installation guide](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/get-started/index.html). Do not replace the application toolchain with this older bootloader toolchain.

After installing/exporting that IDF environment, set these paths for your installation:

```sh
export IDF54_PATH=/path/to/esp-idf-v5.4
export IDF54_PYTHON=/path/to/idf5.4_python_env/bin/python
export IDF_TOOLS_PATH=/path/to/idf-tools
.venv/bin/python scripts/build.py --label build1 --clean-app
```

The build prepares only `.work/crosspoint-reader`, applies the reviewed patch to its pinned revision, and checks the pinned FreeInk submodule. PlatformIO uses this repository's `.cache/platformio`, not a shared cache. A known upstream SCons metadata mismatch is repaired only in this private cache, for the exact known version. Unknown versions fail closed. SCons object/ELF caching is disabled in the local profile: a fresh link must emit the cross-reference map required by the audit. No device-write target is invoked.

After the application link audit, the builder generates a private CrossPoint digest header and compiles the custom bootloader against it. It verifies both image headers, checksums and appended SHA-256, ABI markers, supported SDK configuration and exact partition table. Required NVS/write wrappers and the Wi-Fi NVS callback are checked in the actual ELF and cross-reference map. SPIFFS/LittleFS mount and format APIs must not be linked. The host tests then run. The output is:

```text
.local/out/build1/update/bootloader.bin
.local/out/build1/update/crosspoint.bin
.local/out/build1/update/segments.json
```

The pair is inseparable: the bootloader pins this specific CrossPoint body digest. Local build outputs and logs are ignored by Git. Neither success nor a valid hash proves the new pair works on hardware. The CrossPoint UI keeps the tested integration version string `2.0.0-dualboot-menu-test`; the new tooling version is `1.1.0`; `segments.json` retains its compatible format version `1.0.0`.

Create the optional local fresh image only after the build gates pass:

```sh
.venv/bin/python scripts/assemble.py --bundle .local/out/build1/update --output .local/out/build1/fresh-32MiB.bin
```

This output contains Seeedash and must not be uploaded. The official download is pinned by both registry commit and SHA-256. The original vendor file is never modified.

For a clean same-path reproducibility comparison, run the builder again with `--clean-app --label build2`, then compare both code-segment hashes. `SOURCE_DATE_EPOCH` is fixed in the source lock. Cross-host or different-path bit reproducibility is not promised. Saved dependency names and observed build versions are in `manifests/`; do not use floating upstream sources for this release.

Host checks after preparing dependencies:

```sh
.venv/bin/python tests/run_tests.py --idf-path "$IDF54_PATH"
```

These tests use mocks for hardware and selected real-source function extraction. They cannot measure battery rails, wake timing, e-paper state, or the complete SDK call-chain stack high-water.
