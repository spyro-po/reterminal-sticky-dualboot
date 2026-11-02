#!/usr/bin/env python3
"""Build a private, matched firmware pair. No flash, erase, push or release command."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from common import ROOT,LOCK,require,sha,image,partition_table,parse_table,validate_pair,write_new
from prepare_crosspoint import prepare,CHECKOUT
from elf_audit import crosspoint_checks


def environment():
    env=dict(os.environ)
    env.update(PLATFORMIO_CORE_DIR=str(ROOT/'.cache/platformio'),
               SOURCE_DATE_EPOCH=str(LOCK['source_date_epoch']),PYTHONDONTWRITEBYTECODE='1',TZ='UTC')
    env.pop('PLATFORMIO_BUILD_CACHE_DIR',None)
    return env


def run(command,cwd,log,env):
    path=ROOT/'.local/logs'/log
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w') as stream:
        result=subprocess.run([str(a) for a in command],cwd=cwd,env=env,
                              stdout=stream,stderr=subprocess.STDOUT)
    require(result.returncode==0,'Command failed; inspect private log '+str(path.relative_to(ROOT)))


def pio_command():
    configured=os.environ.get('PIO_COMMAND')
    if configured:
        return shlex.split(configured)
    python=ROOT/'.venv/bin/python'
    return [str(python),'-m','platformio'] if python.exists() else ['pio']


def prepare_platform(command,env):
    version=subprocess.check_output(command+['--version'],env=env,text=True)
    require(LOCK['platformio']['version'] in version,'Use the pinned pioarduino core version')
    core=Path(env['PLATFORMIO_CORE_DIR'])
    platform=core/'platforms/espressif32/platform.json'
    if not platform.exists():
        run(command+['pkg','install','-g','-p',LOCK['platformio']['platform_url']],ROOT,'platform-install.log',env)
    data=json.loads(platform.read_text())
    require(data['version']==LOCK['platformio']['platform_version'],'Unexpected PlatformIO platform')
    scons=data['packages']['tool-scons']
    # Compatibility repair only in this repository's isolated cache, never a global installation.
    if scons.get('package-version')=='4.40801.0':
        scons['package-version']='4.41101.0'
        scons['version']='https://github.com/pioarduino/scons/releases/download/4.11.1/scons-local-4.11.1.tar.gz'
        platform.write_text(json.dumps(data,indent=2)+'\n')
    require(scons.get('package-version')=='4.41101.0','Unexpected SCons metadata; do not guess a repair')


def build(args):
    require(re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,31}',args.label),'Invalid local output label')
    checkout=prepare()
    env=environment()
    command=pio_command()
    prepare_platform(command,env)
    if args.clean_app:
        run(command+['run','-e','sticky-dualboot-test','-t','clean'],checkout,args.label+'-clean.log',env)
    run(command+['run','-e','sticky-dualboot-test'],checkout,args.label+'-crosspoint.log',env)
    cpdir=checkout/'.pio/build/sticky-dualboot-test'
    cp,ci=crosspoint_checks(cpdir)
    require(sha((cpdir/'partitions.bin').read_bytes())==sha(partition_table()),'Built table differs from canonical')
    idf=Path(args.idf_path).resolve() if args.idf_path else None
    require(idf and (idf/'tools/idf.py').is_file(),'Set IDF54_PATH/--idf-path to ESP-IDF v5.4')
    require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=idf,text=True).strip()==LOCK['bootloader_idf']['commit'],
            'Bootloader requires the exact pinned ESP-IDF commit')
    require(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=idf).strip(),
            'ESP-IDF checkout has unreviewed tracked changes')
    project=ROOT/'.build/bootloader-project'
    project.parent.mkdir(exist_ok=True)
    shutil.copytree(ROOT/'firmware',project,dirs_exist_ok=True)
    shutil.copyfile(ROOT/'partitions/sticky-32m.csv',project/'partitions.csv')
    digest=ci['body_sha256']
    pin=('/* Generated only after the application link audit. */\n#pragma once\n'
         f'#define CROSSPOINT_IMAGE_LEN {len(cp)}\n#define CROSSPOINT_IMAGE_SHA_BYTES '
         '{'+','.join('0x'+digest[i:i+2] for i in range(0,64,2))+'}\n')
    (project/'include/crosspoint_pin.h').write_text(pin)
    idf_env=dict(env,IDF_PATH=str(idf))
    if args.idf_tools_path:
        idf_env['IDF_TOOLS_PATH']=str(Path(args.idf_tools_path).resolve())
    # Honor a standard exported IDF environment; prepend only explicitly located tools.
    paths=[ROOT/'.cache/platformio/packages/tool-cmake/bin',ROOT/'.cache/platformio/packages/tool-ninja']
    tools=Path(idf_env.get('IDF_TOOLS_PATH',str(Path.home()/'.espressif')))
    compiler=tools/'tools/xtensa-esp-elf'/LOCK['bootloader_idf']['toolchain']/'xtensa-esp-elf/bin'
    if compiler.is_dir():paths.insert(0,compiler)
    idf_env['PATH']=os.pathsep.join(str(p) for p in paths)+os.pathsep+idf_env['PATH']
    idf_python=args.idf_python or sys.executable
    run([idf_python,idf/'tools/idf.py','-B','build','bootloader'],project,args.label+'-bootloader.log',idf_env)
    boot=(project/'build/bootloader/bootloader.bin').read_bytes()
    bi,ci=validate_pair(boot,cp)
    config=(project/'sdkconfig').read_text()
    for setting in ['CONFIG_ESPTOOLPY_FLASHSIZE_32MB=y','CONFIG_PARTITION_TABLE_OFFSET=0x8000',
                    'CONFIG_PARTITION_TABLE_CUSTOM=y','CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"']:
        require(setting in config,'Bootloader configuration mismatch: '+setting)
    for setting in ['CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE','CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK',
                    'CONFIG_BOOTLOADER_SKIP_VALIDATE_IN_DEEP_SLEEP','CONFIG_BOOTLOADER_FACTORY_RESET',
                    'CONFIG_BOOTLOADER_APP_TEST','CONFIG_SECURE_BOOT','CONFIG_SECURE_FLASH_ENC_ENABLED']:
        require(setting+'=y' not in config,'Unsupported bootloader option '+setting)
    # Check the official generator agrees with the independent stdlib validator.
    generated=ROOT/'.build/idf-partitions.bin'
    run([idf_python,idf/'components/partition_table/gen_esp32part.py',ROOT/'partitions/sticky-32m.csv',generated],
        ROOT,args.label+'-partition-generator.log',idf_env)
    require(generated.read_bytes()==partition_table(),'ESP-IDF and independent table generators disagree')
    test_env=dict(idf_env,DUALBOOT_PIN_INCLUDE=str(project/'include'))
    run([sys.executable,ROOT/'tests/run_tests.py','--idf-path',idf],ROOT,args.label+'-host-tests.log',test_env)
    out=ROOT/'.local/out'/args.label/'update'
    require(not out.exists(),'Local output already exists; choose a new --label')
    out.mkdir(parents=True)
    for name,data in [('bootloader.bin',boot),('crosspoint.bin',cp)]:write_new(out/name,data)
    segments=[]
    for name,offset,info in [('bootloader.bin',0,bi),('crosspoint.bin',0x690000,ci)]:
        segments.append(dict(file=name,offset=hex(offset),**info))
    meta={'version':'1.0.0','segments':segments,'partition_table_sha256':sha(partition_table()),
          'source':LOCK['crosspoint'],'bootloader_idf':LOCK['bootloader_idf'],
          'hardware_tested_this_build':False,'source_date_epoch':LOCK['source_date_epoch'],
          'not_power_fail_atomic':True,'ota':'UNSUPPORTED/FORBIDDEN',
          'public_redistribution':'CrossPoint binary withheld pending combined-binary license compliance; local use only'}
    write_new(out/'segments.json',(json.dumps(meta,indent=2)+'\n').encode())
    write_new(out/'SHA256SUMS.txt',''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in sorted(out.iterdir())).encode())
    print(json.dumps({'local_update':str(out),'bootloader':bi,'crosspoint':ci,'hardware_tested':False},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--idf-path',default=os.environ.get('IDF54_PATH') or os.environ.get('IDF_PATH'))
    parser.add_argument('--idf-python',default=os.environ.get('IDF54_PYTHON'))
    parser.add_argument('--idf-tools-path',default=os.environ.get('IDF_TOOLS_PATH'))
    parser.add_argument('--label',default='build1')
    parser.add_argument('--clean-app',action='store_true')
    build(parser.parse_args())
