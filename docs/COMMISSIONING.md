# Commissioning

Full-screen output is disabled in `config/room.json` until the display server's
single blended Windows monitor is identified. The repository does not guess its
monitor index and does not control the display server's physical blend.

Use [ROOM_DEPLOYMENT_RUNBOOK.md](ROOM_DEPLOYMENT_RUNBOOK.md) as the onsite sequence. This file is the technical acceptance checklist used by that runbook.

## Field-test session

Open <http://127.0.0.1:8765/commissioning> and select **Start room visit** before recording physical results. The session is saved under the local ignored `state/field-sessions` directory and survives browser refreshes and controller restarts.

During the visit:

1. Record every floor-box label, capture device/channel, signal result, and issue in **Hardware**.
2. In **Blended Display**, use **Show ID card** to identify the display-server
   canvas, then use **Open selected output** to prove the OBS Program path.
3. Use **Mode exercise** in **Acceptance** for repeated switching. **Stop & Blank** is immediate and does not require a confirmation phrase.
4. Capture a topology snapshot before reboot and another after recovery. Resolve any reported difference before acceptance.
5. Complete the visit, export the JSON record, and use **Print report** to print or save a PDF with the room change log.

Starting another visit creates a new record; completed reports remain available after a controller restart. Session records can include hardware details and should be retained with the secured commissioning records.

## 1. Prove the hardware path

1. Update both GPU and capture-card drivers to the room-approved versions and record them.
2. Confirm Windows sees the display server as one 11,860 x 1,080 blended monitor
   at the intended refresh rate.
3. Confirm OBS runs on the approved GPU and can sustain that panoramic output.
4. Map all eight floor boxes to `FB_01` through `FB_08` and verify stable 60 FPS capture.
5. Run a one-hour baseline with all captures active before building the operator layouts.

Stop here if OBS misses frames, a display disconnects, or monitor order changes under load. The controller cannot compensate for an unstable Windows/GPU topology.

## 2. Build the OBS contract

Create the Profile and Scene Collection from `docs/OBS_SCENE_CONTRACT.md`. Build and test each logical scene before adding output geometry.

Keep these layers independent:

- Logical scenes decide which floor-box content is visible.
- The selected OBS Program scene decides which logical layout is live.
- The display server owns measured physical projector geometry and blending.

Do not reproduce the display server's seam overlap or physical calibration in
OBS. OBS owns only the complete panoramic raster.

## 3. Enable OBS WebSocket

Install and run the controller in simulation first:

```powershell
.\scripts\Install.ps1
.\scripts\Start-Controller.ps1 -Simulate
```

Open <http://127.0.0.1:8765/commissioning#obs-contract> and use **Renderer connection**. The console detects OBS and offers two paths:

- With OBS closed, **Configure securely** backs up the existing WebSocket file, enables port `4455`, generates a strong password, and stores it in the launch account's `OBS_WEBSOCKET_PASSWORD` environment variable. Launch OBS from the same panel afterward.
- With OBS open, expand **Manual OBS walkthrough** and apply the listed options in **Tools → WebSocket Server Settings**. Enter the same password in the walkthrough's masked field, save it for the controller account, then refresh.

Automatic configuration refuses to edit OBS files while OBS is running. The generated password is never returned by the API or stored in `config/room.json`.

Then restart without `-Simulate` and confirm the UI reports `OBS connected`.

## 4. Select the blended display

With OBS and the controller running:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/v1/monitors
```

Use **Show ID card** in the Commissioning Console to identify the one Windows
monitor exposed by the display server. Windows monitor indexes are not permanent;
repeat this after GPU, driver, cable, or display-topology changes.

1. Assign that index to **Blended display**.
2. Enable it after verifying the ID card appears on the panoramic canvas.
3. Use **Open selected output** to test one full-screen OBS Program window.
4. Leave `auto_open` as `false` until the target is confirmed; enable it later
   only if automatic room startup is desired.

## 5. Acceptance test

Run at least one continuous hour while all eight captures and the one panoramic
Program window are active on the blended display.

- Switch through Wraparound, all four Lecture variants, Multi-source, Custom, and Blank at least 25 times each.
- Confirm no editor window appears on a projector.
- Confirm no route reveals the prior mode or an unfilled canvas region.
- Confirm the display-server blend remains aligned while switching.
- Confirm no missed or skipped frames in OBS Stats.
- Power-cycle the workstation and verify startup, shortcuts, and output restoration.
- Disconnect and reconnect one noncritical input and verify the room recovers predictably.
- Create a known-good backup and complete one supervised restore drill.

Record the accepted OBS version, plugin versions, GPU drivers, capture drivers, monitor map, config checksum, and backup location in the room change log.
