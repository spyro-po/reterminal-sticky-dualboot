# Windows 11 installation

The Docker builder runs Linux tooling under WSL2. The physical flash operation runs **manually on Windows**, using the device's COM port. No USB/serial passthrough, privileged container, USBIP setup or Docker socket mount is needed.

## 1. Docker Desktop and WSL2

Follow [Microsoft's WSL installation instructions](https://learn.microsoft.com/en-us/windows/wsl/install) and [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/). In an administrator PowerShell, if WSL is not installed:

```powershell
wsl --install -d Ubuntu
wsl --update
wsl --list --verbose
```

Restart when requested. Use WSL version 2 for Ubuntu. Start Docker Desktop, select the Linux/WSL2 backend and enable integration for Ubuntu in Docker Desktop's WSL integration settings. Check current supported Windows/WSL versions and Docker licensing in the official documentation; do not assume every Windows or ARM configuration is validated here.

Inside the Ubuntu terminal, install Git if missing, clone the repository and select the approved source version/branch. Store the working tree in the Linux filesystem for better filesystem performance; see [Docker's WSL guidance](https://docs.docker.com/desktop/features/wsl/).

```sh
git clone https://github.com/spyro-po/reterminal-sticky-dualboot.git
cd reterminal-sticky-dualboot
# v1.1.0 is under development: use feature/docker-installer until an approved release exists.
git switch feature/docker-installer
docker version
./sticky-installer.sh list
./sticky-installer.sh build
./sticky-installer.sh verify --mode fresh
```

Generated files are in `out/cp-2.0.0-seeedash-1.2.0/`. Open that directory in Windows Explorer from WSL using `explorer.exe out`. Its Windows path is normally `\\wsl.localhost\Ubuntu\home\YOUR_USER\reterminal-sticky-dualboot\out\cp-2.0.0-seeedash-1.2.0`. Copy the **entire six-file bundle** to `C:\Sticky\bundle`. Do not publish these local files.

## 2. Verify the copied Windows bundle

Run in ordinary PowerShell:

```powershell
$ErrorActionPreference = 'Stop'
$Bundle = 'C:\Sticky\bundle'
Get-Content "$Bundle\SHA256SUMS.txt" | ForEach-Object {
    if ($_ -notmatch '^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$') { throw 'Malformed checksum row' }
    $Expected = $Matches[1]
    $Name = $Matches[2]
    $Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Bundle $Name)).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected) { throw "Checksum mismatch: $Name" }
    Write-Host "OK: $Name"
}
```

Also run the Docker verifier against the copied files from WSL:

```sh
./sticky-installer.sh verify --output /mnt/c/Sticky --directory bundle --mode fresh
```

Checksums detect accidental corruption, not a maliciously replaced bundle. The verifier additionally checks the paired image pin, layout and factory extents.

## 3. Prepare manual Windows esptool

Install Python 3.12 from its official distribution if needed. The builder itself does not require Windows Python; this separate environment is for manual esptool **4.12.0** only. Choose the actual Sticky COM port; COM5 below is a placeholder.

```powershell
py -3.12 -m venv C:\Sticky\esptool-env
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
$EspPy = 'C:\Sticky\esptool-env\Scripts\python.exe'
& $EspPy -m pip install esptool==4.12.0
if ($LASTEXITCODE -ne 0) { throw 'esptool installation failed' }
$Port = 'COM5'
function Invoke-StickyEsp {
    & $EspPy -m esptool --chip esp32s3 --port $Port @args
    if ($LASTEXITCODE -ne 0) { throw 'esptool failed: STOP before the next operation' }
}
Invoke-StickyEsp get_security_info
Invoke-StickyEsp flash_id
if (Test-Path -LiteralPath C:\Sticky\before-32MiB.bin) { throw 'Backup exists: choose a new private filename' }
if (Test-Path -LiteralPath C:\Sticky\before-32MiB.bin.sha256) { throw 'Backup digest exists: choose a new private filename' }
Invoke-StickyEsp --after no_reset read_flash 0x0 0x2000000 C:\Sticky\before-32MiB.bin
Invoke-StickyEsp --after no_reset verify_flash 0x0 C:\Sticky\before-32MiB.bin
$BackupSha256 = (Get-FileHash -Algorithm SHA256 C:\Sticky\before-32MiB.bin).Hash.ToLowerInvariant()
Set-Content -LiteralPath C:\Sticky\before-32MiB.bin.sha256 -Value $BackupSha256 -NoNewline
```

Check every command's exit code (`$LASTEXITCODE` must be 0) before continuing. Confirm 32 MiB Flash, unrestricted ROM download and no Secure Boot/encryption. Stop on any mismatch. Do not burn eFuses or use `--force`. Keep the private backup off GitHub. Use stable USB power and a data cable. Close serial monitors and other programs holding the COM port.

## 4A. Fresh Install — destroys data

Only after verifying the bundle and full backup and explicitly accepting loss of Flash data:

```powershell
Invoke-StickyEsp --after no_reset erase_flash
Invoke-StickyEsp --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 "$Bundle\fresh-32MiB.bin"
Invoke-StickyEsp --after no_reset verify_flash 0x0 "$Bundle\fresh-32MiB.bin"
```

Check each exit code before the next command. Reset without Up after verification. See [INSTALL.md](INSTALL.md) for the physical test checklist.

## 4B. Preserve Data — already compatible Dual Boot only

Do **not** erase. First run in WSL, using the actual full backup from this device:

```sh
./sticky-installer.sh verify --output /mnt/c/Sticky --directory bundle --mode preserve --backup /mnt/c/Sticky/before-32MiB.bin --confirm-layout protected-reference
./sticky-installer.sh info --output /mnt/c/Sticky --directory bundle --mode preserve --backup /mnt/c/Sticky/before-32MiB.bin --confirm-layout protected-reference
```

Stop unless preflight succeeds. The flag alone does not confirm compatibility. Then, in PowerShell, write exactly the matched code pair and keep ROM/stub active:

```powershell
Invoke-StickyEsp --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 "$Bundle\bootloader.bin" 0x690000 "$Bundle\crosspoint.bin"
Invoke-StickyEsp --after no_reset verify_flash 0x0 "$Bundle\bootloader.bin" 0x690000 "$Bundle\crosspoint.bin"
if (Test-Path -LiteralPath C:\Sticky\after-before-boot.bin) { throw 'Readback exists: choose a new private filename' }
Invoke-StickyEsp --after no_reset read_flash 0x0 0x2000000 C:\Sticky\after-before-boot.bin
```

Check each exit code. Before resetting, use the existing preflight readback comparison described in [UPDATE.md](UPDATE.md). With the Docker tools, invoke it from WSL by overriding the entrypoint (no device is attached):

```sh
docker run --rm --platform linux/amd64 --network none --user "$(id -u):$(id -g)" --cap-drop ALL --security-opt no-new-privileges --mount type=bind,src=/mnt/c/Sticky,dst=/check,readonly --entrypoint /opt/sticky/python/bin/python reterminal-sticky-dualboot-builder:1.1.0 /opt/sticky/source/scripts/preflight.py --bundle /check/bundle --backup /check/before-32MiB.bin --after /check/after-before-boot.bin
```

This validates the exact predicted sector writes and unchanged protected bytes; it performs no device write. Never add a partition table, OTA metadata, NVS, `boot_app0` or filesystem image. `0xe000` is inside factory NVS. The paired update is not power-fail atomic.

## 5. Recovery

For an exact restore, use a complete verified backup from **this chip** at offset 0x0 and verify it. A Dual Boot backup restores Dual Boot; it does not restore the factory layout.

```powershell
$ExpectedBackupSha256 = (Get-Content -Raw -LiteralPath C:\Sticky\before-32MiB.bin.sha256).Trim()
if ($ExpectedBackupSha256 -notmatch '^[0-9a-f]{64}$') { throw 'Invalid trusted backup digest' }
if ((Get-FileHash -Algorithm SHA256 C:\Sticky\before-32MiB.bin).Hash.ToLowerInvariant() -ne $ExpectedBackupSha256) { throw 'Backup hash mismatch: STOP' }
if ((Get-Item C:\Sticky\before-32MiB.bin).Length -ne 33554432) { throw 'Backup size mismatch: STOP' }
Invoke-StickyEsp --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 C:\Sticky\before-32MiB.bin
Invoke-StickyEsp --after no_reset verify_flash 0x0 C:\Sticky\before-32MiB.bin
```

Without a suitable factory backup, download the official image directly and validate its pinned hash. This factory-default restore **destroys personal Flash data**:

```powershell
$Url = 'https://raw.githubusercontent.com/Seeed-Projects/reterminal-sticky-playground-registry/f0479400594d8f9a3d7fd7b282f2d7b2a1bdbd0e/firmwares/sticky-factory/firmware/1.2.0/reterminal_sticky_1_2_0.bin'
Invoke-WebRequest -Uri $Url -OutFile C:\Sticky\seeedash-1.2.0.bin
$Expected = '5cd55031ddee26cf32ed9e01dd89ed8d820bdbfe752d0140b136177fab26a2a2'
if ((Get-FileHash -Algorithm SHA256 C:\Sticky\seeedash-1.2.0.bin).Hash.ToLowerInvariant() -ne $Expected) { throw 'Vendor hash mismatch: STOP' }
if ((Get-Item C:\Sticky\seeedash-1.2.0.bin).Length -ne 33292288) { throw 'Vendor size mismatch: STOP' }
Invoke-StickyEsp --after no_reset erase_flash
Invoke-StickyEsp --after no_reset write_flash --flash_mode keep --flash_freq keep --flash_size keep 0x0 C:\Sticky\seeedash-1.2.0.bin
Invoke-StickyEsp --after no_reset verify_flash 0x0 C:\Sticky\seeedash-1.2.0.bin
```

Stop on any command/hash failure. Reset after verification and provision Seeedash again. Full erase clears the last 256 KiB absent from the vendor file. Up is not the ROM BOOT strap; see [RECOVERY.md](RECOVERY.md) if auto-download fails. Do not guess board pads.

Windows installation has not been executed. The owner reports successful Ubuntu Docker build/reproducibility/verification; see the [final audit](V1.1_FINAL_AUDIT.md). The exact image now has owner-reported Preserve Data/flash/readback and 9/9 hardware results; this does not establish Windows execution. Keep all OTA forbidden. Battery power for emergency Up+Reset and sleep/wake stress remain unconfirmed; basic sleep/wake passed.
