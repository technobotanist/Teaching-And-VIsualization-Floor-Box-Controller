[CmdletBinding()]
param(
    [switch]$AutoInstallPython
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VirtualEnvironment = Join-Path $ProjectRoot ".venv"
$Python = Join-Path $VirtualEnvironment "Scripts\python.exe"
$SetupMarker = Join-Path $VirtualEnvironment ".tv-controller-setup.json"
$Manifest = Join-Path $ProjectRoot "pyproject.toml"
$MinimumPython = [Version]"3.11"
$MaximumPython = [Version]"3.14"

Set-Location $ProjectRoot

function Get-CompatiblePython {
    $Candidates = @()
    $PythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($PythonLauncher) {
        foreach ($Version in @("3.13", "3.12", "3.11")) {
            $Candidates += [PSCustomObject]@{
                Command = $PythonLauncher.Source
                Arguments = @("-$Version")
            }
        }
    }

    $PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        $Candidates += [PSCustomObject]@{
            Command = $PythonCommand.Source
            Arguments = @()
        }
    }

    $KnownInstallations = Get-ChildItem `
        -Path (Join-Path $env:LOCALAPPDATA "Programs\Python\Python3*\python.exe") `
        -ErrorAction SilentlyContinue
    foreach ($Installation in $KnownInstallations) {
        $Candidates += [PSCustomObject]@{
            Command = $Installation.FullName
            Arguments = @()
        }
    }

    foreach ($Candidate in $Candidates) {
        try {
            $VersionText = & $Candidate.Command @($Candidate.Arguments) -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
            if ($LASTEXITCODE -ne 0) {
                continue
            }
            $Version = [Version]($VersionText | Select-Object -Last 1)
            if ($Version -ge $MinimumPython -and $Version -lt $MaximumPython) {
                return $Candidate
            }
        }
        catch {
            continue
        }
    }
    return $null
}

function Install-CompatiblePython {
    $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $Winget) {
        throw "Python 3.11-3.13 is required. Install Python 3.11 from https://www.python.org/downloads/ and run this launcher again."
    }

    if (-not $AutoInstallPython) {
        $Response = Read-Host "Python 3.11-3.13 was not found. Install Python 3.11 with Windows Package Manager now? [Y/n]"
        if ($Response -and $Response.Trim().ToLowerInvariant() -notin @("y", "yes")) {
            throw "Python installation was declined. Python 3.11-3.13 is required."
        }
    }

    Write-Host "Installing Python 3.11..." -ForegroundColor Cyan
    & $Winget.Source install `
        --id Python.Python.3.11 `
        --exact `
        --scope user `
        --accept-package-agreements `
        --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Windows Package Manager could not install Python 3.11."
    }
}

if (-not (Test-Path $Python)) {
    $SystemPython = Get-CompatiblePython
    if (-not $SystemPython) {
        Install-CompatiblePython
        $SystemPython = Get-CompatiblePython
    }
    if (-not $SystemPython) {
        throw "Python was installed but could not be located. Open a new terminal and run this launcher again."
    }

    Write-Host "Creating the controller environment..." -ForegroundColor Cyan
    & $SystemPython.Command @($SystemPython.Arguments) -m venv $VirtualEnvironment
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) {
        throw "Could not create the controller environment."
    }
}

Write-Host "Installing required controller libraries..." -ForegroundColor Cyan
& $Python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Could not install the controller libraries. Check the network connection and try again."
}

$PythonVersion = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
$MarkerContent = [ordered]@{
    schema_version = 1
    manifest_sha256 = (Get-FileHash $Manifest -Algorithm SHA256).Hash
    python_version = $PythonVersion
    installed_at = (Get-Date).ToUniversalTime().ToString("o")
}
$MarkerContent | ConvertTo-Json | Set-Content -Path $SetupMarker -Encoding UTF8
& (Join-Path $PSScriptRoot "Install-DesktopShortcuts.ps1")
Write-Host "T&V Display Controller installed at $ProjectRoot"
