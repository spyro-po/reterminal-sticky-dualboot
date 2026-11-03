#!/usr/bin/env python3
"""Read-only upstream metadata discovery. Never downloads firmware or promotes stable."""
import datetime
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from common import require,write_new
from compatibility import manifest

CROSSPOINT='https://api.github.com/repos/crosspoint-reader/crosspoint-reader/releases/latest'
SEEED='https://api.github.com/repos/Seeed-Projects/reterminal-sticky-playground-registry/contents/firmwares/sticky-factory/firmware'


def get_json(url):
    require(url.startswith('https://api.github.com/repos/'),'Unapproved metadata endpoint')
    headers={'Accept':'application/vnd.github+json','User-Agent':'reterminal-sticky-dualboot/1.1.0'}
    token=os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:headers['Authorization']='Bearer '+token
    request=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            require(response.geturl().startswith('https://api.github.com/repos/'),'Unexpected metadata redirect')
            raw=response.read(2_000_001)
            require(len(raw)<=2_000_000,'Metadata response too large')
            return json.loads(raw)
    except urllib.error.HTTPError as error:
        if error.code==404 and url==CROSSPOINT:return None
        raise ValueError('Upstream metadata request failed: HTTP '+str(error.code)) from None
    except urllib.error.URLError:
        raise ValueError('Upstream metadata network request failed; compatibility was not checked') from None


def check(fetch=get_json):
    data=manifest();approved=next(row for row in data['combinations'] if row['id']==data['default'])
    cp=fetch(CROSSPOINT);seen=fetch(SEEED)
    require(isinstance(seen,list),'Invalid Seeed registry listing')
    candidates=[]
    def version_tuple(value):
        match=re.fullmatch(r'v?([0-9]+)\.([0-9]+)\.([0-9]+)',value)
        return tuple(map(int,match.groups())) if match else None
    if cp:
        require(isinstance(cp,dict) and isinstance(cp.get('tag_name'),str),'Invalid CrossPoint release metadata')
        # A release tag is not proof that the approved develop commit is identical.
        latest_version=version_tuple(cp['tag_name'])
        if latest_version is None or latest_version>version_tuple(approved['crosspoint']['version']):
            candidates.append({'project':'CrossPoint','version':cp['tag_name'][:100],
                           'matches_approved_version_label':cp['tag_name'].lstrip('v')==approved['crosspoint']['version'],
                           'channel':'experimental','compatibility':'NOT_VALIDATED',
                           'reason':'Release tag metadata does not establish exact commit, patch or hardware compatibility'})
    versions=sorted({row.get('name','') for row in seen if isinstance(row,dict) and row.get('type')=='dir' and
                     re.fullmatch(r'v?[0-9]+\.[0-9]+\.[0-9]+',row.get('name',''))})
    for version in versions:
        if tuple(map(int,version.lstrip('v').split('.')))>tuple(map(int,approved['seeedash']['version'].split('.'))):
            candidates.append({'project':'Seeedash','version':version,'channel':'experimental',
                               'compatibility':'NOT_VALIDATED','reason':'New registry entry; image was not downloaded or tested'})
    return {'schema_version':1,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'approved_combination':approved['id'],'upstream':{'crosspoint_latest_tag':cp.get('tag_name') if cp else None,'seeedash_versions':versions},
            'candidates':candidates,'stable_manifest_modified':False,'firmware_downloaded':False,
            'candidate_build_tests':'NOT_RUN','candidate_hardware_validation':'NOT_RUN',
            'offline_test_scope':'CI tests the current integration and promotion gates, not the unapproved candidate firmware',
            'next_steps':'Maintainer source/patch/license review, offline build tests and physical hardware verification before any stable promotion'}


def save_report(root,name,report):
    require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}\.json',name),'Report must be a plain JSON filename')
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    target=root/name
    require(not target.is_symlink(),'Symlink report target rejected')
    write_new(target,(json.dumps(report,indent=2)+'\n').encode())


if __name__=='__main__':
    import argparse,sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:save_report(args.output.parent,args.output.name,check())
    except (ValueError,OSError) as error:print('ERROR: '+str(error),file=sys.stderr);sys.exit(2)
