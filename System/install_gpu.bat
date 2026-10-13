@echo off
rem Hevanti - NVIDIA GPU libraries - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
chcp 65001 >nul
cd /d "%~dp0"
echo Installing NVIDIA GPU libraries (about 1GB). Only useful with an NVIDIA graphics card.
set "PY="
rem installed with Hevanti-Setup: its own Python
if exist "%~dp0..\python\python.exe" set "PY="%~dp0..\python\python.exe""
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
%PY% -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
if errorlevel 1 ( echo. & echo GPU INSTALL FAILED - the tool still works on the CPU. Send a screenshot of this window. & pause & exit /b 1 )
echo.
echo GPU libraries installed. Open Hevanti in the main folder.
pause
