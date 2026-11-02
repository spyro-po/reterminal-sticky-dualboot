"""Local image/layout checks. Never opens a serial device or invokes a flasher."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'manifests/dependencies.lock.json').read_text())
FLASH_SIZE = 0x2000000
TABLE_SHA256 = '51fc24d4da9b5bafb4bef860874d891d6ad29044c1724e5f05882724d83be812'
EXPECTED = [
 ('nvs',1,2,0x9000,0x7d000), ('otadata',1,0,0x86000,0x2000),
 ('phy_init',1,1,0x88000,0x1000), ('cp_nvs',1,2,0x89000,0x5000),
 ('bootstate',1,64,0x8e000,0x2000), ('app0',0,16,0x90000,0x600000),
 ('app1',0,32,0x690000,0x600000), ('sys_storage',1,131,0xc90000,0x930000),
 ('usr_storage',1,131,0x15c0000,0xa00000), ('coredump',1,3,0x1fc0000,0x40000)]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def partition_table():
    records = b''.join(struct.pack('<HBBII16sI',0x50aa,t,sub,offset,size,
        name.encode().ljust(16,b'\0'),0) for name,t,sub,offset,size in EXPECTED)
    records += b'\xeb\xeb'+b'\xff'*14+hashlib.md5(records).digest()
    result = records.ljust(3072,b'\xff')
    require(sha(result)==TABLE_SHA256,'Canonical table changed; review all firmware validators')
    return result


def parse_table(data, protected=True):
    require(len(data) in (3072,4096),'Expected a 3072-byte table or 4096-byte sector')
    rows=[]
    for off in range(0,3072,32):
        raw=data[off:off+32]
        if raw[:2]==b'\xeb\xeb':
            require(raw[:16]==b'\xeb\xeb'+b'\xff'*14,'Invalid MD5 record header')
            require(hashlib.md5(data[:off]).digest()==raw[16:],'Partition MD5 mismatch')
            require(all(x==255 for x in data[off+32:]),'Unexpected data after table MD5')
            break
        require(raw[:2]==b'\xaa\x50','Invalid/missing partition record or MD5')
        _,kind,sub,start,size,label,flags=struct.unpack('<HBBII16sI',raw)
        require(b'\0' in label,'Unterminated partition label')
        name=label.split(b'\0')[0].decode('ascii')
        require(size>0 and start+size<=FLASH_SIZE,'Partition outside32MiB')
        require(not rows or start>=rows[-1]['offset']+rows[-1]['size'],'Overlapping/unsorted partitions')
        rows.append(dict(name=name,type=kind,subtype=sub,offset=start,size=size,flags=flags))
    else:
        raise ValueError('No MD5 record')
    if protected:
        require(data[:3072]==partition_table(),'Not the protected-reference layout; do not repartition automatically')
    return rows


def image(data, maximum, name='image'):
    require(24<=len(data)<=maximum,name+': size/bounds')
    require(data[0]==0xe9 and 0<data[1]<=16,name+': invalid ESP image header')
    require(struct.unpack_from('<H',data,12)[0]==9,name+': not ESP32-S3')
    require(data[2:4]==b'\x02\x5f' and data[23]==1,name+': requires DIO/80MHz/32MiB and appended SHA256')
    cursor=24
    checksum=0xef
    for _ in range(data[1]):
        require(cursor+8<=len(data),name+': truncated segment header')
        _,length=struct.unpack_from('<II',data,cursor)
        cursor+=8
        require(length<=len(data)-cursor,name+': truncated segment')
        for byte in data[cursor:cursor+length]:
            checksum ^= byte
        cursor+=length
    checksum_end=((cursor+16)//16)*16
    require(checksum_end+32==len(data),name+': length/trailing data mismatch')
    require(data[checksum_end-1]==checksum,name+': XOR checksum mismatch')
    digest=hashlib.sha256(data[:checksum_end]).digest()
    require(data[checksum_end:]==digest,name+': appended SHA256 mismatch')
    return dict(bytes=len(data),sha256=sha(data),body_sha256=digest.hex())


def boot_contract():
    import re
    text=(ROOT/'firmware/include/boot_contract.h').read_text()
    return re.search(r'#define STICKY_BOOT_CONTRACT "([^"]+)"',text).group(1).encode()


def validate_pair(boot,cp, require_protocol=True):
    bi=image(boot,0x8000,'bootloader')
    ci=image(cp,0x600000,'CrossPoint')
    require(bytes.fromhex(ci['body_sha256']) in boot,'Bootloader pin does not match CrossPoint; never mix pairs')
    if require_protocol:
        require(boot_contract() in boot and boot_contract() in cp,'Selector ABI mismatch')
        require(b'STICKY-DUALBOOT-ABI3;cp_nvs=0x89000:0x5000;bootstate=0x8e000:0x2000;OTA=FORBIDDEN\0' in cp,
                'CrossPoint NVS/OTA integration contract absent')
    for offset,blob,limit in [(0,boot,0x8000),(0x690000,cp,0xc90000)]:
        require((offset+len(blob)+4095)&~4095<=limit,'Erase range reaches protected data')
    return bi,ci


def apply_pair(baseline,boot,cp):
    require(len(baseline)==FLASH_SIZE,'Backup must contain all32MiB')
    parse_table(baseline[0x8000:0x9000])
    validate_pair(boot,cp)
    result=bytearray(baseline)
    for offset,data in [(0,boot),(0x690000,cp)]:
        end=(offset+len(data)+4095)&~4095
        result[offset:end]=b'\xff'*(end-offset)
        result[offset:offset+len(data)]=data
    require(result[0x8000:0x9000]==baseline[0x8000:0x9000],'Table changed')
    for name,_,_,offset,size in EXPECTED:
        if name!='app1':
            require(result[offset:offset+size]==baseline[offset:offset+size],'Protected data changed: '+name)
    return bytes(result)


def official(data):
    meta=LOCK['seeedash']
    require(len(data)==meta['bytes'] and sha(data)==meta['sha256'],'Official Seeedash SHA256/size mismatch')
    # The physical extents must remain intact; app1 subtype alone changes in our layout.
    old=parse_table(data[0x8000:0x9000],protected=False)
    desired={name:(t,sub,offset,size) for name,t,sub,offset,size in EXPECTED}
    require(len(old)==8,'Unexpected official partition count')
    for p in old:
        typ,sub,off,size=desired[p['name']]
        require((p['type'],p['offset'],p['size'],p['flags'])==(typ,off,size,0),'Official extent mismatch')
        require(p['subtype']==(17 if p['name']=='app1' else sub),'Official subtype mismatch')
    require(data[0x89000:0x90000]==b'\xff'*0x7000,'Official private gap is occupied')
    require(data[0x690000:0xc90000]==b'\xff'*0x600000,'Official app1 not empty')
    return data


def fresh_image(factory,boot,cp):
    official(factory)
    validate_pair(boot,cp)
    result=bytearray(factory+b'\xff'*(FLASH_SIZE-len(factory)))
    result[:0x8000]=boot.ljust(0x8000,b'\xff')
    result[0x8000:0x9000]=partition_table().ljust(4096,b'\xff')
    result[0x690000:0x690000+len(cp)]=cp
    for name,_,_,offset,size in EXPECTED:
        if name in ['nvs','otadata','phy_init','app0','sys_storage','usr_storage']:
            require(result[offset:offset+size]==factory[offset:offset+size],'Vendor bytes changed: '+name)
    require(len(result)==FLASH_SIZE,'Merged output is not32MiB')
    return bytes(result)


def write_new(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    require(not path.exists(),'Refuse to replace existing artifact: '+path.name)
    temporary=path.with_name(path.name+'.partial')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
        require(sha(temporary.read_bytes())==sha(data),'Artifact readback mismatch')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
