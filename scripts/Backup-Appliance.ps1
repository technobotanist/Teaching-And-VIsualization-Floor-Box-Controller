[CmdletBinding()]
param(
    [string]$Name = (Get-Date -Format "production-yyyyMMdd-HHmmss"),
    [string]$DestinationRoot,
    [string]$ObsConfigPath
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $DestinationRoot) {
    $DestinationRoot = Join-Path $ProjectRoot "backups"
}

if (-not $ObsConfigPath) {
    $PortableConfig = Join-Path $ProjectRoot "obs-portable\config\obs-studio"
    $ObsConfigPath = if (Test-Path $PortableConfig) {
        $PortableConfig
    } else {
        Join-Path $env:APPDATA "obs-studio"
    }
}

if (-not (Test-Path $ObsConfigPath)) {
    throw "OBS configuration not found at $ObsConfigPath"
}

$Destination = Join-Path $DestinationRoot $Name
if (Test-Path $Destination) {
    throw "Backup already exists at $Destination"
}

$ControllerBackup = Join-Path $Destination "controller"
New-Item -ItemType Directory -Path $ControllerBackup -Force | Out-Null
Copy-Item (Join-Path $ProjectRoot "config") $ControllerBackup -Recurse

$AssetsPath = Join-Path $ProjectRoot "assets"
if (Test-Path $AssetsPath) {
    Copy-Item $AssetsPath $ControllerBackup -Recurse
}

Copy-Item $ObsConfigPath (Join-Path $Destination "obs-studio") -Recurse

$Metadata = [ordered]@{
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    computer = $env:COMPUTERNAME
    obs_config_source = $ObsConfigPath
    controller_version = "0.2.1"
}
$Metadata | ConvertTo-Json | Set-Content (Join-Path $Destination "metadata.json") -Encoding UTF8

$Manifest = Get-ChildItem $Destination -File -Recurse |
    Where-Object Name -ne "manifest.json" |
    ForEach-Object {
        [ordered]@{
            path = $_.FullName.Substring($Destination.Length + 1)
            sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
        }
    }
$Manifest | ConvertTo-Json -Depth 3 | Set-Content (Join-Path $Destination "manifest.json") -Encoding UTF8

Write-Host "Known-good appliance backup created at $Destination"
