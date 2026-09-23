param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Query,
    [ValidateSet("both", "ocr", "asr")]
    [string]$Mode = "both",
    [int]$Limit = 10,
    [ValidateRange(1,2)]
    [int]$MaxEdits = 1,
    [ValidateRange(0,20)]
    [int]$PrefixLength = 1
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONPATH = $PSScriptRoot

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw ".venv is missing. Run .\setup_first_time.ps1 first."
}

& $VenvPython search_metadata.py $Query --mode $Mode --limit $Limit --max-edits $MaxEdits --prefix-length $PrefixLength
if ($LASTEXITCODE -ne 0) { throw "Search failed." }
