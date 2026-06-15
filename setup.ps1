#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$Distro = 'Ubuntu'

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-WslReady {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return $false }
    $raw = & wsl.exe --list --quiet 2>$null
    $clean = ($raw -join "`n") -replace "`0", ""
    return ($clean -match [regex]::Escape($Distro))
}

Write-Host '== Dragon FPV Decoder - Windows setup ==' -ForegroundColor Cyan

if (-not (Test-WslReady)) {
    if (-not (Test-IsAdmin)) {
        Write-Host "WSL2 + $Distro not found. Close this window, open PowerShell as Administrator, and run this script again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Installing WSL2 + $Distro (this may require a reboot)..." -ForegroundColor Cyan
    & wsl.exe --install -d $Distro
    Write-Host ''
    Write-Host "If Windows asked for a REBOOT, reboot now. After reboot, let $Distro finish its first-run user setup, then run this script again." -ForegroundColor Yellow
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$drive = $scriptDir.Substring(0, 1).ToLower()
$wslSrc = '/mnt/' + $drive + (($scriptDir.Substring(2)) -replace '\\', '/')

$inner = @"
set -e
if ! command -v rsync >/dev/null || ! command -v git >/dev/null; then
  sudo apt-get update -qq && sudo apt-get install -y -qq rsync git
fi
rsync -a --exclude=.git --exclude=__pycache__ "$wslSrc/" "`$HOME/dragon-fpv-decoder/"
cd "`$HOME/dragon-fpv-decoder"
./setup.sh
./tests/smoke_test.sh
"@

Write-Host "Copying the project into $Distro and running ./setup.sh + smoke test..." -ForegroundColor Cyan
& wsl.exe -d $Distro -- bash -lc $inner
$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Host ''
    Write-Host "Done. In the $Distro shell:  cd ~/dragon-fpv-decoder  then  ./fpv_scanner.sh --sdr hackrf" -ForegroundColor Green
    Write-Host "For a USB radio, attach it first (Admin PowerShell): usbipd list; usbipd bind --busid <id>; usbipd attach --wsl --busid <id>" -ForegroundColor Green
}
exit $code
