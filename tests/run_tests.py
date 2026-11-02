#!/usr/bin/env python3
"""Host tests; source extraction is limited to the two real IDF OTA decision functions."""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import partition_table, official
parser=argparse.ArgumentParser()
parser.add_argument('--idf-path',type=Path,required=True)
args=parser.parse_args()
IDF=args.idf_path
OUT=ROOT/'.build/host-tests'
OUT.mkdir(parents=True,exist_ok=True)
CP=ROOT/'.work/crosspoint-reader'
try:
    import ziglang
    COMPILER=[str(Path(ziglang.__file__).parent/'zig')]
except ImportError:
    COMPILER=shlex.split(os.environ.get('HOST_CC','cc'))
CC=COMPILER+['cc'] if len(COMPILER)==1 and Path(COMPILER[0]).name=='zig' else COMPILER
CXX=COMPILER+['c++'] if len(COMPILER)==1 and Path(COMPILER[0]).name=='zig' else shlex.split(os.environ.get('HOST_CXX','c++'))


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def function(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


run(sys.executable, "tests/test_build_guards.py")
run(sys.executable, "tests/test_integrity.py")

common = CC + [ "-std=c17", "-Wall", "-Wextra", "-Wno-unused-parameter", "-Werror", "-I"+os.environ.get("DUALBOOT_PIN_INCLUDE",str(ROOT/"firmware/include")), "-Ifirmware/include", "-Itests"]
run(*common, "firmware/bootloader_components/main/boot_policy.c", "tests/test_policy.c", "-o", str(OUT / "policy"))
run(str(OUT / "policy"))
# Compile the real HAL selector block with small SDK I/O stubs; panic handling is outside this test.
hal = (CP / "lib/hal/HalSystem.cpp").read_text()
start = hal.index("namespace {\nstruct SeeedashPartition")
end = hal.index("void begin()", start)
(OUT / "menu_hal.cpp").write_text('#include "test_menu_api.h"\nnamespace HalSystem {\n'+hal[start:end]+'\n}\n')
run(*common, "-c", "firmware/bootloader_components/main/boot_policy.c", "-o", str(OUT / "menu_policy.o"))
run(*CXX, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
    "-DCROSSPOINT_STICKY_DUALBOOT=1", "-I"+os.environ.get("DUALBOOT_PIN_INCLUDE",str(ROOT/"firmware/include")), "-Ifirmware/include", "-Itests", "-I"+str(CP/"lib/hal"),
    str(OUT / "menu_hal.cpp"), "tests/test_menu.cpp", str(OUT / "menu_policy.o"), "-o", str(OUT / "menu"))
run(str(OUT / "menu"))

run(*common, "-DBOOT_HOST_TEST", "crosspoint/nvs_isolation.c", "tests/test_nvs.c", "-o", str(OUT / "nvs"))
run(str(OUT / "nvs"))
# Reuse real NVS mocks without their main for the lower-level guard test.
run(*common, "-Dmain=nvs_test_main", "-c", "tests/test_nvs.c", "-o", str(OUT / "nvs_mocks.o"))
run(*common, "-DBOOT_HOST_TEST", "crosspoint/nvs_isolation.c",
    "crosspoint/flash_guards.c", "tests/test_flash.c", str(OUT / "nvs_mocks.o"), "-o", str(OUT / "flash"))
run(str(OUT / "flash"))
run(*common, "-fPIC", "-shared", "firmware/bootloader_components/main/boot_policy.c", "-o", str(OUT / "policy.so"))
crc = ctypes.CDLL(str(OUT / "policy.so")).boot_seq_crc
crc.argtypes, crc.restype = [ctypes.c_uint32], ctypes.c_uint32
for seq in (0, 1, 2, 3, 17, 0x7fffffff, 0xfffffffd, 0xfffffffe, 0xffffffff):
    assert crc(seq) == zlib.crc32(seq.to_bytes(4, "little"), 0xffffffff)
print("PASS: sequence CRC agrees with independent Python zlib reference", flush=True)

prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
typedef int esp_err_t;
typedef int esp_ota_handle_t;
typedef int esp_partition_subtype_t;
typedef int ota_ops_entry_t;
typedef struct { int type,subtype; } esp_partition_t;
#define ESP_OK 0
#define ESP_ERR_INVALID_ARG 1
#define ESP_ERR_NOT_FOUND 2
#define ESP_ERR_OTA_PARTITION_CONFLICT 3
#define ESP_PARTITION_TYPE_APP 0
#define ESP_PARTITION_SUBTYPE_APP_OTA_0 16
#define ESP_PARTITION_SUBTYPE_APP_OTA_MIN 16
#define ESP_PARTITION_SUBTYPE_APP_OTA_MAX 32
esp_partition_t seeed={0,16}, crosspoint={0,32};
const esp_partition_t *running=&seeed;
const esp_partition_t *esp_ota_get_running_partition(void) { return running; }
const esp_partition_t *esp_partition_verify(const esp_partition_t *p) { return p; }
const esp_partition_t *esp_partition_find_first(int type,int sub,const char *name) {
  if(sub==seeed.subtype) return &seeed;
  if(sub==crosspoint.subtype) return &crosspoint;
  return NULL;
}
'''
suffix = r'''
int main(void) {
 const esp_partition_t *p=esp_ota_get_next_update_partition(NULL);
 esp_ota_handle_t h;
 assert(p==&seeed && esp_ota_begin(p,0,&h)==ESP_ERR_OTA_PARTITION_CONFLICT);
 assert(esp_ota_begin(&crosspoint,0,&h)==ESP_ERR_INVALID_ARG);
 crosspoint.subtype=17; /* Original two-slot layout exposes CrossPoint for erase. */
 assert(esp_ota_get_next_update_partition(NULL)==&crosspoint);
 assert(esp_ota_begin(&crosspoint,0,&h)==12345);
 crosspoint.subtype=32; running=&crosspoint;
 assert(esp_ota_get_next_update_partition(NULL)==&seeed);
 /* CP's raw target would be Seeedash: pre-erase guard alone is NOT enough.
    The separate real partition/flash wrapper tests must deny these writes. */
 assert(esp_ota_begin(&seeed,0,&h)==12345);
 puts("PASS: real IDF next-partition algorithm and pre-erase guards reject the protected test partition");
}
'''
for ota_idf in [IDF, ROOT/".cache/platformio/packages/framework-espidf"]:
    source = (ota_idf / "components/app_update/esp_ota_ops.c").read_text()
    next_partition = function(source, "const esp_partition_t* esp_ota_get_next_update_partition(")
    is_ota = function(source, "static bool is_ota_partition(")
    begin = function(source, "esp_err_t esp_ota_begin(")
    # Retain the actual pre-erase guards; the later IDF implementation is outside this host test.
    begin = begin[:begin.index("#ifdef CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE")]
    begin += "}"*(begin.count("{")-begin.count("}")-1) + "return 12345; }\n"
    (OUT / "idf_ota_guards.c").write_text(prefix + is_ota + next_partition + begin + suffix)
    run(*common, "-Wno-unused-variable", str(OUT / "idf_ota_guards.c"), "-o", str(OUT / "ota"))
    run(str(OUT / "ota"))


# Verify CSV against the actual official package, not a second hand-written map.
spec = importlib.util.spec_from_file_location("gen_esp32part", IDF / "components/partition_table/gen_esp32part.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
table = gen.PartitionTable.from_csv((ROOT / "partitions/sticky-32m.csv").read_text())
table.verify()
vendor=ROOT/'.local/vendor/seeedash-1.2.0.bin'
if vendor.exists():
    factory=official(vendor.read_bytes())
    old=gen.PartitionTable.from_binary(factory[0x8000:0x8c00])
    for p in old:
        new=table[p.name]
        assert (new.offset,new.size,new.type)==(p.offset,p.size,p.type)
        assert new.subtype==(32 if p.name=='app1' else p.subtype)
    print('PASS: official factory digest, vendor extents and erased private gap')
else:
    print('SKIP: optional local Seeedash artifact not downloaded; no factory-image claim')
assert table.to_binary()==partition_table()
assert sum(p.type==0 and 16<=p.subtype<32 for p in table)==1

adapter = (ROOT / "firmware/bootloader_components/main/bootloader_start.c").read_text()
supported = function(adapter, "static bool supported_layout(")
validate_image = function(adapter, "static bool validate_image(")
pins = adapter[adapter.index("static const uint8_t seeedash_sha"):adapter.index("static void early_power_latch")]
blob = table.to_binary()
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "boot_policy.h"
#define ESP_OK 0
#define ESP_IMAGE_VERIFY 0
#define ESP_PARTITION_MAGIC 0x50aa
typedef struct { uint32_t offset,size; } esp_partition_pos_t;
typedef struct { esp_partition_pos_t ota_info,ota[16],test; unsigned app_count; } bootloader_state_t;
typedef struct { uint16_t magic; uint8_t type,subtype; esp_partition_pos_t pos; char label[16]; uint32_t flags; } esp_partition_info_t;
typedef struct { unsigned spi_size,hash_appended; } fake_image_t;
typedef struct { fake_image_t image; uint32_t image_len; uint8_t image_digest[32]; } esp_image_metadata_t;
_Alignas(4) unsigned char raw_table[3072];
esp_image_metadata_t fake_image;
int verify_error;
int esp_image_verify(int mode,const esp_partition_pos_t *p,esp_image_metadata_t *m) {
  *m=fake_image; return verify_error;
}
int bootloader_flash_read(size_t address,void *out,size_t size,bool decrypt) {
  assert(address>=0x8000 && address+size<=0x8c00);
  memcpy(out,raw_table+(address-0x8000),size); return ESP_OK;
}
'''
initializer = "static const unsigned char reference[] = {" + ",".join(str(x) for x in blob) + "};\n"
suffix = r'''
int main(void) {
 memcpy(raw_table,reference,sizeof(reference));
 bootloader_state_t bs={.ota_info={0x86000,0x2000},.ota={{0x90000,0x600000}},.test={0x690000,0x600000},.app_count=1};
 assert(supported_layout(&bs));
 for(unsigned i=0;i<10;++i) {
  esp_partition_info_t *p=(void *)(raw_table+32*i); uint32_t saved=p->pos.offset;
  p->pos.offset+=4096; assert(!supported_layout(&bs)); p->pos.offset=saved;
  p->flags=1; assert(!supported_layout(&bs)); p->flags=0;
  p->subtype^=1; assert(!supported_layout(&bs)); p->subtype^=1;
 }
 raw_table[10*32]=0xaa; raw_table[10*32+1]=0x50; assert(!supported_layout(&bs));
 memcpy(raw_table,reference,sizeof(reference)); bs.app_count=2; assert(!supported_layout(&bs)); bs.app_count=1;
 flash_context_t ctx={&bs,0x8e000};
 fake_image=(esp_image_metadata_t){.image={5,1},.image_len=3261088}; memcpy(fake_image.image_digest,seeedash_sha,32);
 assert(validate_image(&ctx,BOOT_SEEEDASH));
 #if CROSSPOINT_IMAGE_LEN == 0
 assert(!validate_image(&ctx,BOOT_CROSSPOINT));
#else
 fake_image.image_len=CROSSPOINT_IMAGE_LEN; memcpy(fake_image.image_digest,crosspoint_sha,32);
 assert(validate_image(&ctx,BOOT_CROSSPOINT));
 fake_image.image_digest[0]^=1; assert(!validate_image(&ctx,BOOT_CROSSPOINT));
 fake_image.image_digest[0]^=1;
 fake_image.image_len--; assert(!validate_image(&ctx,BOOT_CROSSPOINT));
 fake_image.image_len=3261088; memcpy(fake_image.image_digest,seeedash_sha,32);
#endif
 fake_image.image_digest[0]^=1; assert(!validate_image(&ctx,BOOT_SEEEDASH)); fake_image.image_digest[0]^=1;
 fake_image.image.spi_size=4; assert(!validate_image(&ctx,BOOT_SEEEDASH)); fake_image.image.spi_size=5;
 fake_image.image.hash_appended=0; assert(!validate_image(&ctx,BOOT_SEEEDASH)); fake_image.image.hash_appended=1;
 fake_image.image_len--; assert(!validate_image(&ctx,BOOT_SEEEDASH)); fake_image.image_len++;
 verify_error=1; assert(!validate_image(&ctx,BOOT_SEEEDASH)); verify_error=0;
 ctx.offset=0x86000; assert(!validate_image(&ctx,BOOT_CROSSPOINT));
 puts("PASS: production layout/image adapter with mocked IDF reads, protected CSV, mutation rejection and CP pin checks");
}
'''
(OUT / "adapter.c").write_text(prefix + pins + supported + validate_image + initializer + suffix)
run(*common, str(OUT / "adapter.c"), "-o", str(OUT / "adapter"))
run(str(OUT / "adapter"))
(OUT / "results.json").write_text(json.dumps({"host_tests": "PASS", "hardware_tested": False,
    "factory_checked": vendor.exists(),
    "idf_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=IDF, text=True).strip()}, indent=2) + "\n")
