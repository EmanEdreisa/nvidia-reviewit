@echo off
setlocal
cd /d "%~dp0"
title Video Lecture Transcriber Debug

if not exist ".venv\Scripts\python.exe" (
    echo Double-click setup.bat first.
    pause
    exit /b 1
)

call ".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
