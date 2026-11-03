"""Prepare pioarduino's private application-IDF Python, separate from IDF5.4."""
import json
from pathlib import Path
import subprocess
from common import ROOT,LOCK,require,sha


# Runs with the application interpreter, isolated from caller site/PYTHONPATH.
PROBE='''
import importlib.metadata as m,json,pathlib,re,sys
assert pathlib.Path(sys.prefix).resolve()==pathlib.Path(sys.argv[1]).resolve(), 'Wrong application interpreter'
expected=dict(re.findall(r'^([A-Za-z0-9_.-]+)==([A-Za-z0-9.+!-]+)',pathlib.Path(sys.argv[2]).read_text(),re.M))
normalize=lambda s:s.lower().replace('_','-').replace('.','-')
actual={normalize(d.metadata['Name']):d.version for d in m.distributions() if d.metadata.get('Name')}
assert actual=={normalize(k):v for k,v in expected.items()}, 'Application Python package drift'
import idf_component_manager,idf_component_manager.prepare_components
import esp_idf_kconfig,kconfiglib,kconfgen,cryptography,pyparsing
print(json.dumps({'python':sys.executable,'prefix':sys.prefix,'packages':actual},sort_keys=True))
'''


def initialize_app_idf(checkout,label,env,run):
    builder=json.loads((ROOT/'manifests/builder.lock.json').read_text())
    config=builder['app_idf_environment']
    require(config['idf_version']==LOCK['platformio']['app_idf'],'Application IDF version differs from lock')
    lock=ROOT/config['lock']
    require(sha(lock.read_bytes())==builder['files'][config['lock']],'Application Python lock integrity mismatch')
    core=Path(env['PLATFORMIO_CORE_DIR']).resolve()
    platform=core/'platforms/espressif32/builder/frameworks/espidf.py'
    requirements=core/'packages/framework-espidf/tools/requirements/requirements.core.txt'
    require(sha(platform.read_bytes())==config['upstream_builder_sha256'] and
            sha(requirements.read_bytes())==config['core_requirements_sha256'],
            'Application IDF Python bootstrap contract changed; review required')
    require(not (requirements.parents[2]/'.pio_skip_pypackages').exists(),
            'Application IDF dependency checks must not be skipped')
    directory=core/'penv'/('.espidf-'+config['idf_version'])
    require(not directory.is_symlink() and directory.resolve().is_relative_to(core),
            'Application IDF environment must not be a symlink outside the private core')
    marker=directory/'pio-idf-venv.json'
    require(not marker.is_symlink(),'Application IDF metadata must not be a symlink')
    if marker.exists():marker.unlink()
    python=directory/'bin/python'
    uv=core/'penv/bin/uv'
    base=core/'penv/bin/python'
    app_env=dict(env)
    for name in ['UV_OVERRIDE','UV_CONSTRAINT','UV_BUILD_CONSTRAINT','PIP_CONSTRAINT','PYTHONPATH','PYTHONHOME']:
        app_env.pop(name,None)
    app_env.update(UV_CONSTRAINT=str(lock),UV_BUILD_CONSTRAINT=str(lock),UV_PYTHON_DOWNLOADS='never')
    if not python.is_file():
        run([uv,'venv','--clear','--python',base,directory],checkout,label+'-app-idf-create.log',app_env)
    run([python,'-I','-c',
         "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path(sys.argv[1]).resolve(), 'Wrong application interpreter'",
         directory],checkout,label+'-app-idf-interpreter.log',app_env)
    # Sync repairs stale/partially installed caches and removes unpinned packages.
    run([uv,'pip','sync','--python',python,'--require-hashes',lock],
        checkout,label+'-app-idf-install.log',app_env)
    run([uv,'pip','check','--python',python],checkout,label+'-app-idf-check.log',app_env)
    run([python,'-I','-c',PROBE,directory,lock],checkout,label+'-app-idf-probe.log',app_env)
    version=subprocess.check_output([python,'-I','-c',
        "import sys;print('{0}.{1}.{2}-{3}.{4}'.format(*list(sys.version_info)))"],env=app_env,text=True).strip()
    # Write upstream's cache metadata only AFTER actual installation/import checks.
    # Its unchanged ensure_python_venv_available still checks this environment.
    marker.write_text(json.dumps({'version':config['pio_environment_version'],
        'python_version':version,'deps_hash':sha(json.dumps(config['dependencies'],sort_keys=True).encode())},indent=2)+'\n')
    print('Application IDF Python imports and exact hashed package lock verified: '+str(python),flush=True)
