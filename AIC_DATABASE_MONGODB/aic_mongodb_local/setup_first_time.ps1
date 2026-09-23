$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = $ProjectRoot

function Require-Command {
    param(
        [string]$Name,
        [string]$Message
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw $Message
    }
}

function Assert-LastExitCode {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

function Wait-ContainerHealthy {
    param(
        [string]$ContainerName = "aic2026-mongodb",
        [int]$TimeoutSeconds = 300
    )

    Write-Host "Waiting for MongoDB container health..." -ForegroundColor Cyan

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastStatus = ""

    while ((Get-Date) -lt $deadline) {
        $status = docker inspect --format='{{.State.Health.Status}}' $ContainerName 2>$null

        if ($LASTEXITCODE -eq 0) {
            $status = "$status".Trim()

            if ($status -ne $lastStatus) {
                Write-Host "MongoDB container health: $status"
                $lastStatus = $status
            }

            if ($status -eq "healthy") {
                Write-Host "MongoDB container is HEALTHY." -ForegroundColor Green
                return
            }

            if ($status -eq "unhealthy") {
                Write-Host "MongoDB became unhealthy. Last container logs:" -ForegroundColor Red
                docker logs --tail 150 $ContainerName
                throw "MongoDB container is unhealthy."
            }
        }

        Start-Sleep -Seconds 2
    }

    Write-Host "MongoDB did not become healthy. Last container logs:" -ForegroundColor Red
    docker logs --tail 150 $ContainerName
    throw "MongoDB container did not become healthy within $TimeoutSeconds seconds."
}

Write-Host "=== AIC 2026 MongoDB local - Windows setup (named volumes) ===" -ForegroundColor Cyan

# ============================================================
# 1. Prerequisites
# ============================================================
Write-Host "`n[1/9] Checking prerequisites..." -ForegroundColor Cyan
Require-Command docker "Docker was not found. Install Docker Desktop first."

Set-ExecutionPolicy -Scope Process Bypass
Write-Host "Docker engine is running." -ForegroundColor Green

$PythonCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = @("py", "-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = @("python")
} else {
    throw "Python 3 was not found. Install Python 3 and add it to PATH."
}

# ============================================================
# 2. Environment
# ============================================================
Write-Host "`n[2/9] Preparing .env..." -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    if (-not (Test-Path ".env.example")) {
        throw ".env.example not found."
    }

    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example." -ForegroundColor Yellow
} else {
    Write-Host ".env already exists." -ForegroundColor Green
}

Write-Host "MongoDB persistent storage: Docker named volumes" -ForegroundColor Green
Write-Host "  aic2026_mongodb_data" -ForegroundColor DarkGray
Write-Host "  aic2026_mongodb_config" -ForegroundColor DarkGray
Write-Host "  aic2026_mongodb_mongot" -ForegroundColor DarkGray

# ============================================================
# 3. Start MongoDB Atlas Local
# ============================================================
Write-Host "`n[3/9] Pulling and starting MongoDB Atlas Local..." -ForegroundColor Cyan

docker compose pull
Assert-LastExitCode "docker compose pull"

docker compose up -d
Assert-LastExitCode "docker compose up -d"

# ============================================================
# 4. Wait for Docker HEALTHY
# ============================================================
Write-Host "`n[4/9] Waiting for container HEALTHY..." -ForegroundColor Cyan
Wait-ContainerHealthy -ContainerName "aic2026-mongodb" -TimeoutSeconds 300

# ============================================================
# 5. Prepare Python virtual environment
# ============================================================
Write-Host "`n[5/9] Preparing Python virtual environment..." -ForegroundColor Cyan

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$venvHealthy = $false

if (Test-Path $VenvPython) {
    & $VenvPython -m pip --version *> $null

    if ($LASTEXITCODE -eq 0) {
        $venvHealthy = $true
        Write-Host "Existing .venv is healthy; reusing it." -ForegroundColor Green
    } else {
        Write-Host "Existing .venv is broken; recreating it..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force ".venv"
    }
}

if (-not $venvHealthy) {
    Write-Host "Creating .venv..."

    if ($PythonCmd.Count -eq 2) {
        & $PythonCmd[0] $PythonCmd[1] -m venv .venv
    } else {
        & $PythonCmd[0] -m venv .venv
    }

    Assert-LastExitCode "Creating Python virtual environment"
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "Installing Python dependencies..."
# Do not upgrade pip here. Windows/antivirus can temporarily lock pip files.
& $VenvPython -m pip install -r requirements.txt
Assert-LastExitCode "Installing Python dependencies"

# ============================================================
# 6. Wait for stable writable MongoDB primary
# ============================================================
Write-Host "`n[6/9] Waiting for MongoDB writable stability..." -ForegroundColor Cyan

& $VenvPython scripts\00_wait_mongo.py
Assert-LastExitCode "MongoDB writable readiness check"

# ============================================================
# 7. Validate metadata ZIPs
# ============================================================
Write-Host "`n[7/9] Checking OCR/ASR input ZIPs..." -ForegroundColor Cyan

$OcrZip = "data\raw\metadata_ocr.zip"
$AsrZip = "data\raw\metadata_asr_clean.zip"

if (-not (Test-Path $OcrZip)) {
    throw "OCR metadata ZIP not found: $OcrZip"
}

if (-not (Test-Path $AsrZip)) {
    throw "ASR metadata ZIP not found: $AsrZip"
}

Write-Host "OCR ZIP: $OcrZip" -ForegroundColor Green
Write-Host "ASR ZIP: $AsrZip" -ForegroundColor Green

# ============================================================
# 8. Ingest metadata + create indexes
# ============================================================
Write-Host "`n[8/9] Ingesting OCR + ASR metadata..." -ForegroundColor Cyan

& $VenvPython scripts\01_ingest_metadata.py --ocr $OcrZip --asr $AsrZip
Assert-LastExitCode "Metadata ingestion"

Write-Host "`nCreating MongoDB indexes..." -ForegroundColor Cyan
& $VenvPython scripts\02_create_indexes.py
Assert-LastExitCode "Index creation"

# ============================================================
# 9. Wait Search indexes + verify stats
# ============================================================
Write-Host "`n[9/9] Waiting for MongoDB Search indexes..." -ForegroundColor Cyan

& $VenvPython scripts\03_wait_search_indexes.py
Assert-LastExitCode "Search index readiness"

Write-Host "`nDatabase statistics:" -ForegroundColor Cyan
& $VenvPython scripts\04_show_stats.py
Assert-LastExitCode "Database stats"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " SETUP COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "MongoDB persistent storage: Docker named volumes" -ForegroundColor Green
Write-Host "MongoDB endpoint: mongodb://localhost:27017" -ForegroundColor Green
Write-Host ""
Write-Host "Test fuzzy search:" -ForegroundColor Cyan
Write-Host '.\search.ps1 "Herbalife"' -ForegroundColor White
Write-Host ""
Write-Host "After restarting Windows, do NOT ingest again." -ForegroundColor Yellow
Write-Host "Run .\start_mongodb.ps1 and then .\search.ps1 <query>." -ForegroundColor Yellow
Write-Host "Do NOT run 'docker compose down -v' unless you intentionally want to delete the database." -ForegroundColor Red
