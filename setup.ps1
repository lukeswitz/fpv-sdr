#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$Distro = 'Ubuntu'

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-WslPresent {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return $false }
    $raw = & wsl.exe --list --quiet 2>$null
    $clean = ($raw -join "`n") -replace "`0", ""
    return ($clean -match [regex]::Escape($Distro))
}

Write-Host '== Dragon FPV Decoder - Windows setup ==' -ForegroundColor Cyan

if (-not (Test-WslPresent)) {
    if (-not (Test-IsAdmin)) {
        Write-Host "WSL + $Distro not found. Open PowerShell as Administrator and run this script again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Installing WSL + $Distro (this may require a reboot)..." -ForegroundColor Cyan
    & wsl.exe --install -d $Distro
    Write-Host ''
    Write-Host "If Windows asked for a REBOOT, reboot now, finish first-run user setup, then run this script again." -ForegroundColor Yellow
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$bash = @'
set -e

on_wsl1() {
  grep -qi microsoft /proc/version 2>/dev/null || return 1
  mount 2>/dev/null | grep -q "type 9p" && return 1
  return 0
}

if on_wsl1; then
  echo "WSL1 detected: neutralizing systemd-sysusers so dpkg can finish."
  if [ -e /bin/systemd-sysusers ] && [ ! -L /bin/systemd-sysusers ]; then
    sudo mv -f /bin/systemd-sysusers /bin/systemd-sysusers.real
    sudo ln -s "$(command -v echo)" /bin/systemd-sysusers
  fi
  sudo sed -i -e '/systemd-sysusers/s/$/ || true/' /var/lib/dpkg/info/*.postinst 2>/dev/null || true
  sudo dpkg --configure systemd >/dev/null 2>&1 || true
fi

sudo dpkg --configure -a || true
sudo apt-get -f install -y || true

rm -rf "$HOME/dragon-fpv-decoder"
mkdir -p "$HOME/dragon-fpv-decoder"
cp -a "$SRC_DIR"/. "$HOME/dragon-fpv-decoder/"
cd "$HOME/dragon-fpv-decoder"
chmod +x setup.sh tests/*.sh fpv_scanner.sh fpv_detect.py fpv_viewer.py fpv_sdr.py 2>/dev/null || true
./setup.sh
./tests/smoke_test.sh
'@

$bash = $bash -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))

Write-Host "Copying the project into $Distro and running ./setup.sh + smoke test..." -ForegroundColor Cyan
& wsl.exe -d $Distro --cd "$scriptDir" -- bash -lc "export SRC_DIR=`"`$PWD`"; echo $b64 | base64 -d | bash -s"
$code = $LASTEXITCODE

if ($code -eq 0) {
    Write-Host ''
    Write-Host "Done. In the $Distro shell:  cd ~/dragon-fpv-decoder  then  ./fpv_scanner.sh --sdr hackrf" -ForegroundColor Green
    Write-Host "For a USB radio, attach it first (Admin PowerShell): usbipd list; usbipd bind --busid <id>; usbipd attach --wsl --busid <id>" -ForegroundColor Green
} else {
    Write-Host ''
    Write-Host "Setup failed. Re-run once; dpkg state is repaired and apt should proceed." -ForegroundColor Red
}

exit $code
