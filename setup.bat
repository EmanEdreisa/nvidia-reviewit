@echo off
setlocal
cd /d "%~dp0"
title Video Lecture Transcriber Setup

echo Creating the Python environment...
where py >nul 2>nul
if errorlevel 1 goto :try_python
py -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul
if not errorlevel 1 goto :use_launcher

:try_python
where python >nul 2>nul
if errorlevel 1 goto :no_python
python -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul
if errorlevel 1 goto :no_python
python -m venv .venv
goto :venv_created

:use_launcher
py -m venv .venv

:venv_created
if errorlevel 1 goto :failed

call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed

echo Installing application packages. This may take several minutes...
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Setup complete. Double-click run.bat to start the application.
pause
exit /b 0

:no_python
echo.
echo No compatible Python was found. Install 64-bit Python 3.10 through 3.13.
pause
exit /b 1

:failed
echo.
echo Setup failed. Confirm that Python 3.10 through 3.13 is installed and internet access is available.
pause
exit /b 1
