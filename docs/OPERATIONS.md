# T&V HDMI Floor Box Controller - Operations

## Daily start

On a new Windows machine, double-click `Start-Controller.cmd` in the repository
folder once. It installs the controller dependencies, creates the desktop
shortcuts, starts the local server, and opens the browser. For training without
OBS, double-click `Start-Simulation.cmd` or the installed `T&V Controller - Simulation`
desktop shortcut. See the [first-launch requirements](../README.md#install-and-preview).

1. Power on the projectors and room workstation.
2. Start OBS with Profile `T&V Display System` and Scene Collection `T&V Production`.
3. Open the `T&V HDMI Floor Box Controller` desktop shortcut.
4. Confirm the top-right status reads `OBS connected` and the commissioned count is correct.
5. Select the required room mode.
6. Select **Show [layout] full screen** to open that layout on every commissioned
   projector display. For all eight floor boxes, select **Multi-source**, then
   **Show Multi-source full screen**.

The controller shortcut starts both the local API and browser UI; no separate
frontend server is needed. Its server window is minimized and must remain open.
Launching the same controller again reopens the browser rather than starting a
second server. To stop the controller or switch simulation settings, restore its
server window and press **Ctrl+C** before launching again. OBS is started separately.

The full-screen button opens the locked OBS `OUT_Pn` source-projector windows on
their commissioned Windows displays. It is disabled until at least one projector
has been assigned a monitor index and enabled in the Commissioning Console.
The full-screen icon in the page header only expands the browser controller; it
does not send video to the projector array.

## Mode map

| Button | OBS scene | Room use |
| --- | --- | --- |
| `1` Wraparound | `04_WRAPAROUND` | Panoramic server canvas |
| `2` Lecture Single | `06_LECTURE_SINGLE` | Floor boxes 4 and 5 centered once |
| `3` Lecture Double | `07_LECTURE_DOUBLE` | Floor boxes 4 and 5 repeated twice |
| `4` Lecture Single + Background | `08_LECTURE_SINGLE_BACKGROUND` | Centered pair over server desktop |
| `5` Lecture Double + Background | `09_LECTURE_DOUBLE_BACKGROUND` | Repeated pair over server desktop |
| `8` Multi-source | `01_EIGHT_SOURCE` | Approved fixed floor-box mapping |
| `0` Blank | `00_BLACK` | Immediate black output |
| `+` Custom Routing | `05_CUSTOM` | Editable source-to-projector assignments |

The number keys shown above also work while the browser controller has focus.

## Custom routing

Custom Routing uses the locked slot scenes in OBS Scene Collection `T&V Production`:

1. Select **Custom Routing**.
2. For each projector, choose `Floor box 1` through `Floor box 8`, or `Blank`.
3. A floor box may be assigned to more than one projector.
4. Select **Apply routing**. The assignments are saved and `05_CUSTOM` becomes live.
5. Use **Blank array** to hide the array without changing the saved assignments.

Do not edit `CUSTOM_SLOT_P1` through `CUSTOM_SLOT_P8`, `ROUTE_ACTIVE`, or `OUT_P1` through `OUT_P8` during normal operation. Those scenes contain locked logical placement, switching, and projector calibration.

## Stream Deck and desktop commands

Each control calls the same local API. Stream Deck System/Open actions can launch:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Path\To\Octave4505\scripts\Switch-Mode.ps1" -Mode lecture-single
```

Replace `lecture-single` with `lecture-double`, `lecture-single-background`, `lecture-double-background`, `multi-source`, `wraparound`, `blank`, or `custom`. Artwork is in `assets/stream-deck`.

First-time controller setup generates the Windows desktop shortcuts automatically.
To regenerate them manually (for example after moving the repository), run:

```powershell
.\scripts\Install-DesktopShortcuts.ps1
```

## Recovery

Use `Blank` first if incorrect content is visible. A mode-selection failure does not modify projector calibration.

Create a known-good backup after every approved OBS or controller change:

```powershell
.\scripts\Backup-Appliance.ps1 -Name production-v1.0
```

Copy the resulting folder from `backups` to the secured shared drive. It contains controller configuration, assets, the complete OBS configuration, metadata, and SHA-256 checksums.

To restore, close OBS and run from an administrator-approved staff session:

```powershell
.\scripts\Restore-Appliance.ps1 -BackupPath "X:\T&V-OBS\production-v1.0" -Confirm
```

The restore validates every checksum and retains the previous OBS configuration beside the restored directory for rollback.
