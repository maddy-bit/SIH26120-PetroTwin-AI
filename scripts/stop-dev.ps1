$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $repoRoot '.dev-pids.json'
if (-not (Test-Path $pidFile)) { Write-Host 'No PETRO-TWIN dev PID file found; nothing to stop.'; exit 0 }

$record = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json
foreach ($entry in @($record.backend, $record.frontend)) {
  if (-not $entry.id) { continue }
  $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
  if (-not $process) { continue }
  $recordedStart = [DateTime]$entry.started
  $startDifference = [Math]::Abs(($process.StartTime.ToUniversalTime() - $recordedStart.ToUniversalTime()).TotalSeconds)
  $matchesRecorded = ($process.Path -ieq $entry.path) -and ($startDifference -lt 5)
  if ($matchesRecorded) {
    Stop-Process -Id $entry.id -Force -ErrorAction SilentlyContinue
  } else {
    Write-Warning "PID $($entry.id) no longer identifies the recorded PETRO-TWIN process; left it running."
  }
}
Remove-Item -LiteralPath $pidFile -Force
Write-Host 'Stopped recorded PETRO-TWIN development processes.'
