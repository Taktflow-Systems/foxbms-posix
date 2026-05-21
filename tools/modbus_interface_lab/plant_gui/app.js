const state = {
  status: null,
  registers: [],
  timer: null,
  workbookSheets: [],
};

const presets = [
  ["nominal", "Nominal"],
  ["fault_l2", "L2 Fault"],
  ["fault_l3", "L3 Fault"],
  ["sw_flashing", "SW Flashing"],
  ["power_saving", "Power Saving"],
  ["thermal_limit", "Thermal Limit"],
];

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || response.statusText);
  return payload;
}

async function loadStatus() {
  try {
    state.status = await api("/api/status");
    $("serverStatus").textContent = "Ready";
    $("endpointLine").textContent = `GUI ${state.status.http.host}:${state.status.http.port} | Modbus ${state.status.modbus.host}:${state.status.modbus.port}`;
    renderStatus();
    await loadRegisters();
  } catch (error) {
    $("serverStatus").textContent = "Error";
    $("eventLog").textContent = String(error);
  }
}

async function loadRegisters() {
  const query = encodeURIComponent($("registerSearch").value.trim());
  const payload = await api(`/api/registers?limit=500&q=${query}`);
  state.registers = payload.registers;
  renderRegisters();
}

function renderStatus() {
  const status = state.status;
  $("registerCount").textContent = status.registers;
  $("deviceAddress").textContent = status.device_address;
  $("presetName").textContent = status.state.preset;
  $("eventCount").textContent = `${status.events.length} events`;
  renderPresets(status.state.preset);
  renderUseCases(status.use_cases || []);
  $("eventLog").textContent = status.events.map(formatEvent).join("\n");
}

function renderPresets(activePreset) {
  $("presetGrid").innerHTML = presets
    .map(([key, label]) => {
      const active = key === activePreset ? " active" : "";
      return `<button class="preset${active}" data-preset="${esc(key)}" title="${esc(label)}">${esc(label)}</button>`;
    })
    .join("");
  document.querySelectorAll(".preset").forEach((button) => {
    button.addEventListener("click", () => setPreset(button.dataset.preset));
  });
}

function renderUseCases(cases) {
  $("useCases").innerHTML = cases
    .map(
      (item) => `
        <div class="useCase">
          <strong>${esc(item.id)}. ${esc(item.title)}</strong>
          <span>${esc(item.detail)}</span>
        </div>
      `,
    )
    .join("");
}

function renderRegisters() {
  $("registerRows").innerHTML = state.registers
    .map(
      (row) => `
        <tr>
          <td>${esc(row.table)}</td>
          <td>${esc(row.address)}</td>
          <td>${esc(row.name || "-")}</td>
          <td>${row.available === false ? "N/A (0xFFFF)" : esc(row.value)}</td>
          <td>${esc(row.source)}</td>
          <td>${row.available === false ? "not available" : row.writable ? "write" : "read"}</td>
        </tr>
      `,
    )
    .join("");
}

function formatEvent(event) {
  const time = new Date(event.ts * 1000).toLocaleTimeString();
  const fields = Object.entries(event)
    .filter(([key]) => !["ts", "event"].includes(key))
    .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
    .join(" ");
  return `${time} ${event.event}${fields ? " " + fields : ""}`;
}

async function uploadFile(event) {
  event.preventDefault();
  const file = $("file").files[0];
  if (!file) {
    $("importSummary").textContent = "Choose a CSV or Excel file first.";
    return;
  }
  if (isOcrEvidenceFile(file.name)) {
    $("importSummary").textContent =
      "OCR evidence CSVs are not register databases. Load a reviewed CSV/XLSX with address/count/value columns.";
    $("importSummary").classList.add("warning");
    return;
  }
  const body = new FormData();
  body.append("file", file);
  if (file.name.toLowerCase().endsWith(".xlsx")) {
    const sheet = $("workbookSheet").value;
    if (!sheet) {
      $("importSummary").textContent = "Choose a register sheet first.";
      return;
    }
    body.append("sheet_name", sheet);
  }
  $("importSummary").textContent = "Loading file...";
  $("importSummary").classList.remove("warning");
  try {
    const result = await api("/api/import", { method: "POST", body });
    const sheet = result.workbook_sheet ? ` from sheet ${result.workbook_sheet}` : "";
    $("importSummary").textContent = `${result.imported_registers} registers loaded${sheet}, ${result.skipped_rows} rows skipped.`;
    $("importSummary").classList.remove("warning");
    await loadStatus();
  } catch (error) {
    $("importSummary").textContent = String(error);
    $("importSummary").classList.add("warning");
  }
}

async function inspectWorkbook() {
  const file = $("file").files[0];
  state.workbookSheets = [];
  $("workbookSheet").innerHTML = "";
  $("workbookSheetWrap").classList.add("hidden");
  if (!file) {
    $("importSummary").textContent = "";
    return;
  }
  if (isOcrEvidenceFile(file.name)) {
    $("importSummary").textContent =
      "OCR evidence selected. This file is for review/search only, not plant-model import.";
    $("importSummary").classList.add("warning");
    return;
  }
  $("importSummary").classList.remove("warning");
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    $("importSummary").textContent = "CSV/TSV selected; no workbook sheet selection needed.";
    return;
  }

  const body = new FormData();
  body.append("file", file);
  $("importSummary").textContent = "Reading workbook sheets...";
  try {
    const result = await api("/api/workbook/sheets", { method: "POST", body });
    state.workbookSheets = result.sheets || [];
    $("workbookSheet").innerHTML = state.workbookSheets
      .map((sheet) => `<option value="${esc(sheet.name)}">${esc(sheet.name)}</option>`)
      .join("");
    $("workbookSheetWrap").classList.toggle("hidden", state.workbookSheets.length === 0);
    $("importSummary").textContent = state.workbookSheets.length
      ? `${state.workbookSheets.length} workbook sheets found.`
      : "No sheets found in workbook.";
  } catch (error) {
    $("importSummary").textContent = String(error);
  }
}

function isOcrEvidenceFile(filename) {
  const lower = filename.toLowerCase();
  return lower.includes("_ocr_lines") || lower.includes("_ocr_words");
}

async function setPreset(preset) {
  await api("/api/preset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preset }),
  });
  await loadStatus();
}

async function resetModel() {
  await api("/api/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  $("importSummary").textContent = "Plant model reset to generated BMS profile data.";
  await loadStatus();
}

$("uploadForm").addEventListener("submit", uploadFile);
$("file").addEventListener("change", inspectWorkbook);
$("resetModel").addEventListener("click", resetModel);
$("registerSearch").addEventListener("input", () => {
  clearTimeout(state.timer);
  state.timer = setTimeout(loadRegisters, 180);
});

loadStatus();
setInterval(loadStatus, 2500);
