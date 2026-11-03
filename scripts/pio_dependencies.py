"""Initialize the pinned project dependencies before SCons can execute pre-scripts."""
import json
from pathlib import Path
from common import LOCK,require


def framework_sources():
    arduino=LOCK['platformio']['arduino']
    idf=LOCK['platformio']['app_idf']
    base=f'https://github.com/espressif/arduino-esp32/releases/download/{arduino}/esp32-core-{arduino}'
    return {
        'framework-arduinoespressif32':base+'.tar.xz',
        'framework-arduinoespressif32-libs':base+'-libs.tar.xz',
        'framework-espidf':f'https://github.com/pioarduino/esp-idf/releases/download/v{idf}/esp-idf-v{idf}.tar.xz',
    }


def validate_frameworks(core):
    """Reject incomplete/wrong-source caches rather than skipping a pre-script.

    These are package prerequisites, not an archive/content integrity claim.
    The existing final-link, configuration and image audits still apply.
    """
    packages=Path(core)/'packages'
    for name,url in framework_sources().items():
        directory=packages/name
        require((directory/'.piopm').is_file() and (directory/'package.json').is_file(),
                'PlatformIO initialization incomplete: '+name+' metadata missing')
        metadata=json.loads((directory/'.piopm').read_text())
        manifest=json.loads((directory/'package.json').read_text())
        require(metadata.get('name')==name and manifest.get('name')==name and
                metadata.get('spec',{}).get('uri')==url and
                bool(manifest.get('version')) and metadata.get('version') in
                (manifest['version'],manifest['version']+'.0'),
                'PlatformIO initialization source/metadata mismatch: '+name)
    libs=packages/'framework-arduinoespressif32-libs/esp32s3'
    require((libs/'sdkconfig').is_file() or (libs/'sdkconfig.orig').is_file(),
            'PlatformIO initialization incomplete: ESP32-S3 SDK configuration missing')


def initialize_project(command,checkout,label,env,run):
    core=Path(env['PLATFORMIO_CORE_DIR'])
    platform=json.loads((core/'platforms/espressif32/platform.json').read_text())
    require(platform.get('version')==LOCK['platformio']['platform_version'] and
            all(platform.get('packages',{}).get(name,{}).get('version')==url
                for name,url in framework_sources().items()),
            'PlatformIO platform framework sources differ from approved versions')
    missing=[name for name in framework_sources() if not (core/'packages'/name/'package.json').is_file()]
    print('PlatformIO frameworks missing before project initialization: '+json.dumps(missing),flush=True)
    # Environment-scoped install resolves optional frameworks and pinned lib_deps
    # without executing SCons/pre-scripts. Do this on warm caches as well.
    run(command+['pkg','install','--environment','sticky-dualboot-test','--no-save'],
        checkout,label+'-dependencies.log',env)
    validate_frameworks(core)
    print('PlatformIO pinned framework prerequisites verified before clean/build.',flush=True)
