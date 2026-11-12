# Hevanti - reading the text on the slides: Tesseract OCR (free, offline) with Hebrew and English.
# (c) 2026 Hevanti. MIT License, see LICENSE.txt
# The language files go to %LOCALAPPDATA%\Hevanti\tessdata (no admin needed). Tesseract itself comes from
# github.com/tesseract-ocr/tesseract (its installer asks Windows for permission once).
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
# Every download is checked against its SHA-256 (pinned 12.11.2026): the Tesseract installer runs with administrator rights,
# so a file that is not exactly this one is never run (audit #25). The language files come from a fixed version (4.1.0).
$sha = @{ 'heb' = '11F9E43AB227F786352A50F75C94C2E9906F1BABA86D93276DA19DA7CE0904DB'; 'eng' = '7D4322BD2A7749724879683FC3912CB542F19906C83BCC1A52132556427170B2'; 'setup' = 'BEE9E3434BD94FD65387D9BE28CD467A41F61B1275383B55B0F59A1331270AE4' }
function Assert-Sha($path, $want) {
  if ((Get-FileHash $path -Algorithm SHA256).Hash -ne $want) { Remove-Item $path -ErrorAction SilentlyContinue; throw "The file $path is not the expected one (SHA-256). Nothing was installed." }
}
$td = Join-Path $env:LOCALAPPDATA 'Hevanti\tessdata'
New-Item -ItemType Directory -Force -Path $td | Out-Null
foreach ($l in 'heb', 'eng') {
  Write-Host "Downloading the language file: $l"
  $out = Join-Path $td "$l.traineddata"
  Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/$l.traineddata" -OutFile $out
  Assert-Sha $out $sha[$l]
}
$found = @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe", "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe",
           "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe") | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if ($found) {
  Write-Host "Tesseract is already installed: $found"
} else {
  $url = 'https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe'
  $setup = Join-Path $env:TEMP 'tesseract-ocr-setup.exe'
  Write-Host "Downloading Tesseract: $url"
  Invoke-WebRequest -UseBasicParsing $url -OutFile $setup
  Assert-Sha $setup $sha['setup']
  Write-Host 'Installing Tesseract - Windows will ask for permission...'
  Start-Process -FilePath $setup -ArgumentList '/S' -Verb RunAs -Wait
  Remove-Item $setup -ErrorAction SilentlyContinue
}
Write-Host ''
Write-Host 'Reading slides: installed OK. Open Hevanti again (close it first if it is open).'
