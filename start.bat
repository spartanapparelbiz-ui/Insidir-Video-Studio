@echo off
rem One click: sets up on first run, reuses a studio that is already open, otherwise starts it.
cd /d "%~dp0"
title Insidir Video Studio

rem Already running? Just bring it up in the browser.
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:7860/'; if ($r.Content -match 'Insidir') { exit 0 } } catch { }; exit 1" >nul 2>&1
if not errorlevel 1 (
  start "" "http://127.0.0.1:7860/"
  exit /b 0
)

rem First run: install everything, then carry straight on.
if not exist ".venv\Scripts\python.exe" (
  echo First run: setting up Insidir Video Studio. This takes 5-15 minutes and only happens once.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\install.ps1"
  if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Setup did not finish. Read the message above, then double-click start.bat again.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -m insidir_studio serve
pause
