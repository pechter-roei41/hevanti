@echo off
rem Hevanti - lectures, transcribed live or from a recording - (c) 2026 Roei Pechter. MIT License, see System\LICENSE.txt
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "PY="
rem Hevanti's own Python (System\python), or one that is installed
if exist "%~dp0System\python\python.exe" set "PY="%~dp0System\python\python.exe""
for %%V in (3.12 3.13 3.14 3.11 3.10) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo Hevanti is not installed yet: double-click Install first, then this file again.
  pause
  exit /b 1
)
set "SCRIPT=System\Program\live_transcribe.py"
rem Opens the app in the browser - everything is done there.
rem It runs in its own small window, minimized: while that window is on the taskbar the tool is running,
rem and closing it stops the tool. A recording dragged onto this file opens in the page.
start "Hevanti" /min %PY% "%SCRIPT%" --app %*
