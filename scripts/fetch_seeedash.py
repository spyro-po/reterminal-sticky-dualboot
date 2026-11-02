#!/usr/bin/env python3
"""Download the official artifact for LOCAL use only. No device access."""
import argparse
import hashlib
from pathlib import Path
import urllib.request
from common import LOCK, ROOT, require, official


def fetch(destination):
    destination=Path(destination)
    if destination.exists():
        official(destination.read_bytes())
        return destination
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(destination.name+'.download')
    meta=LOCK['seeedash']
    digest=hashlib.sha256()
    total=0
    try:
        request=urllib.request.Request(meta['url'],headers={'User-Agent':'reterminal-sticky-dualboot/1.0.0'})
        with urllib.request.urlopen(request,timeout=120) as response,temporary.open('xb') as output:
            require(response.geturl().startswith('https://raw.githubusercontent.com/'),'Unexpected download host')
            while chunk:=response.read(1024*1024):
                total+=len(chunk)
                require(total<=meta['bytes'],'Download exceeds official image size')
                digest.update(chunk)
                output.write(chunk)
        require(total==meta['bytes'] and digest.hexdigest()==meta['sha256'],'Download integrity failed')
        official(temporary.read_bytes())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'.local/vendor/seeedash-1.2.0.bin')
    args=parser.parse_args()
    result=fetch(args.output)
    print('Verified official Seeedash1.2.0 for LOCAL use:',result)
    print('Do not publish this file or any combined image containing it.')
