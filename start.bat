@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install.bat first.
  pause
  exit /b 1
)
title Insidir Video Studio
".venv\Scripts\python.exe" -m insidir_studio serve
pause
