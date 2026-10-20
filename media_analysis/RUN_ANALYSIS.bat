@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "AD_ANALYSIS_PYTHON=python"
if exist "..\.venv\Scripts\python.exe" set "AD_ANALYSIS_PYTHON=..\.venv\Scripts\python.exe"
"%AD_ANALYSIS_PYTHON%" run_analysis.py --open-report
echo.
pause
