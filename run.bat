@echo off
setlocal
cd /d "%~dp0"
title Video Lecture Transcriber

if not exist ".venv\Scripts\pythonw.exe" (
    echo The application is not installed yet.
    echo Double-click setup.bat first.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" app.py
exit /b 0
