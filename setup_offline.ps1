#Requires -Version 5.1
# The only script that uses the network: downloads wheels for Windows x64 / Python 3.11,
# installs them and runs the offline self-test. Works in Windows PowerShell 5.1 and PowerShell 7.
# The thermodynamic database is already built: chem_agent\data\crc.db (raw data in offline_cache\*.tsv).
$ErrorActionPreference = "Stop"

$Root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Wheels = Join-Path $Root "offline_cache\wheels"
$Venv   = Join-Path $Root ".venv"
$Py     = Join-Path $Venv "Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $Wheels | Out-Null

Write-Host "[1/5] Checking Python 3.11..."
py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 not found. Install it from python.org (x64, with the py launcher)." }

Write-Host "[2/5] Creating venv..."
if (-not (Test-Path $Venv)) { py -3.11 -m venv $Venv }

Write-Host "[3/5] Downloading wheels (the only network step)..."
& $Py -m pip download --only-binary=:all: -r (Join-Path $Root "requirements-dev.txt") -d $Wheels
if ($LASTEXITCODE -ne 0) { throw "pip download failed" }

Write-Host "[4/5] Installing from local wheels..."
& (Join-Path $Root "install_offline.ps1") -SkipSelfTest

Write-Host "[5/5] Offline self-test..."
$env:CHEM_AGENT_OFFLINE = "1"
Push-Location $Root
try { & $Py -m chem_agent self-test } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "self-test failed" }
Write-Host "Done."
