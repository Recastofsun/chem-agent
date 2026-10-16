@echo off
chcp 65001 >nul
cd /d "%~dp0"
set CHEM_AGENT_OFFLINE=1
set PYTHONPATH=%~dp0
echo chem-agent: рабочая папка %CD%
echo.
cmd /k