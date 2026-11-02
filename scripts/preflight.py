#!/usr/bin/env python3
"""Offline paired-update verification. No serial access, erase or flash commands."""
import argparse
import json
from pathlib import Path
from common import *


def load_pair(directory):
    directory=Path(directory)
    meta=json.loads((directory/'segments.json').read_text())
    require(meta.get('version')=='1.0.0','Unsupported update manifest')
    require(meta.get('partition_table_sha256')==TABLE_SHA256,'Wrong manifest layout')
    entries=meta.get('segments',[])
    require(len(entries)==2,'Exactly two code segments required')
    blobs=[]
    for entry,(name,offset,limit) in zip(entries,[('bootloader.bin',0,0x8000),('crosspoint.bin',0x690000,0x600000)]):
        require(entry['file']==name and int(entry['offset'],0)==offset,'Unexpected filename/offset')
        require(not (directory/name).is_symlink(),'Symlink segment rejected')
        data=(directory/name).read_bytes()
        info=image(data,limit,name)
        require(all(entry.get(k)==v for k,v in info.items()),'Manifest integrity mismatch: '+name)
        blobs.append(data)
    validate_pair(*blobs)
    return blobs


def backup_check(backup,boot,cp):
    require(len(backup)==FLASH_SIZE,'Full private backup must be exactly33554432 bytes')
    parse_table(backup[0x8000:0x9000])
    seen=backup[0x90000:0x90000+3261088]
    info=image(seen,0x600000,'Installed Seeedash')
    require(info['body_sha256']=='b7184469aa47a680c293848b264342705cc817689f4f7693d2e674f0ab23eec7',
            'Installed Seeedash is not the supported1.2.0 image')
    return apply_pair(backup,boot,cp)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--table',type=Path,help='Checks layout only; not a substitute for the full backup before writing')
    group.add_argument('--backup',type=Path,help='Private full32MiB backup from this chip')
    parser.add_argument('--after',type=Path,help='Optional full readback before first app boot')
    args=parser.parse_args()
    boot,cp=load_pair(args.bundle)
    if args.backup:
        expected=backup_check(args.backup.read_bytes(),boot,cp)
        if args.after:
            require(args.after.read_bytes()==expected,'Readback differs from simulated code-only sector writes')
        print('PASS: matched pair, installed Seeedash, canonical table, sector ranges and protected data')
    else:
        require(not args.after,'--after requires --backup')
        parse_table(args.table.read_bytes())
        print('PASS: matched pair and canonical table only; full private backup is still required')
