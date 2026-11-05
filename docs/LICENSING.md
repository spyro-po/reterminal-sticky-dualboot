# Licensing and provenance

This is a conservative publication decision based on the inspected sources, not a claim of legal clearance for a combined firmware binary. Local downloading/building does not establish a right to distribute the result.

## Included source

| Material | Provenance | Public source treatment |
| --- | --- | --- |
| Eight-file CrossPoint patch | CrossPoint commit `e8299b5f126817282939059d6505f90429489276` plus Stage 4 integration | MIT; preserve CrossPoint copyright/license |
| FreeInk SDK | Pinned submodule `5e94fe7480f019c89fbf691aef87523eb1b46704` | Not vendored; MIT and SDK dependency notices retained |
| Bootloader entry | Adapted from ESP-IDF v5.4, commit `67c1de1eebe095d554d281952fde63c16ee2dca0` | Apache-2.0 header and license retained |
| Original policy, wrappers, scripts and documentation | This integration | Scoped MIT grant in root LICENSE |
| Reader+ | Angel Esteban; studied as a switching reference | No source copied; MIT license retained for attribution |
| Device photographs, schematic and vendor image | Not supplied as licensed release assets | Not included; official documentation is linked |

See [CrossPoint's license](https://github.com/crosspoint-reader/crosspoint-reader/blob/e8299b5f126817282939059d6505f90429489276/LICENSE), [FreeInk's license](https://github.com/Free-Ink/freeink-sdk/blob/5e94fe7480f019c89fbf691aef87523eb1b46704/LICENSE), [Reader+](https://github.com/estebangel-crypto/reader-plus), and [ESP-IDF's license](https://github.com/espressif/esp-idf/blob/67c1de1eebe095d554d281952fde63c16ee2dca0/LICENSE).

## Seeedash: not cleared for redistribution

The official [1.2.0 manifest](https://github.com/Seeed-Projects/reterminal-sticky-playground-registry/blob/f0479400594d8f9a3d7fd7b282f2d7b2a1bdbd0e/firmwares/sticky-factory/firmware/1.2.0/manifest.json) provides an image, size and SHA-256 but no artifact-specific firmware license. The registry has a repository-level MIT license; this alone was not treated as sufficiently explicit permission for distributing a compiled factory firmware with all its embedded components. Public availability is not proof of permission.

**Policy:** do not include Seeedash BIN, full merged image, factory data extents or device Flash dumps in Git or Releases. The downloader fetches the immutable official URL and verifies its manifest digest. Seek explicit artifact-specific permission and dependency terms before reconsidering this policy. No permission was requested from or granted by Seeed during this preparation.

## CrossPoint: MIT is not the complete binary license

The linked application includes Arduino-wolfSSL **5.7.2**, WebSockets **2.7.3**, Arduino-ESP32 **3.3.11** and other dependencies. The installed wolfSSL source headers say GPL v2 or later; its package metadata says `GPL-2.0-only`. This discrepancy is recorded rather than silently resolved. WebSockets identifies LGPL-2.1, and Arduino-ESP32 contains LGPL-2.1 material. Their terms survive compilation regardless of the MIT license on the top-level reader.

Before a public CrossPoint BIN can be cleared, finish the combined-work compatibility assessment, exact complete corresponding-source package and build scripts, applicable source/object/relinking obligations, notices, and treatment of prebuilt SDK/system libraries. A URL to a moving upstream branch or the MIT patch alone is not presented as satisfying these obligations. A separate commercial license, if applicable, would also need to be evidenced; none is assumed.

**Policy:** v1.0.0 is source-only. No compiled CrossPoint BIN or update ZIP is publicly distributed. The locally generated `segments.json` describes a private matched pair, not permission to upload it. This does not assert that compliant binary distribution is impossible; it has not been completed here.

## Bootloader binary

The bootloader source is included with its applicable terms. A compiled loader also links IDF/toolchain components (including Xtensa HAL, newlib, GCC runtime and micro-ecc). Although relevant permissive and runtime-exception notices were located, a separate complete binary dependency/notice closure has not been established for this release. To keep the public package unambiguous and avoid an unsafe standalone pinned loader, **no compiled bootloader is included either**.

License copies for examined dependencies are provided for traceability. They are not an assertion that every dependency is included in this source package or that those texts alone satisfy all binary obligations. Reassess the exact final ELF/map and complete dependency sources before changing the source-only policy.

## v1.1.0 local Docker tooling

The Dockerfile/launcher are original integration source under the scoped MIT grant. The tools image is built locally, with upstream SDK/compiler/Python dependencies under their own terms; no prebuilt image is distributed or automatically pushed to a registry. ESP-IDF's dependency-constraint snapshot retains its upstream provenance and Apache-2.0 notice where applicable. A tools-image redistribution audit is separate from this source release.

The official Seeedash download occurs only when the user runs a local build, in a disposable container workspace. Generated firmware is exported to a local output bind directory. Neither that output nor a runtime container snapshot may be uploaded, committed into an image layer, or attached to public Releases under the existing policy. CrossPoint combined-binary obligations remain unresolved. New dependency pins do not change any firmware redistribution permission.
