@echo off
chcp 65001 >nul
cd /d "%~dp0"
title VM Drop EXE Build

python -m pip install --upgrade pip pyinstaller windnd
if errorlevel 1 goto hata

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist VM_Drop.spec del /q VM_Drop.spec

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "VM_Drop" ^
  --hidden-import windnd ^
  --hidden-import host_drop ^
  --hidden-import guest_agent ^
  "vm_drop_app.py"
if errorlevel 1 goto hata

echo.
echo BASARILI: dist\VM_Drop.exe
explorer "%~dp0dist"
exit /b 0

:hata
echo HATA
pause
exit /b 1
