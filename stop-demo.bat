@echo off
REM Double-click to stop Flint local demo (calls stop-demo.ps1 in this folder)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-demo.ps1"
echo.
pause >nul
