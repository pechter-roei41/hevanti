# Hevanti - reading the text on the slides: Tesseract OCR (free, offline) with Hebrew and English.
# (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
# The language files go to %LOCALAPPDATA%\Hevanti\tessdata (no admin needed). Tesseract itself comes from
# github.com/tesseract-ocr/tesseract (its installer asks Windows for permission once).
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$td = Join-Path $env:LOCALAPPDATA 'Hevanti\tessdata'
New-Item -ItemType Directory -Force -Path $td | Out-Null
foreach ($l in 'heb', 'eng') {
  Write-Host "Downloading the language file: $l"
  Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$l.traineddata" -OutFile (Join-Path $td "$l.traineddata")
}
$found = @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe", "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe",
           "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe") | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if ($found) {
  Write-Host "Tesseract is already installed: $found"
} else {
  $url = 'https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe'
  try {
    $rel = Invoke-RestMethod -UseBasicParsing 'https://api.github.com/repos/tesseract-ocr/tesseract/releases/latest'
    $a = $rel.assets | Where-Object { $_.name -like 'tesseract-ocr-w64-setup-*.exe' } | Select-Object -First 1
    if ($a) { $url = $a.browser_download_url }
  } catch { }
  $setup = Join-Path $env:TEMP 'tesseract-ocr-setup.exe'
  Write-Host "Downloading Tesseract: $url"
  Invoke-WebRequest -UseBasicParsing $url -OutFile $setup
  Write-Host 'Installing Tesseract - Windows will ask for permission...'
  Start-Process -FilePath $setup -ArgumentList '/S' -Verb RunAs -Wait
  Remove-Item $setup -ErrorAction SilentlyContinue
}
Write-Host ''
Write-Host 'Reading slides: installed OK. Open Hevanti again (close it first if it is open).'
