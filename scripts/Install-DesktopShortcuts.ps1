[CmdletBinding()]
param(
    [string]$Destination = [Environment]::GetFolderPath("Desktop")
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$Shell = New-Object -ComObject WScript.Shell

function New-ControllerShortcut {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Script,
        [string]$ScriptArguments = ""
    )

    $ShortcutPath = Join-Path $Destination "$Name.lnk"
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PowerShell
    $Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Script`" $ScriptArguments"
    $Shortcut.WorkingDirectory = $ProjectRoot
    $Shortcut.WindowStyle = 7
    $Shortcut.Save()
}

$StartLauncher = Join-Path $ProjectRoot "Start-Controller.cmd"
$SwitchScript = Join-Path $PSScriptRoot "Switch-Mode.ps1"

foreach ($Launcher in @(
    @{ Name = "T&V HDMI Floor Box Controller"; Arguments = "" },
    @{ Name = "T&V Controller - Simulation"; Arguments = "-Simulate" }
)) {
    $Shortcut = $Shell.CreateShortcut((Join-Path $Destination "$($Launcher.Name).lnk"))
    $Shortcut.TargetPath = $env:ComSpec
    $Shortcut.Arguments = "/d /c `"`"$StartLauncher`" $($Launcher.Arguments)`""
    $Shortcut.WorkingDirectory = $ProjectRoot
    $Shortcut.WindowStyle = 7
    $Shortcut.Save()
}

$Modes = [ordered]@{
    "T&V - Wraparound" = "wraparound"
    "T&V - Lecture Single" = "lecture-single"
    "T&V - Lecture Double" = "lecture-double"
    "T&V - Lecture Single with Background" = "lecture-single-background"
    "T&V - Lecture Double with Background" = "lecture-double-background"
    "T&V - Multi-source" = "multi-source"
    "T&V - Blank" = "blank"
    "T&V - Custom Routing" = "custom"
}

foreach ($ShortcutName in $Modes.Keys) {
    New-ControllerShortcut `
        -Name $ShortcutName `
        -Script $SwitchScript `
        -ScriptArguments "-Mode $($Modes[$ShortcutName])"
}

Write-Host "Controller shortcuts installed in $Destination"
