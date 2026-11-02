#!/usr/bin/env python3
"""Prepare a pinned upstream checkout under .work; never edit another project."""
import argparse
import os
from pathlib import Path
import subprocess
from common import ROOT, LOCK, require, sha

CHECKOUT=ROOT/'.work/crosspoint-reader'


def run(args,cwd=None,capture=False):
    result=subprocess.run([str(a) for a in args],cwd=cwd,check=True,
                          stdout=subprocess.PIPE if capture else None,text=True)
    return result.stdout.strip() if capture else None


def prepare(seed=None, sdk_seed=None):
    target=CHECKOUT
    meta=LOCK['crosspoint']
    patch=ROOT/meta['patch']
    require(sha(patch.read_bytes())==meta['patch_sha256'],'CrossPoint patch changed')
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        run(['git','clone','--no-hardlinks','--no-checkout',str(seed) if seed else meta['url'],target])
        run(['git','remote','set-url','origin',meta['url']],target)
        run(['git','checkout','--detach',meta['commit']],target)
    require(target.resolve().is_relative_to((ROOT/'.work').resolve()),'Checkout outside isolated work directory')
    require(run(['git','rev-parse','HEAD'],target,True)==meta['commit'],'Wrong CrossPoint revision')
    result=subprocess.run(['git','apply','--check',str(patch)],cwd=target,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if result.returncode==0:
        require(not run(['git','diff','--name-only'],target,True),'Checkout has unexpected modifications')
        run(['git','apply',str(patch)],target)
    else:
        run(['git','apply','--reverse','--check',str(patch)],target)
    options=['-c','protocol.file.allow=always','-c','submodule.freeink-sdk.url='+str(sdk_seed)] if sdk_seed else []
    run(['git',*options,'submodule','update','--init','freeink-sdk'],target)
    require(run(['git','rev-parse','HEAD'],target/'freeink-sdk',True)==LOCK['freeink']['commit'],'Wrong FreeInk SDK')
    require(not run(['git','status','--porcelain','--untracked-files=no'],target/'freeink-sdk',True),'FreeInk SDK has unreviewed changes')
    # Refuse extra tracked changes even if the reverse patch check happened to pass.
    actual=subprocess.check_output(['git','diff','--full-index','--binary','HEAD'],cwd=target)
    require(actual==patch.read_bytes(),'Checkout differs from the reviewed patch')
    profile=(ROOT/'crosspoint/profile.ini').read_text()
    local=target/'platformio.local.ini'
    if local.exists():
        require(local.read_text()==profile,'Unexpected local build profile')
    else:
        local.write_text(profile)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=Path,help='Optional read-only local Git object source; checkout is still pinned')
    parser.add_argument('--sdk-seed',type=Path,help='Optional read-only FreeInk object source')
    args=parser.parse_args()
    print(prepare(args.seed,args.sdk_seed))
