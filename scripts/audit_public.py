#!/usr/bin/env python3
"""Fail-closed audit of Git-index source or a release source archive. No network."""
import argparse
from pathlib import Path,PurePosixPath
import re
import subprocess
import zipfile
from common import ROOT,require,sha

ROOT_FILES={'.clang-format','.gitattributes','.gitignore','README.md','LICENSE','NOTICE','VERSION',
            'CHANGELOG.md','RELEASE_NOTES.md','requirements-build.txt','SOURCE_FILES.sha256'}
PREFIXES={'firmware','crosspoint','partitions','patches','scripts','tests','docs','licenses','manifests'}
FORBIDDEN_SUFFIXES={'.bin','.elf','.map','.log','.pdf','.png','.jpg','.jpeg','.zip','.gz','.env','.pem','.key'}
PATTERNS=[rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
          rb'gh[pousr]_[A-Za-z0-9_]{30,}',rb'github_pat_[A-Za-z0-9_]{40,}',
          rb'AKIA[A-Z0-9]{16}',rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}']


def check_file(name,data):
    p=PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts,'Unsafe path: '+name)
    require((len(p.parts)==1 and name in ROOT_FILES) or (len(p.parts)>1 and p.parts[0] in PREFIXES),
            'File outside publication allowlist: '+name)
    require(not any(part.startswith('.') for part in p.parts[1:]),'Hidden nested file: '+name)
    require(p.suffix.lower() not in FORBIDDEN_SUFFIXES,'Binary/private artifact type: '+name)
    require(len(data)<2_000_000,'Unexpected large source file: '+name)
    require(b'\0' not in data,'Binary contents: '+name)
    text=data.decode('utf-8')
    require('/'+'workspace/' not in text,'Private workspace path: '+name)
    for pattern in PATTERNS:require(not re.search(pattern,data),'Potential secret: '+name)
    return {'path':name,'bytes':len(data),'sha256':sha(data)}


def index_files():
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).split(b'\0')
    require(any(names),'No Git-index files')
    results=[]
    for item in names:
        if not item:continue
        name=item.decode()
        staged=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
        path=ROOT/name
        require(not path.is_symlink() and path.is_file(),'Symlink/non-file: '+name)
        require(path.read_bytes()==staged,'Index differs from working source: '+name)
        results.append(check_file(name,staged))
    return results


def archive_files(path):
    results=[]
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        require(len({i.filename for i in entries})==len(entries),'Duplicate archive paths')
        for entry in entries:
            require(not entry.is_dir(),'Unexpected archive directory record')
            require((entry.external_attr>>16)&0o170000 in (0,0o100000),'Non-regular archive member')
            require(entry.file_size<2_000_000,'Oversized archive member')
            results.append(check_file(entry.filename,archive.read(entry)))
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    args=parser.parse_args()
    files=archive_files(args.archive) if args.archive else index_files()
    print('PASS: '+str(len(files))+' source files; allowlist, text-only, size, path and secret-pattern checks')
