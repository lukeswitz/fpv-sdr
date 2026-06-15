#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$Distro = 'Ubuntu'

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-WslReady {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return $false }
    $raw = & wsl.exe --list --quiet 2>$null
    $clean = ($raw -join "`n") -replace "`0", ""
    return ($clean -match [regex]::Escape($Distro))
}

function Get-DistroWslVersion {
    $raw = & wsl.exe -l -v 2>$null
    $clean = ($raw -join "`n") -replace "`0", ""
    foreach ($line in ($clean -split "`n")) {
        if ($line -match [regex]::Escape($Distro)) {
            if ($line -match '(\d+)\s*$') { return [int]$Matches[1] }
        }
    }
    return 0
}

function Update-Wsl {
    Write-Host 'Updating WSL kernel...' -ForegroundColor Cyan
    & wsl.exe --update 2>$null | Out-Null
    & wsl.exe --shutdown 2>$null | Out-Null
}

function Convert-ToWsl2 {
    Write-Host "$Distro is on WSL1, which cannot run systemd (the /etc/passwd lock error). Converting to WSL2..." -ForegroundColor Cyan
    & wsl.exe --set-default-version 2 2>$null | Out-Null
    & wsl.exe --set-version $Distro 2
    if ($LASTEXITCODE -ne 0) {
        Show-Wsl2Blocked (Get-HostEnv)
        exit 1
    }
    & wsl.exe --shutdown 2>$null | Out-Null
}

function Enable-Systemd {
    $conf = "[boot]`nsystemd=true`n"
    $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($conf))
    & wsl.exe -d $Distro -- bash -lc "echo $b64 | base64 -d | sudo tee /etc/wsl.conf >/dev/null" 2>$null | Out-Null
    & wsl.exe --shutdown 2>$null | Out-Null
}

function Get-HostEnv {
    try { $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop } catch { return 'unknown' }
    $m = "$($cs.Manufacturer) $($cs.Model)"
    if ($m -match 'Parallels') { return 'parallels' }
    if ($m -match 'VMware') { return 'vmware' }
    if ($m -match 'VirtualBox|innotek|Oracle') { return 'virtualbox' }
    if ($m -match 'QEMU|KVM') { return 'qemu' }
    if ($m -match 'Microsoft Corporation' -and $m -match 'Virtual Machine') { return 'hyperv' }
    return 'physical'
}

function Test-ArmCpu {
    return ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64')
}

function Show-Wsl2Blocked {
    param([string]$HostEnv)
    if ($HostEnv -eq 'parallels' -and (Test-ArmCpu)) {
        Write-Host 'WSL2 cannot start: Parallels on an Apple Silicon Mac.' -ForegroundColor Red
        Write-Host 'WSL2 needs nested virtualization, which Apple Silicon supports only on M3 or newer (macOS 15+).' -ForegroundColor Yellow
        Write-Host 'On an M1/M2 Mac it is not possible. Use a physical Windows PC, or an M3+ Mac with nested virtualization' -ForegroundColor Yellow
        Write-Host 'enabled in the VM settings (shut the VM down first: Hardware > CPU & Memory > Advanced).' -ForegroundColor Yellow
    } elseif ($HostEnv -in @('parallels', 'vmware', 'virtualbox', 'qemu')) {
        Write-Host "WSL2 cannot start inside this $HostEnv VM." -ForegroundColor Red
        Write-Host 'Enable nested virtualization in the VM settings (with the VM powered off), then re-run this script.' -ForegroundColor Yellow
    } else {
        Write-Host 'WSL2 cannot start: hardware virtualization is off.' -ForegroundColor Red
        Write-Host 'Turn on virtualization (VT-x/AMD-V/SVM) in firmware/BIOS, enable Virtual Machine Platform, reboot, then re-run:' -ForegroundColor Yellow
        Write-Host '  dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart' -ForegroundColor Yellow
    }
}

Write-Host '== Dragon FPV Decoder - Windows setup ==' -ForegroundColor Cyan
$HostEnv = Get-HostEnv
if ($HostEnv -notin @('physical', 'unknown')) {
    Write-Host "Detected: running inside a $HostEnv virtual machine ($env:PROCESSOR_ARCHITECTURE)." -ForegroundColor DarkGray
    if ($HostEnv -eq 'parallels' -and (Test-ArmCpu)) {
        Write-Host 'Heads-up: WSL2 on Parallels needs an M3+ Mac (macOS 15+). On M1/M2 it will not start.' -ForegroundColor DarkYellow
    }
}

if (-not (Test-WslReady)) {
    if (-not (Test-IsAdmin)) {
        Write-Host "WSL2 + $Distro not found. Open PowerShell as Administrator and run this script again." -ForegroundColor Yellow
        exit 1
    }
    Update-Wsl
    Write-Host "Installing WSL2 + $Distro (this may require a reboot)..." -ForegroundColor Cyan
    & wsl.exe --install -d $Distro
    Write-Host ''
    Write-Host "If Windows asked for a REBOOT, reboot now. After reboot, finish first-run user setup, then run this script again." -ForegroundColor Yellow
    exit 0
}

if (Test-IsAdmin) {
    Update-Wsl
    if ((Get-DistroWslVersion) -eq 1) { Convert-ToWsl2 }
    Enable-Systemd
} else {
    if ((Get-DistroWslVersion) -eq 1) {
        Write-Host "$Distro is on WSL1 and must be converted. Run as Administrator:  wsl --set-version $Distro 2" -ForegroundColor Red
        exit 1
    }
    Write-Host 'Note: run as Administrator once to update the WSL kernel.' -ForegroundColor Yellow
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$inner = @"
set -e
sudo dpkg --configure -a || true
sudo apt-get -f install -y || true
rm -rf "`$HOME/dragon-fpv-decoder"
mkdir -p "`$HOME/dragon-fpv-decoder"
cp -a ./. "`$HOME/dragon-fpv-decoder/"
cd "`$HOME/dragon-fpv-decoder"
chmod +x setup.sh tests/*.sh fpv_scanner.sh fpv_detect.py fpv_viewer.py fpv_sdr.py 2>/dev/null || true
./setup.sh
./tests/smoke_test.sh
"@

Write-Host "Copying the project into $Distro and running ./setup.sh + smoke test..." -ForegroundColor Cyan
& wsl.exe -d $Distro --cd "$scriptDir" -- bash -lc $inner
$code = $LASTEXITCODE

if ($code -eq 0) {
    Write-Host ''
    Write-Host 'Install complete and tested. To run the scanner:' -ForegroundColor Green
    Write-Host "  1. Open the $Distro app from the Start menu" -ForegroundColor Green
    Write-Host '  2. cd ~/dragon-fpv-decoder' -ForegroundColor Green
    Write-Host '  3. ./fpv_scanner.sh --sdr hackrf      then type:  scan' -ForegroundColor Green
    Write-Host ''
    Write-Host 'Using a USB radio (HackRF/BladeRF)? First, in this Admin PowerShell:' -ForegroundColor Green
    Write-Host '   usbipd list      then      usbipd attach --wsl --busid <BUSID>' -ForegroundColor Green
} else {
    Write-Host ''
    Write-Host "Setup failed. Verify WSL2:  wsl -l -v  (must say VERSION 2). If still broken: wsl --unregister $Distro then re-run." -ForegroundColor Red
}

exit $code