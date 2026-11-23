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
$$(".switch").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".switch").forEach((b) => b.classList.remove("active"));
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
  $("#streams").innerHTML = nodeIds.map((id) => `
    <div class="video-screen">
      <img src="/stream/${id}" alt="live stream ${id}" />
      <div class="hud-bar">
        <span class="hud-dot" aria-hidden="true"></span>
        <span class="hud-node">${id}</span>
        <span class="hud-fps" data-hud-fps>-- fps</span>
      </div>
    </div>
  `).join("");
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
  $$("[data-hud-fps]").forEach((el) => { el.textContent = `${stats.processed_fps ?? "--"} fps`; });
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
    setStatusPill(true, (data.last_health && data.last_health.status) || "running");
    $("#node-id-label").textContent = (data.node_ids && data.node_ids[0]) || "--";
    $("#status-time").textContent = new Date().toLocaleTimeString();
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
function setFeedback(el, ok, text) {
  el.textContent = text;
  el.className = "feedback " + (ok ? "ok" : "err");
}

$("#btn-restart").addEventListener("click", async () => {
  setFeedback($("#control-feedback"), true, "Restarting...");
  const res = await fetch("/api/control/restart", { method: "POST" });
  setFeedback($("#control-feedback"), res.ok, res.ok ? "Restart requested." : "Restart failed.");
});

$("#btn-apply-conf").addEventListener("click", async () => {
  const value = parseFloat($("#conf-threshold").value);
  const res = await fetch("/api/control/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confidence_threshold: value }),
  });
  const body = await res.json();
  setFeedback($("#control-feedback"), res.ok, res.ok ? "Applied." : `Failed: ${body.detail}`);
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
let roiState = { frameSize: [640, 480], approaches: {}, approachDisplayNames: {}, polygons: {}, currentPoints: [] };

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
    drawPoly(points, key === roiKey() ? "#4fa3c7" : "#3f8f63", true);
  });
  drawPoly(roiState.currentPoints, "#b8503d", false);
  renderRoiLegend();
}

function roiDisplayName(nodeId, approachId) {
  return (roiState.approachDisplayNames[nodeId] || {})[approachId] || approachId;
}

function renderRoiLegend() {
  const items = [];
  Object.entries(roiState.approaches).forEach(([nodeId, approaches]) => {
    approaches.forEach((a) => {
      const done = !!roiState.polygons[`${nodeId}::${a}`];
      const name = roiDisplayName(nodeId, a);
      const label = name === a ? `${nodeId} / ${a}` : `${nodeId} / ${name} (${a})`;
      items.push(`<li class="${done ? "done" : "pending"}"><span class="dot"></span>${label}</li>`);
    });
  });
  $("#roi-legend").innerHTML = items.join("") || `<li class="muted">No approaches loaded yet.</li>`;
}

async function loadRoi() {
  const res = await fetch("/api/roi");
  const data = await res.json();
  roiState.frameSize = data.frame_size;
  roiState.approaches = data.approaches;
  roiState.approachDisplayNames = data.approach_display_names || {};
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
  const nodeId = $("#roi-node").value;
  const approaches = roiState.approaches[nodeId] || [];
  $("#roi-approach").innerHTML = approaches.map(
    (a) => `<option value="${a}">${roiDisplayName(nodeId, a)}</option>`
  ).join("");
}
$("#roi-node").addEventListener("change", () => { updateApproachOptions(); redrawRoiCanvas(); });
$("#roi-approach").addEventListener("change", redrawRoiCanvas);

$("#btn-roi-refresh-snapshot").addEventListener("click", () => {
  const nodeId = $("#roi-node").value || knownNodeIds[0];
  if (nodeId) $("#roi-snapshot").src = `/snapshot/${nodeId}?t=${Date.now()}`;
});

function roiPointFromEvent(e) {
  const canvas = $("#roi-canvas");
  const rect = canvas.getBoundingClientRect();
  const sx = roiState.frameSize[0] / canvas.width;
  const sy = roiState.frameSize[1] / canvas.height;
  return [Math.round((e.clientX - rect.left) * sx), Math.round((e.clientY - rect.top) * sy)];
}

$("#roi-canvas").addEventListener("click", (e) => {
  roiState.currentPoints.push(roiPointFromEvent(e));
  redrawRoiCanvas();
});

$("#roi-canvas").addEventListener("mousemove", (e) => {
  const [x, y] = roiPointFromEvent(e);
  $("#roi-coords").textContent = `x ${x}  y ${y}`;
});
$("#roi-canvas").addEventListener("mouseleave", () => {
  $("#roi-coords").textContent = "x --  y --";
});

$("#btn-roi-undo").addEventListener("click", () => {
  roiState.currentPoints.pop();
  redrawRoiCanvas();
});

$("#btn-roi-close-polygon").addEventListener("click", () => {
  if (roiState.currentPoints.length < 3) {
    setFeedback($("#roi-feedback"), false, "A polygon needs at least 3 points.");
    return;
  }
  roiState.polygons[roiKey()] = roiState.currentPoints;
  roiState.currentPoints = [];
  setFeedback($("#roi-feedback"), true, `Polygon saved for ${roiKey()}. Pick the next approach.`);
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
    setFeedback($("#roi-feedback"), false, `Missing polygons for: ${missing.map(([n]) => n).join(", ")}`);
    return;
  }
  const res = await fetch("/api/roi", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ camera: "local_dashboard", frame_size: roiState.frameSize, nodes }),
  });
  const body = await res.json();
  setFeedback($("#roi-feedback"), res.ok, res.ok ? `Saved to ${body.path}. Pipeline reloading.` : `Failed: ${body.detail}`);
});

loadRoi();
