@echo off
rem Hevanti - first-time setup - (c) 2026 Roei Pechter. MIT License, see System\LICENSE.txt
rem Uses Hevanti's own Python (System\python - comes in the ZIP, or is downloaded here once). No Python to install.
chcp 65001 >nul
cd /d "%~dp0"
rem Remove the Windows "downloaded from the internet" mark from the tool's files (and its Python)
powershell -NoProfile -Command "Get-ChildItem -Path '.\*','.\System' -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1
set "PYDIR=%~dp0System\python"
set "PY="
if not exist "%PYDIR%\python.exe" (
  echo Getting Python for Hevanti ^(about 11MB, only once^)...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0System\get_python.ps1" "%PYDIR%"
)
if exist "%PYDIR%\python.exe" set "PY="%PYDIR%\python.exe""
rem no Hevanti Python (no internet to python.org?): a Python that is already installed
for %%V in (3.12 3.13 3.14 3.11 3.10) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo Could not get Python. Check the internet connection and run Install again.
  pause
  exit /b 1
)
echo Using: %PY%
%PY% -m pip --version >nul 2>&1
if errorlevel 1 if exist "%PYDIR%\get-pip.py" %PY% "%PYDIR%\get-pip.py" --no-warn-script-location
%PY% -m pip install --upgrade pip --no-warn-script-location
%PY% -m pip install "faster-whisper>=1.1" pyaudiowpatch numpy mss pillow comtypes --no-warn-script-location
if errorlevel 1 ( echo. & echo INSTALL FAILED - send a screenshot of this window to Hevanti support & pause & exit /b 1 )
echo.
echo Reading the text on the slides ^(optional, free^): Windows will ask for permission once.
call "%~dp0System\install_ocr.bat" nopause
echo.
echo Installed OK. Close this window and open Hevanti.
pause
