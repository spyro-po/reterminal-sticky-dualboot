"""Snapshot the first sdkconfig.h on the actual compilation include path."""
from pathlib import Path
Import('env')
for entry in env.Flatten(env.get('CPPPATH', [])):
    candidate = Path(env.subst(str(entry))) / 'sdkconfig.h'
    if candidate.is_file():
        destination = Path(env.subst('$BUILD_DIR')) / 'dualboot-sdkconfig.h'
        destination.write_bytes(candidate.read_bytes())
        break
else:
    raise RuntimeError('Cannot determine the effective SDK configuration')
