@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo [ERROR] Please run INSTALL.bat first.
  pause
  exit /b 1
)
start "MAFIA VOICE V3.1" ".venv\Scripts\pythonw.exe" launch.py
exit /b 0
