#Requires -Version 5.1
# Offline install on the target machine: venv + wheels from offline_cache\wheels.
param([switch]$SkipSelfTest)
$ErrorActionPreference = "Stop"

$Root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Wheels = Join-Path $Root "offline_cache\wheels"
$Venv   = Join-Path $Root ".venv"
$Py     = Join-Path $Venv "Scripts\python.exe"

Write-Host "[1/4] Checking Python 3.11..."
py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 not found. Install it from python.org (x64, with the py launcher)." }

Write-Host "[2/4] Creating venv..."
if (-not (Test-Path $Venv)) { py -3.11 -m venv $Venv }

Write-Host "[3/4] Installing packages offline..."
$env:CHEM_AGENT_OFFLINE = "1"
& $Py -m pip install --no-index --find-links=$Wheels -r (Join-Path $Root "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) { throw "Offline install failed (is offline_cache\wheels empty? run setup_offline.bat once)" }

# 'chem-agent' command inside the venv: a small wrapper, the package runs from the project folder
$Shim = Join-Path $Venv "Scripts\chem-agent.cmd"
$Lines = @(
    "@echo off",
    "chcp 65001 >nul",
    "set ""CHEM_AGENT_OFFLINE=1""",
    "set ""PYTHONPATH=$Root""",
    """%~dp0python.exe"" -m chem_agent %*"
)
[System.IO.File]::WriteAllText($Shim, ($Lines -join "`r`n") + "`r`n", (New-Object System.Text.UTF8Encoding($false)))

if (-not $SkipSelfTest) {
    Write-Host "[4/4] Self-test..."
    $env:CHEM_AGENT_OFFLINE = "1"
    Push-Location $Root
    try { & $Py -m chem_agent self-test } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "self-test failed" }
}
Write-Host "Installed. Try: run_cli.bat predict --reagents ""NaOH:0.1,HCl:0.1"" --output html --open"
