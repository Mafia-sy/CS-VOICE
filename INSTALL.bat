@echo off
setlocal
cd /d "%~dp0"
echo.
echo  =================================================
echo    MAFIA VOICE CONTROL V3.1 - THE BOSS EDITION
 echo               CREATED BY MAFIA
echo  =================================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher not found. Install Python 3.12 first.
  echo If you have Python Manager, run: py install 3.12
  pause
  exit /b 1
)
py -3.12 --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.12 not found. Run in PowerShell: py install 3.12
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo [OK] V3 installed. Use START.bat to launch.
pause
exit /b 0
:failed
echo.
echo [ERROR] Installation failed. See details above.
pause
exit /b 1
