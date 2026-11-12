# Hevanti - its own Python (the official "embeddable" Python for Windows, from python.org), when the ZIP came without it.
# (c) 2026 Hevanti. MIT License, see LICENSE.txt
# Usage: get_python.ps1 <folder>   (Install runs it: System\python)
param([string]$Dest)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ver = '3.12.10'
# Every download is checked against its SHA-256 (pinned 12.11.2026): a file that was replaced on the way or at the source is refused (audit #25).
$embedSha = '4ACBED6DD1C744B0376E3B1CF57CE906F9DC9E95E68824584C8099A63025A3C3'
$getPipUrl = 'https://raw.githubusercontent.com/pypa/get-pip/26.3/public/get-pip.py'
$getPipSha = 'F7654C5589318E1D0789575B2586CE76937EB9943602ADDA8B15B3BE3AA0DAC3'
function Assert-Sha($path, $sha) {
  if ((Get-FileHash $path -Algorithm SHA256).Hash -ne $sha) { Remove-Item $path -ErrorAction SilentlyContinue; throw "The file $path is not the expected one (SHA-256). Try again later." }
}
# The zip goes next to the target folder, not to %TEMP%: with a Hebrew user name %TEMP% is a short 8.3 name (C:\Users\131B~1)
# that Remove-Item and some other commands reject.
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$zip = Join-Path $Dest "python-$ver-embed-amd64.zip"
Invoke-WebRequest -UseBasicParsing "https://www.python.org/ftp/python/$ver/python-$ver-embed-amd64.zip" -OutFile $zip
Assert-Sha $zip $embedSha
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Expand-Archive -Path $zip -DestinationPath $Dest -Force
try { [IO.File]::Delete($zip) } catch { }
# let it use installed packages (site-packages), which the embeddable Python turns off
$pth = Get-ChildItem $Dest -Filter 'python*._pth' | Select-Object -First 1
(Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName -Encoding ascii
$gp = Join-Path $Dest 'get-pip.py'
Invoke-WebRequest -UseBasicParsing $getPipUrl -OutFile $gp
Assert-Sha $gp $getPipSha
Write-Host "Python $ver is ready in $Dest"
