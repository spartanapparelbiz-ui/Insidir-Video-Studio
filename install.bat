@echo off
rem One-time setup: Python packages, FFmpeg and the Kokoro voice model.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\install.ps1"
pause
