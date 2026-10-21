# T&V HDMI Floor Box Controller

Local HDMI floor-box and projector-array control software for the Teaching & Visualization Lab at NC State University's Hunt Library. OBS Studio remains the capture, compositing, calibration, and projector-output engine; this application presents a constrained operator interface over OBS WebSocket.

## Prototype scope

- Activates Wraparound, four Lecture variants, fixed Multi-source, Blank, and Custom Routing OBS scenes.
- Exposes the same localhost API to the browser UI, Windows desktop shortcuts, Stream Deck actions, and a future wall-panel bridge.
- Keeps logical room modes separate from physical projector calibration.
- Runs without OBS in simulation mode for UI review and training.
- Provides versioned configuration, backup, restore, commissioning, and operations workflows.

The eight-output, two-GPU topology and all crop/blend geometry must be commissioned on the room workstation before projection output is enabled. The checked-in configuration intentionally does not guess Windows monitor indexes.

## Architecture

The browser UI, desktop shortcuts, Stream Deck, and a future wall-panel bridge all call one localhost API. The API controls a shared `ROUTE_ACTIVE` OBS scene over WebSocket. Eight persistent `OUT_P1` through `OUT_P8` projector scenes nest that router while retaining independent, locked calibration.

See [Architecture](docs/ARCHITECTURE.md) and the [OBS scene contract](docs/OBS_SCENE_CONTRACT.md).

## Install and preview

### Windows: double-click to launch

Keep the extracted repository in a permanent folder, then double-click
**Start-Controller.cmd**. No terminal commands, Node.js, or React development server
are needed: the Python server serves both the browser UI and API.

On first launch, the launcher automatically installs Python 3.11 if a compatible
Python 3.11-3.13 installation is not found, creates its local environment, installs
the controller libraries, and creates desktop shortcuts. Initial setup needs an
internet connection and Windows Package Manager (`winget`) if Python is missing.
If automatic Python installation is unavailable, install Python 3.11-3.13 and
double-click the launcher again. Windows may request approval during installation.

After setup, use either desktop icon:

- **T&V HDMI Floor Box Controller** starts the real OBS-connected controller.
- **T&V Controller - Simulation** starts a preview without OBS or projectors.

In the room controls, select a layout and use **Show [layout] full screen** to
open the corresponding locked OBS outputs on all commissioned projector displays.
For the one-source-per-projector layout, select **Multi-source**, then
**Show Multi-source full screen**. This action remains disabled until projector
monitor indexes are assigned and enabled during commissioning.

For a first-time preview, double-click **Start-Simulation.cmd** instead; it performs
the same automatic setup. Both launchers start the server and open the browser.
Desktop launches keep the server window minimized. Leave that window running;
closing the browser does not stop the controller. To stop it, restore the server
window and press **Ctrl+C**. Repeat launches reopen an already-running controller
with the same configuration and simulation setting. Stop the existing server
before switching between real and simulation mode, or after updating the code.

OBS installation, OBS launch, and room commissioning are separate from controller
setup; the launcher does not install or start OBS or enable physical outputs.
Mode-specific desktop shortcuts require the controller to be running already.
If you move the repository, double-click its launcher in the new location to
refresh the desktop shortcuts automatically.

### PowerShell alternative

```powershell
.\scripts\Install.ps1
.\scripts\Start-Controller.ps1 -Simulate
```

Open <http://127.0.0.1:8765>. Simulation mode exercises the complete UI and automation path without OBS or projectors.

## Connect OBS

Start with the staged [Room Deployment Runbook](docs/ROOM_DEPLOYMENT_RUNBOOK.md). It separates hardware proof, OBS construction, projector calibration, and staff handoff into four gated room sessions.

Start the controller on the room server and open the admin workspace:

<http://127.0.0.1:8765/commissioning>

The Commissioning Console provides:

- Read-only Windows GPU, monitor, and capture-device inventory.
- Durable field-test sessions with guided floor-box mapping and visit notes.
- OBS installation/process detection, Launch or Focus, guarded WebSocket configuration, and a manual setup walkthrough.
- Automated OBS profile, canvas, frame-rate, input, scene, monitor, and live-stat checks.
- Guarded, one-at-a-time projector ID cards, OBS output tests, and observed-result records.
- Automated mode cycling with an immediate Stop & Blank action.
- Persistent soak/reboot checks plus downloadable JSON and print/PDF reports.
- Four room-readiness gates and a one-hour acceptance timer.

Physical cable identification and visual projector focus, overlap, feathering, color, crop, mask, and warp judgments still require a technician in the room. Geometry remains in locked OBS `OUT_Pn` scenes; the commissioning API cannot alter transforms or filters.

For a standalone JSON inventory export, run `.\scripts\Collect-RoomInventory.ps1`.

1. Complete [Commissioning](docs/COMMISSIONING.md), including the two-GPU soak test.
2. Build the exact scenes in the [OBS scene contract](docs/OBS_SCENE_CONTRACT.md).
3. Use **OBS Contract → Renderer connection** to configure authenticated WebSocket access while OBS is closed, or follow its manual walkthrough while OBS is open.
4. Enter verified monitor indexes in `config/room.json`, then enable each commissioned output.
5. Start with `.\scripts\Start-Controller.ps1`.

The UI reports OBS and projector readiness. Physical outputs remain locked while the checked-in projector entries are disabled.

## Automation

Switch modes from PowerShell, Stream Deck, or a desktop shortcut through the same API:

```powershell
.\scripts\Switch-Mode.ps1 -Mode lecture-single
.\scripts\Install-DesktopShortcuts.ps1
```

Custom Stream Deck artwork is under `assets/stream-deck`. The concise staff procedure is [Operations](docs/OPERATIONS.md).

## Recovery

Backups include the complete OBS configuration, controller configuration, media assets, metadata, and a SHA-256 manifest:

```powershell
.\scripts\Backup-Appliance.ps1 -Name production-v1.0
.\scripts\Restore-Appliance.ps1 -BackupPath "X:\T&V-OBS\production-v1.0" -Confirm
```

Store production backups on the secured shared drive because OBS configuration can contain authentication material.

## Test

```powershell
.\.venv\Scripts\python -m pytest
```

## Repository layout

```text
assets/                       Stream Deck artwork and production media
backups/                      Local ignored backup staging area
config/room.json              Room modes and commissioned monitor map
docs/                         Architecture, OBS contract, commissioning, operations
scripts/                      Windows setup, launch, shortcut, backup, restore tools
src/tv_display_controller/    API, OBS gateway, service, and browser UI
tests/                        Configuration, routing, service, and API tests
```
