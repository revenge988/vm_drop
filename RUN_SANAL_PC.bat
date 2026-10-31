@echo off
chcp 65001 >nul
cd /d "%~dp0"
title VM Drop Agent - Sanal PC
echo.
echo Sanal agent basliyor...
echo Bu pencere/program SANALDA acik kalsin.
echo Sanal adini PC-1 / PC-2 / PC-3 yap (VMware sekme adiyla ayni).
echo.
python guest_agent.py
if errorlevel 1 pause
