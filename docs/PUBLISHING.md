# Publication checklist

The intended repository name is `reterminal-sticky-dualboot`. Local preparation and a local commit do not authorize publication. The owner explicitly requires confirmation before public repository creation, push or GitHub Release publication.

Before asking for that confirmation:

1. Finish source/build review, offline checks, source inventory and privacy/license audit.
2. Commit the reviewed source locally; inspect `git status` and the exact commit.
3. Generate the source-only v1.0.0 assets with `scripts/package_release.py` and verify SHA256SUMS.
4. State that no firmware BIN, factory image or private backup is included, and disclose outstanding binary-licensing and hardware limits.

In the preparation environment, GitHub CLI was not installed. The connected GitHub application was authenticated as `spyro-po`; the requested public repository URL returned 404. This is not proof that no conflicting private repository exists. No repository, push, tag or release was published. No GitHub token was copied into this repository.

The available GitHub connector can read source metadata but does not provide the required repository-creation and binary Release-upload operations. After approval, use a properly authenticated GitHub CLI installed from its official distribution, or the GitHub web interface plus Git transport. Prefer browser/device authentication or a credential manager. Never paste access tokens into files, logs, shell history or release assets.

After the owner's approval, recheck the authenticated owner, repository-name availability, staged/committed contents and asset hashes. Create the repository without auto-generating conflicting files, push the reviewed commit, tag that commit as `v1.0.0`, and publish only the audited source archive, release notes, source-only manifest and SHA256SUMS. Do not use wildcard uploads from `.local/` or attach build logs/backups. No publication script in this repository creates a remote repository or uploads anything.
