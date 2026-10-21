const elements = {
  acceptanceState: document.querySelector("#acceptance-state"),
  cancelConfirm: document.querySelector("#cancel-confirm"),
  captureDeviceOptions: document.querySelector("#capture-device-options"),
  capturePostReboot: document.querySelector("#capture-post-reboot"),
  capturePreReboot: document.querySelector("#capture-pre-reboot"),
  commissionedCount: document.querySelector("#commissioned-count"),
  completeSession: document.querySelector("#complete-session"),
  completionBar: document.querySelector("#completion-bar"),
  completionCount: document.querySelector("#completion-count"),
  computerName: document.querySelector("#computer-name"),
  confirmDetail: document.querySelector("#confirm-detail"),
  confirmDialog: document.querySelector("#confirm-dialog"),
  confirmForm: document.querySelector("#confirm-form"),
  confirmInput: document.querySelector("#confirm-input"),
  confirmPhrase: document.querySelector("#confirm-phrase"),
  confirmTitle: document.querySelector("#confirm-title"),
  engineState: document.querySelector("#engine-state"),
  engineStatus: document.querySelector("#commission-state"),
  exerciseCycles: document.querySelector("#exercise-cycles"),
  exerciseInterval: document.querySelector("#exercise-interval"),
  exerciseMessage: document.querySelector("#mode-exercise-message"),
  exerciseSwitches: document.querySelector("#exercise-switches"),
  exerciseTarget: document.querySelector("#exercise-target"),
  fieldSessionDetail: document.querySelector("#field-session-detail"),
  fieldSessionHeading: document.querySelector("#field-session-heading"),
  gpuCount: document.querySelector("#gpu-count"),
  gpuList: document.querySelector("#gpu-list"),
  htmlReport: document.querySelector("#html-report"),
  inputCaptureChannel: document.querySelector("#input-capture-channel"),
  inputCaptureDevice: document.querySelector("#input-capture-device"),
  inputFloorLabel: document.querySelector("#input-floor-label"),
  inputMapProgress: document.querySelector("#input-map-progress"),
  inputNotes: document.querySelector("#input-notes"),
  inputSignalStatus: document.querySelector("#input-signal-status"),
  inputSourceName: document.querySelector("#input-source-name"),
  inputStepNumber: document.querySelector("#input-step-number"),
  jsonReport: document.querySelector("#json-report"),
  mediaDeviceCount: document.querySelector("#media-device-count"),
  mediaDeviceList: document.querySelector("#media-device-list"),
  monitorDeviceCount: document.querySelector("#monitor-device-count"),
  monitorDeviceList: document.querySelector("#monitor-device-list"),
  modeSelection: document.querySelector("#mode-selection"),
  obsAuthDetail: document.querySelector("#obs-auth-detail"),
  obsAuthState: document.querySelector("#obs-auth-state"),
  obsCheckList: document.querySelector("#obs-check-list"),
  obsConfigureWebsocket: document.querySelector("#obs-configure-websocket"),
  obsInstallPath: document.querySelector("#obs-install-path"),
  obsInstallState: document.querySelector("#obs-install-state"),
  obsLaunch: document.querySelector("#obs-launch"),
  obsManualPassword: document.querySelector("#obs-manual-password"),
  obsProcessState: document.querySelector("#obs-process-state"),
  obsSavePassword: document.querySelector("#obs-save-password"),
  obsSetupMessage: document.querySelector("#obs-setup-message"),
  obsSetupRefresh: document.querySelector("#obs-setup-refresh"),
  obsWebsocketDetail: document.querySelector("#obs-websocket-detail"),
  obsWebsocketPort: document.querySelector("#obs-websocket-port"),
  obsWebsocketState: document.querySelector("#obs-websocket-state"),
  phaseKicker: document.querySelector("#phase-kicker"),
  phaseTitle: document.querySelector("#phase-title"),
  previousInput: document.querySelector("#previous-input"),
  projectorObservedDisplay: document.querySelector("#projector-observed-display"),
  projectorRows: document.querySelector("#projector-rows"),
  projectorTestExpected: document.querySelector("#projector-test-expected"),
  projectorTestNotes: document.querySelector("#projector-test-notes"),
  projectorTestProgress: document.querySelector("#projector-test-progress"),
  projectorTestStatus: document.querySelector("#projector-test-status"),
  projectorTestTarget: document.querySelector("#projector-test-target"),
  refreshInventory: document.querySelector("#refresh-inventory"),
  refreshObs: document.querySelector("#refresh-obs"),
  resetSoak: document.querySelector("#reset-soak"),
  rebootMessage: document.querySelector("#reboot-message"),
  saveInput: document.querySelector("#save-input"),
  saveProjectorResult: document.querySelector("#save-projector-result"),
  sessionNotes: document.querySelector("#session-notes"),
  showDisplayIdentifier: document.querySelector("#show-display-identifier"),
  soakClock: document.querySelector("#soak-clock"),
  soakMessage: document.querySelector("#soak-message"),
  startSoak: document.querySelector("#start-soak"),
  startExercise: document.querySelector("#start-exercise"),
  startSession: document.querySelector("#start-session"),
  statFps: document.querySelector("#stat-fps"),
  statOutputSkips: document.querySelector("#stat-output-skips"),
  statRenderSkips: document.querySelector("#stat-render-skips"),
  statRenderTime: document.querySelector("#stat-render-time"),
  submitConfirm: document.querySelector("#submit-confirm"),
  stopExercise: document.querySelector("#stop-exercise"),
  toast: document.querySelector("#toast"),
  windowsVersion: document.querySelector("#windows-version"),
  openProjectorTest: document.querySelector("#open-projector-test"),
};

const phaseMetadata = {
  hardware: ["PHASE 01", "Hardware inventory"],
  "obs-contract": ["PHASE 02", "OBS display engine"],
  projectors: ["PHASE 03", "Blended display output"],
  acceptance: ["PHASE 04", "Production acceptance"],
};

const state = {
  config: null,
  completingSoak: false,
  inputIndex: 0,
  notesTimer: null,
  obsSetup: null,
  snapshot: null,
  pendingConfirmation: null,
  projectorIndex: 0,
  session: null,
  sessionPollTimer: null,
  checks: {},
  toastTimer: null,
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Accept": "application/json", "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Retain the useful HTTP status when the body is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

function showToast(message) {
  clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  state.toastTimer = setTimeout(() => elements.toast.classList.remove("is-visible"), 3500);
}

function fieldSessionPath(suffix = "") {
  if (!state.session) throw new Error("Start a field-test session first");
  return `/api/v1/field-session/${state.session.id}${suffix}`;
}

function isSessionActive() {
  return state.session?.status === "in_progress";
}

function acceptSession(session) {
  const previousSession = state.session;
  state.session = session;
  state.checks = session?.checks || {};
  if (
    state.config
    && session
    && (!previousSession || session.mode_exercise.status === "running" || session.mode_exercise.status === "completed")
  ) {
    renderModeSelection(session.mode_exercise.mode_ids);
  }
  renderFieldSession();
  scheduleSessionPoll();
}

async function loadFieldSession() {
  try {
    const payload = await request("/api/v1/field-session");
    acceptSession(payload.session);
  } catch (error) {
    showToast(error.message);
  }
}

async function startFieldSession() {
  elements.startSession.disabled = true;
  try {
    acceptSession(await request("/api/v1/field-session", {
      method: "POST",
      body: "{}",
    }));
    showToast("Field-test session started");
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.startSession.disabled = false;
  }
}

async function saveSessionMetadata() {
  if (!isSessionActive()) return;
  try {
    acceptSession(await request(fieldSessionPath(), {
      method: "PUT",
      body: JSON.stringify({
        current_phase: state.session.current_phase,
        notes: elements.sessionNotes.value,
      }),
    }));
  } catch (error) {
    showToast(error.message);
  }
}

async function updateSessionCheck(checkId, checked) {
  if (!isSessionActive()) return;
  try {
    acceptSession(await request(fieldSessionPath(`/checks/${checkId}`), {
      method: "PUT",
      body: JSON.stringify({ checked }),
    }));
  } catch (error) {
    showToast(error.message);
  }
}

function asArray(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function renderDataList(container, items, secondaryField) {
  container.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No devices reported";
    container.append(empty);
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "data-item";
    const name = document.createElement("strong");
    name.textContent = item.Name || item.name || "Unnamed device";
    const detail = document.createElement("small");
    detail.textContent = item[secondaryField] || item.Status || "Status unavailable";
    row.append(name, detail);
    container.append(row);
  });
}

function renderSystem() {
  const system = state.snapshot.system;
  const gpus = asArray(system.gpus);
  const monitors = asArray(system.monitor_devices);
  const media = asArray(system.media_devices);
  elements.computerName.textContent = system.computer_name || "Unknown";
  elements.windowsVersion.textContent = system.windows || system.inventory_error || "Unknown OS";
  elements.gpuCount.textContent = String(gpus.length);
  elements.monitorDeviceCount.textContent = String(monitors.length);
  elements.mediaDeviceCount.textContent = String(media.length);
  renderDataList(elements.gpuList, gpus, "DriverVersion");
  renderDataList(elements.monitorDeviceList, monitors, "Manufacturer");
  renderDataList(elements.mediaDeviceList, media, "Manufacturer");
  elements.captureDeviceOptions.replaceChildren();
  media.forEach((device) => {
    const option = document.createElement("option");
    option.value = device.Name || device.name || "";
    if (option.value) elements.captureDeviceOptions.append(option);
  });
}

function renderInputMapper() {
  const mappings = state.session?.input_mappings || {};
  const sourceNames = Object.keys(mappings).sort();
  const active = isSessionActive();
  state.inputIndex = Math.min(state.inputIndex, Math.max(sourceNames.length - 1, 0));
  const sourceName = sourceNames[state.inputIndex] || "FB_01";
  const mapping = mappings[sourceName] || {};
  const passed = Object.values(mappings).filter((item) => item.signal_status === "pass").length;
  elements.inputMapProgress.textContent = `${passed} / ${sourceNames.length || 8} passed`;
  elements.inputStepNumber.textContent = `INPUT ${String(state.inputIndex + 1).padStart(2, "0")} / ${String(sourceNames.length || 8).padStart(2, "0")}`;
  elements.inputSourceName.textContent = sourceName;
  elements.inputFloorLabel.value = mapping.floor_label || "";
  elements.inputCaptureDevice.value = mapping.capture_device || "";
  elements.inputCaptureChannel.value = mapping.capture_channel || "";
  elements.inputSignalStatus.value = mapping.signal_status || "untested";
  elements.inputNotes.value = mapping.notes || "";
  elements.previousInput.disabled = !active || state.inputIndex === 0;
  elements.saveInput.disabled = !active;
  [elements.inputFloorLabel, elements.inputCaptureDevice, elements.inputCaptureChannel, elements.inputSignalStatus, elements.inputNotes]
    .forEach((control) => { control.disabled = !active; });
}

async function saveInputMapping() {
  if (!isSessionActive()) return;
  const sourceName = elements.inputSourceName.textContent;
  try {
    const session = await request(fieldSessionPath(`/inputs/${sourceName}`), {
      method: "PUT",
      body: JSON.stringify({
        floor_label: elements.inputFloorLabel.value.trim(),
        capture_device: elements.inputCaptureDevice.value.trim(),
        capture_channel: elements.inputCaptureChannel.value.trim(),
        signal_status: elements.inputSignalStatus.value,
        notes: elements.inputNotes.value.trim(),
      }),
    });
    acceptSession(session);
    const allPassed = Object.values(state.session.input_mappings)
      .every((mapping) => mapping.signal_status === "pass");
    if (allPassed && !state.checks["inputs-verified"]) {
      await updateSessionCheck("inputs-verified", true);
    }
    state.inputIndex = Math.min(
      state.inputIndex + 1,
      Object.keys(state.session.input_mappings).length - 1,
    );
    renderInputMapper();
    showToast(`${sourceName} observation saved`);
  } catch (error) {
    showToast(error.message);
  }
}

function renderObsChecks() {
  elements.obsCheckList.replaceChildren();
  state.snapshot.checks.forEach((check) => {
    const row = document.createElement("div");
    row.className = `check-row is-${check.status}`;
    const dot = document.createElement("span");
    dot.className = "check-dot";
    dot.setAttribute("aria-hidden", "true");
    const label = document.createElement("strong");
    label.textContent = check.label;
    const detail = document.createElement("small");
    detail.textContent = check.detail;
    row.append(dot, label, detail);
    elements.obsCheckList.append(row);
  });

  const stats = state.snapshot.obs.stats || {};
  elements.statFps.textContent = stats.active_fps == null ? "—" : Number(stats.active_fps).toFixed(2);
  elements.statRenderTime.textContent = stats.average_frame_render_time == null
    ? "—"
    : `${Number(stats.average_frame_render_time).toFixed(2)} ms`;
  elements.statRenderSkips.textContent = String(stats.render_skipped_frames ?? "—");
  elements.statOutputSkips.textContent = String(stats.output_skipped_frames ?? "—");
}

function renderObsSetup() {
  const setup = state.obsSetup;
  if (!setup) return;

  elements.obsInstallState.textContent = setup.installed ? "Detected" : "Not found";
  elements.obsInstallPath.textContent = setup.executable_path || "Set OBS_EXECUTABLE to override discovery";
  elements.obsInstallPath.title = setup.executable_path || "";
  elements.obsProcessState.textContent = setup.running ? "Running" : "Stopped";
  elements.obsLaunch.textContent = setup.running ? "Focus OBS" : "Launch OBS";
  elements.obsLaunch.disabled = !setup.installed;

  elements.obsWebsocketPort.value = String(setup.websocket_port);
  elements.obsWebsocketState.textContent = setup.websocket_listening
    ? "Listening"
    : setup.websocket_enabled
      ? "Enabled"
      : "Disabled";
  elements.obsWebsocketDetail.textContent = setup.websocket_listening
    ? `Port ${setup.websocket_port} is accepting connections`
    : setup.websocket_enabled
      ? `Port ${setup.websocket_port} will be checked after OBS starts`
      : `Port ${setup.websocket_port} is not enabled`;

  elements.obsAuthState.textContent = setup.authentication_required
    ? setup.controller_password_configured ? "Managed" : "OBS only"
    : "Not required";
  elements.obsAuthDetail.textContent = setup.authentication_required
    ? setup.controller_password_configured
      ? "Controller password environment is configured"
      : "Configure securely to synchronize credentials"
    : "Authentication should be enabled";

  elements.obsConfigureWebsocket.disabled = !setup.automatic_configuration_available;
  if (!setup.installed) {
    elements.obsSetupMessage.textContent = "OBS Studio was not found in a supported installation path.";
  } else if (setup.running && !setup.websocket_listening) {
    elements.obsSetupMessage.textContent = "Close OBS to configure automatically, or use the manual walkthrough while it is open.";
  } else if (setup.websocket_listening && setup.controller_password_configured) {
    elements.obsSetupMessage.textContent = "OBS WebSocket is ready for the controller.";
  } else if (setup.websocket_enabled) {
    elements.obsSetupMessage.textContent = "Start OBS, then refresh to verify the WebSocket listener.";
  } else {
    elements.obsSetupMessage.textContent = "Automatic configuration is available while OBS remains closed.";
  }
}

async function loadObsSetup() {
  try {
    state.obsSetup = await request("/api/v1/obs/setup");
    renderObsSetup();
  } catch (error) {
    elements.obsSetupMessage.textContent = error.message;
  }
}

async function launchOrFocusObs() {
  elements.obsLaunch.disabled = true;
  try {
    state.obsSetup = await request("/api/v1/obs/setup/launch", {
      method: "POST",
      body: "{}",
    });
    renderObsSetup();
    showToast(state.obsSetup.running ? "OBS focused" : "OBS launch requested");
    window.setTimeout(loadObsSetup, 1200);
  } catch (error) {
    showToast(error.message);
  } finally {
    elements.obsLaunch.disabled = false;
  }
}

function configureObsWebsocket() {
  const port = Number(elements.obsWebsocketPort.value);
  confirmAction({
    phrase: "CONFIGURE OBS",
    title: "Configure OBS WebSocket",
    detail: "Back up the existing WebSocket settings, enable authenticated access, generate a managed password, and store it for the controller account. OBS must be closed.",
    run: () => request("/api/v1/obs/setup/websocket", {
      method: "PUT",
      body: JSON.stringify({ port, confirmation: "CONFIGURE OBS" }),
    }),
  });
}

function saveManualObsPassword() {
  const password = elements.obsManualPassword.value;
  if (password.length < 12) {
    showToast("Use an OBS WebSocket password with at least 12 characters");
    return;
  }
  confirmAction({
    phrase: "SAVE OBS PASSWORD",
    title: "Save controller credential",
    detail: "Store this OBS WebSocket password for the Windows account running the controller. The value will not be returned by the API.",
    run: () => request("/api/v1/obs/setup/password", {
      method: "PUT",
      body: JSON.stringify({ password, confirmation: "SAVE OBS PASSWORD" }),
    }),
  });
}

function monitorLabel(monitor) {
  const dimensions = monitor.width && monitor.height ? ` · ${monitor.width}×${monitor.height}` : "";
  const position = monitor.x != null && monitor.y != null ? ` · (${monitor.x}, ${monitor.y})` : "";
  return `${monitor.index}: ${monitor.name}${dimensions}${position}`;
}

function actionButton(label, className, handler, disabled = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", handler);
  return button;
}

function renderProjectors() {
  elements.projectorRows.replaceChildren();
  elements.commissionedCount.textContent = String(state.snapshot.commissioned_count);
  const monitors = state.snapshot.obs.monitors || [];
  const targetCount = state.snapshot.projectors.length;
  document.querySelector("#output-target-count").textContent = String(targetCount);

  state.snapshot.projectors.forEach((projector) => {
    const row = document.createElement("div");
    row.className = "projector-row";
    row.setAttribute("role", "row");

    const label = document.createElement("strong");
    label.textContent = projector.label;
    const source = document.createElement("span");
    const outputName = projector.kind === "program" ? "OBS Program" : projector.source_name;
    source.textContent = outputName;

    const select = document.createElement("select");
    select.setAttribute("aria-label", `${projector.label} Windows display`);
    const unassigned = document.createElement("option");
    unassigned.value = "";
    unassigned.textContent = "Unassigned";
    select.append(unassigned);
    monitors.forEach((monitor) => {
      const option = document.createElement("option");
      option.value = String(monitor.index);
      option.textContent = monitorLabel(monitor);
      option.selected = projector.monitor_index === monitor.index;
      select.append(option);
    });

    const enabled = document.createElement("input");
    enabled.className = "projector-enabled";
    enabled.type = "checkbox";
    enabled.checked = projector.enabled;
    enabled.disabled = projector.monitor_index == null;
    enabled.setAttribute("aria-label", `Enable ${projector.label}`);
    select.addEventListener("change", () => {
      enabled.disabled = select.value === "";
      if (enabled.disabled) enabled.checked = false;
    });

    const actions = document.createElement("div");
    actions.className = "projector-actions";
    const save = actionButton("Save map", "secondary-button", () => {
      const monitorIndex = select.value === "" ? null : Number(select.value);
      confirmAction({
        phrase: `MAP ${projector.id.toUpperCase()}`,
        title: `Save ${projector.label} map`,
        detail: monitorIndex == null
          ? `Clear the Windows display assignment for ${projector.label}.`
          : `Assign ${outputName} to OBS monitor index ${monitorIndex}${enabled.checked ? " and enable it" : ""}.`,
        run: () => request(`/api/v1/commissioning/projectors/${projector.id}`, {
          method: "PUT",
          body: JSON.stringify({ monitor_index: monitorIndex, enabled: enabled.checked, confirmation: `MAP ${projector.id.toUpperCase()}` }),
        }),
      });
    });
    const test = actionButton(
      "Test output",
      "primary-button",
      () => confirmAction({
        phrase: `TEST ${projector.id.toUpperCase()}`,
        title: `Open ${projector.label} test`,
        detail: `Open ${outputName} full-screen on its saved Windows display. This can cover content currently visible on that display.`,
        run: () => request(`/api/v1/commissioning/projectors/${projector.id}/test`, {
          method: "POST",
          body: JSON.stringify({ confirmation: `TEST ${projector.id.toUpperCase()}` }),
        }),
      }),
      projector.monitor_index == null,
    );
    actions.append(save, test);
    row.append(label, source, select, enabled, actions);
    elements.projectorRows.append(row);
  });
  renderProjectorTest();
}

function renderProjectorTest() {
  const projectors = state.snapshot?.projectors || [];
  const results = state.session?.projector_tests || {};
  const active = isSessionActive();
  const selectedId = projectors[state.projectorIndex]?.id;
  elements.projectorTestTarget.replaceChildren();
  projectors.forEach((projector, index) => {
    const option = document.createElement("option");
    option.value = projector.id;
    option.textContent = `${projector.label} · ${projector.kind === "program" ? "OBS Program" : projector.source_name}`;
    option.selected = projector.id === selectedId;
    elements.projectorTestTarget.append(option);
    if (option.selected) state.projectorIndex = index;
  });
  const projector = projectors[state.projectorIndex];
  const result = projector ? results[projector.id] || {} : {};
  const passed = Object.values(results).filter((item) => item.status === "pass").length;
  elements.projectorTestProgress.textContent = `${passed} / ${projectors.length || 1} passed`;
  elements.projectorTestExpected.textContent = projector?.monitor_index == null
    ? "Assign a Windows display below first"
    : `Expected OBS monitor index ${projector.monitor_index}`;
  elements.projectorObservedDisplay.value = result.observed_display || "";
  elements.projectorTestStatus.value = result.status || "untested";
  elements.projectorTestNotes.value = result.notes || "";
  elements.openProjectorTest.disabled = !active || !projector || projector.monitor_index == null;
  elements.showDisplayIdentifier.disabled = !active || !projector || projector.monitor_index == null;
  elements.saveProjectorResult.disabled = !active || !projector;
  elements.projectorTestTarget.disabled = !active || !projectors.length;
  [elements.projectorObservedDisplay, elements.projectorTestStatus, elements.projectorTestNotes]
    .forEach((control) => { control.disabled = !active || !projector; });
}

function openSelectedProjectorTest() {
  const projector = state.snapshot?.projectors[state.projectorIndex];
  if (!projector) return;
  confirmAction({
    phrase: `TEST ${projector.id.toUpperCase()}`,
    title: `Open ${projector.label} test`,
    detail: `Open ${projector.kind === "program" ? "OBS Program" : projector.source_name} full-screen on OBS monitor index ${projector.monitor_index}. Confirm that it fills the blended display.`,
    run: () => request(`/api/v1/commissioning/projectors/${projector.id}/test`, {
      method: "POST",
      body: JSON.stringify({ confirmation: `TEST ${projector.id.toUpperCase()}` }),
    }),
  });
}

function showSelectedDisplayIdentifier() {
  const projector = state.snapshot?.projectors[state.projectorIndex];
  if (!projector) return;
  confirmAction({
    phrase: `IDENTIFY ${projector.id.toUpperCase()}`,
    title: `Show ${projector.label} ID card`,
    detail: `Cover OBS monitor index ${projector.monitor_index} with a ${projector.id.toUpperCase()} identification grid for 20 seconds. Click the card or press Escape to close it early.`,
    run: () => request(`/api/v1/commissioning/projectors/${projector.id}/identify`, {
      method: "POST",
      body: JSON.stringify({ confirmation: `IDENTIFY ${projector.id.toUpperCase()}` }),
    }),
  });
}

async function saveProjectorResult() {
  const projector = state.snapshot?.projectors[state.projectorIndex];
  if (!projector || !isSessionActive()) return;
  try {
    acceptSession(await request(fieldSessionPath(`/projectors/${projector.id}`), {
      method: "PUT",
      body: JSON.stringify({
        status: elements.projectorTestStatus.value,
        observed_display: elements.projectorObservedDisplay.value.trim(),
        notes: elements.projectorTestNotes.value.trim(),
      }),
    }));
    const allPassed = Object.values(state.session.projector_tests)
      .every((result) => result.status === "pass");
    if (allPassed && !state.checks["outputs-identified"]) {
      await updateSessionCheck("outputs-identified", true);
    }
    state.projectorIndex = Math.min(
      state.projectorIndex + 1,
      state.snapshot.projectors.length - 1,
    );
    renderProjectorTest();
    showToast(`${projector.label} result saved`);
  } catch (error) {
    showToast(error.message);
  }
}

async function loadPublicConfig() {
  try {
    state.config = await request("/api/v1/config");
    renderModeSelection(state.session?.mode_exercise.mode_ids || null);
  } catch (error) {
    showToast(error.message);
  }
}

function renderModeSelection(selectedModeIds = null) {
  const currentSelection = [...elements.modeSelection.querySelectorAll("input:checked")]
    .map((input) => input.value);
  const selected = new Set(selectedModeIds || currentSelection);
  const useDefaultSelection = selectedModeIds === null && currentSelection.length === 0;
  elements.modeSelection.replaceChildren();
  (state.config?.modes || []).filter((mode) => mode.enabled).forEach((mode) => {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = mode.id;
    checkbox.checked = useDefaultSelection || selected.has(mode.id);
    const name = document.createElement("span");
    name.textContent = mode.label;
    label.append(checkbox, name);
    elements.modeSelection.append(label);
  });
}

function selectedExerciseModes() {
  return [...elements.modeSelection.querySelectorAll("input:checked")]
    .map((input) => input.value);
}

function startModeExercise() {
  const modeIds = selectedExerciseModes();
  if (!modeIds.length) {
    showToast("Select at least one room mode");
    return;
  }
  const intervalSeconds = Number(elements.exerciseInterval.value);
  const targetCycles = Number(elements.exerciseTarget.value);
  confirmAction({
    phrase: "START TEST",
    title: "Start automated mode exercise",
    detail: `Cycle ${modeIds.length} selected modes every ${intervalSeconds} second(s) for ${targetCycles} cycle(s). Stop & Blank remains available throughout.`,
    run: () => request(fieldSessionPath("/mode-exercise/start"), {
      method: "POST",
      body: JSON.stringify({
        mode_ids: modeIds,
        interval_seconds: intervalSeconds,
        target_cycles: targetCycles,
      }),
    }),
  });
}

async function stopModeExercise() {
  if (!state.session) return;
  elements.stopExercise.disabled = true;
  try {
    acceptSession(await request(fieldSessionPath("/mode-exercise/stop"), {
      method: "POST",
      body: "{}",
    }));
    showToast("Mode exercise stopped; Blank activated");
  } catch (error) {
    showToast(error.message);
  }
}

function renderModeExercise() {
  const exercise = state.session?.mode_exercise;
  const running = exercise?.status === "running";
  elements.exerciseCycles.textContent = String(exercise?.completed_cycles || 0);
  elements.exerciseSwitches.textContent = `${exercise?.switch_count || 0} switches`;
  elements.exerciseMessage.textContent = running
    ? `Running ${exercise.current_mode_id || "next mode"}; use Stop & Blank before entering the array.`
    : exercise?.errors?.length
      ? exercise.errors.at(-1)
      : exercise?.status === "completed"
        ? "Target reached and Blank activated."
        : "Select modes and start a controlled switching run.";
  elements.startExercise.disabled = !isSessionActive() || running;
  elements.stopExercise.disabled = !running;
  elements.exerciseInterval.disabled = !isSessionActive() || running;
  elements.exerciseTarget.disabled = !isSessionActive() || running;
  elements.modeSelection.querySelectorAll("input").forEach((input) => {
    input.disabled = !isSessionActive() || running;
  });
}

function scheduleSessionPoll() {
  clearTimeout(state.sessionPollTimer);
  if (state.session?.mode_exercise.status !== "running") return;
  state.sessionPollTimer = setTimeout(loadFieldSession, 1200);
}

function renderFieldSession() {
  const session = state.session;
  const active = isSessionActive();
  if (!session) {
    elements.fieldSessionHeading.textContent = "No active room visit";
    elements.fieldSessionDetail.textContent = "Start a session before recording physical observations.";
  } else {
    elements.fieldSessionHeading.textContent = session.status === "completed"
      ? "Completed room visit"
      : "Room visit in progress";
    elements.fieldSessionDetail.textContent = `Started ${new Date(session.created_at).toLocaleString()} · ${session.id.slice(0, 8)}`;
  }
  elements.startSession.hidden = active;
  elements.startSession.textContent = session ? "Start another visit" : "Start room visit";
  elements.completeSession.hidden = !active;
  elements.jsonReport.hidden = !session;
  elements.htmlReport.hidden = !session;
  elements.sessionNotes.disabled = !active;
  if (document.activeElement !== elements.sessionNotes) {
    elements.sessionNotes.value = session?.notes || "";
  }
  if (session) {
    elements.jsonReport.href = `/api/v1/field-session/${session.id}/report.json`;
    elements.htmlReport.href = `/api/v1/field-session/${session.id}/report.html`;
  }
  document.querySelectorAll("[data-check]").forEach((checkbox) => {
    checkbox.checked = Boolean(state.checks[checkbox.dataset.check]);
    checkbox.disabled = !active;
  });
  elements.capturePreReboot.disabled = !active;
  elements.capturePostReboot.disabled = !active;
  renderInputMapper();
  renderProjectorTest();
  renderModeExercise();
  updateSoakTimer();
  renderRebootStatus();
  renderProgress();
}

function manualGateReady(keys) {
  return keys.every((key) => state.checks[key]);
}

function renderProgress() {
  if (!state.snapshot) return;
  const phaseReady = [
    manualGateReady(["inputs-verified", "outputs-identified", "hardware-soak"]),
    state.snapshot.obs_contract_ready && manualGateReady(["input-order", "opaque-scenes", "route-switching"]),
    state.snapshot.commissioned_count === 8 && manualGateReady(["geometry-locked", "seams-verified", "no-editor-output"]),
    Boolean(state.session?.soak.completed_at) && manualGateReady([
      "switch-cycles", "power-cycle", "input-recovery", "shortcuts-installed", "backup-restored", "staff-trained",
    ]),
  ];
  const completeCount = phaseReady.filter(Boolean).length;
  elements.completionCount.textContent = String(completeCount);
  elements.completionBar.style.width = `${completeCount * 25}%`;
  document.querySelectorAll(".step-tab").forEach((tab, index) => {
    tab.classList.toggle("is-ready", phaseReady[index]);
  });
  elements.acceptanceState.textContent = phaseReady[3] ? "Ready for release" : "Not ready";
  elements.acceptanceState.classList.toggle("is-ready", phaseReady[3]);
}

function renderSnapshot() {
  const online = !state.snapshot.obs_error;
  const simulation = Boolean(state.snapshot.obs.simulation);
  elements.engineStatus.classList.toggle("is-online", online);
  elements.engineStatus.classList.toggle("is-offline", !online);
  elements.engineState.textContent = !online
    ? "OBS unavailable"
    : simulation
      ? "Simulation mode"
      : "OBS connected";
  renderSystem();
  renderObsChecks();
  renderProjectors();
  renderFieldSession();
}

async function loadSnapshot(path = "/api/v1/commissioning", options = {}) {
  try {
    state.snapshot = await request(path, options);
    renderSnapshot();
  } catch (error) {
    showToast(error.message);
  }
}

function confirmAction(action) {
  state.pendingConfirmation = action;
  elements.confirmTitle.textContent = action.title;
  elements.confirmDetail.textContent = action.detail;
  elements.confirmPhrase.textContent = action.phrase;
  elements.confirmInput.value = "";
  elements.submitConfirm.disabled = true;
  elements.confirmDialog.showModal();
  elements.confirmInput.focus();
}

async function executeConfirmedAction() {
  if (!state.pendingConfirmation) return;
  elements.submitConfirm.disabled = true;
  try {
    const result = await state.pendingConfirmation.run();
    elements.confirmDialog.close();
    showToast("Commissioning command completed");
    if (result.projectors) {
      state.snapshot = result;
      renderSnapshot();
    } else if (result.id && result.input_mappings) {
      acceptSession(result);
    } else if (Object.hasOwn(result, "websocket_enabled")) {
      state.obsSetup = result;
      elements.obsManualPassword.value = "";
      renderObsSetup();
    } else {
      await loadSnapshot();
    }
  } catch (error) {
    showToast(error.message);
  } finally {
    state.pendingConfirmation = null;
  }
}

function activatePanel(panelName) {
  document.querySelectorAll(".step-tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.panelTarget === panelName);
  });
  document.querySelectorAll(".commission-panel").forEach((panel) => {
    const active = panel.dataset.panel === panelName;
    panel.classList.toggle("is-active", active);
    panel.hidden = !active;
  });
  const [kicker, title] = phaseMetadata[panelName];
  elements.phaseKicker.textContent = kicker;
  elements.phaseTitle.textContent = title;
  history.replaceState(null, "", `#${panelName}`);
  if (isSessionActive() && state.session.current_phase !== panelName) {
    state.session = { ...state.session, current_phase: panelName };
    clearTimeout(state.notesTimer);
    state.notesTimer = setTimeout(saveSessionMetadata, 250);
  }
}

function formatDuration(milliseconds) {
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return [hours, minutes, remainder].map((value) => String(value).padStart(2, "0")).join(":");
}

function updateSoakTimer() {
  const startedAt = Date.parse(state.session?.soak.started_at || "");
  const completed = Boolean(state.session?.soak.completed_at);
  const duration = Number(state.session?.soak.duration_seconds || 3600) * 1000;
  elements.resetSoak.disabled = !isSessionActive();
  if (completed) {
    elements.soakClock.textContent = "00:00:00";
    elements.soakMessage.textContent = "One-hour soak completed";
    elements.startSoak.disabled = true;
    renderProgress();
    return;
  }
  if (!startedAt) {
    elements.soakClock.textContent = "01:00:00";
    elements.soakMessage.textContent = "Timer has not started";
    elements.startSoak.disabled = !isSessionActive();
    return;
  }
  const remaining = duration - (Date.now() - startedAt);
  if (remaining <= 0) {
    completeSoak();
    return;
  }
  elements.soakClock.textContent = formatDuration(remaining);
  elements.soakMessage.textContent = "Keep all eight inputs and outputs active";
  elements.startSoak.disabled = true;
}

async function updateSoak(action) {
  if (!isSessionActive()) return;
  try {
    acceptSession(await request(fieldSessionPath("/soak"), {
      method: "PUT",
      body: JSON.stringify({ action }),
    }));
  } catch (error) {
    showToast(error.message);
  }
}

async function completeSoak() {
  if (state.completingSoak || !isSessionActive() || state.session.soak.completed_at) return;
  state.completingSoak = true;
  try {
    await updateSoak("complete");
    showToast("One-hour soak completed");
  } finally {
    state.completingSoak = false;
  }
}

function topologySignature(snapshot) {
  const system = snapshot?.data?.system || {};
  const obs = snapshot?.data?.obs || {};
  const names = (items) => asArray(items)
    .map((item) => item.Name || item.name || "")
    .filter(Boolean)
    .sort();
  return JSON.stringify({
    computer: system.computer_name || "",
    gpus: names(system.gpus),
    monitorDevices: names(system.monitor_devices),
    mediaDevices: names(system.media_devices),
    obsMonitors: asArray(obs.monitors)
      .map((monitor) => `${monitor.index}:${monitor.name}:${monitor.width}x${monitor.height}@${monitor.x},${monitor.y}`)
      .sort(),
  });
}

function renderRebootStatus() {
  const snapshots = state.session?.snapshots || [];
  const pre = [...snapshots].reverse().find((snapshot) => snapshot.kind === "pre_reboot");
  const post = [...snapshots].reverse().find((snapshot) => snapshot.kind === "post_reboot");
  if (pre && post) {
    elements.rebootMessage.textContent = topologySignature(pre) === topologySignature(post)
      ? "Pre/post topology matches. Verify outputs, then mark power-cycle recovery passed."
      : "Pre/post topology changed. Review the exported report before proceeding.";
  } else if (pre) {
    elements.rebootMessage.textContent = "Pre-reboot state saved. Reboot, restore the controller, then capture again.";
  } else {
    elements.rebootMessage.textContent = "Capture the room state before reboot, then capture it again after recovery.";
  }
}

async function captureTopologySnapshot(kind) {
  if (!isSessionActive()) return;
  try {
    acceptSession(await request(fieldSessionPath(`/snapshots/${kind}`), {
      method: "POST",
      body: "{}",
    }));
    showToast(kind === "pre_reboot" ? "Pre-reboot snapshot saved" : "Post-reboot snapshot saved");
  } catch (error) {
    showToast(error.message);
  }
}

function completeFieldSession() {
  confirmAction({
    phrase: "COMPLETE VISIT",
    title: "Complete field-test session",
    detail: "Capture a final room snapshot and close this visit. The reports remain available, and a new visit can be started afterward.",
    run: () => request(fieldSessionPath("/complete"), {
      method: "POST",
      body: "{}",
    }),
  });
}

document.querySelectorAll(".step-tab").forEach((tab) => {
  tab.addEventListener("click", () => activatePanel(tab.dataset.panelTarget));
});

document.querySelectorAll("[data-check]").forEach((checkbox) => {
  checkbox.disabled = true;
  checkbox.addEventListener("change", () => updateSessionCheck(checkbox.dataset.check, checkbox.checked));
});

elements.confirmInput.addEventListener("input", () => {
  const expected = state.pendingConfirmation?.phrase || "";
  elements.submitConfirm.disabled = elements.confirmInput.value.trim().toUpperCase() !== expected;
});
elements.confirmForm.addEventListener("submit", (event) => {
  event.preventDefault();
  executeConfirmedAction();
});
elements.cancelConfirm.addEventListener("click", () => {
  state.pendingConfirmation = null;
  elements.confirmDialog.close();
});
elements.refreshInventory.addEventListener("click", () => loadSnapshot(
  "/api/v1/commissioning/inventory/refresh",
  { method: "POST", body: "{}" },
));
elements.refreshObs.addEventListener("click", () => loadSnapshot());
elements.obsSetupRefresh.addEventListener("click", loadObsSetup);
elements.obsLaunch.addEventListener("click", launchOrFocusObs);
elements.obsConfigureWebsocket.addEventListener("click", configureObsWebsocket);
elements.obsSavePassword.addEventListener("click", saveManualObsPassword);
elements.startSession.addEventListener("click", startFieldSession);
elements.completeSession.addEventListener("click", completeFieldSession);
elements.sessionNotes.addEventListener("input", () => {
  clearTimeout(state.notesTimer);
  state.notesTimer = setTimeout(saveSessionMetadata, 650);
});
elements.previousInput.addEventListener("click", () => {
  state.inputIndex = Math.max(0, state.inputIndex - 1);
  renderInputMapper();
});
elements.saveInput.addEventListener("click", saveInputMapping);
elements.projectorTestTarget.addEventListener("change", () => {
  state.projectorIndex = Math.max(
    0,
    state.snapshot.projectors.findIndex(
      (projector) => projector.id === elements.projectorTestTarget.value,
    ),
  );
  renderProjectorTest();
});
elements.openProjectorTest.addEventListener("click", openSelectedProjectorTest);
elements.showDisplayIdentifier.addEventListener("click", showSelectedDisplayIdentifier);
elements.saveProjectorResult.addEventListener("click", saveProjectorResult);
elements.startExercise.addEventListener("click", startModeExercise);
elements.stopExercise.addEventListener("click", stopModeExercise);
elements.startSoak.addEventListener("click", () => updateSoak("start"));
elements.resetSoak.addEventListener("click", () => updateSoak("reset"));
elements.capturePreReboot.addEventListener("click", () => captureTopologySnapshot("pre_reboot"));
elements.capturePostReboot.addEventListener("click", () => captureTopologySnapshot("post_reboot"));

const initialPanel = location.hash.slice(1);
activatePanel(phaseMetadata[initialPanel] ? initialPanel : "hardware");
updateSoakTimer();
setInterval(updateSoakTimer, 1000);
loadSnapshot();
loadObsSetup();
loadPublicConfig();
loadFieldSession();