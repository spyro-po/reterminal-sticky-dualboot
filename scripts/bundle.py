"""Export and verify complete local bundles. Contains no device-write operation."""
import json
from pathlib import Path
import re
import shutil
import tempfile
from common import ROOT, LOCK, EXPECTED, FLASH_SIZE, partition_table, sha, require, fresh_image
from compatibility import select, MANIFEST
from preflight import load_pair, backup_check

FILES={'fresh-32MiB.bin','bootloader.bin','crosspoint.bin','segments.json','build-report.json','SHA256SUMS.txt'}


def bundle_path(root,name):
    require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}',name) and name not in ('.','..'),'Invalid bundle directory name')
    root=Path(root).resolve()
    path=root/name
    require(not path.is_symlink() and path.resolve().parent==root,'Bundle must be a direct child of the output root')
    return path


def verify(directory,combination=None,mode='artifacts',backup=None,confirm=None):
    require(mode in ('artifacts','fresh','preserve'),'Unsupported verification mode')
    directory=Path(directory)
    require(directory.is_dir() and not directory.is_symlink(),'Bundle directory missing or symlinked')
    require({p.name for p in directory.iterdir()}==FILES,'Bundle must contain exactly the six documented files')
    require(all(p.is_file() and not p.is_symlink() for p in directory.iterdir()),'Bundle entries must be regular files')
    limits={'fresh-32MiB.bin':FLASH_SIZE,'bootloader.bin':0x8000,'crosspoint.bin':0x600000,
            'segments.json':262144,'build-report.json':1048576,'SHA256SUMS.txt':4096}
    for name,maximum in limits.items():require((directory/name).stat().st_size<=maximum,'Bundle file exceeds size limit: '+name)
    entry=select(combination)
    rows=(directory/'SHA256SUMS.txt').read_text().splitlines()
    sums={}
    for row in rows:
        match=re.fullmatch(r'([0-9a-f]{64})  ([a-zA-Z0-9_.-]+)',row)
        require(match,'Malformed checksum row')
        digest,name=match.groups()
        require(name not in sums and name in FILES-{'SHA256SUMS.txt'},'Duplicate/unexpected checksum filename')
        sums[name]=digest
    require(set(sums)==FILES-{'SHA256SUMS.txt'},'Checksum inventory is incomplete')
    for name,digest in sums.items():require(sha((directory/name).read_bytes())==digest,'Checksum mismatch: '+name)
    boot,cp=load_pair(directory)
    report=json.loads((directory/'build-report.json').read_text())
    require(isinstance(report,dict),'Malformed build-report.json: expected a JSON object')
    require(report.get('combination')==entry['id'] and report.get('builder_version')=='1.1.0','Wrong bundle combination/builder')
    require(report.get('compatibility_manifest_sha256')==sha(MANIFEST.read_bytes()),'Compatibility manifest changed')
    require(report.get('dependency_lock_sha256')==sha((ROOT/'manifests/dependencies.lock.json').read_bytes()),'Dependency lock changed')
    require(report.get('builder_lock_sha256')==sha((ROOT/'manifests/builder.lock.json').read_bytes()),'Builder lock changed')
    require(report.get('hardware_tested_this_build') is False,'New build incorrectly claims hardware validation')
    data=(directory/'fresh-32MiB.bin').read_bytes()
    require(len(data)==FLASH_SIZE,'Fresh image must be exactly32MiB')
    require(data[:0x8000]==boot.ljust(0x8000,b'\xff'),'Fresh bootloader region differs from paired segment')
    require(data[0x8000:0x9000]==partition_table().ljust(4096,b'\xff'),'Fresh partition sector differs')
    require(data[0x690000:0xc90000]==cp.ljust(0x600000,b'\xff'),'Fresh CrossPoint region differs from paired segment')
    require(data[0x89000:0x90000]==b'\xff'*0x7000 and data[0x1fc0000:]==b'\xff'*0x40000,
            'Fresh private partitions/coredump must be erased')
    for name,_,_,offset,size in EXPECTED:
        expected=entry['factory_partition_sha256'].get(name)
        if expected:require(sha(data[offset:offset+size])==expected,'Factory bytes changed: '+name)
    require(len(entry['factory_partition_sha256'])==6,'Incomplete factory-extent hash contract')
    if mode=='preserve':
        require(confirm=='protected-reference','Preserve Data requires --confirm-layout protected-reference')
        require(backup is not None,'Preserve Data requires a complete private device backup, not a table hash alone')
        path=Path(backup)
        require(path.is_file(),'Backup file not found')
        require(path.stat().st_size==FLASH_SIZE,'Full private backup must be exactly33554432 bytes')
        backup_check(path.read_bytes(),boot,cp)
    else:
        require(backup is None and confirm is None,'Backup/layout acknowledgement applies only to Preserve Data')
    return {'status':'PASS','mode':mode,'combination':entry['id'],'hardware_tested_this_build':False,
            'preserve_data_preflight':mode=='preserve','fresh_image_sha256':sha(data)}


def export(directory,pair,factory,entry,report):
    directory=Path(directory)
    require(not directory.exists(),'Output already exists; use a different --directory or keep the existing verified bundle')
    directory.parent.mkdir(parents=True,exist_ok=True)
    boot,cp=load_pair(pair)
    image=fresh_image(factory,boot,cp)
    # Verify everything in a sibling temporary directory before making the bundle visible.
    staging=Path(tempfile.mkdtemp(prefix='.sticky-build-',dir=directory.parent))
    try:
        for name in ['bootloader.bin','crosspoint.bin','segments.json']:
            shutil.copyfile(Path(pair)/name,staging/name)
        (staging/'fresh-32MiB.bin').write_bytes(image)
        (staging/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
        (staging/'SHA256SUMS.txt').write_text(''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in sorted(staging.iterdir())))
        verify(staging,entry['id'])
        require(not directory.exists(),'Output appeared during validation; refusing replacement')
        staging.rename(directory)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return directory
