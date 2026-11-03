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



def apt_sources(lock):
    """Require the full signed Debian snapshot closure used by the pinned base."""
    source=ROOT/'docker/apt.sources'
    require(sha(source.read_bytes())==lock['files'].get('docker/apt.sources'),'APT source file differs from builder lock')
    expected={'debian':['bookworm','bookworm-updates'],'debian-security':['bookworm-security']}
    require(lock.get('debian_apt_suites')==expected,'Unsupported APT suite set')
    timestamp=lock['debian_snapshot']
    import re
    require(re.fullmatch(r'[0-9]{8}T[0-9]{6}Z',timestamp),'Invalid snapshot timestamp')
    entries=[];fields={}
    for row in source.read_text().splitlines()+['']:
        if row.startswith('#'):continue
        if not row.strip():
            if fields:entries.append(fields);fields={}
            continue
        require(not row[0].isspace() and ': ' in row,'Malformed APT deb822 source field')
        key,value=row.split(': ',1)
        require(key not in fields,'Duplicate APT source field')
        fields[key]=value
    require(len(entries)==2,'Both main/updates and security APT archives are required')
    for entry,(archive,suites) in zip(entries,expected.items()):
        wanted={'Types':'deb','URIs':'https://snapshot.debian.org/archive/'+archive+'/'+timestamp+'/',
                'Suites':' '.join(suites),'Components':'main',
                'Signed-By':'/usr/share/keyrings/debian-archive-keyring.gpg','Check-Valid-Until':'no'}
        require(entry==wanted,'APT source streams, timestamp or signature policy differs from lock')
    return entries


def configuration():
    lock=json.loads((ROOT/'manifests/builder.lock.json').read_text())
    apt_sources(lock)
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
             'docker/requirements-pio.lock','docker/requirements-idf.lock','docker/espidf.constraints.v5.4.txt','docker/apt.sources'}
    for line in lines:
        if line.startswith('COPY '):
            parts=shlex.split(line)[1:]
            require(all(x in allowed for x in parts[:-1]),'Docker COPY is outside the reviewed source/tool allowlist')
            require(parts[-1].startswith('/opt/sticky/') or parts==['docker/apt.sources','/etc/apt/sources.list.d/sticky.sources'],'Unexpected Docker COPY destination')
            copies.extend(parts[:-1])
    require(copies,'Docker has no reviewed source copies')
    require('COPY docker/apt.sources /etc/apt/sources.list.d/sticky.sources' in lines,'Docker must install the locked APT source file')
    apt_runs=[line for line in lines if line.startswith('RUN ') and 'apt-get update' in line]
    require(len(apt_runs)==1 and ' '.join(apt_runs[0].split()).startswith('RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources && apt-get update && '),
            'Docker must remove inherited live APT sources before updating')
    require(not any(flag in apt_runs[0] for flag in ['--force','--allow-downgrades','--allow-unauthenticated','|| true']),
            'APT dependency or signature failures must not be bypassed')
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
