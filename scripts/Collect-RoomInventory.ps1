[CmdletBinding()]
param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $OutputPath) {
    $FileName = "room-inventory-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    $OutputPath = Join-Path $ProjectRoot $FileName
}

$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$OutputDirectory = Split-Path $OutputPath -Parent
if (-not (Test-Path $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
}

$OperatingSystem = Get-CimInstance Win32_OperatingSystem
$ComputerSystem = Get-CimInstance Win32_ComputerSystem

$GraphicsAdapters = @(
    Get-CimInstance Win32_VideoController |
        Select-Object Name, DriverVersion, AdapterRAM, VideoProcessor,
            CurrentHorizontalResolution, CurrentVerticalResolution, CurrentRefreshRate,
            Status, PNPDeviceID
)

$Monitors = @(
    Get-CimInstance Win32_PnPEntity |
        Where-Object PNPClass -eq "Monitor" |
        Select-Object Name, Manufacturer, Status, DeviceID
)

$MediaDevices = @(
    Get-CimInstance Win32_PnPEntity |
        Where-Object {
            $_.PNPClass -in @("Camera", "MEDIA") -or
            $_.Name -match "capture|video input"
        } |
        Select-Object PNPClass, Name, Manufacturer, Status, DeviceID
)

$ObsCandidates = @(
    (Join-Path $ProjectRoot "obs-portable\bin\64bit\obs64.exe"),
    (Join-Path $env:ProgramFiles "obs-studio\bin\64bit\obs64.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "obs-studio\bin\64bit\obs64.exe")
) | Where-Object { $_ -and (Test-Path $_) }

$ObsInstallations = @(
    foreach ($Candidate in $ObsCandidates) {
        $Executable = Get-Item $Candidate
        [ordered]@{
            path = $Executable.FullName
            product_version = $Executable.VersionInfo.ProductVersion
            file_version = $Executable.VersionInfo.FileVersion
        }
    }
)

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
$Python = if ($PythonCommand) {
    [ordered]@{
        path = $PythonCommand.Source
        version = (& $PythonCommand.Source --version 2>&1 | Out-String).Trim()
    }
} else {
    $null
}

$Inventory = [ordered]@{
    collected_at = (Get-Date).ToUniversalTime().ToString("o")
    computer = [ordered]@{
        name = $env:COMPUTERNAME
        manufacturer = $ComputerSystem.Manufacturer
        model = $ComputerSystem.Model
        total_memory_bytes = [uint64]$ComputerSystem.TotalPhysicalMemory
    }
    windows = [ordered]@{
        caption = $OperatingSystem.Caption
        version = $OperatingSystem.Version
        build_number = $OperatingSystem.BuildNumber
    }
    graphics_adapters = $GraphicsAdapters
    monitors = $Monitors
    media_devices = $MediaDevices
    obs_installations = $ObsInstallations
    python = $Python
}

$Inventory | ConvertTo-Json -Depth 6 | Set-Content $OutputPath -Encoding UTF8

Write-Host "Room inventory written to $OutputPath"
Write-Host "Graphics adapters: $($GraphicsAdapters.Count)"
Write-Host "Monitor devices: $($Monitors.Count)"
Write-Host "Media/capture candidates: $($MediaDevices.Count)"
Write-Host "OBS installations: $($ObsInstallations.Count)"
