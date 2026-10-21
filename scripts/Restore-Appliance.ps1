[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory)]
    [string]$BackupPath,

    [string]$ObsConfigPath
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackupPath = (Resolve-Path $BackupPath).Path
$BackupObs = Join-Path $BackupPath "obs-studio"
$BackupController = Join-Path $BackupPath "controller"
$ManifestPath = Join-Path $BackupPath "manifest.json"

if (-not (Test-Path $BackupObs) -or -not (Test-Path $ManifestPath)) {
    throw "Backup is incomplete: expected obs-studio and manifest.json."
}

$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
foreach ($Entry in $Manifest) {
    $FilePath = Join-Path $BackupPath $Entry.path
    if (-not (Test-Path $FilePath)) {
        throw "Backup validation failed: missing $($Entry.path)"
    }
    $ActualHash = (Get-FileHash $FilePath -Algorithm SHA256).Hash
    if ($ActualHash -ne $Entry.sha256) {
        throw "Backup validation failed: checksum mismatch for $($Entry.path)"
    }
}

if (Get-Process obs64 -ErrorAction SilentlyContinue) {
    throw "Close OBS Studio before restoring the appliance."
}

if (-not $ObsConfigPath) {
    $PortableConfig = Join-Path $ProjectRoot "obs-portable\config\obs-studio"
    $ObsConfigPath = if (Test-Path (Split-Path $PortableConfig -Parent)) {
        $PortableConfig
    } else {
        Join-Path $env:APPDATA "obs-studio"
    }
}

if (-not $PSCmdlet.ShouldProcess($ObsConfigPath, "Restore T&V OBS appliance backup")) {
    return
}

$RollbackPath = "$ObsConfigPath.pre-restore-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
if (Test-Path $ObsConfigPath) {
    Move-Item $ObsConfigPath $RollbackPath
}

try {
    Copy-Item $BackupObs $ObsConfigPath -Recurse

    $BackupConfig = Join-Path $BackupController "config"
    if (Test-Path $BackupConfig) {
        Copy-Item (Join-Path $BackupConfig "*") (Join-Path $ProjectRoot "config") -Recurse -Force
    }

    $BackupAssets = Join-Path $BackupController "assets"
    if (Test-Path $BackupAssets) {
        Copy-Item $BackupAssets $ProjectRoot -Recurse -Force
    }
} catch {
    if (Test-Path $ObsConfigPath) {
        Remove-Item $ObsConfigPath -Recurse -Force
    }
    if (Test-Path $RollbackPath) {
        Move-Item $RollbackPath $ObsConfigPath
    }
    throw
}

Write-Host "Appliance restored from $BackupPath"
if (Test-Path $RollbackPath) {
    Write-Host "Pre-restore OBS configuration retained at $RollbackPath"
}
