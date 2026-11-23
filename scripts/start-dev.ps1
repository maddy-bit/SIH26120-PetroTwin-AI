$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $repoRoot '.dev-pids.json'
$backendOut = Join-Path $repoRoot 'data\backend-dev.out.log'
$backendErr = Join-Path $repoRoot 'data\backend-dev.err.log'
$frontendOut = Join-Path $repoRoot 'data\frontend-dev.out.log'
$frontendErr = Join-Path $repoRoot 'data\frontend-dev.err.log'

if (Test-Path $pidFile) {
  throw "A PETRO-TWIN dev PID file already exists at $pidFile. Run scripts/health-check.ps1, then scripts/stop-dev.ps1 if these are stale."
}

$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) { $pythonExe = 'python' }
$nodeExe = (Get-Command node -ErrorAction Stop).Source
$viteEntry = Join-Path $repoRoot 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path (Join-Path $repoRoot 'frontend\node_modules'))) {
  throw 'Frontend dependencies are missing. Run npm ci from the frontend directory first.'
}

$backend = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','ml_service.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
$frontendArgs = '"{0}" --host 127.0.0.1 --port 5173' -f $viteEntry
$frontend = Start-Process -FilePath $nodeExe -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $repoRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr
Start-Sleep -Milliseconds 500
$backend = Get-Process -Id $backend.Id -ErrorAction SilentlyContinue
$frontend = Get-Process -Id $frontend.Id -ErrorAction SilentlyContinue
if (-not $backend -or -not $frontend) {
  if ($backend) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
  if ($frontend) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
  throw "A service exited during startup. Inspect $backendOut, $backendErr, $frontendOut, and $frontendErr."
}
@{ backend = @{ id = $backend.Id; path = $backend.Path; started = $backend.StartTime.ToUniversalTime().ToString('o') }; frontend = @{ id = $frontend.Id; path = $frontend.Path; started = $frontend.StartTime.ToUniversalTime().ToString('o') } } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $pidFile
Write-Host "Started FastAPI (PID $($backend.Id)) and Vite (PID $($frontend.Id))."
Write-Host 'Dashboard: http://localhost:5173  API docs: http://localhost:8000/docs'
Write-Host 'Run scripts/health-check.ps1 to check readiness; scripts/stop-dev.ps1 to stop these processes.'
