#Requires -Version 5.1
# Builds the portable archive. offline_cache\wheels must contain the wheels (setup_offline.ps1).
$ErrorActionPreference = "Stop"

$Root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp  = Get-Date -Format "yyyyMMdd"
$Bundle = Join-Path $Root "chem-agent-offline-$Stamp.zip"

$Items = @(
    "chem_agent", "models", "templates", "static",
    "offline_cache", "tests", "examples",
    "requirements.txt", "requirements-dev.txt",
    "setup_offline.ps1", "setup_offline.bat",
    "install_offline.ps1", "install_offline.bat",
    "build_offline_bundle.ps1", "build_offline_bundle.bat",
    "self_test.ps1", "self_test.bat", "enable_long_paths.ps1", "run_cli.bat", "run_api.bat",
    "README.md", "LICENSE", "CHANGELOG.md", "LIMITATIONS.md", "IMPLEMENTATION_REPORT.md", "SELF_TEST_RESULTS.txt",
    "pyproject.toml", ".python-version", ".gitignore",
    "Dockerfile.offline", "docker-compose.offline.yml"
) | ForEach-Object { Join-Path $Root $_ }

$Wheels = Get-ChildItem (Join-Path $Root "offline_cache\wheels") -Filter *.whl -ErrorAction SilentlyContinue
if (-not $Wheels) { Write-Warning "offline_cache\wheels is empty: the archive will not install without internet" }

Get-ChildItem $Root -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Compress-Archive -Path $Items -DestinationPath $Bundle -Force
Write-Host "Bundle: $Bundle"
Write-Host ("Size: {0:N1} MB" -f ((Get-Item $Bundle).Length / 1MB))
