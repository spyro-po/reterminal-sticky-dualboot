#!/usr/bin/env python3
"""Audit image source inputs and fixed tool locks without reading host credentials."""
import argparse
import json
from pathlib import Path
import sys
import shlex
from common import ROOT,require,sha
from audit_public import check_file
from compatibility import manifest


def audit(source):
    source=Path(source)
    require(source.resolve()==ROOT.resolve(),'Audit the source tree containing this validator')
    lock=json.loads((source/'manifests/builder.lock.json').read_text())
    require(lock['platform']=='linux/amd64' and lock['python']=='3.12.16','Unsupported Docker platform/Python')
    require(lock['base_image'].endswith('@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337'),'Unapproved base digest')
    for name,digest in lock['files'].items():require(sha((source/name).read_bytes())==digest,'Builder lock mismatch: '+name)
    inventory={}
    for row in (source/'SOURCE_FILES.sha256').read_text().splitlines():
        digest,name=row.split('  ',1)
        require(name not in inventory,'Duplicate source inventory entry')
        inventory[name]=digest
    for p in source.rglob('*'):
        if p.is_file():
            require(not p.is_symlink(),'Source symlink rejected')
            name=p.relative_to(source).as_posix()
            check_file(name,p.read_bytes())
            if name!='SOURCE_FILES.sha256':
                require(inventory.get(name)==sha(p.read_bytes()),'Image source is not in the reviewed inventory: '+name)
    manifest()
    return {'status':'PASS','source_files':sum(p.is_file() for p in source.rglob('*')),'vendor_firmware_included':False}


def configuration():
    lock=json.loads((ROOT/'manifests/builder.lock.json').read_text())
    physical=(ROOT/'Dockerfile').read_text().splitlines()
    lines=[];pending=''
    for row in physical:
        if not row.strip() or row.lstrip().startswith('#'):continue
        pending+=row.strip()
        if pending.endswith('\\'):
            pending=pending[:-1]+' '
        else:
            lines.append(pending);pending=''
    require(not pending,'Unterminated Dockerfile instruction')
    require(lines[0]=='FROM '+lock['base_image'],'Docker FROM does not match the locked image digest')
    copies=[]
    allowed={'VERSION','README.md','LICENSE','NOTICE','SOURCE_FILES.sha256','requirements-build.txt',
             'firmware','crosspoint','partitions','patches','scripts','tests','manifests','licenses','docker',
             'docker/requirements-pio.lock','docker/requirements-idf.lock','docker/espidf.constraints.v5.4.txt'}
    for line in lines:
        if line.startswith('COPY '):
            parts=shlex.split(line)[1:]
            require(all(x in allowed for x in parts[:-1]),'Docker COPY is outside the reviewed source/tool allowlist')
            require(parts[-1].startswith('/opt/sticky/'),'Unexpected Docker COPY destination')
            copies.extend(parts[:-1])
    require(copies,'Docker has no reviewed source copies')
    ignore=[x.strip() for x in (ROOT/'.dockerignore').read_text().splitlines() if x.strip() and not x.startswith('#')]
    require(ignore[0]=='**','Docker context must deny files by default')
    require('**/*.bin' in ignore and not any(x.startswith('!') and any(y in x for y in ['.local','.git/','.cache','.work','out/','dist/']) for x in ignore),
            'Docker ignore can expose private build state')
    require('USER 1000:1000' in lines and not any(x.startswith('ADD ') for x in lines),'Docker must run as non-root and avoid implicit remote ADD')
    for line in lines:
        if line.startswith('RUN '):
            require('fetch_seeedash' not in line and 'scripts/build.py' not in line,'Firmware must not be generated in a tools-image layer')
    return {'status':'PASS','base_image':lock['base_image'],'source_copy_allowlist':sorted(set(copies))}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--configuration',action='store_true')
    args=parser.parse_args()
    try:print(json.dumps(configuration() if args.configuration else audit(args.source or ROOT),indent=2))
    except (ValueError,OSError,KeyError) as error:print('ERROR: '+str(error),file=sys.stderr);sys.exit(2)
