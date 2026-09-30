#Requires -RunAsAdministrator
# Optional: enables paths longer than 260 characters system-wide. chem-agent works without it
# (it writes files with the \\?\ prefix), but other programs may fail to open such paths.
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
    -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force | Out-Null
Write-Host "Long paths enabled. A reboot is required."
