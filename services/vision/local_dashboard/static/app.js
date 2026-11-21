// EdgeFlow AI -- Vision Local Dashboard. Plain JS, no build step: the browser's native Basic
// Auth prompt (triggered by the server's 401 + WWW-Authenticate header) handles credentials for
// every same-origin fetch() below, so this file never touches a password itself.

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function fmtTime(ms) {
  return ms ? new Date(ms).toLocaleTimeString() : "--";
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
$$(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab-btn").forEach((b) => b.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------------------------------------------------------------------------
// Live status polling
// ---------------------------------------------------------------------------
let knownNodeIds = [];

function renderStreams(nodeIds) {
  if (JSON.stringify(nodeIds) === JSON.stringify(knownNodeIds)) return;
  knownNodeIds = nodeIds;
  $("#streams").innerHTML = nodeIds.map(
    (id) => `<div><div class="muted">${id}</div><img src="/stream/${id}" alt="live stream ${id}" /></div>`
  ).join("");
}

function renderRuntimeCards(stats, health) {
  const latency = (stats.latency_ms && stats.latency_ms.total_ms) || {};
  const hardware = (health && health.hardware) || {};
  const cards = [
    ["FPS", stats.processed_fps],
    ["Frames OK", stats.frames_ok],
    ["Frames failed", stats.frames_failed],
    ["Latency p50/p95", latency.p50 != null ? `${latency.p50}/${latency.p95} ms` : "--"],
    ["CPU temp", hardware.cpu_temp_c != null ? `${hardware.cpu_temp_c} C` : "--"],
    ["Status", (health && health.status) || "--"],
  ];
  $("#runtime-cards").innerHTML = cards.map(
    ([label, value]) => `<div class="stat"><div class="label">${label}</div><div class="value">${value}</div></div>`
  ).join("");
}

function setStatusPill(ok, text) {
  const pill = $("#status-pill");
  pill.textContent = text;
  pill.className = "pill " + (ok ? "success" : "critical");
}

async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderStreams(data.node_ids || []);
    renderRuntimeCards(data.stats || {}, data.last_health);
    setStatusPill(true, (data.last_health && data.last_health.status) || "RUNNING");
    if (!$("#conf-threshold").value && data.identity) {
      $("#conf-threshold").value = data.identity.confidence_threshold || "";
    }
  } catch (e) {
    setStatusPill(false, "unreachable");
  }
}
pollStatus();
setInterval(pollStatus, 2000);

// ---------------------------------------------------------------------------
// Controls
// ---------------------------------------------------------------------------
$("#btn-restart").addEventListener("click", async () => {
  $("#control-feedback").textContent = "Restarting...";
  const res = await fetch("/api/control/restart", { method: "POST" });
  $("#control-feedback").textContent = res.ok ? "Restart requested." : "Restart failed.";
});

$("#btn-apply-conf").addEventListener("click", async () => {
  const value = parseFloat($("#conf-threshold").value);
  const res = await fetch("/api/control/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confidence_threshold: value }),
  });
  const body = await res.json();
  $("#control-feedback").textContent = res.ok ? "Applied." : `Failed: ${body.detail}`;
});

// ---------------------------------------------------------------------------
// History tables
// ---------------------------------------------------------------------------
async function refreshTelemetry() {
  const res = await fetch("/api/telemetry/history?limit=50");
  const { records } = await res.json();
  $("#telemetry-table tbody").innerHTML = records.map((r) => `
    <tr><td>${fmtTime(r.timestamp_ms)}</td><td>${r.node_id}</td><td>${r.current_phase_id || "--"}</td>
    <td>${(r.approaches || []).map((a) => `${a.approach_id}:${(a.queue_vehicles || 0).toFixed(1)}`).join(" ")}</td></tr>
  `).join("");
}
async function refreshHealth() {
  const res = await fetch("/api/health/history?limit=50");
  const { records } = await res.json();
  $("#health-table tbody").innerHTML = records.map((r) => `
    <tr><td>${fmtTime(r.timestamp_ms)}</td><td>${r.status || "--"}</td>
    <td>${(r.runtime && r.runtime.processed_fps) || "--"}</td>
    <td>${(r.hardware && r.hardware.cpu_temp_c) || "--"}</td></tr>
  `).join("");
}
async function refreshEvents() {
  const res = await fetch("/api/events?limit=50");
  const { records } = await res.json();
  $("#events-table tbody").innerHTML = records.map((r) => `
    <tr><td>${fmtTime(r.timestamp_ms)}</td><td>${r.event_type}</td><td>${JSON.stringify(r.detail)}</td></tr>
  `).join("");
}
$("#btn-refresh-telemetry").addEventListener("click", refreshTelemetry);
$("#btn-refresh-health").addEventListener("click", refreshHealth);
$("#btn-refresh-events").addEventListener("click", refreshEvents);
refreshTelemetry(); refreshHealth(); refreshEvents();

// ---------------------------------------------------------------------------
// ROI calibration
// ---------------------------------------------------------------------------
let roiState = { frameSize: [640, 480], approaches: {}, polygons: {}, currentPoints: [] };

function roiKey() {
  return `${$("#roi-node").value}::${$("#roi-approach").value}`;
}

function redrawRoiCanvas() {
  const canvas = $("#roi-canvas");
  const img = $("#roi-snapshot");
  canvas.width = img.clientWidth || roiState.frameSize[0];
  canvas.height = img.clientHeight || roiState.frameSize[1];
  const sx = canvas.width / roiState.frameSize[0];
  const sy = canvas.height / roiState.frameSize[1];
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const drawPoly = (points, color, closed) => {
    if (!points.length) return;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach(([x, y], i) => {
      const px = x * sx, py = y * sy;
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    if (closed) ctx.closePath();
    ctx.stroke();
    points.forEach(([x, y]) => {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x * sx, y * sy, 3, 0, Math.PI * 2);
      ctx.fill();
    });
  };

  Object.entries(roiState.polygons).forEach(([key, points]) => {
    drawPoly(points, key === roiKey() ? "#0284c7" : "#16a34a", true);
  });
  drawPoly(roiState.currentPoints, "#dc2626", false);
}

async function loadRoi() {
  const res = await fetch("/api/roi");
  const data = await res.json();
  roiState.frameSize = data.frame_size;
  roiState.approaches = data.approaches;
  roiState.polygons = {};
  if (data.current) {
    Object.entries(data.current.nodes).forEach(([nodeId, apps]) => {
      Object.entries(apps).forEach(([approachId, poly]) => {
        roiState.polygons[`${nodeId}::${approachId}`] = poly;
      });
    });
  }
  const nodeSel = $("#roi-node");
  nodeSel.innerHTML = Object.keys(roiState.approaches).map((n) => `<option value="${n}">${n}</option>`).join("");
  updateApproachOptions();
  redrawRoiCanvas();
}
function updateApproachOptions() {
  const approaches = roiState.approaches[$("#roi-node").value] || [];
  $("#roi-approach").innerHTML = approaches.map((a) => `<option value="${a}">${a}</option>`).join("");
}
$("#roi-node").addEventListener("change", () => { updateApproachOptions(); redrawRoiCanvas(); });
$("#roi-approach").addEventListener("change", redrawRoiCanvas);

$("#btn-roi-refresh-snapshot").addEventListener("click", () => {
  const nodeId = $("#roi-node").value || knownNodeIds[0];
  if (nodeId) $("#roi-snapshot").src = `/snapshot/${nodeId}?t=${Date.now()}`;
});

$("#roi-canvas").addEventListener("click", (e) => {
  const canvas = $("#roi-canvas");
  const rect = canvas.getBoundingClientRect();
  const sx = roiState.frameSize[0] / canvas.width;
  const sy = roiState.frameSize[1] / canvas.height;
  const x = Math.round((e.clientX - rect.left) * sx);
  const y = Math.round((e.clientY - rect.top) * sy);
  roiState.currentPoints.push([x, y]);
  redrawRoiCanvas();
});

$("#btn-roi-undo").addEventListener("click", () => {
  roiState.currentPoints.pop();
  redrawRoiCanvas();
});

$("#btn-roi-close-polygon").addEventListener("click", () => {
  if (roiState.currentPoints.length < 3) {
    $("#roi-feedback").textContent = "A polygon needs at least 3 points.";
    return;
  }
  roiState.polygons[roiKey()] = roiState.currentPoints;
  roiState.currentPoints = [];
  $("#roi-feedback").textContent = `Polygon saved for ${roiKey()}. Pick the next approach.`;
  redrawRoiCanvas();
});

$("#btn-roi-save").addEventListener("click", async () => {
  const nodes = {};
  Object.entries(roiState.polygons).forEach(([key, points]) => {
    const [nodeId, approachId] = key.split("::");
    nodes[nodeId] = nodes[nodeId] || {};
    nodes[nodeId][approachId] = points;
  });
  const missing = Object.entries(roiState.approaches).filter(
    ([nodeId, approaches]) => approaches.some((a) => !(nodes[nodeId] && nodes[nodeId][a]))
  );
  if (missing.length) {
    $("#roi-feedback").textContent = `Missing polygons for: ${missing.map(([n]) => n).join(", ")}`;
    return;
  }
  const res = await fetch("/api/roi", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ camera: "local_dashboard", frame_size: roiState.frameSize, nodes }),
  });
  const body = await res.json();
  $("#roi-feedback").textContent = res.ok ? `Saved to ${body.path}. Pipeline reloading.` : `Failed: ${body.detail}`;
});

loadRoi();
