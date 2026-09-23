$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = $ProjectRoot

Write-Host "Checking Docker Desktop engine..." -ForegroundColor Cyan
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop engine is not running. Start Docker Desktop first."
}

Write-Host "Starting AIC MongoDB..." -ForegroundColor Cyan
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up -d failed."
}

$deadline = (Get-Date).AddSeconds(300)
$lastStatus = ""
while ((Get-Date) -lt $deadline) {
    $status = docker inspect --format='{{.State.Health.Status}}' aic2026-mongodb 2>$null

    if ($LASTEXITCODE -eq 0) {
        $status = "$status".Trim()
        if ($status -ne $lastStatus) {
            Write-Host "MongoDB container health: $status"
            $lastStatus = $status
        }
        if ($status -eq "healthy") {
            break
        }
        if ($status -eq "unhealthy") {
            docker logs --tail 150 aic2026-mongodb
            throw "MongoDB container became unhealthy."
        }
    }

    Start-Sleep -Seconds 2
}

$status = docker inspect --format='{{.State.Health.Status}}' aic2026-mongodb 2>$null
if ($LASTEXITCODE -ne 0 -or "$status".Trim() -ne "healthy") {
    docker logs --tail 150 aic2026-mongodb
    throw "MongoDB container did not become healthy."
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw ".venv is missing. Run .\setup_first_time.ps1 first."
}

& $VenvPython scripts\00_wait_mongo.py
if ($LASTEXITCODE -ne 0) {
    throw "MongoDB did not become a stable writable primary."
}

Write-Host "MongoDB is ready at mongodb://localhost:27017" -ForegroundColor Green
Write-Host "Persistent data is in Docker named volumes (aic2026_mongodb_*)." -ForegroundColor Green
