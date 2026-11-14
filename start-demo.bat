@echo off
REM Double-click to start Flint local demo (calls start-demo.ps1 in this folder)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-demo.ps1"
echo.
echo (Press any key to close this window. Backend/frontend keep running in their own windows.)
pause >nul
