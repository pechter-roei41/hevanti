# Hevanti - its own Python (the official "embeddable" Python for Windows, from python.org), when the ZIP came without it.
# (c) 2026 Roei Pechter. MIT License, see LICENSE.txt
# Usage: get_python.ps1 <folder>   (Install runs it: System\python)
param([string]$Dest)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ver = '3.12.10'
$zip = Join-Path $env:TEMP "python-$ver-embed-amd64.zip"
Invoke-WebRequest -UseBasicParsing "https://www.python.org/ftp/python/$ver/python-$ver-embed-amd64.zip" -OutFile $zip
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Expand-Archive -Path $zip -DestinationPath $Dest -Force
Remove-Item $zip -ErrorAction SilentlyContinue
# let it use installed packages (site-packages), which the embeddable Python turns off
$pth = Get-ChildItem $Dest -Filter 'python*._pth' | Select-Object -First 1
(Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName -Encoding ascii
Invoke-WebRequest -UseBasicParsing 'https://bootstrap.pypa.io/get-pip.py' -OutFile (Join-Path $Dest 'get-pip.py')
Write-Host "Python $ver is ready in $Dest"
