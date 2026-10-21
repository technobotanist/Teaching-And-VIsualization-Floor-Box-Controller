[CmdletBinding()]
param(
    [switch]$Simulate,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RoomConfig = Join-Path $ProjectRoot "config\room.json"

if (-not (Test-Path $Python)) {
    throw "Controller environment not found. Run scripts\Install.ps1 first."
}

$ControllerArguments = @(
    "-m",
    "tv_display_controller",
    "--config",
    $RoomConfig
)

if ($Simulate) {
    $ControllerArguments += "--simulate"
}

if (-not $NoBrowser) {
    $ControllerArguments += "--open-browser"
}

& $Python @ControllerArguments
