$ErrorActionPreference = 'Continue'
$checks = @(
  @{ Name = 'FastAPI'; Url = 'http://127.0.0.1:8000/health' },
  @{ Name = 'Vite'; Url = 'http://127.0.0.1:5173/' }
)
$failed = $false
foreach ($check in $checks) {
  try {
    $response = Invoke-WebRequest -Uri $check.Url -TimeoutSec 5
    Write-Host "$($check.Name): HTTP $([int]$response.StatusCode)"
    if ($check.Name -eq 'FastAPI') { $response.Content }
  } catch {
    Write-Error "$($check.Name): unavailable ($($_.Exception.Message))"
    $failed = $true
  }
}
if ($failed) { exit 1 }
