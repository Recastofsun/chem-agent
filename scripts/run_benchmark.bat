@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set CHEM_AGENT_OFFLINE=1
set PYTHONPATH=%CD%

echo [1/2] Пересборка JSON...
".venv\Scripts\python.exe" scripts\build_holdout.py

echo.
echo [2/2] Прогон benchmark...
".venv\Scripts\python.exe" -m chem_agent benchmark --reference tests\fixtures\holdout_100.json -v

pause