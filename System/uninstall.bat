@echo off
rem Hevanti - UNINSTALL - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "PY="
rem installed with Hevanti-Setup: its own Python
if exist "%~dp0..\python\python.exe" set "PY="%~dp0..\python\python.exe""
for %%V in (3.12 3.13 3.14 3.11 3.10) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo Python not found. To finish removing: delete the folder C:\Users\Public\whisper_models and this folder.
  pause
  exit /b 1
)
echo Using: %PY%
set "SCRIPT=Program\live_transcribe.py"
%PY% "%SCRIPT%" --uninstall
pause
