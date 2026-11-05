# Source-only publication

Repository: `spyro-po/reterminal-sticky-dualboot`. The owner approved the v1.1.0
source-only release. Firmware binaries, complete Flash images, Docker images,
device backups and private data remain excluded. New publication actions need
owner authorization; this approval covers finalizing PR#1 and v1.1.0.

1. Audit the exact source commit, licenses, secrets, source inventory and archive.
   Verify all required CI checks pass and the PR is mergeable.
2. Mark PR#1 Ready for Review and merge with a merge commit, retaining history.
   Confirm the default branch contains `989edad` and the hardware report.
3. Create an annotated `v1.1.0` tag on that merge commit and push that tag only.
4. Package the clean merged tree with `scripts/package_release.py`. Retain older
   local packages privately; never upload a stale package or use wildcard uploads.
5. Publish only `reterminal-sticky-dualboot-v1.1.0-source.zip`, `RELEASE_NOTES.md`
   and `SHA256SUMS.txt`. The uploaded checksum file must cover the two other assets;
   no checksum entry may depend on an unpublished companion file.
6. Download the public assets again, check their hashes and source-only contents,
   and verify the annotated tag resolves to the merge commit. Test the README's
   tag checkout and CLI help/list path. No device operation is part of publication.

The local packager also writes a source-only manifest for provenance; this need
not be uploaded as a separate asset. GitHub's automatic source archives contain
the tracked source tree only. All standard OTA stays unsupported and forbidden.
Exact-build owner hardware evidence never validates every rebuild or device.

Use authenticated GitHub CLI/Git with a credential manager or device/browser
authentication. Never put tokens in source, command arguments, logs or assets.
No repository script automatically merges, tags, publishes or flashes a device.
