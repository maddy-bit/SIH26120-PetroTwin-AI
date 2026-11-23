$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) { $pythonExe = 'python' }

Push-Location $repoRoot
try {
  & $pythonExe scripts/test_all.py
  if ($LASTEXITCODE -ne 0) { throw 'Test suite failed; services were not started.' }
  & (Join-Path $PSScriptRoot 'start-dev.ps1')
  Start-Sleep -Seconds 3
  & (Join-Path $PSScriptRoot 'health-check.ps1')
} finally {
  Pop-Location
}
