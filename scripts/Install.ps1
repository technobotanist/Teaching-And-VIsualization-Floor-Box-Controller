[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VirtualEnvironment = Join-Path $ProjectRoot ".venv"
$Python = Join-Path $VirtualEnvironment "Scripts\python.exe"

Set-Location $ProjectRoot

if (-not (Test-Path $Python)) {
    $SystemPython = (Get-Command python -ErrorAction Stop).Source
    & $SystemPython -m venv $VirtualEnvironment
}

& $Python -m pip install -e ".[dev]"
Write-Host "T&V Display Controller installed at $ProjectRoot"
