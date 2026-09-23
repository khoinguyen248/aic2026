$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Stopping AIC MongoDB..." -ForegroundColor Cyan
docker compose stop
if ($LASTEXITCODE -ne 0) {
    throw "docker compose stop failed."
}
Write-Host "MongoDB stopped. Docker named volumes were NOT deleted." -ForegroundColor Green
Write-Host "Do not use 'docker compose down -v' unless you intentionally want to delete the database." -ForegroundColor Yellow
