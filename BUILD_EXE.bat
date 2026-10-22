@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Run INSTALL.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.9,<7"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name "MAFIA VOICE CONTROL V3.1" --icon "assets\mafia_voice.ico" --add-data "assets;assets" --collect-all faster_whisper --collect-all ctranslate2 --collect-data av --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 launch.py
if errorlevel 1 goto failed
echo.
echo Build complete: dist\MAFIA VOICE CONTROL V3.1\MAFIA VOICE CONTROL V3.1.exe
echo This needs testing on Windows 11 before distribution.
pause
exit /b 0
:failed
echo.
echo [ERROR] Build failed, read above.
pause
exit /b 1
