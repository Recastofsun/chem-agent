bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
set CHEM_AGENT_OFFLINE=1
set PYTHONPATH=%~dp0

.venv\Scripts\python.exe run_server.py

pause