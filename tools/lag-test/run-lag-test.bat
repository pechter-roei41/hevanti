@echo off
rem Two live runs of one lecture (old and new pieces) and a lag line for every minute. See README-lag-test.txt (Hebrew).
chcp 65001 >nul
set PYTHONUTF8=1
set PY=%LOCALAPPDATA%\Programs\Hevanti\python\python.exe
if not exist "%PY%" (
  echo Hevanti is not installed here: %PY% was not found.
  pause
  exit /b 1
)
"%PY%" "%~dp0lag_run.py" %1 %2
echo.
pause
