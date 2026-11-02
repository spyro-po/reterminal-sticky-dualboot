"""Build-only integration; retained write guards and shared selector policy."""
from pathlib import Path
import json
Import('env')
from SCons.Script import COMMAND_LINE_TARGETS
allowed={'buildprog','checkprogsize','clean','size','compiledb','envdump','idedata','nobuild'}
if any(t not in allowed for t in COMMAND_LINE_TARGETS):
    raise RuntimeError('Dual-boot profile is build-only; device-write/debug/filesystem targets are forbidden')
root=(Path(env.subst('$PROJECT_DIR'))/env.GetProjectOption('custom_dualboot_root')).resolve()
rows=[line.strip()[len('-Wl,--wrap='):].split(',--wrap=')
      for line in (root/'crosspoint/link_flags.txt').read_text().splitlines()
      if line.strip().startswith('-Wl,--wrap=')]
symbols=[name for row in rows for name in row]
env.Append(LINKFLAGS=['-Wl,--wrap='+name for name in symbols]+
           ['-Wl,-u,__wrap_'+name for name in symbols]+['-Wl,-u,sticky_dualboot_build_contract','-Wl,--cref'])
env.Append(CPPPATH=[str(root/'firmware/include')])
env.BuildSources('$BUILD_DIR/dualboot_policy',str(root/'firmware/bootloader_components/main'),
                 src_filter=['+<boot_policy.c>'])
env.BuildSources('$BUILD_DIR/dualboot_guard',str(root/'crosspoint'),
                 src_filter=['+<nvs_isolation.c>','+<flash_guards.c>'])
original=env.AddPostAction
def filter_merge(environment,files,action):
    if getattr(getattr(action,'execfunction',None),'__name__','')=='esp32_create_combined_bin':
        print('Dual boot: unchecked automatic factory merge disabled')
        return None
    return original(files,action)
env.AddMethod(filter_merge,'AddPostAction')
out=Path(env.subst('$BUILD_DIR'));out.mkdir(parents=True,exist_ok=True)
(out/'dualboot-link-policy.json').write_text(json.dumps({'wrap_symbols':symbols,'profile':env.subst('$PIOENV')},indent=2)+'\n')
