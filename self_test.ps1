#Requires -Version 5.1
# Full pytest suite, offline.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:CHEM_AGENT_OFFLINE = "1"
$env:PYTHONIOENCODING = "utf-8"
Push-Location $Root
try {
    & (Join-Path $Root ".venv\Scripts\python.exe") -m pytest (Join-Path $Root "tests") -v --maxfail=1
    $code = $LASTEXITCODE
} finally { Pop-Location }
exit $code
