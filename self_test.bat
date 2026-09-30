@echo off
chcp 65001 >nul
where pwsh >nul 2>&1
if %errorlevel%==0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0self_test.ps1" %*
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0self_test.ps1" %*
)
pause
