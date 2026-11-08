# A clean-machine test of Hevanti-Setup.exe: install it silently into a new folder, start the program with its own
# Python, check that every package is inside and that the pages are served, then uninstall and check that the
# program is gone. Runs on a Windows machine that has never seen Hevanti (the GitHub runner).
#   pwsh tools/smoke_install.ps1 dist/Hevanti-Setup.exe
param([Parameter(Mandatory = $true)][string]$Setup)
$ErrorActionPreference = "Stop"
$Setup = (Resolve-Path $Setup).Path
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Join-Path ([IO.Path]::GetTempPath()) ("HevantiSmoke" + [guid]::NewGuid().ToString("N").Substring(0, 6))
$failed = @()
function Check($name, $ok, $detail = "") {
    if ($ok) { Write-Host "PASS $name" } else { Write-Host "FAIL ${name}: $detail"; $script:failed += $name; Write-Host "::error title=$name::$detail" }
}

# --- install
$p = Start-Process $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/LOG=$root.log", "/DIR=$root" -Wait -PassThru
Check "the installer finishes" ($p.ExitCode -eq 0) "exit code $($p.ExitCode)"
foreach ($f in "python\python.exe", "System\Program\live_transcribe.py", "System\Program\app.html", "System\Program\player.html",
               "System\Program\mini.html", "System\Program\ask.js", "System\Program\hevanti_mcp.py", "hevanti.ico", "unins000.exe") {
    Check "installed: $f" (Test-Path (Join-Path $root $f)) "missing"
}
$py = Join-Path $root "python\python.exe"

# --- the packages are inside (no Install step for the student)
$out = & $py -c "import faster_whisper, pyaudiowpatch, numpy, mss, PIL, comtypes, sherpa_onnx; print('packages OK')" 2>&1 | Out-String
Check "every package imports with the program's own Python" ($out -match "packages OK") $out
$out = & $py -m py_compile (Join-Path $root "System\Program\live_transcribe.py") (Join-Path $root "System\Program\hevanti_mcp.py") 2>&1 | Out-String
Check "the program compiles" ($LASTEXITCODE -eq 0) $out

# --- the program starts and serves its pages
$out = & $py (Join-Path $here "smoke_server.py") $root 2>&1 | Out-String
Write-Host $out
Check "the installed program starts and serves its pages" ($LASTEXITCODE -eq 0 -and $out -match "all passed") $out

# --- the update-check box of the installer was applied (no 'updates' task -> off): the setting is read back
$out = & $py (Join-Path $root "System\Program\live_transcribe.py") --set-update-check off 2>&1 | Out-String
Check "the program's own command line works" ($LASTEXITCODE -eq 0) $out

# --- uninstall
$u = Start-Process (Join-Path $root "unins000.exe") -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
Check "the uninstaller finishes" ($u.ExitCode -eq 0) "exit code $($u.ExitCode)"
$end = (Get-Date).AddSeconds(60)
while ((Test-Path (Join-Path $root "python")) -and (Get-Date) -lt $end) { Start-Sleep -Seconds 1 }   # (it finishes in a copy of itself)
Check "uninstalled: the program and its Python are gone" (-not (Test-Path (Join-Path $root "python")) -and -not (Test-Path (Join-Path $root "System"))) "still there"

Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue
if ($failed.Count) { Write-Host "`n$($failed.Count) failed: $($failed -join ', ')"; exit 1 }
Write-Host "`nall passed"
