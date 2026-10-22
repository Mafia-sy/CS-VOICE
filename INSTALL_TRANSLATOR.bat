@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Please run INSTALL.bat first.
  pause
  exit /b 1
)
echo Installing OPTIONAL offline Arabic-English general sentence translator...
".venv\Scripts\python.exe" -m pip install "argostranslate>=1.9,<2"
if errorlevel 1 goto error
".venv\Scripts\python.exe" install_offline_translator.py
if errorlevel 1 goto error
echo SUCCESS. Translation runs locally after the one-time model download.
pause
exit /b 0
:error
echo [ERROR] Failed installing translator. CS2 glossary works without it.
pause
exit /b 1
