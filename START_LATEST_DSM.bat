@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_latest_windows.ps1"
if errorlevel 1 (
  echo.
  echo Launch failed.
  pause
)
endlocal
