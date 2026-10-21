# Room Deployment Runbook

This is the path from the working simulation to a production room. Commission
the single blended display path one layer at a time and keep `Blank` available
throughout.

## What exists today

Already built and testable:

- The HDMI Floor Box Controller browser interface.
- The localhost API and OBS WebSocket client.
- Mode commands for browser, keyboard, desktop shortcuts, and Stream Deck.
- The required OBS scene naming and routing contract.
- Backup, restore, and operator documentation.

Still requiring work in the physical room:

- Map the two capture cards to floor boxes 1-8.
- Prove that Windows and OBS can sustain the display server's one panoramic blended monitor.
- Build the production OBS sources and scenes.
- Verify the display server's existing physical projector blend.
- Map the one OBS Program projector to the blended Windows monitor.
- Configure Windows startup, Stream Deck, recovery storage, and staff acceptance.

The repository cannot supply the hardware mappings or physical blend because
they depend on the installed cards, drivers, cabling, and display server.

## People and access

Have these available before the first room session:

- A room owner who can authorize projector, cabling, driver, and startup changes.
- A technician with local administrator access to the Windows server.
- A person who knows the physical floor-box and projector numbering.
- The capture-card and GPU model information and approved drivers.
- A laptop or HDMI test generator that can be connected to every floor box.
- Access to projector power, remotes, and the existing wall controls.
- The secured shared-drive path for production backups.
- A maintenance window when all eight projectors can run continuously.

Do not update a production driver merely because a newer version exists. Record the current known-working version first and change it only through the room's normal approval process.

## Session 1: Inventory and hardware proof

**Goal:** Establish whether the proposed OBS topology is viable before building scenes.

Estimated room time: 2-4 hours, plus a one-hour unattended soak.

On the room server, place the project at a stable approved path such as `C:\TV-Display-Controller`. Do not use the developer's profile directory as the final production location. Start the controller, open <http://127.0.0.1:8765/commissioning>, and use the **Hardware** tab before changing drivers or display settings.

Select **Start room visit** first. Use the guided floor-box mapper as the working input table and keep visit-wide issues in the persistent notes field. Export the session report before leaving the room.

The page displays the Windows, GPU, monitor, and capture-device baseline. Export the same facts to a standalone JSON file when needed:

```powershell
.\scripts\Collect-RoomInventory.ps1
```

The generated `room-inventory-*.json` is ignored by Git. Retain it with the room's commissioning records and compare it with the final accepted inventory. Manual gate checkmarks in the browser are workflow aids; the signed room change log remains the official commissioning record.

### Record the physical map

Complete this table during the visit:

| Logical ID | Floor label | Capture card | Card input | OBS source | Signal verified |
| --- | --- | --- | --- | --- | --- |
| 1 |  |  |  | `FB_01` |  |
| 2 |  |  |  | `FB_02` |  |
| 3 |  |  |  | `FB_03` |  |
| 4 |  |  |  | `FB_04` |  |
| 5 |  |  |  | `FB_05` |  |
| 6 |  |  |  | `FB_06` |  |
| 7 |  |  |  | `FB_07` |  |
| 8 |  |  |  | `FB_08` |  |

Record the output path separately:

| Output | Display-server connection | Windows display | Resolution | OBS monitor index |
| --- | --- | --- | --- | --- |
| Blended canvas |  |  | `11860 x 1080` |  |

### Prove the inputs

1. Connect a known-good 1080p60 HDMI signal to floor box 1.
2. Identify its capture-card channel and create OBS source `FB_01`.
3. Record the card and input above; do not rely on device enumeration order.
4. Repeat for floor boxes 2-8.
5. Display all eight feeds in OBS simultaneously and open **View > Stats**.
6. Run for one hour while recording rendering lag, encoding lag, missed frames, GPU use, and capture disconnects.

### Prove the outputs

1. Confirm Windows Extended Desktop exposes the display server as one panoramic monitor.
2. Use Windows **Identify** and the Commissioning Console ID card to fill in the output table.
3. Confirm the blended monitor runs at `11860 x 1080` and the intended refresh rate.
4. Start OBS on the chosen render GPU.
5. Open one temporary OBS Program projector and confirm it fills the blended canvas.

### Gate 1

Proceed only if all eight inputs remain live and the blended output remains
connected for one hour without unacceptable OBS rendering lag.

**Deliverable:** Completed input/output maps, hardware/driver inventory, OBS Stats results, and a written choice of OBS render GPU.

## Session 2: Build the OBS display engine

**Goal:** Produce correct room content before projector blending.

Estimated room time: 3-6 hours.

1. Create Profile `T&V Display System` at `11860 x 1080`, 60 FPS.
2. Create Scene Collection `T&V Production`.
3. Build the required layouts in [OBS_SCENE_CONTRACT.md](OBS_SCENE_CONTRACT.md).
   Existing scene names may be retained and mapped in the Commissioning Console.
4. Build `01_EIGHT_SOURCE` first and verify floor boxes 1-8 appear in the approved projector mapping.
5. Build `04_WRAPAROUND` and verify `SERVER_DESKTOP` spans the panoramic canvas.
6. Build the four `06_` through `09_` Lecture scenes and verify they use only `FB_04`, `FB_05`, black, and `SERVER_DESKTOP` as specified.
7. Build `CUSTOM_SLOT_P1` through `CUSTOM_SLOT_P8`, lock every source transform, then nest all slots over black in `05_CUSTOM`.
8. Enable OBS WebSocket on port `4455` with authentication.
9. Set `OBS_WEBSOCKET_PASSWORD` for the Windows account that will launch the controller.
10. Start the controller without `-Simulate` and open the Commissioning Console's **OBS Contract** tab.
11. Resolve every failed automated check, then verify mode buttons and Custom assignments change the OBS Program scene as expected.

At this point, switching should work inside OBS even though the blended Windows
display is not yet enabled in `config/room.json`.

### Gate 2

Proceed only if all seven operating modes plus Blank switch correctly in OBS Preview/Program, every floor-box label is correct, Custom Routing addresses every slot, and switching never exposes a transparent or stale region.

**Deliverable:** Working production Profile and Scene Collection with controller-driven logical switching.

## Session 3: Commission the blended display

**Goal:** Establish the one permanent full-screen output while leaving physical
projector geometry in the display server.

Estimated room time: 4-8 hours, depending on the existing blend/mask process.

1. Put a full-canvas alignment grid into a temporary OBS scene.
2. Verify the display server maps that one raster across all physical projectors.
3. Complete seam, warp, mask, and blend adjustments in the display server.
4. Open the Commissioning Console's **Blended Display** tab.
5. Select the verified panoramic Windows monitor, confirm `MAP P1`, and enable it.
6. Use `TEST P1` to open OBS Program full-screen on that monitor.
7. Switch through every room mode and confirm the display-server geometry remains stationary.

Use **Show ID card** to verify the Windows display location, then **Open selected
output** to verify the OBS Program path. Record the blended display observed and
mark it Correct, Wrong display, or No signal.

The monitor list remains available from PowerShell for troubleshooting:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/v1/monitors
```

The console writes `monitor_index` and `enabled` atomically to `config/room.json`.
If Program opens on the wrong display, disable the entry and correct the target
before proceeding.

Only after the blended output is correct should `auto_open` be changed to `true`.

### Gate 3

Proceed only if OBS Program fills the intended blended display, all physical
seams remain calibrated across every room mode, and no OBS editor or controller
window appears on the array.

**Deliverable:** Verified blended-display calibration notes and a confirmed
`config/room.json` monitor target.

## Session 4: Productionize and hand off

**Goal:** Make the system recoverable and operable by staff.

Estimated room time: 2-3 hours plus the one-hour acceptance soak.

1. Install the desktop shortcuts with `scripts/Install-DesktopShortcuts.ps1`.
2. Configure the Stream Deck buttons with `scripts/Switch-Mode.ps1` and the supplied artwork.
3. Configure OBS and the controller to start for the approved room account.
4. Keep the controller bound to `127.0.0.1`; do not expose it to the campus network.
5. Run the acceptance test in [COMMISSIONING.md](COMMISSIONING.md).
6. Use the Commissioning Console's **Acceptance** tab to run automated mode cycling, track the one-hour soak, capture pre/post reboot topology, and complete the handoff checks.
7. Create the first known-good backup:

```powershell
.\scripts\Backup-Appliance.ps1 -Name production-v1.0
```

8. Copy it to the secured shared drive and complete one supervised restore drill.
9. Train staff using [OPERATIONS.md](OPERATIONS.md): start, select each mode, use Blank, enter Custom, and recover from an incorrect layout.

### Gate 4

Production is accepted only when the power-cycle test, one-hour mode-switch soak, backup/restore drill, and staff walkthrough all pass.

**Deliverable:** Approved production system, known-good backup, startup configuration, Stream Deck, desktop shortcuts, room change log, and named support owner.

## Your immediate next action

Schedule Session 1 and open the Commissioning Console on the actual room server. Before changing anything, confirm these four facts from the Hardware tab and physical labels:

1. Capture-card manufacturer and model numbers.
2. GPU manufacturer and model numbers.
3. Display-server model and current Windows display topology.
4. Whether the room server already has OBS 28 or newer and Python 3.11 or newer.

Do not enter a monitor index or enable the blended output until the panoramic
Windows display has been positively identified.
