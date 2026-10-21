[CmdletBinding()]
param(
    [switch]$Simulate,
    [switch]$NoBrowser,
    [switch]$AutoInstall,
    [switch]$SetupOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RoomConfig = Join-Path $ProjectRoot "config\room.json"
$Manifest = Join-Path $ProjectRoot "pyproject.toml"
$SetupMarker = Join-Path $ProjectRoot ".venv\.tv-controller-setup.json"
$InstallScript = Join-Path $PSScriptRoot "Install.ps1"

function Get-SetupProblem {
    if (-not (Test-Path $Python)) {
        return "The controller environment has not been installed."
    }
    if (-not (Test-Path $SetupMarker)) {
        return "The controller setup has not been verified on this machine."
    }

    try {
        $Marker = Get-Content $SetupMarker -Raw | ConvertFrom-Json
        $ManifestHash = (Get-FileHash $Manifest -Algorithm SHA256).Hash
        if ($Marker.manifest_sha256 -ne $ManifestHash) {
            return "The required libraries changed since the last installation."
        }

        & $Python -c "import fastapi, obsws_python, uvicorn, tv_display_controller" 2>$null
        if ($LASTEXITCODE -ne 0) {
            return "One or more required libraries are missing."
        }
    }
    catch {
        return "The controller installation could not be validated."
    }
    return $null
}

$SetupProblem = Get-SetupProblem
if ($SetupProblem) {
    Write-Host "First-time setup required" -ForegroundColor Yellow
    Write-Host $SetupProblem
    if (-not $AutoInstall) {
        $Response = Read-Host "Install the required components now? [Y/n]"
        if ($Response -and $Response.Trim().ToLowerInvariant() -notin @("y", "yes")) {
            throw "Controller setup was declined. Run this launcher again when ready."
        }
    }

    & $InstallScript -AutoInstallPython
    if ($LASTEXITCODE -ne 0) {
        throw "Controller setup did not complete successfully."
    }

    $SetupProblem = Get-SetupProblem
    if ($SetupProblem) {
        throw "Controller setup is still incomplete: $SetupProblem"
    }
}

if ($SetupOnly) {
    Write-Host "Controller setup is ready." -ForegroundColor Green
    return
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$MainShortcut = Join-Path $Desktop "T&V HDMI Floor Box Controller.lnk"
$SimulationShortcut = Join-Path $Desktop "T&V Controller - Simulation.lnk"
$ShortcutShell = New-Object -ComObject WScript.Shell
$LauncherPath = Join-Path $ProjectRoot "Start-Controller.cmd"
$NeedsShortcuts = $false
foreach ($ShortcutPath in @($MainShortcut, $SimulationShortcut)) {
    if (-not (Test-Path $ShortcutPath)) {
        $NeedsShortcuts = $true
        break
    }
    $Shortcut = $ShortcutShell.CreateShortcut($ShortcutPath)
    if ($Shortcut.Arguments.IndexOf($LauncherPath, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        $NeedsShortcuts = $true
        break
    }
}
if ($NeedsShortcuts) {
    & (Join-Path $PSScriptRoot "Install-DesktopShortcuts.ps1")
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
