@echo off
chcp 65001 >nul
cd /d "%~dp0"
title VM Drop Host - Ana PC
python -m pip install windnd -q
echo.
echo Ana PC host basliyor...
echo VMware penceresinin ustundeki mavi seride dosya birak.
echo.
python host_drop.py
if errorlevel 1 pause
