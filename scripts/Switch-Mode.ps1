[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet("wraparound", "lecture-single", "lecture-double", "lecture-single-background", "lecture-double-background", "multi-source", "custom", "blank")]
    [string]$Mode,

    [string]$ControllerUrl = "http://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"
$Endpoint = "$ControllerUrl/api/v1/modes/$Mode/activate"

try {
    $Status = Invoke-RestMethod -Method Post -Uri $Endpoint -TimeoutSec 8
} catch {
    throw "The display controller did not activate '$Mode'. Confirm that the controller and OBS are running. $($_.Exception.Message)"
}

Write-Host "Active mode: $($Status.active_mode_id)"
Write-Host "OBS scene: $($Status.obs.current_scene)"
