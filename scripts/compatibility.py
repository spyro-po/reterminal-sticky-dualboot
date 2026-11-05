"""Versioned compatibility gate. Upstream discovery never grants stable status."""
import json
from pathlib import Path
from common import ROOT, LOCK, TABLE_SHA256, sha, require

MANIFEST=ROOT/'manifests/compatibility.json'


def manifest():
    data=json.loads(MANIFEST.read_text())
    require(data.get('schema_version')==1,'Unsupported compatibility manifest schema')
    rows=data.get('combinations',[])
    require(rows and len({r['id'] for r in rows})==len(rows),'Empty/duplicate compatibility entries')
    require(all(r.get('channel') in ('stable','experimental') for r in rows),'Unknown compatibility channel')
    stable=[r for r in rows if r['channel']=='stable']
    require(len(stable)==1 and data.get('default')==stable[0]['id'],'Exactly one approved stable default is required')
    approved=stable[0]
    require(approved['crosspoint']['version']=='2.0.0' and approved['seeedash']['version']=='1.2.0',
            'Unapproved version cannot be stable')
    require(approved['crosspoint']['commit']==LOCK['crosspoint']['commit'] and
            approved['crosspoint']['patch_sha256']==LOCK['crosspoint']['patch_sha256'],
            'Stable CrossPoint source/patch differs from the approved dependency lock')
    require(all(approved['seeedash'][key]==LOCK['seeedash'][key] for key in ['version','bytes','sha256','registry_commit']),
            'Stable Seeedash differs from the official pinned artifact')
    require(approved['bootloader']['version']=='stage4' and approved['bootloader']['protocol']=='STKY-BOOT-V1',
            'Unapproved bootloader contract')
    require(approved['partitions']['id']=='protected-reference-32m' and
            approved['partitions']['table_sha256']==TABLE_SHA256,'Unsupported partition layout')
    files=dict(approved['bootloader']['source_sha256'])
    files.update(approved['integration_sources_sha256'])
    files[approved['partitions']['csv']]=approved['partitions']['csv_sha256']
    files[approved['build_profile']['file']]=approved['build_profile']['sha256']
    files[LOCK['crosspoint']['patch']]=LOCK['crosspoint']['patch_sha256']
    for name,digest in files.items():
        path=Path(name)
        require(not path.is_absolute() and '..' not in path.parts,'Unsafe compatibility source path')
        require(sha((ROOT/path).read_bytes())==digest,'Approved source integrity mismatch: '+name)
    require(approved['build_profile']['environment']=='sticky-dualboot-test','Unsupported build profile')
    require(approved['hardware_validation']['status']=='owner-reported-stage4' and
            approved['hardware_validation']['new_build_tested'] is False and
            approved['hardware_validation']['docker_build_tested'] is False,
            'New artifacts must not inherit a hardware-test claim')
    return data


def select(identifier=None):
    data=manifest()
    identifier=identifier or data['default']
    entry=next((row for row in data['combinations'] if row['id']==identifier),None)
    require(entry is not None,'Unknown combination: '+str(identifier)+'; use list')
    require(entry['channel']=='stable','Experimental combination cannot be built as stable; approval is required')
    return entry
