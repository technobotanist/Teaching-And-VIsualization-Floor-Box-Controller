[CmdletBinding()]
param(
    [string]$Destination = [Environment]::GetFolderPath("Desktop")
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
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

$StartScript = Join-Path $PSScriptRoot "Start-Controller.ps1"
$SwitchScript = Join-Path $PSScriptRoot "Switch-Mode.ps1"

New-ControllerShortcut -Name "T&V HDMI Floor Box Controller" -Script $StartScript

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
