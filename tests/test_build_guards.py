"""Execute the real early target rejection with a fake SCons command context.
No PlatformIO process, serial port or device-write target is invoked.
"""
from pathlib import Path
import sys
import types

source = Path(__file__).resolve().parents[1] / 'crosspoint/platformio_build.py'
scons = types.ModuleType('SCons')
script = types.ModuleType('SCons.Script')
sys.modules['SCons'] = scons
sys.modules['SCons.Script'] = script
for target in ['upload', 'uploadfs', 'erase', 'erase_flash', 'flash', 'buildfs', 'debug', 'unknown']:
    script.COMMAND_LINE_TARGETS = [target]
    try:
        exec(compile(source.read_text(), str(source), 'exec'), {'Import': lambda name: None})
    except RuntimeError as error:
        assert 'targets are forbidden' in str(error)
    else:
        raise AssertionError(target)
print('PASS: 8 device-write/debug/unknown targets rejected before environment/flash access')
