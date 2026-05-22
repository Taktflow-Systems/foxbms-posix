const state = {
  model: null,
  selectedId: "1",
  activeRunId: null,
  pollTimer: null,
  monitoring: false,
  scenarioStates: {},
  case1ReadMode: "profile",
  case1CustomRegisters: "",
  signalBoard: {
    runId: null,
    samples: {},
    filter: "",
    plotMode: "all",
    pinned: {},
  },
};

const MONITOR_CYCLES = 3600;

const icons = {
  play:
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 4l14 8-14 8z"/></svg>',
  stop:
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="6" width="12" height="12"/></svg>',
  read:
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16"/><path d="M4 12h10"/><path d="M4 17h7"/></svg>',
  write:
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>',
  manual:
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18"/><path d="M5 8h14"/><path d="M7 16h10"/></svg>',
  monitor:
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h4l2-6 4 12 2-6h6"/><path d="M4 20h16"/></svg>',
};

const $ = (id) => document.getElementById(id);

function kindClass(value) {
  return String(value || "unknown")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function setRunState(text, tone = "idle") {
  const node = $("runState");
  node.textContent = text;
  node.dataset.tone = tone;
}

function setServerStatus(text, tone = "loading") {
  const node = $("serverStatus");
  node.textContent = text;
  node.dataset.tone = tone;
}

function runTone(status) {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "cancelled") return "warning";
  if (status === "running" || status === "created") return "running";
  return "idle";
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || response.statusText);
  return payload;
}

async function loadModel() {
  try {
    state.model = await api("/api/model");
    populateAdapters(state.model.adapters, state.model.defaults.adapter);
    applyDefaults(state.model.defaults);
    $("sourceLine").textContent = `${state.model.use_case_markdown} | ${state.model.profile_file}`;
    setServerStatus("Ready", "ready");
    render();
  } catch (error) {
    setServerStatus("Error", "error");
    $("runLog").textContent = String(error);
  }
}

function populateAdapters(adapters, defaultAdapter) {
  const select = $("adapter");
  select.innerHTML = Object.entries(adapters || {})
    .map(([key, adapter]) => `<option value="${esc(key)}">${esc(adapter.label || key)}</option>`)
    .join("");
  if (defaultAdapter && adapters[defaultAdapter]) select.value = defaultAdapter;
  updateAdapterHints();
}

function applyDefaults(defaults) {
  for (const [key, value] of Object.entries(defaults)) {
    const input = $(key);
    if (input) input.value = value;
  }
  $("dry_run").checked = true;
  $("allow_writes").checked = false;
}

function updateAdapterHints() {
  const adapter = $("adapter").value;
  if (adapter === "backend_polling_api") {
    $("host").placeholder = "Backend URL or host";
    $("port").placeholder = "Backend API port";
    return;
  }
  $("host").placeholder = "BMS IP or host";
  $("port").placeholder = "Modbus port";
}

function selectedCase() {
  return state.model.use_cases.find((item) => item.id === state.selectedId) || state.model.use_cases[0];
}

function render() {
  if (!state.model) return;
  renderCases();
  renderDetails();
}

function renderCases() {
  $("caseList").innerHTML = state.model.use_cases
    .map((item) => {
      const active = item.id === state.selectedId ? " active" : "";
      return `
        <button class="caseCard${active}" data-id="${esc(item.id)}" title="${esc(item.title)}">
          <span class="caseId">${esc(item.id)}</span>
          <span>
            <span class="caseTitle">${esc(item.title)}</span>
            <span class="caseSub">${esc(item.available_test || item.status)}</span>
          </span>
          <span class="kind ${esc(kindClass(item.kind))}">${esc(item.kind)}</span>
        </button>
      `;
    })
    .join("");

  document.querySelectorAll(".caseCard").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedId = button.dataset.id;
      render();
    });
  });
}

function renderDetails() {
  const item = selectedCase();
  $("detailTitle").textContent = `${item.id}. ${item.title}`;
  $("detailMeta").textContent = `${item.available_test} | ${item.status}`;
  $("detailText").textContent = item.detail || item.title;
  $("actionFlow").innerHTML = renderActionFlow(item);
  $("operationPlan").innerHTML = renderOperations(item);
  $("csvSnippets").innerHTML = renderSnippets(item);
  $("monitorSelected").innerHTML = `${icons.monitor}<span>Monitor 1s</span>`;
  $("monitorSelected").title = `Live read every 1 second; stop manually or after ${MONITOR_CYCLES} cycles`;
  $("monitorSelected").classList.toggle("hidden", item.id !== "1");
  $("runSelected").innerHTML = `${icons.play}<span>Run</span>`;
  $("cancelRun").innerHTML = `${icons.stop}<span>Cancel</span>`;
  bindActionButtons(item);
  bindRegisterReadControls(item);
  renderSignalBoard(item);
}

function currentFlowState(item) {
  return state.scenarioStates[item.id] || item.action_flow?.initial_state || "ready";
}

function currentActionIndex(item) {
  const actions = item.action_flow?.actions || [];
  const flowState = currentFlowState(item);
  if (flowState === (item.action_flow?.initial_state || "ready")) return 0;
  const doneIndex = actions.findIndex((action) => action.to_state === flowState);
  return doneIndex >= 0 ? doneIndex + 1 : 0;
}

function renderActionFlow(item) {
  const actions = item.action_flow?.actions || [];
  if (!actions.length) return '<span class="chip manual">No action buttons found</span>';
  const availableIndex = currentActionIndex(item);
  return actions
    .map((action, index) => {
      const status = index < availableIndex ? "done" : index === availableIndex ? "available" : "locked";
      const disabled = status === "available" ? "" : " disabled";
      const target = action.target || action.label;
      return `
        <button class="flowButton ${status}" data-action-id="${esc(action.id)}" title="${esc(action.from_state)} -> ${esc(action.to_state)}"${disabled}>
          <span class="flowVerb">${esc(action.verb)}</span>
          <span class="flowTarget">${esc(target)}</span>
        </button>
      `;
    })
    .join("");
}

function bindActionButtons(item) {
  document.querySelectorAll(".flowButton.available").forEach((button) => {
    button.addEventListener("click", () => transitionAction(item, button.dataset.actionId));
  });
  $("resetFlow").onclick = () => {
    state.scenarioStates[item.id] = item.action_flow?.initial_state || "ready";
    renderDetails();
  };
}

async function transitionAction(item, actionId) {
  try {
    const result = await api("/api/action/transition", {
      method: "POST",
      body: JSON.stringify({
        scenario_id: item.id,
        action_id: actionId,
        state: currentFlowState(item),
      }),
    });
    state.scenarioStates[item.id] = result.state;
    $("runLog").textContent += `${$("runLog").textContent ? "\n" : ""}action ${result.action.label}: ${result.previous_state} -> ${result.state}`;
    renderDetails();
  } catch (error) {
    setRunState("Action blocked", "warning");
    $("runLog").textContent += `${$("runLog").textContent ? "\n" : ""}${String(error)}`;
  }
}

function renderOperations(item) {
  const chips = [];
  if (item.id === "1") {
    chips.push(renderRegisterReadControl());
  }
  for (const read of item.reads || []) {
    chips.push(
      `<span class="chip">${icons.read} ${esc(read.name)} ${esc(read.address)}:${esc(read.count)}</span>`,
    );
  }
  for (const write of item.writes || []) {
    chips.push(
      `<span class="chip write">${icons.write} ${esc(write.name)} ${esc(write.address)} = ${esc(write.default)}</span>`,
    );
  }
  if (item.kind === "manual") {
    chips.push(`<span class="chip manual">${icons.manual} Manual gate</span>`);
  }
  return chips.length ? chips.join("") : '<span class="chip manual">No executable Modbus plan</span>';
}

function renderRegisterReadControl() {
  return `
    <div class="registerRead">
      <label>
        Read Source
        <select id="read_mode" name="read_mode">
          <option value="profile">All Available</option>
          <option value="custom">Custom</option>
        </select>
      </label>
      <label>
        Register Text
        <input id="custom_registers" name="custom_registers" autocomplete="off" placeholder="40071:10, input:30001:4" />
      </label>
    </div>
  `;
}

function bindRegisterReadControls(item) {
  const mode = $("read_mode");
  const custom = $("custom_registers");
  if (item.id !== "1" || !mode || !custom) return;

  mode.value = state.case1ReadMode;
  custom.value = state.case1CustomRegisters;
  custom.disabled = mode.value !== "custom";

  mode.addEventListener("change", () => {
    state.case1ReadMode = mode.value;
    custom.disabled = mode.value !== "custom";
    if (mode.value === "custom") custom.focus();
  });
  custom.addEventListener("focus", () => {
    state.case1ReadMode = "custom";
    mode.value = "custom";
    custom.disabled = false;
  });
  custom.addEventListener("input", () => {
    state.case1CustomRegisters = custom.value;
  });
}

function signalEntries() {
  return Object.values(state.signalBoard.samples).sort((a, b) => a.label.localeCompare(b.label));
}

function visibleSignalEntries() {
  const filter = state.signalBoard.filter.trim().toLowerCase();
  const entries = signalEntries();
  if (!filter) return entries;
  return entries.filter((entry) => entry.label.toLowerCase().includes(filter) || entry.addressText.includes(filter));
}

function collectSignals(run) {
  const samples = {};
  for (const event of run.events || []) {
    if (event.event !== "read_ok" || !Array.isArray(event.raw)) continue;
    const baseAddress = Number(event.address);
    for (let index = 0; index < event.raw.length; index += 1) {
      const value = Number(event.raw[index]);
      if (!Number.isFinite(value)) continue;
      const address = Number.isFinite(baseAddress) ? baseAddress + index : index;
      const key = `${event.name}|${address}`;
      if (!samples[key]) {
        samples[key] = {
          key,
          label: `${event.name} [${address}]`,
          source: event.name,
          address,
          addressText: String(address),
          points: [],
          latest: null,
        };
      }
      const point = { ts: Number(event.ts), value };
      samples[key].points.push(point);
      samples[key].latest = point;
    }
  }
  return samples;
}

function renderSignalBoard(item) {
  const board = $("signalBoard");
  if (!board) return;
  if (item.id !== "1") {
    board.classList.add("hidden");
    return;
  }
  board.classList.remove("hidden");

  const entries = visibleSignalEntries();
  const total = signalEntries().length;
  const pinnedCount = Object.keys(state.signalBoard.pinned).length;
  const liveText = state.monitoring ? ` | live 1s monitor running | max ${MONITOR_CYCLES} cycles` : "";
  $("signalBoardMeta").textContent =
    total > 0
      ? `${total} signals captured from run ${state.signalBoard.runId || ""} | ${pinnedCount} pinned${liveText}`
      : state.monitoring
        ? `Live 1s monitor started; waiting for the first read. Max ${MONITOR_CYCLES} cycles.`
        : "Run use case 1 against hardware or the plant model, or start the 1s monitor.";
  $("signalPlotMode").value = state.signalBoard.plotMode;
  $("signalFilter").value = state.signalBoard.filter;
  $("startSignalMonitor").disabled = state.monitoring;
  $("startSignalMonitor").title = `Live read every 1 second; stop manually or after ${MONITOR_CYCLES} cycles`;
  $("stopSignalMonitor").disabled = !state.monitoring;
  $("stopSignalMonitor").title = "Stop the active live monitor run";
  $("signalChart").innerHTML = renderSignalChart(entries);
  $("signalList").innerHTML = renderSignalList(entries, total);
  bindSignalBoardControls();
}

function plottedEntries(entries) {
  if (state.signalBoard.plotMode === "pinned") {
    return signalEntries().filter((entry) => state.signalBoard.pinned[entry.key]);
  }
  return entries;
}

function renderSignalChart(entries) {
  const plotted = plottedEntries(entries);
  if (!plotted.length) {
    return '<div class="emptyChart">No plotted signal yet. Use All Visible, or pin signals from the table.</div>';
  }

  const width = 900;
  const height = 260;
  const pad = { left: 54, right: 18, top: 18, bottom: 32 };
  const points = plotted.flatMap((entry) => entry.points);
  let minTs = Math.min(...points.map((point) => point.ts));
  let maxTs = Math.max(...points.map((point) => point.ts));
  let minValue = Math.min(...points.map((point) => point.value));
  let maxValue = Math.max(...points.map((point) => point.value));
  if (minTs === maxTs) {
    minTs -= 1;
    maxTs += 1;
  }
  if (minValue === maxValue) {
    minValue -= 1;
    maxValue += 1;
  }

  const x = (ts) => pad.left + ((ts - minTs) / (maxTs - minTs)) * (width - pad.left - pad.right);
  const y = (value) => height - pad.bottom - ((value - minValue) / (maxValue - minValue)) * (height - pad.top - pad.bottom);
  const colors = ["#147a59", "#256f9c", "#a76516", "#b5413c", "#5b6c2a", "#6b4ea0", "#007d7e", "#8f4b2e"];
  const lines = plotted
    .map((entry, index) => {
      const color = colors[index % colors.length];
      const coords = entry.points.map((point) => `${x(point.ts).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ");
      const last = entry.points[entry.points.length - 1];
      return `
        <polyline class="seriesLine" points="${coords}" fill="none" stroke="${color}" />
        <circle cx="${x(last.ts).toFixed(1)}" cy="${y(last.value).toFixed(1)}" r="3.2" fill="${color}" />
      `;
    })
    .join("");
  const legend = plotted
    .slice(0, 10)
    .map((entry, index) => {
      const color = colors[index % colors.length];
      return `<span><i style="background:${color}"></i>${esc(entry.label)}</span>`;
    })
    .join("");

  return `
    <svg class="plotSvg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Signal plot">
      <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" class="axis" />
      <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" class="axis" />
      <text x="8" y="${pad.top + 5}" class="axisLabel">${maxValue.toFixed(1)}</text>
      <text x="8" y="${height - pad.bottom}" class="axisLabel">${minValue.toFixed(1)}</text>
      ${lines}
    </svg>
    <div class="plotLegend">${legend}${plotted.length > 10 ? `<span>+${plotted.length - 10} more</span>` : ""}</div>
  `;
}

function renderSignalList(entries, total) {
  if (!total) return '<div class="emptySignals">No live signal values captured yet.</div>';
  if (!entries.length) return '<div class="emptySignals">No signal matches the filter.</div>';
  return `
    <div class="signalRows signalRowsHeader" aria-hidden="true">
      <span></span>
      <span>Signal</span>
      <span>Value</span>
      <span>Samples</span>
    </div>
    <div class="signalRows signalRowsBody">
      ${entries
        .map((entry) => {
          const pinned = Boolean(state.signalBoard.pinned[entry.key]);
          return `
            <button class="pinButton ${pinned ? "pinned" : ""}" data-signal-key="${esc(entry.key)}" title="${pinned ? "Unpin" : "Pin"} ${esc(entry.label)}">
              <span>${pinned ? "Unpin" : "Pin"}</span>
            </button>
            <span class="signalName">${esc(entry.label)}</span>
            <span class="signalValue">${esc(entry.latest?.value ?? "")}</span>
            <span class="signalSamples">${entry.points.length}</span>
          `;
        })
        .join("")}
    </div>
  `;
}

function bindSignalBoardControls() {
  $("signalPlotMode").onchange = () => {
    state.signalBoard.plotMode = $("signalPlotMode").value;
    renderSignalBoard(selectedCase());
  };
  $("signalFilter").oninput = () => {
    state.signalBoard.filter = $("signalFilter").value;
    renderSignalBoard(selectedCase());
  };
  $("pinVisibleSignals").onclick = () => {
    for (const entry of visibleSignalEntries()) state.signalBoard.pinned[entry.key] = true;
    state.signalBoard.plotMode = "pinned";
    renderSignalBoard(selectedCase());
  };
  $("clearPinnedSignals").onclick = () => {
    state.signalBoard.pinned = {};
    renderSignalBoard(selectedCase());
  };
  $("startSignalMonitor").onclick = startSignalMonitor;
  $("stopSignalMonitor").onclick = stopSignalMonitor;
  document.querySelectorAll(".pinButton").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.signalKey;
      if (state.signalBoard.pinned[key]) delete state.signalBoard.pinned[key];
      else state.signalBoard.pinned[key] = true;
      renderSignalBoard(selectedCase());
    });
  });
}

function renderSnippets(item) {
  const snippets = item.snippets || [];
  if (!snippets.length) return '<div class="snippet"><small>No CSV match</small>No matching OCR line found.</div>';
  return snippets
    .map(
      (row) => `
        <div class="snippet">
          <small>${esc(row.sheet_key)} | ${esc(row.source_image)} | line ${esc(row.line_index)}</small>
          ${esc(row.text)}
        </div>
      `,
    )
    .join("");
}

function formPayload(id) {
  const numeric = [
    "port",
    "unit_id",
    "cycles",
    "interval",
    "sessions",
    "hold_seconds",
    "write_value",
  ];
  const payload = {
    scenario_id: id,
    adapter: $("adapter").value,
    host: $("host").value.trim(),
    address_base: state.model.defaults.address_base || "auto",
    dry_run: $("dry_run").checked,
    allow_writes: $("allow_writes").checked,
  };
  for (const key of numeric) {
    payload[key] = Number($(key).value);
  }
  if (id === "1") {
    payload.read_mode = $("read_mode")?.value || state.case1ReadMode;
    payload.custom_registers = $("custom_registers")?.value || state.case1CustomRegisters;
  }
  return payload;
}

async function runSelected() {
  const item = selectedCase();
  setRunState("Starting", "running");
  $("runLog").textContent = "";
  try {
    const payload = await api("/api/run", {
      method: "POST",
      body: JSON.stringify(formPayload(item.id)),
    });
    state.activeRunId = payload.run_id;
    pollRun();
  } catch (error) {
    setRunState("Error", "error");
    $("runLog").textContent = String(error);
  }
}

function openSignalDashboard() {
  if (state.selectedId !== "1") {
    state.selectedId = "1";
    render();
  }
  $("signalBoard").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function startSignalMonitor() {
  openSignalDashboard();
  if ($("dry_run").checked) {
    state.monitoring = false;
    setRunState("Monitor blocked", "warning");
    $("runLog").textContent = "Live monitor requires Dry Run to be unchecked.";
    renderSignalBoard(selectedCase());
    return;
  }
  $("interval").value = 1;
  setRunState(`Starting 1s monitor (${MONITOR_CYCLES} max)`, "running");
  $("runLog").textContent = "";
  state.monitoring = true;
  state.signalBoard.samples = {};
  state.signalBoard.runId = null;
  renderSignalBoard(selectedCase());
  try {
    const payload = {
      ...formPayload("1"),
      dry_run: false,
      allow_writes: false,
      cycles: MONITOR_CYCLES,
      interval: 1,
    };
    const result = await api("/api/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.activeRunId = result.run_id;
    pollRun();
  } catch (error) {
    state.monitoring = false;
    setRunState("Monitor error", "error");
    $("runLog").textContent = String(error);
    renderSignalBoard(selectedCase());
  }
}

async function stopSignalMonitor() {
  state.monitoring = false;
  await cancelRun();
  renderSignalBoard(selectedCase());
}

async function cancelRun() {
  if (!state.activeRunId) return;
  try {
    await api(`/api/run/${state.activeRunId}/cancel`, { method: "POST", body: "{}" });
  } catch (error) {
    $("runLog").textContent += `\n${String(error)}`;
  }
}

async function pollRun() {
  if (!state.activeRunId) return;
  clearTimeout(state.pollTimer);
  try {
    const run = await api(`/api/run/${state.activeRunId}`);
    setRunState(`${run.status}${run.exit_code === null ? "" : ` (${run.exit_code})`}`, runTone(run.status));
    $("runLog").textContent = run.events.map(formatEvent).join("\n");
    if (run.scenario_id === "1") {
      state.signalBoard.runId = run.run_id;
      state.signalBoard.samples = collectSignals(run);
      renderSignalBoard(selectedCase());
    }
    const done = ["completed", "failed", "cancelled"].includes(run.status);
    if (done) state.monitoring = false;
    if (!done) state.pollTimer = setTimeout(pollRun, 600);
    else if (run.scenario_id === "1") renderSignalBoard(selectedCase());
  } catch (error) {
    state.monitoring = false;
    setRunState("Error", "error");
    $("runLog").textContent += `\n${String(error)}`;
    renderSignalBoard(selectedCase());
  }
}

function formatEvent(event) {
  const time = new Date(event.ts * 1000).toLocaleTimeString();
  const parts = Object.entries(event)
    .filter(([key]) => !["ts", "event", "scenario_id"].includes(key))
    .map(([key, value]) => `${key}=${JSON.stringify(value)}`);
  return `${time} ${event.event}${parts.length ? " " + parts.join(" ") : ""}`;
}

$("runSelected").addEventListener("click", runSelected);
$("cancelRun").addEventListener("click", cancelRun);
$("monitorSelected").addEventListener("click", startSignalMonitor);
$("adapter").addEventListener("change", updateAdapterHints);
loadModel();
