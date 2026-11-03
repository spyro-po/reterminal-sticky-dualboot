#!/usr/bin/env python3
"""Local-only builder and offline installer preflight. Never flashes a device."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from common import ROOT,LOCK,require,sha,official
from compatibility import manifest,select,MANIFEST
from bundle import bundle_path,verify,export
from fetch_seeedash import fetch
from process_log import new_session,run_logged


def build_bundle(args):
    entry=select(args.combination)
    target=bundle_path(args.output_root,args.directory or entry['id'])
    require(not target.exists(),'Output already exists; select a new --directory')
    diagnostics=new_session(args.output_root/'diagnostics')
    print('Private build diagnostics (persist after container exit): '+str(diagnostics),flush=True)
    env=dict(os.environ,STICKY_BUILD_LOG_DIR=str(diagnostics))
    factory=official(fetch(ROOT/'.local/vendor/seeedash-1.2.0.bin').read_bytes())
    print('Official Seeedash SHA-256 verified. Preparing the pinned CrossPoint source and matched loader.',flush=True)
    labels=['installer-first']+(['installer-repeat'] if args.reproducibility_check else [])
    for label in labels:
        project=ROOT/'.build/bootloader-project'
        require(not project.is_symlink(),'Generated bootloader project must not be a symlink')
        # IDF rejects a cached project configured with a different Python environment.
        shutil.rmtree(project,ignore_errors=True)
        print('Building '+label+'; detailed progress: '+str(diagnostics/(label+'-driver.log')),flush=True)
        run_logged([sys.executable,ROOT/'scripts/build.py','--label',label,'--clean-app'],
                   ROOT,label+'-driver.log',env,diagnostics)
    first=ROOT/'.local/out'/labels[0]/'update'
    if len(labels)==2:
        other=ROOT/'.local/out'/labels[1]/'update'
        for name in ['bootloader.bin','crosspoint.bin']:
            require((first/name).read_bytes()==(other/name).read_bytes(),'Reproducibility mismatch: '+name+'; no export was produced')
    versions={d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata.get('Name')}
    packages={}
    for path in sorted((ROOT/'.cache/platformio/packages').glob('*/package.json')):
        data=json.loads(path.read_text());packages[path.parent.name]=data.get('version','unknown')
    runtime_python=ROOT/'.cache/platformio/penv/bin/python'
    runtime_versions={}
    if runtime_python.is_file():
        runtime_versions=json.loads(subprocess.check_output([runtime_python,'-c',
            "import importlib.metadata as m,json;print(json.dumps({d.metadata['Name']:d.version for d in m.distributions() if d.metadata.get('Name')}))"],text=True))
        normalized={k.lower().replace('_','-'):v for k,v in runtime_versions.items()}
        for row in (ROOT/'docker/requirements-pio.lock').read_text().splitlines():
            if row and not row.startswith('#'):
                name,version=row.split('==')
                require(normalized.get(name.lower().replace('_','-'))==version,'Runtime Python package drift: '+name)
    else:
        require(False,'PlatformIO runtime Python environment is missing')
    report={'builder_version' :'1.1.0','combination':entry['id'],'channel':entry['channel'],
            'crosspoint':entry['crosspoint'],'seeedash':entry['seeedash'],'bootloader':entry['bootloader']['version'],
            'partition_layout':entry['partitions']['id'],'build_profile':entry['build_profile']['environment'],
            'compatibility_manifest_sha256':sha(MANIFEST.read_bytes()),
            'dependency_lock_sha256':sha((ROOT/'manifests/dependencies.lock.json').read_bytes()),
            'builder_lock_sha256':sha((ROOT/'manifests/builder.lock.json').read_bytes()),
            'python':platform.python_version(),'python_packages':versions,'platformio_packages':packages,
            'platformio_runtime_python_packages':runtime_versions,
            'source_date_epoch':LOCK['source_date_epoch'],'hardware_tested_this_build':False,
            'target_build_and_host_tests':'PASS','same_environment_reproducibility':'PASS' if len(labels)==2 else 'NOT_RUN',
            'context':'container' if os.environ.get('STICKY_CONTAINER')=='1' else 'host',
            'redistribution':'LOCAL_ONLY; includes Seeedash. Do not upload bundle, image, container layer or compiled firmware.',
            'ota':'UNSUPPORTED/FORBIDDEN','power_fail_atomic':False}
    export(target,first,factory,entry,report)
    print(json.dumps({'output':str(target),'verification':verify(target,entry['id'])},indent=2))


def instructions(args):
    entry=select(args.combination)
    if args.mode=='recovery':
        print('DESTRUCTIVE FACTORY RECOVERY; manual host commands only. Establish ROM access and back up first.')
        print('Official1.2.0 URL: '+LOCK['seeedash']['url'])
        print('Expected SHA256: '+LOCK['seeedash']['sha256'])
        print('After download and hash verification, use host esptool4.12.0: erase_flash; write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 seeedash-1.2.0.bin; verify_flash 0x0 seeedash-1.2.0.bin')
        print('The vendor file is33292288 bytes. Full erase also clears the final coredump area. See docs/RECOVERY.md and docs/WINDOWS_INSTALL.md.')
        return
    directory=bundle_path(args.output_root,args.directory or entry['id'])
    result=verify(directory,entry['id'],args.mode,args.backup,args.confirm_layout)
    print(json.dumps(result,indent=2))
    print('MANUAL HOST esptool4.12.0 instructions; no device is attached to this container.')
    print('Prerequisites: verified private full backup,32MiB Flash, no Secure Boot/encryption, reliable ROM access and stable USB power.')
    if args.mode=='preserve':
        print('PRESERVE DATA: actual backup table and installed Seeedash passed. Do NOT erase, repartition or add boot_app0.')
        print('write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 bootloader.bin 0x690000 crosspoint.bin')
        print('verify_flash 0x0 bootloader.bin 0x690000 crosspoint.bin')
        print('Write both paired segments. Not power-fail atomic. Keep ROM/stub active for protected-byte readback before boot.')
    else:
        print('FRESH INSTALL: replaces all Flash data. Accept data loss before manually running erase_flash.')
        print('write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 fresh-32MiB.bin')
        print('verify_flash 0x0 fresh-32MiB.bin')
    print('Prefix with host Python -m esptool --chip esp32s3 --port YOUR_PORT --after no_reset. Never flash at0xe000.')
    print('See docs/INSTALL.md, docs/UPDATE.md and docs/RECOVERY.md. All OTA remains forbidden. New outputs are not hardware tested.')


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='command',required=True)
    for name in ['list','build','verify','info','check-updates']:
        sub=commands.add_parser(name)
        sub.add_argument('--output-root',type=Path,default=Path('/output'),help=argparse.SUPPRESS)
        if name in ['build','verify','info']:
            sub.add_argument('--combination')
            sub.add_argument('--directory')
        if name=='build':sub.add_argument('--reproducibility-check',action='store_true')
        if name in ['verify','info']:
            sub.add_argument('--mode',choices=['fresh','preserve','recovery'] if name=='info' else ['artifacts','fresh','preserve'],default='fresh' if name=='info' else 'artifacts')
            sub.add_argument('--backup',type=Path)
            sub.add_argument('--confirm-layout',choices=['protected-reference'])
        if name=='check-updates':sub.add_argument('--report',default='upstream-report.json')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    if args.command=='list':
        data=manifest()
        for row in data['combinations']:
            print(row['id']+'\t'+row['channel']+'\tCrossPoint '+row['crosspoint']['version']+' + Seeedash '+row['seeedash']['version']+'\t'+row['hardware_validation']['status']+'; new builds untested')
    elif args.command=='build':build_bundle(args)
    elif args.command=='verify':
        entry=select(args.combination)
        print(json.dumps(verify(bundle_path(args.output_root,args.directory or entry['id']),entry['id'],args.mode,args.backup,args.confirm_layout),indent=2))
    elif args.command=='info':instructions(args)
    else:
        from check_updates import check,save_report
        report=check();save_report(args.output_root,args.report,report);print(json.dumps(report,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError,subprocess.CalledProcessError) as error:
        print('ERROR: '+str(error)+'; stopped without flashing or exporting an unchecked bundle.',file=sys.stderr)
        sys.exit(2)
