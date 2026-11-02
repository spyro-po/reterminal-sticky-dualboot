"""Independent synthetic corruption, layout and erase-boundary checks; no device data."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest
import tempfile
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import *
from preflight import load_pair


def synthetic(payload):
    header=bytearray(24)
    header[0:4]=bytes([0xe9,1,2,0x5f]);header[12]=9;header[23]=1
    data=header+struct.pack('<II',0x3c000020,len(payload))+payload
    checksum=0xef
    for byte in payload:checksum^=byte
    data+=b'\0'*((-(len(data)+1))%16)+bytes([checksum])
    return bytes(data)+hashlib.sha256(data).digest()


def pair():
    cp=synthetic(boot_contract()+b'STICKY-DUALBOOT-ABI3;cp_nvs=0x89000:0x5000;bootstate=0x8e000:0x2000;OTA=FORBIDDEN\0')
    boot=synthetic(boot_contract()+bytes.fromhex(image(cp,0x600000)['body_sha256']))
    return boot,cp


class Integrity(unittest.TestCase):
    def test_table(self):
        table=partition_table()
        self.assertEqual(len(parse_table(table)),10)
        self.assertEqual(parse_table(table),parse_table(table+b'\xff'*1024))
        for index in (0,3,4,8,12,28,32*10,32*10+16,3071):
            corrupt=bytearray(table);corrupt[index]^=1
            with self.assertRaises(ValueError):parse_table(corrupt)
        with self.assertRaises(ValueError):parse_table(table+b'\0'*1024)
        # A self-consistent but different table still must fail the canonical check.
        raw=bytearray(table);raw[3]^=1;raw[336:352]=hashlib.md5(raw[:320]).digest()
        with self.assertRaises(ValueError):parse_table(raw)

    def test_images(self):
        boot,cp=pair();validate_pair(boot,cp)
        for index in (0,1,2,3,12,23,24,32,len(cp)-33,len(cp)-1):
            raw=bytearray(cp);raw[index]^=1
            with self.assertRaises(ValueError):image(raw,0x600000)
        for raw in (cp[:-1],cp+b'\xff',b'',b'\xff'*24):
            with self.assertRaises(ValueError):image(raw,0x600000)
        with self.assertRaises(ValueError):image(cp,len(cp)-1)
        other=synthetic(b'wrong application')
        with self.assertRaises(ValueError):validate_pair(boot,other)
        with self.assertRaises(ValueError):validate_pair(synthetic(boot_contract()),cp)

    def test_sector_preservation(self):
        boot,cp=pair()
        baseline=bytearray(b'\xa5'*FLASH_SIZE)
        baseline[0x8000:0x9000]=partition_table()+b'\xff'*1024
        result=apply_pair(bytes(baseline),boot,cp)
        self.assertEqual(result[0x8000:0x690000],baseline[0x8000:0x690000])
        self.assertEqual(result[0xc90000:],baseline[0xc90000:])
        for broken in (baseline[:-1],b'\xff'*FLASH_SIZE):
            with self.assertRaises(ValueError):apply_pair(broken,boot,cp)

    def test_manifest(self):
        boot,cp=pair()
        bi,ci=validate_pair(boot,cp)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            (path/'bootloader.bin').write_bytes(boot)
            (path/'crosspoint.bin').write_bytes(cp)
            rows=[dict(file=name,offset=offset,**info) for name,offset,info in
                  [('bootloader.bin','0x0',bi),('crosspoint.bin','0x690000',ci)]]
            meta=dict(version='1.0.0',partition_table_sha256=TABLE_SHA256,segments=rows)
            manifest=path/'segments.json'
            manifest.write_text(json.dumps(meta));self.assertEqual(load_pair(path),[boot,cp])
            for key,value in [('offset','0x680000'),('file','../crosspoint.bin'),('bytes',1),('sha256','0'*64)]:
                old=rows[1][key];rows[1][key]=value;manifest.write_text(json.dumps(meta))
                with self.assertRaises(ValueError):load_pair(path)
                rows[1][key]=old
            meta['segments']=rows[:1];manifest.write_text(json.dumps(meta))
            with self.assertRaises(ValueError):load_pair(path)

    def test_source_audit(self):
        from audit_public import check_file
        check_file('docs/example.md',b'Public documentation')
        for name,data in [('device.bin',b'private'),('docs/../dump.txt',b'x'),
                          ('docs/.env',b'token'),('docs/secret.txt',b'ghp_'+b'a'*40),
                          ('docs/dump.txt',b'\0'*20),('docs/device.txt',b'a'*2_000_001)]:
            with self.assertRaises(ValueError):check_file(name,data)


if __name__=='__main__':unittest.main()
