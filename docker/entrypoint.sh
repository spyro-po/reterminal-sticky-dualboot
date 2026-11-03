#!/bin/sh
set -eu
umask 077
# Fail before creating a workspace if the immutable SDK installation is incomplete.
test -x /opt/esp/idf-python/bin/python
test -x /opt/esp/tools/tools/xtensa-esp-elf/esp-14.2.0_20241119/xtensa-esp-elf/bin/xtensa-esp-elf-gcc
test -r /opt/sticky/locks/espidf.constraints.v5.4.txt
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
