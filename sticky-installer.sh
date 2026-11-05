#!/usr/bin/env bash
# Host launcher: Docker CLI stays on the host. No serial device is passed through.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if [[ $# -eq 0 || "${1:-}" == "--help" || "${1:-}" == "help" ]]; then
  cat <<'HELP'
Usage: ./sticky-installer.sh COMMAND [OPTIONS]
Commands: list, build, verify, info, check-updates
  --combination ID           Default: cp-2.0.0-seeedash-1.2.0
  --output DIRECTORY         Host output root (default: ./out)
  --directory NAME           Existing bundle directory under the output root
  --mode artifacts|fresh|preserve|recovery  verify/info mode
  --backup FILE              Private full device backup, mounted read-only
  --confirm-layout protected-reference    Required for Preserve Data
  --reproducibility-check    Compile twice and require byte-identical outputs
  --report NAME.json          New metadata report filename; existing reports are kept
Firmware is built locally. No command flashes, erases or accesses a serial device.
Run from Linux or WSL2 with Docker Desktop's Linux backend.
HELP
  exit 0
fi
command -v docker >/dev/null || { echo 'ERROR: Docker CLI is missing. See docs/DOCKER_INSTALL.md.' >&2; exit 2; }
ARGS=(); OUTPUT="$ROOT/out"; BACKUP=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) [[ $# -ge 2 && -n "$2" ]] || { echo 'ERROR: --output requires a path' >&2; exit 2; }; OUTPUT=$2; shift 2 ;;
    --backup) [[ $# -ge 2 && -f "$2" ]] || { echo 'ERROR: --backup requires an existing file' >&2; exit 2; }; BACKUP=$(realpath -- "$2"); shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
case "${ARGS[0]:-}" in list|build|verify|info|check-updates) ;; *) echo 'ERROR: Unknown command; use --help.' >&2; exit 2 ;; esac
mkdir -p -- "$OUTPUT"
OUTPUT=$(cd -- "$OUTPUT" && pwd -P)
[[ "$ROOT/" != "$OUTPUT/"* ]] || { echo 'ERROR: Output must not be the repository root or its ancestor.' >&2; exit 2; }
[[ "$OUTPUT$BACKUP" != *','* && "$OUTPUT$BACKUP" != *$'\n'* ]] || { echo 'ERROR: Docker bind paths must not contain commas or newlines.' >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo 'ERROR: Docker daemon is unavailable. Start Docker Engine/Desktop; no firmware was built.' >&2; exit 2; }
IMAGE=reterminal-sticky-dualboot-builder:1.1.0
docker build --platform linux/amd64 --tag "$IMAGE" --file "$ROOT/Dockerfile" "$ROOT" >&2
MOUNTS=(--mount "type=bind,src=$OUTPUT,dst=/output")
if [[ -n "$BACKUP" ]]; then
  MOUNTS+=(--mount "type=bind,src=$BACKUP,dst=/device-backup.bin,readonly")
  ARGS+=(--backup /device-backup.bin)
fi
exec docker run --rm --platform linux/amd64 --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges "${MOUNTS[@]}" "$IMAGE" "${ARGS[@]}"
