@echo off
chcp 65001 >nul
cd /d "%~dp0"
title VM Drop - Otomatik Baslat

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%STARTUP%\VM_Drop_Agent.bat"

(
  echo @echo off
  echo cd /d "%~dp0"
  echo start "" pythonw "%~dp0guest_agent.py"
) > "%TARGET%"

echo Agent baslangica eklendi:
echo %TARGET%
echo.
echo Not: pythonw yoksa RUN_SANAL_PC.bat ile elle ac.
pause
