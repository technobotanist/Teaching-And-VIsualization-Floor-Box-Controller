const elements = {
  activeScene: document.querySelector("#active-scene"),
  canvas: document.querySelector("#canvas-value"),
  clock: document.querySelector("#system-clock"),
  connection: document.querySelector("#connection"),
  connectionLabel: document.querySelector("#connection-label"),
  customApply: document.querySelector("#custom-apply"),
  customBlank: document.querySelector("#custom-blank"),
  customCancel: document.querySelector("#custom-cancel"),
  customClose: document.querySelector("#custom-close"),
  customDialog: document.querySelector("#custom-dialog"),
  customLiveState: document.querySelector("#custom-live-state"),
  customReset: document.querySelector("#custom-reset"),
  customRoutingGrid: document.querySelector("#custom-routing-grid"),
  customRoutingStatus: document.querySelector("#custom-routing-status"),
  fps: document.querySelector("#fps-value"),
  fullscreen: document.querySelector("#fullscreen-button"),
  modeGrid: document.querySelector("#mode-grid"),
  openOutputs: document.querySelector("#open-outputs-button"),
  outputCount: document.querySelector("#output-count"),
  outputState: document.querySelector("#output-state"),
  refresh: document.querySelector("#refresh-button"),
  roomName: document.querySelector("#room-name"),
  siteName: document.querySelector("#site-name"),
  toast: document.querySelector("#toast"),
};

const state = {
  busy: false,
  config: null,
  customRouting: null,
  status: null,
  toastTimer: null,
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Accept": "application/json" },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // The status code remains useful when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

function showToast(message) {
  window.clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  state.toastTimer = window.setTimeout(() => {
    elements.toast.classList.remove("is-visible");
  }, 3200);
}

function previewSegmentCount(mode) {
  const counts = {
    "lecture-single": 2,
    "lecture-double": 4,
    "lecture-single-background": 2,
    "lecture-double-background": 4,
    "multi-source": 8,
    "wraparound": 1,
    "blank": 8,
    "custom": 8,
  };
  return counts[mode.id] || 1;
}

function createModeTile(mode, index) {
  const button = document.createElement("button");
  button.className = "mode-tile";
  button.type = "button";
  button.dataset.modeId = mode.id;
  button.dataset.kind = mode.kind;
  button.style.setProperty("--tile-index", index);
  button.setAttribute("aria-pressed", "false");

  const topLine = document.createElement("span");
  topLine.className = "mode-topline";

  const key = document.createElement("span");
  key.className = "mode-key";
  key.textContent = mode.key;

  const modeState = document.createElement("span");
  modeState.className = "mode-state";
  modeState.textContent = "Ready";

  const name = document.createElement("span");
  name.className = "mode-name";
  name.textContent = mode.label;

  const detail = document.createElement("span");
  detail.className = "mode-detail";
  detail.textContent = mode.detail;

  const preview = document.createElement("span");
  preview.className = "layout-preview";
  preview.setAttribute("aria-hidden", "true");
  for (let number = 0; number < previewSegmentCount(mode); number += 1) {
    const segment = document.createElement("span");
    segment.className = "layout-segment";
    preview.append(segment);
  }

  topLine.append(key, modeState);
  button.append(topLine, name, detail, preview);
  button.addEventListener("click", () => activateMode(mode.id));
  return button;
}

function renderModes() {
  elements.modeGrid.replaceChildren();
  state.config.modes.forEach((mode, index) => {
    if (mode.enabled) {
      elements.modeGrid.append(createModeTile(mode, index));
    }
  });
  renderStatus();
}

function renderConfig() {
  const { room } = state.config;
  elements.roomName.textContent = room.name;
  elements.siteName.textContent = room.site;
  elements.canvas.textContent = `${room.canvas_width.toLocaleString()} × ${room.canvas_height.toLocaleString()}`;
  elements.fps.textContent = `${room.fps} FPS`;
  renderModes();
}

function renderStatus() {
  if (!state.status) {
    return;
  }

  const connected = state.status.obs.connected;
  elements.connection.classList.toggle("is-online", connected);
  elements.connection.classList.toggle("is-offline", !connected);
  elements.connectionLabel.textContent = state.status.obs.message;
  elements.activeScene.textContent = state.status.obs.current_scene || "No active scene";

  const totalOutputs = state.config?.outputs.projector_count || 8;
  const commissioned = state.status.commissioned_output_count;
  const activeMode = state.config?.modes.find(
    (mode) => mode.id === state.status.active_mode_id,
  );
  const activeLayout = activeMode?.label || "active layout";
  elements.outputCount.textContent = `${commissioned} of ${totalOutputs}`;
  elements.outputState.textContent = state.status.outputs_opened
    ? `${activeLayout} full screen`
    : commissioned > 0
      ? "Ready for full screen"
      : "Outputs locked";

  elements.openOutputs.disabled = state.busy || !connected || commissioned === 0;
  elements.openOutputs.title = commissioned === 0
    ? "Commission at least one projector display before presenting full screen"
    : `Open ${activeLayout} full screen on the commissioned projector displays`;
  elements.openOutputs.textContent = state.status.outputs_opened
    ? `Reopen ${activeLayout} full screen`
    : `Show ${activeLayout} full screen`;

  const customIsActive = state.status.active_mode_id === "custom";
  elements.customLiveState.textContent = customIsActive
    ? "05_CUSTOM IS LIVE"
    : "PROJECTOR ARRAY IS NOT SHOWING CUSTOM";
  elements.customLiveState.closest(".custom-live-banner").classList.toggle(
    "is-inactive",
    !customIsActive,
  );

  document.querySelectorAll(".mode-tile").forEach((tile) => {
    const isActive = tile.dataset.modeId === state.status.active_mode_id;
    tile.classList.toggle("is-active", isActive);
    tile.setAttribute("aria-pressed", String(isActive));
    tile.disabled = state.busy || !connected;
    const statusLabel = tile.querySelector(".mode-state");
    statusLabel.textContent = isActive ? "Live" : "Ready";
  });
}

function setBusy(busy) {
  state.busy = busy;
  renderStatus();
}

async function loadStatus({ announceErrors = false } = {}) {
  try {
    state.status = await request("/api/v1/status");
    renderStatus();
  } catch (error) {
    state.status = {
      obs: { connected: false, current_scene: null, message: "Controller unavailable" },
      active_mode_id: null,
      outputs_opened: false,
      commissioned_output_count: 0,
    };
    renderStatus();
    if (announceErrors) {
      showToast(error.message);
    }
  }
}

async function activateMode(modeId) {
  if (state.busy) {
    return;
  }
  if (modeId === "custom") {
    await openCustomRouting();
    return;
  }
  setBusy(true);
  try {
    state.status = await request(`/api/v1/modes/${encodeURIComponent(modeId)}/activate`, {
      method: "POST",
    });
    renderStatus();
  } catch (error) {
    showToast(error.message);
    await loadStatus();
  } finally {
    setBusy(false);
  }
}

function renderCustomRouting() {
  elements.customRoutingGrid.replaceChildren();
  state.customRouting.projectors.forEach((projector) => {
    const row = document.createElement("label");
    row.className = "route-row";

    const projectorLabel = document.createElement("span");
    projectorLabel.className = "route-projector";
    const projectorNumber = document.createElement("b");
    projectorNumber.textContent = projector.id.toUpperCase();
    const projectorName = document.createElement("span");
    projectorName.textContent = projector.label;
    projectorLabel.append(projectorNumber, projectorName);

    const arrow = document.createElement("span");
    arrow.className = "route-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "←";

    const select = document.createElement("select");
    select.dataset.projectorId = projector.id;
    select.setAttribute("aria-label", `${projector.label} source`);
    const blankOption = document.createElement("option");
    blankOption.value = "";
    blankOption.textContent = "Blank";
    select.append(blankOption);
    state.customRouting.sources.forEach((sourceName) => {
      const option = document.createElement("option");
      option.value = sourceName;
      option.textContent = `Floor box ${Number(sourceName.slice(-2))}`;
      select.append(option);
    });
    select.value = state.customRouting.assignments[projector.id] || "";
    select.addEventListener("change", () => {
      elements.customRoutingStatus.textContent = "Assignments changed. Apply routing to make them live.";
    });

    row.append(projectorLabel, arrow, select);
    elements.customRoutingGrid.append(row);
  });
  elements.customRoutingStatus.textContent = "Saved assignments loaded.";
}

async function openCustomRouting() {
  if (state.busy) {
    return;
  }
  setBusy(true);
  try {
    state.customRouting = await request("/api/v1/custom-routing");
    renderCustomRouting();
    if (!elements.customDialog.open) {
      elements.customDialog.showModal();
    }
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

function routingAssignmentsFromForm() {
  return Object.fromEntries(
    Array.from(elements.customRoutingGrid.querySelectorAll("select")).map((select) => [
      select.dataset.projectorId,
      select.value || null,
    ]),
  );
}

async function applyCustomRouting() {
  elements.customApply.disabled = true;
  elements.customRoutingStatus.textContent = "Applying projector routes…";
  try {
    const result = await request("/api/v1/custom-routing", {
      method: "PUT",
      headers: { "Accept": "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ assignments: routingAssignmentsFromForm() }),
    });
    state.customRouting = result;
    state.status = result.status;
    renderStatus();
    elements.customDialog.close();
    showToast("Custom projector routing is live");
  } catch (error) {
    elements.customRoutingStatus.textContent = error.message;
  } finally {
    elements.customApply.disabled = false;
  }
}

function resetCustomRouting() {
  elements.customRoutingGrid.querySelectorAll("select").forEach((select, index) => {
    select.value = state.customRouting.sources[index] || "";
  });
  elements.customRoutingStatus.textContent = "One-to-one assignments ready. Apply routing to make them live.";
}

async function blankCustomOutput() {
  elements.customDialog.close();
  await activateMode("blank");
  showToast("Projector array blanked. Saved custom assignments were not changed.");
}

async function openOutputs() {
  if (state.busy) {
    return;
  }
  setBusy(true);
  try {
    state.status = await request("/api/v1/outputs/open", { method: "POST" });
    renderStatus();
    const activeMode = state.config?.modes.find(
      (mode) => mode.id === state.status.active_mode_id,
    );
    showToast(`${activeMode?.label || "Active layout"} is full screen on the projector outputs`);
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

async function toggleFullscreen() {
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await document.documentElement.requestFullscreen();
    }
  } catch {
    showToast("Full screen is unavailable in this browser");
  }
}

function updateFullscreenLabel() {
  const isFullscreen = Boolean(document.fullscreenElement);
  const label = isFullscreen ? "Exit full screen" : "Enter full screen";
  elements.fullscreen.setAttribute("aria-label", label);
  elements.fullscreen.title = label;
}

function updateClock() {
  elements.clock.textContent = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date());
}

function handleShortcut(event) {
  if (event.altKey || event.ctrlKey || event.metaKey || event.repeat || state.busy) {
    return;
  }
  const mode = state.config?.modes.find((candidate) => candidate.key === event.key);
  if (mode?.enabled) {
    event.preventDefault();
    activateMode(mode.id);
  }
}

async function start() {
  updateClock();
  window.setInterval(updateClock, 30_000);
  try {
    const [config, status] = await Promise.all([
      request("/api/v1/config"),
      request("/api/v1/status"),
    ]);
    state.config = config;
    state.status = status;
    renderConfig();
  } catch (error) {
    elements.connection.classList.add("is-offline");
    elements.connectionLabel.textContent = "Controller unavailable";
    elements.activeScene.textContent = "Service offline";
    showToast(error.message);
  }

  window.setInterval(() => loadStatus(), 3000);
}

elements.refresh.addEventListener("click", () => loadStatus({ announceErrors: true }));
elements.fullscreen.addEventListener("click", toggleFullscreen);
elements.openOutputs.addEventListener("click", openOutputs);
elements.customClose.addEventListener("click", () => elements.customDialog.close());
elements.customCancel.addEventListener("click", () => elements.customDialog.close());
elements.customApply.addEventListener("click", applyCustomRouting);
elements.customReset.addEventListener("click", resetCustomRouting);
elements.customBlank.addEventListener("click", blankCustomOutput);
document.addEventListener("fullscreenchange", updateFullscreenLabel);
document.addEventListener("keydown", handleShortcut);
start();