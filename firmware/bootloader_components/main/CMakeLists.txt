idf_component_register(SRCS "bootloader_start.c" "boot_policy.c"
                       INCLUDE_DIRS "../../include"
                       REQUIRES bootloader bootloader_support spi_flash)
idf_build_get_property(target IDF_TARGET)
set(scripts "${IDF_PATH}/components/bootloader/subproject/main/ld/${target}/bootloader.ld"
            "${IDF_PATH}/components/bootloader/subproject/main/ld/${target}/bootloader.rom.ld")
target_linker_script(${COMPONENT_LIB} INTERFACE "${scripts}")
