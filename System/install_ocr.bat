@echo off
rem Hevanti - reading the text on the slides (Tesseract OCR, Hebrew + English) - (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
chcp 65001 >nul
cd /d "%~dp0"
echo Installing the free OCR (Tesseract, Hebrew + English), so Hevanti can read the text on the slides.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_ocr.ps1"
if errorlevel 1 ( echo. & echo OCR INSTALL FAILED - Hevanti still works, only without reading the slides. Send a screenshot of this window. & (if /i not "%~1"=="nopause" pause) & exit /b 1 )
if /i not "%~1"=="nopause" pause
