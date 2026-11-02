#!/usr/bin/env python3
"""Create a LOCAL destructive fresh-install image. Never publish this output."""
import argparse
from pathlib import Path
from common import *
from preflight import load_pair

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--factory',type=Path,default=ROOT/'.local/vendor/seeedash-1.2.0.bin')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    require(output.is_relative_to((ROOT/'.local').resolve()),'Combined images must remain inside ignored .local/')
    boot,cp=load_pair(args.bundle)
    data=fresh_image(args.factory.read_bytes(),boot,cp)
    write_new(output,data)
    write_new(output.with_suffix('.sha256'),(sha(data)+'  '+output.name+'\n').encode())
    print('LOCAL ONLY,33554432 bytes,SHA256='+sha(data))
