"""Final-link coverage audit retained from the hardware-reported Stage4 implementation."""
import re
import struct
from elftools.elf.elffile import ELFFile
from common import ROOT, require, image, parse_table, boot_contract
BOOT_CONTRACT=boot_contract()
CONTRACT=b'STICKY-DUALBOOT-ABI3;cp_nvs=0x89000:0x5000;bootstate=0x8e000:0x2000;OTA=FORBIDDEN\0'

def crosspoint_checks(build):
    data = (build/'firmware.bin').read_bytes()
    info = image(data, 0x600000, 'CrossPoint')
    require(CONTRACT in data, 'Missing integration ABI contract')
    require(BOOT_CONTRACT in data, 'Missing menu selector protocol')
    parse_table((build/'partitions.bin').read_bytes())
    require(not (build/'firmware.factory.bin').exists(), 'Unchecked automatic factory merge exists')
    config = (build/'dualboot-sdkconfig.h').read_text()
    for define in ['CONFIG_ESPTOOLPY_FLASHSIZE_32MB 1', 'CONFIG_ESPTOOLPY_FLASHSIZE "32MB"']:
        require('#define '+define in config, 'Missing generated config: '+define)
    for option in ['CONFIG_NVS_ENCRYPTION', 'CONFIG_SECURE_BOOT', 'CONFIG_SECURE_FLASH_ENC_ENABLED',
                   'CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE', 'CONFIG_BOOTLOADER_APP_ANTI_ROLLBACK',
                   'CONFIG_ARDUINO_SELECTIVE_LittleFS', 'CONFIG_ARDUINO_SELECTIVE_SPIFFS']:
        require('#define '+option+' 1' not in config, 'Unsupported config '+option)
    with (build/'firmware.elf').open('rb') as f:
        elf = ELFFile(f)
        require(elf['e_machine'] == 'EM_XTENSA', 'ELF architecture')
        symbols = {s.name:s for s in elf.get_section_by_name('.symtab').iter_symbols() if s['st_shndx'] != 'SHN_UNDEF'}
        wraps = re.findall(r'--wrap=([a-zA-Z_][a-zA-Z_0-9]*)',
                           (ROOT/'crosspoint/link_flags.txt').read_text())
        for name in ['__wrap_'+n for n in wraps]+['sticky_dualboot_build_contract']:
            require(name in symbols, 'Linked guard missing: '+name)
        for name in ['nvs_flash_generate_keys','nvs_flash_generate_keys_v2',
                     'nvs_flash_register_security_scheme','esp_vfs_spiffs_register',
                     'esp_vfs_littlefs_register','esp_spiffs_format','esp_littlefs_format']:
            require(name not in symbols, 'Unused/unisolated flash API linked: '+name)
        osi = symbols.get('g_wifi_osi_funcs')
        require(osi and osi['st_size'] >= 200, 'Wi-Fi OSI table missing')
        sec = elf.get_section(osi['st_shndx'])
        off = osi['st_value']-sec['sh_addr']
        table = sec.data()[off:off+osi['st_size']]
        ptr = struct.pack('<I',symbols['__wrap_nvs_open']['st_value'])
        require(ptr in table, 'Wi-Fi OSI nvs_open does not point to isolation wrapper')
        if 'nvs_open' in symbols:
            require(struct.pack('<I',symbols['nvs_open']['st_value']) not in table,
                    'Wi-Fi OSI still references default NVS open')
    link_map = (build/'firmware.map').read_text()
    require('Cross Reference Table' in link_map, 'No link cross-reference table')
    refs = link_map.split('Cross Reference Table',1)[1]
    def references(symbol):
        match = re.search(r'^'+re.escape(symbol)+r'\s+[^\n]*\n(?:[ \t]+[^\n]*\n)*', refs, re.M)
        require(match, 'Missing link reference: '+symbol)
        return match.group()
    require('esp32-hal-misc.c.o' in references('__wrap_nvs_flash_init'),
            'Arduino startup does not reference the NVS init wrapper')
    require('Preferences.cpp.o' in references('__wrap_nvs_open'),
            'Preferences does not reference the default NVS open wrapper')
    require('nvs_partition.cpp.obj' in references('__wrap_esp_partition_write') or
            'nvs_partition.cpp.o' in references('__wrap_esp_partition_write'),
            'NVS writes bypass partition wrapper')
    require('HalSystem.cpp.o' in references('boot_choose'),
            'Menu does not use the private journal selector')
    return data, info
