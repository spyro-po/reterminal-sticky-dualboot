#!/bin/sh
set -eu
umask 077
mkdir -p "$HOME" /tmp/sticky-project
# Only the source allowlist baked into the image is copied, never host source/cache.
cp -R /opt/sticky/source/. /tmp/sticky-project/
mkdir -p "$HOME/.espressif"
ln -s /opt/esp/tools/tools "$HOME/.espressif/tools"
cp /opt/sticky/locks/espidf.constraints.v5.4.txt "$HOME/.espressif/"
export IDF_TOOLS_PATH="$HOME/.espressif"
if [ "${1:-}" = build ]; then
  # PlatformIO's helper installs editable esptool into its own writable penv.
  mkdir -p /tmp/sticky-project/.cache/platformio
  cp -R /opt/sticky/python /tmp/sticky-project/.cache/platformio/penv
fi
exec /opt/sticky/python/bin/python /tmp/sticky-project/scripts/installer.py "$@"
