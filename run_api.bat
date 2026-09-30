@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "CHEM_AGENT_OFFLINE=1"
set "PYTHONPATH=%~dp0"
start "" "http://127.0.0.1:8000/"
".venv\Scripts\python.exe" -m uvicorn chem_agent.api.server:app --host 127.0.0.1 --port 8000
