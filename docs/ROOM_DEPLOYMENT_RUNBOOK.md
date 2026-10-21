# Room Deployment Runbook

This is the path from the working simulation to a production room. Do not begin by enabling all eight outputs. Commission one layer at a time and keep `Blank` available throughout.

## What exists today

Already built and testable:

- The HDMI Floor Box Controller browser interface.
- The localhost API and OBS WebSocket client.
- Mode commands for browser, keyboard, desktop shortcuts, and Stream Deck.
- The required OBS scene naming and routing contract.
- Backup, restore, and operator documentation.

Still requiring work in the physical room:

- Map the two capture cards to floor boxes 1-8.
- Prove that Windows and OBS can sustain all eight projector displays across two GPUs.
- Build the production OBS sources and scenes.
- Measure and calibrate each projector output.
- Map OBS monitor indexes to physical projectors.
- Configure Windows startup, Stream Deck, recovery storage, and staff acceptance.

The repository cannot supply the last six items because they depend on the installed cards, drivers, cabling, displays, and measured projector overlap.

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

| Projector | Physical label | GPU | GPU port | Windows display | Native mode | OBS monitor index |
| --- | --- | --- | --- | --- | --- | --- |
| P1 |  |  |  |  |  |  |
| P2 |  |  |  |  |  |  |
| P3 |  |  |  |  |  |  |
| P4 |  |  |  |  |  |  |
| P5 |  |  |  |  |  |  |
| P6 |  |  |  |  |  |  |
| P7 |  |  |  |  |  |  |
| P8 |  |  |  |  |  |  |

### Prove the inputs

1. Connect a known-good 1080p60 HDMI signal to floor box 1.
2. Identify its capture-card channel and create OBS source `FB_01`.
3. Record the card and input above; do not rely on device enumeration order.
4. Repeat for floor boxes 2-8.
5. Display all eight feeds in OBS simultaneously and open **View > Stats**.
6. Run for one hour while recording rendering lag, encoding lag, missed frames, GPU use, and capture disconnects.

### Prove the outputs

1. Confirm Windows Extended Desktop exposes eight independent projector displays.
2. Use Windows **Identify** and a physical observer to fill in the output table.
3. Confirm every projector runs at its intended native resolution and refresh rate.
4. Start OBS on the chosen render GPU while both GPUs continue driving their displays.
5. Open temporary OBS projectors one at a time and confirm the two-GPU output path remains stable.

### Gate 1

Proceed only if all eight inputs remain live and all eight outputs remain connected for one hour without unacceptable OBS rendering lag. If this gate fails, stop controller work and resolve the Windows, driver, GPU, capture, or cabling problem first.

**Deliverable:** Completed input/output maps, hardware/driver inventory, OBS Stats results, and a written choice of OBS render GPU.

## Session 2: Build the OBS display engine

**Goal:** Produce correct room content before projector blending.

Estimated room time: 3-6 hours.

1. Create Profile `T&V Display System` at `11860 x 1080`, 60 FPS.
2. Create Scene Collection `T&V Production`.
3. Build the exact scenes in [OBS_SCENE_CONTRACT.md](OBS_SCENE_CONTRACT.md).
4. Build `01_EIGHT_SOURCE` first and verify floor boxes 1-8 appear in the approved projector mapping.
5. Build `04_WRAPAROUND` and verify `SERVER_DESKTOP` spans the panoramic canvas.
6. Build the four `06_` through `09_` Lecture scenes and verify they use only `FB_04`, `FB_05`, black, and `SERVER_DESKTOP` as specified.
7. Build `CUSTOM_SLOT_P1` through `CUSTOM_SLOT_P8`, lock every source transform, then nest all slots over black in `05_CUSTOM`.
8. Add all eight numbered logical scenes to `ROUTE_ACTIVE`, reset their transforms, and leave only `00_BLACK` enabled.
9. Enable OBS WebSocket on port `4455` with authentication.
10. Set `OBS_WEBSOCKET_PASSWORD` for the Windows account that will launch the controller.
11. Start the controller without `-Simulate` and open the Commissioning Console's **OBS Contract** tab.
12. Resolve every failed automated check, then verify mode buttons and Custom assignments change the expected visibility in OBS.

At this point, switching should work inside OBS even though no production projector outputs are enabled in `config/room.json`.

### Gate 2

Proceed only if all seven operating modes plus Blank switch correctly in OBS Preview/Program, every floor-box label is correct, Custom Routing addresses every slot, and switching never exposes a transparent or stale region.

**Deliverable:** Working production Profile and Scene Collection with controller-driven logical switching.

## Session 3: Calibrate one projector, then eight

**Goal:** Establish the permanent physical output layer without letting mode changes alter geometry.

Estimated room time: 4-8 hours, depending on the existing blend/mask process.

1. Put a full-canvas alignment grid into `ROUTE_ACTIVE` or a temporary calibration scene.
2. Build `OUT_P1` with `ROUTE_ACTIVE` nested inside it.
3. Apply only P1's measured crop, scale, position, mask, and correction in `OUT_P1`.
4. Lock the calibrated items.
5. Open `OUT_P1` as an OBS source projector on physical projector 1.
6. Switch through all room modes. P1 geometry must remain stationary.
7. Repeat for `OUT_P2` through `OUT_P8`, calibrating seams in physical order.

Do not use the estimated 500-pixel overlap as a calibration value. Record the actual crop and blend region at every seam.

After the scenes are calibrated, open the Commissioning Console's **Projector Map** tab. For each output, select the verified Windows display, type the requested `MAP Pn` confirmation, save it, then use `TEST Pn` to open only that output.

For each assignment, use **Show ID card** to verify the Windows display location, then **Open selected output** to verify the OBS `OUT_Pn` path. Record the physical display observed and mark it Correct, Wrong projector, or No signal. Do not mark the output map gate complete until all eight observed results pass.

The monitor list remains available from PowerShell for troubleshooting:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/v1/monitors
```

The console writes `monitor_index` and `enabled` atomically to `config/room.json`; duplicate monitor assignments are rejected. If a source opens on the wrong display, disable that entry and correct the physical map before proceeding.

Only after all eight outputs are correct should `auto_open` be changed to `true`.

### Gate 3

Proceed only if every `OUT_Pn` opens on the intended projector, all seams remain calibrated across every room mode, and no OBS editor or control window appears on the array.

**Deliverable:** Eight locked output scenes, measured calibration notes, and a verified `config/room.json` monitor map.

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
3. Projector model and current Windows display topology.
4. Whether the room server already has OBS 28 or newer and Python 3.11 or newer.

Do not enter monitor indexes or enable projector entries yet. The first implementation decision depends on whether the eight-display, two-GPU path passes Gate 1.
