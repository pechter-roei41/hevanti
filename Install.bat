@echo off
rem Hevanti - first-time setup - (c) 2026 Roei Pechter. MIT License, see System\LICENSE.txt
chcp 65001 >nul
cd /d "%~dp0"
rem Remove the Windows "downloaded from the internet" mark from the tool files, so only install shows the warning
powershell -NoProfile -Command "Get-ChildItem -Path '.\*','.\System\*','.\System\Program\*' -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1
set "PY="
for %%V in (3.12 3.13 3.14 3.11 3.10) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo Python not found. Install Python 3.14 from https://www.python.org/downloads/windows/ ^(check "Add python.exe to PATH"^) and run again.
  pause
  exit /b 1
)
echo Using: %PY%
%PY% -m pip install --upgrade pip
%PY% -m pip install faster-whisper pyaudiowpatch numpy mss pillow comtypes
if errorlevel 1 ( echo. & echo INSTALL FAILED - send a screenshot of this window to Hevanti support & pause & exit /b 1 )
echo.
echo Installed OK. Close this window and open Hevanti.
pause
