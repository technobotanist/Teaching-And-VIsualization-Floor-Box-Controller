# T&V HDMI Floor Box Controller

Local HDMI floor-box and panoramic-display control software for the Teaching & Visualization Lab at NC State University's Hunt Library. OBS Studio composites one 11,860 x 1,080 Program canvas; the display server presents that canvas as one blended Windows monitor spanning the physical projector array.

## Prototype scope

- Activates Wraparound, four Lecture variants, fixed Multi-source, Blank, and Custom Routing OBS scenes.
- Exposes the same localhost API to the browser UI, Windows desktop shortcuts, Stream Deck actions, and a future wall-panel bridge.
- Keeps logical room modes separate from the display server's physical blend.
- Runs without OBS in simulation mode for UI review and training.
- Provides versioned configuration, backup, restore, commissioning, and operations workflows.

The display server owns projector alignment, overlap, and blending. OBS opens one full-canvas Program projector on that blended Windows display. The checked-in configuration intentionally does not guess its monitor index.

## Architecture

The browser UI, desktop shortcuts, Stream Deck, and a future wall-panel bridge all call one localhost API. Mode commands select the corresponding OBS Program scene. One full-screen OBS Program window sends the complete panoramic canvas to the display server's blended monitor.

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
open the complete OBS Program canvas on the blended display. For the apparent
one-source-per-projector layout, select **Multi-source**, then
**Show Multi-source full screen**. If the display is not configured yet, the
button opens the one-time blended-display selection workflow.

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
- Live scene discovery and a saved room-layout-to-OBS-scene mapping, so existing
  OBS scene names do not need to match repository defaults.
- Automated OBS profile, canvas, frame-rate, input, scene, monitor, and live-stat checks.
- Guarded blended-display identification and OBS Program output testing.
- Automated mode cycling with an immediate Stop & Blank action.
- Persistent soak/reboot checks plus downloadable JSON and print/PDF reports.
- Four room-readiness gates and a one-hour acceptance timer.

Physical cable identification and visual projector focus, overlap, feathering, color, crop, mask, and warp judgments still require a technician in the room. That geometry belongs to the display server's blend configuration, outside OBS and this controller.

For a standalone JSON inventory export, run `.\scripts\Collect-RoomInventory.ps1`.

1. Complete [Commissioning](docs/COMMISSIONING.md), including the blended-display soak test.
2. Build the required layouts in the [OBS scene contract](docs/OBS_SCENE_CONTRACT.md);
   the listed names are defaults, not requirements.
3. Use **OBS Contract → Renderer connection** to configure authenticated WebSocket access while OBS is closed, or follow its manual walkthrough while OBS is open.
4. In **Room layout scene mapping**, select the existing OBS scene for every
   operator layout and save the mapping.
5. Select the display server's blended Windows monitor in the Commissioning Console and enable it.
6. Start with `.\scripts\Start-Controller.ps1`.

The UI reports OBS and blended-display readiness. Full-screen presentation remains locked until the blended Windows monitor is selected.

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
