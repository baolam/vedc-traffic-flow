// EdgeFlow AI -- Vision Local Console (JavaScript Client)
// Plain modern JavaScript, 0 external dependencies, works 100% offline.

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function fmtTime(ms) {
  if (!ms) return "--";
  const d = new Date(ms);
  return d.toLocaleTimeString("vi-VN", { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

function fmtDate(ms) {
  if (!ms) return "--";
  const d = new Date(ms);
  return d.toLocaleDateString("vi-VN") + " " + d.toLocaleTimeString("vi-VN", { hour12: false });
}

// ---------------------------------------------------------------------------
// Toast Notifications
// ---------------------------------------------------------------------------
function showToast(msg, type = "info") {
  const container = $("#toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "all 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ---------------------------------------------------------------------------
// Theme Toggle (Dark / Light Field Mode)
// ---------------------------------------------------------------------------
const themeToggleBtn = $("#btn-theme-toggle");
const currentTheme = localStorage.getItem("edgeflow_vision_theme") || "dark";
document.documentElement.setAttribute("data-theme", currentTheme);

if (themeToggleBtn) {
  themeToggleBtn.addEventListener("click", () => {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    const nextTheme = isDark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", nextTheme);
    localStorage.setItem("edgeflow_vision_theme", nextTheme);
    showToast(`Đã chuyển sang giao diện ${nextTheme === "dark" ? "Tối (Console)" : "Sáng (Field)"}`);
  });
}

// ---------------------------------------------------------------------------
// Main Tab Navigation
// ---------------------------------------------------------------------------
$$(".switchbank .switch").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".switchbank .switch").forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-selected", "false");
    });
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    const target = $(`#tab-${btn.dataset.tab}`);
    if (target) target.classList.add("active");

    if (btn.dataset.tab === "history") {
      refreshActiveHistory();
    } else if (btn.dataset.tab === "roi") {
      loadRoi();
    }
  });
});

// ---------------------------------------------------------------------------
// History Sub-Tabs
// ---------------------------------------------------------------------------
$$(".history-subnav .sub-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".history-subnav .sub-tab").forEach((b) => b.classList.remove("active"));
    $$(".subpanel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    const target = $(`#subpanel-${btn.dataset.subtab}`);
    if (target) target.classList.add("active");
  });
});

// ---------------------------------------------------------------------------
// Live Status Polling & Rendering
// ---------------------------------------------------------------------------
let knownNodeIds = [];
let lastStatusData = null;

function renderStreams(nodeIds) {
  if (JSON.stringify(nodeIds) === JSON.stringify(knownNodeIds)) return;
  knownNodeIds = nodeIds;
  const container = $("#streams");
  if (!container) return;

  container.innerHTML = nodeIds.map((id) => `
    <div class="video-screen" id="stream-box-${id}">
      <img id="stream-img-${id}" src="/stream/${id}" alt="Live stream ${id}" onerror="handleStreamError('${id}')" />
      <div class="hud-bar">
        <div class="hud-left">
          <span class="hud-dot" aria-hidden="true"></span>
          <span class="hud-node">NODE: ${id}</span>
          <span class="badge-subtle">LIVE MJPEG</span>
        </div>
        <div class="hud-right">
          <span class="hud-fps" id="hud-fps-${id}">-- fps</span>
          <div class="hud-actions">
            <button class="btn-hud" onclick="reloadStream('${id}')" title="Tải lại luồng">Tải lại</button>
            <button class="btn-hud" onclick="downloadSnapshot('${id}')" title="Chụp ảnh">Snapshot</button>
          </div>
        </div>
      </div>
    </div>
  `).join("");
}

window.reloadStream = function(nodeId) {
  const img = $(`#stream-img-${nodeId}`);
  if (img) {
    img.src = `/stream/${nodeId}?t=${Date.now()}`;
    showToast(`Đang kết nối lại luồng video ${nodeId}...`);
  }
};

window.downloadSnapshot = function(nodeId) {
  const link = document.createElement("a");
  link.href = `/snapshot/${nodeId}?t=${Date.now()}`;
  link.download = `snapshot_${nodeId}_${Date.now()}.jpg`;
  link.click();
};

window.handleStreamError = function(nodeId) {
  const img = $(`#stream-img-${nodeId}`);
  if (img) {
    setTimeout(() => {
      img.src = `/stream/${nodeId}?retry=${Date.now()}`;
    }, 2000);
  }
};

function renderRuntimeCards(stats, health, identity) {
  const latency = (stats.latency_ms && stats.latency_ms.total_ms) || {};
  const inferLat = (stats.latency_ms && stats.latency_ms.inference_ms) || {};
  const hardware = (health && health.hardware) || {};

  const fpsVal = stats.processed_fps != null ? Number(stats.processed_fps).toFixed(1) : "--";
  const cpuTemp = hardware.cpu_temp_c != null ? Number(hardware.cpu_temp_c).toFixed(1) : null;
  const tempClass = cpuTemp == null ? "" : (cpuTemp < 60 ? "good" : (cpuTemp < 75 ? "warn" : "bad"));

  const cards = [
    { label: "Tốc độ xử lý (FPS)", val: `${fpsVal} fps`, cls: stats.processed_fps > 5 ? "good" : "warn" },
    { label: "Khung hình OK / Thất bại", val: `${stats.frames_ok || 0} / ${stats.frames_failed || 0}`, cls: stats.frames_failed === 0 ? "good" : "warn" },
    { label: "Độ trễ suy luận AI (p50)", val: inferLat.p50 != null ? `${inferLat.p50.toFixed(1)} ms` : "--", cls: "" },
    { label: "Tổng độ trễ Pipeline (p95)", val: latency.p95 != null ? `${latency.p95.toFixed(1)} ms` : "--", cls: "" },
    { label: "Nhiệt độ CPU SoC", val: cpuTemp != null ? `${cpuTemp} °C` : "N/A (VM/Host)", cls: tempClass },
    { label: "Mô hình nhận diện", val: identity.model || "YOLOv8", cls: "" },
  ];

  const grid = $("#runtime-cards");
  if (grid) {
    grid.innerHTML = cards.map(c => `
      <div class="stat-row">
        <span class="stat-label">${c.label}</span>
        <span class="stat-val ${c.cls}">${c.val}</span>
      </div>
    `).join("");
  }

  // Update HUD FPS
  knownNodeIds.forEach(id => {
    const el = $(`#hud-fps-${id}`);
    if (el) el.textContent = `${fpsVal} fps`;
  });

  const devBadge = $("#hardware-device-badge");
  if (devBadge && identity.device) {
    devBadge.textContent = identity.device.toUpperCase();
  }
}

function renderApproachCards(telemetry, approachesMap, approachNamesMap) {
  const grid = $("#approach-cards-grid");
  const phaseBadge = $("#active-phase-badge");
  if (!grid) return;

  const activeNode = knownNodeIds[0];
  const nodeTelem = (telemetry && telemetry[activeNode]) || null;

  if (phaseBadge) {
    phaseBadge.textContent = (nodeTelem && nodeTelem.current_phase_id) || "J1_PHASE_NS";
  }

  const appDataList = (nodeTelem && nodeTelem.approaches) || [];
  const appDataMap = {};
  appDataList.forEach(a => { appDataMap[a.approach_id] = a; });

  const approachIds = (approachesMap && approachesMap[activeNode]) || Object.keys(appDataMap);
  const names = (approachNamesMap && approachNamesMap[activeNode]) || {};

  if (!approachIds.length) {
    grid.innerHTML = `<div class="empty-state">Chưa phát hiện xe trong vùng nhận diện.</div>`;
    return;
  }

  grid.innerHTML = approachIds.map(appId => {
    const data = appDataMap[appId] || {};
    const q = data.queue_vehicles != null ? Number(data.queue_vehicles).toFixed(1) : "0.0";
    const speed = data.mean_speed_mps != null ? `${Number(data.mean_speed_mps * 3.6).toFixed(1)} km/h` : "--";
    const displayName = names[appId] || appId;

    return `
      <div class="approach-card">
        <span class="app-name" title="${appId}">${displayName}</span>
        <span class="app-queue">${q} <small style="font-size:0.65rem;font-weight:600;color:var(--text-dim)">xe</small></span>
        <div class="app-meta">
          <span>Vận tốc: ${speed}</span>
          <span style="color:var(--accent-green)">OK</span>
        </div>
      </div>
    `;
  }).join("");
}

function setStatusPill(status) {
  const pill = $("#status-pill");
  if (!pill) return;
  const textEl = pill.querySelector(".status-text");

  pill.className = "pill";
  if (status === "HEALTHY" || status === "running") {
    pill.classList.add("success");
    if (textEl) textEl.textContent = "HOẠT ĐỘNG TỐT";
  } else if (status === "DEGRADED") {
    pill.classList.add("warning");
    if (textEl) textEl.textContent = "HIỆU NĂNG GIẢM";
  } else if (status === "OFFLINE" || status === "unreachable") {
    pill.classList.add("critical");
    if (textEl) textEl.textContent = "MẤT KẾT NỐI";
  } else {
    pill.classList.add("neutral");
    if (textEl) textEl.textContent = status || "ĐANG KHỞI ĐỘNG";
  }
}

async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    lastStatusData = data;

    renderStreams(data.node_ids || []);
    renderRuntimeCards(data.stats || {}, data.last_health, data.identity || {});

    const statusStr = (data.last_health && data.last_health.status) || "running";
    setStatusPill(statusStr);

    const nodeLabel = $("#node-id-label");
    if (nodeLabel) nodeLabel.textContent = (data.node_ids && data.node_ids[0]) || "--";

    const timeLabel = $("#status-time");
    if (timeLabel) timeLabel.textContent = new Date().toLocaleTimeString("vi-VN", { hour12: false });

    // Sync confidence slider on initial load
    if (data.identity && data.identity.confidence_threshold) {
      const confRange = $("#conf-range");
      const confPreview = $("#conf-val-preview");
      if (confRange && !confRange.dataset.userEdited) {
        confRange.value = data.identity.confidence_threshold;
        if (confPreview) confPreview.textContent = Number(data.identity.confidence_threshold).toFixed(2);
      }
    }

    // Refresh telemetry cards
    if (roiState && roiState.approaches) {
      renderApproachCards(data.last_telemetry, roiState.approaches, roiState.approachDisplayNames);
    }
  } catch (e) {
    setStatusPill("unreachable");
  }
}

pollStatus();
setInterval(pollStatus, 2000);

// ---------------------------------------------------------------------------
// Controls (Confidence threshold & Pipeline Restart)
// ---------------------------------------------------------------------------
const confRange = $("#conf-range");
const confPreview = $("#conf-val-preview");
const applyConfBtn = $("#btn-apply-conf");

if (confRange && confPreview) {
  confRange.addEventListener("input", (e) => {
    confRange.dataset.userEdited = "true";
    confPreview.textContent = Number(e.target.value).toFixed(2);
  });
}

if (applyConfBtn && confRange) {
  applyConfBtn.addEventListener("click", async () => {
    const val = parseFloat(confRange.value);
    applyConfBtn.disabled = true;
    try {
      const res = await fetch("/api/control/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confidence_threshold: val }),
      });
      const body = await res.json();
      if (res.ok) {
        showToast(`Đã lưu ngưỡng nhận diện: ${val.toFixed(2)}`, "success");
      } else {
        showToast(`Lỗi: ${body.detail}`, "error");
      }
    } catch (err) {
      showToast("Không thể gửi cài đặt đến thiết bị", "error");
    } finally {
      applyConfBtn.disabled = false;
    }
  });
}

// Restart Modal Handling
const restartModal = $("#restart-modal");
const openRestartBtn = $("#btn-open-restart-modal");
const cancelRestartBtn = $("#btn-modal-cancel");
const confirmRestartBtn = $("#btn-modal-confirm-restart");

if (openRestartBtn && restartModal) {
  openRestartBtn.addEventListener("click", () => restartModal.classList.add("open"));
}
if (cancelRestartBtn && restartModal) {
  cancelRestartBtn.addEventListener("click", () => restartModal.classList.remove("open"));
}

if (confirmRestartBtn && restartModal) {
  confirmRestartBtn.addEventListener("click", async () => {
    confirmRestartBtn.disabled = true;
    confirmRestartBtn.textContent = "Đang khởi động...";
    try {
      const res = await fetch("/api/control/restart", { method: "POST" });
      if (res.ok) {
        showToast("Đã gửi lệnh khởi động lại Perception Engine", "success");
      } else {
        showToast("Không thể khởi động lại", "error");
      }
    } catch (e) {
      showToast("Lỗi kết nối", "error");
    } finally {
      confirmRestartBtn.disabled = false;
      confirmRestartBtn.textContent = "Xác nhận Khởi động lại";
      restartModal.classList.remove("open");
    }
  });
}

const takeSnapshotBtn = $("#btn-take-snapshot");
if (takeSnapshotBtn) {
  takeSnapshotBtn.addEventListener("click", () => {
    const activeNode = knownNodeIds[0] || "J1";
    downloadSnapshot(activeNode);
    showToast("Đang tải ảnh snapshot xuống...");
  });
}

// ---------------------------------------------------------------------------
// History Tables & CSV Export
// ---------------------------------------------------------------------------
const historyLimitSelect = $("#history-limit-select");
const refreshHistoryBtn = $("#btn-refresh-history");
const exportCsvBtn = $("#btn-export-csv");

async function refreshActiveHistory() {
  const limit = (historyLimitSelect && historyLimitSelect.value) || 50;
  await Promise.all([refreshTelemetry(limit), refreshHealth(limit), refreshEvents(limit)]);
}

if (refreshHistoryBtn) refreshHistoryBtn.addEventListener("click", refreshActiveHistory);
if (historyLimitSelect) historyLimitSelect.addEventListener("change", refreshActiveHistory);

async function refreshTelemetry(limit = 50) {
  const res = await fetch(`/api/telemetry/history?limit=${limit}`);
  const { records } = await res.json();
  const tbody = $("#telemetry-table tbody");
  if (!tbody) return;

  if (!records.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-muted" style="text-align:center;padding:24px;">Chưa có dữ liệu Telemetry ghi lại trên thiết bị.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => {
    const approachesStr = (r.approaches || []).map(a => `
      <span class="table-badge phase" style="margin-right:4px;">
        ${a.approach_id}: <strong>${Number(a.queue_vehicles || 0).toFixed(1)}</strong> xe
      </span>
    `).join("");

    return `
      <tr>
        <td>${fmtDate(r.timestamp_ms)}</td>
        <td><strong class="mono">${r.node_id}</strong></td>
        <td><span class="table-badge phase">${r.current_phase_id || "--"}</span></td>
        <td>${approachesStr || "--"}</td>
      </tr>
    `;
  }).join("");
}

async function refreshHealth(limit = 50) {
  const res = await fetch(`/api/health/history?limit=${limit}`);
  const { records } = await res.json();
  const tbody = $("#health-table tbody");
  if (!tbody) return;

  if (!records.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-muted" style="text-align:center;padding:24px;">Chưa có dữ liệu Health ghi lại trên thiết bị.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => {
    const status = r.status || "UNKNOWN";
    const statusClass = status === "HEALTHY" ? "healthy" : (status === "DEGRADED" ? "degraded" : "offline");
    const fps = r.runtime && r.runtime.processed_fps != null ? Number(r.runtime.processed_fps).toFixed(1) : "--";
    const temp = r.hardware && r.hardware.cpu_temp_c != null ? `${Number(r.hardware.cpu_temp_c).toFixed(1)} °C` : "--";
    const lat = r.runtime && r.runtime.latency_ms && r.runtime.latency_ms.total_ms;
    const latStr = lat ? `${lat.p50}/${lat.p95} ms` : "--";

    return `
      <tr>
        <td>${fmtDate(r.timestamp_ms)}</td>
        <td><span class="table-badge ${statusClass}">${status}</span></td>
        <td><span class="mono">${fps}</span></td>
        <td><span class="mono">${temp}</span></td>
        <td><span class="mono">${latStr}</span></td>
      </tr>
    `;
  }).join("");
}

async function refreshEvents(limit = 50) {
  const res = await fetch(`/api/events?limit=${limit}`);
  const { records } = await res.json();
  const tbody = $("#events-table tbody");
  if (!tbody) return;

  if (!records.length) {
    tbody.innerHTML = `<tr><td colspan="3" class="text-muted" style="text-align:center;padding:24px;">Chưa có nhật ký sự kiện thao tác.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => `
    <tr>
      <td>${fmtDate(r.timestamp_ms)}</td>
      <td><span class="table-badge phase">${r.event_type}</span></td>
      <td><code class="mono" style="font-size:0.75rem;color:var(--text-muted);">${JSON.stringify(r.detail)}</code></td>
    </tr>
  `).join("");
}

// CSV Export Utility
if (exportCsvBtn) {
  exportCsvBtn.addEventListener("click", () => {
    const activeSubpanel = $(".subpanel.active");
    if (!activeSubpanel) return;
    const table = activeSubpanel.querySelector("table");
    if (!table) return;

    let csvContent = "";
    const rows = table.querySelectorAll("tr");
    rows.forEach(row => {
      const cols = row.querySelectorAll("th, td");
      const rowData = Array.from(cols).map(c => `"${c.innerText.replace(/"/g, '""').trim()}"`).join(",");
      csvContent += rowData + "\r\n";
    });

    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    const subtabId = activeSubpanel.id.replace("subpanel-", "");
    link.href = URL.createObjectURL(blob);
    link.download = `edgeflow_${subtabId}_${Date.now()}.csv`;
    link.click();
    showToast(`Đã xuất file CSV cho bảng ${subtabId}!`, "success");
  });
}

// ---------------------------------------------------------------------------
// ROI Calibration Engine
// ---------------------------------------------------------------------------
const APPROACH_COLORS = [
  "#38bdf8", // Cyan (North)
  "#34d399", // Emerald (South)
  "#fbbf24", // Amber (East)
  "#a78bfa", // Purple (West)
  "#f472b6", // Pink
  "#60a5fa", // Blue
];

let roiState = {
  frameSize: [640, 480],
  approaches: {},
  approachDisplayNames: {},
  polygons: {},
  currentPoints: [],
  aspectRatio: 16 / 9
};

function getApproachColor(index) {
  return APPROACH_COLORS[index % APPROACH_COLORS.length];
}

function roiKey() {
  const nodeEl = $("#roi-node");
  const appEl = $("#roi-approach");
  return `${nodeEl ? nodeEl.value : ""}::${appEl ? appEl.value : ""}`;
}

function updateRoiLegend() {
  const legend = $("#roi-legend");
  const completionBadge = $("#roi-completion-badge");
  if (!legend) return;

  const activeNode = $("#roi-node") ? $("#roi-node").value : "";
  const approaches = (roiState.approaches && roiState.approaches[activeNode]) || [];
  let completedCount = 0;

  const items = approaches.map((a, idx) => {
    const key = `${activeNode}::${a}`;
    const isDone = !!roiState.polygons[key];
    if (isDone) completedCount++;
    const isCurrent = key === roiKey();
    const color = getApproachColor(idx);
    const name = (roiState.approachDisplayNames[activeNode] && roiState.approachDisplayNames[activeNode][a]) || a;

    return `
      <li class="${isCurrent ? 'current' : ''}">
        <div class="roi-legend-left">
          <span class="roi-swatch" style="background:${color}"></span>
          <span>${name} <small class="text-dim">(${a})</small></span>
        </div>
        <span class="roi-status-tag ${isDone ? 'done' : 'pending'}">${isDone ? 'ĐÃ VẼ' : 'CHƯA VẼ'}</span>
      </li>
    `;
  });

  legend.innerHTML = items.join("") || `<li class="text-muted">Chưa nạp danh sách hướng tiếp cận.</li>`;
  if (completionBadge) {
    completionBadge.textContent = `${completedCount}/${approaches.length} Đã vẽ`;
    completionBadge.className = `badge-subtle ${completedCount === approaches.length && approaches.length > 0 ? 'good' : ''}`;
  }

  const ptsCountLabel = $("#roi-current-pts-count");
  if (ptsCountLabel) {
    ptsCountLabel.textContent = `${roiState.currentPoints.length} điểm`;
  }
}

function redrawRoiCanvas() {
  const canvas = $("#roi-canvas");
  const img = $("#roi-snapshot");
  if (!canvas || !img) return;

  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width || roiState.frameSize[0];
  canvas.height = rect.height || roiState.frameSize[1];

  const sx = canvas.width / roiState.frameSize[0];
  const sy = canvas.height / roiState.frameSize[1];
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const drawPolygon = (points, strokeColor, fillColor, closed = true) => {
    if (!points || !points.length) return;
    ctx.strokeStyle = strokeColor;
    ctx.fillStyle = fillColor;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    points.forEach(([x, y], i) => {
      const px = x * sx, py = y * sy;
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    if (closed) {
      ctx.closePath();
      ctx.fill();
    }
    ctx.stroke();

    // Draw vertex handles
    points.forEach(([x, y]) => {
      ctx.fillStyle = strokeColor;
      ctx.beginPath();
      ctx.arc(x * sx, y * sy, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.stroke();
    });
  };

  const activeNode = $("#roi-node") ? $("#roi-node").value : "";
  const approaches = (roiState.approaches && roiState.approaches[activeNode]) || [];

  // Draw completed polygons
  approaches.forEach((appId, idx) => {
    const key = `${activeNode}::${appId}`;
    const poly = roiState.polygons[key];
    if (poly) {
      const color = getApproachColor(idx);
      const isSelected = key === roiKey();
      drawPolygon(poly, color, isSelected ? `${color}40` : `${color}20`, true);
    }
  });

  // Draw currently drawing points
  if (roiState.currentPoints.length) {
    drawPolygon(roiState.currentPoints, "#ef4444", "rgba(239, 68, 68, 0.25)", false);
  }

  updateRoiLegend();
}

async function loadRoi() {
  const loading = $("#roi-canvas-loading");
  if (loading) loading.style.display = "block";

  try {
    const res = await fetch("/api/roi");
    const data = await res.json();
    roiState.frameSize = data.frame_size || [640, 480];
    roiState.approaches = data.approaches || {};
    roiState.approachDisplayNames = data.approach_display_names || {};
    roiState.polygons = {};

    const frameSizeLabel = $("#roi-framesize-label");
    if (frameSizeLabel) {
      frameSizeLabel.textContent = `${roiState.frameSize[0]} x ${roiState.frameSize[1]}`;
    }

    if (data.current && data.current.nodes) {
      Object.entries(data.current.nodes).forEach(([nodeId, apps]) => {
        Object.entries(apps).forEach(([approachId, poly]) => {
          roiState.polygons[`${nodeId}::${approachId}`] = poly;
        });
      });
    }

    const nodeSel = $("#roi-node");
    if (nodeSel) {
      nodeSel.innerHTML = Object.keys(roiState.approaches).map(n => `<option value="${n}">${n}</option>`).join("");
      updateApproachOptions();
    }

    refreshRoiSnapshot();
  } catch (err) {
    showToast("Không thể nạp thông tin ROI từ thiết bị", "error");
  } finally {
    if (loading) loading.style.display = "none";
  }
}

function updateApproachOptions() {
  const nodeSel = $("#roi-node");
  const appSel = $("#roi-approach");
  if (!nodeSel || !appSel) return;
  const nodeId = nodeSel.value;
  const approaches = (roiState.approaches && roiState.approaches[nodeId]) || [];
  const names = roiState.approachDisplayNames[nodeId] || {};

  appSel.innerHTML = approaches.map(a => `<option value="${a}">${names[a] || a}</option>`).join("");
}

function refreshRoiSnapshot() {
  const nodeSel = $("#roi-node");
  const nodeId = (nodeSel && nodeSel.value) || knownNodeIds[0] || "J1";
  const img = $("#roi-snapshot");
  if (img) {
    img.src = `/snapshot/${nodeId}?t=${Date.now()}`;
    img.onload = () => {
      redrawRoiCanvas();
    };
  }
}

const roiNodeSelect = $("#roi-node");
if (roiNodeSelect) {
  roiNodeSelect.addEventListener("change", () => {
    updateApproachOptions();
    refreshRoiSnapshot();
  });
}

const roiAppSelect = $("#roi-approach");
if (roiAppSelect) {
  roiAppSelect.addEventListener("change", () => {
    roiState.currentPoints = [];
    redrawRoiCanvas();
  });
}

const refreshSnapshotBtn = $("#btn-roi-refresh-snapshot");
if (refreshSnapshotBtn) {
  refreshSnapshotBtn.addEventListener("click", () => {
    refreshRoiSnapshot();
    showToast("Đã cập nhật ảnh snapshot mới từ camera!", "info");
  });
}

// Canvas Click to Plot Polygon Points
const canvas = $("#roi-canvas");
if (canvas) {
  canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    const sx = roiState.frameSize[0] / canvas.width;
    const sy = roiState.frameSize[1] / canvas.height;
    const x = Math.round((e.clientX - rect.left) * sx);
    const y = Math.round((e.clientY - rect.top) * sy);

    roiState.currentPoints.push([x, y]);
    redrawRoiCanvas();
  });

  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const sx = roiState.frameSize[0] / canvas.width;
    const sy = roiState.frameSize[1] / canvas.height;
    const x = Math.round((e.clientX - rect.left) * sx);
    const y = Math.round((e.clientY - rect.top) * sy);

    const coords = $("#roi-coords");
    if (coords) coords.textContent = `Tọa độ: X: ${x} | Y: ${y}`;
  });

  canvas.addEventListener("mouseleave", () => {
    const coords = $("#roi-coords");
    if (coords) coords.textContent = "Tọa độ: X: -- | Y: --";
  });
}

window.addEventListener("resize", () => {
  redrawRoiCanvas();
});

// Close Polygon Button
const closePolyBtn = $("#btn-roi-close-polygon");
if (closePolyBtn) {
  closePolyBtn.addEventListener("click", () => {
    if (roiState.currentPoints.length < 3) {
      showToast("Một vùng đa giác cần tối thiểu 3 điểm đỉnh", "error");
      return;
    }
    const key = roiKey();
    roiState.polygons[key] = [...roiState.currentPoints];
    roiState.currentPoints = [];
    showToast(`Đã khép góc đa giác cho ${key}. Tiếp tục chọn hướng kế tiếp!`, "success");
    redrawRoiCanvas();
  });
}

// Undo Point Button
const undoBtn = $("#btn-roi-undo");
if (undoBtn) {
  undoBtn.addEventListener("click", () => {
    if (roiState.currentPoints.length > 0) {
      roiState.currentPoints.pop();
      redrawRoiCanvas();
    } else {
      showToast("Không có điểm nào đang vẽ để hoàn tác", "info");
    }
  });
}

// Clear Single Approach Polygon
const clearApproachBtn = $("#btn-roi-clear-approach");
if (clearApproachBtn) {
  clearApproachBtn.addEventListener("click", () => {
    const key = roiKey();
    if (roiState.polygons[key]) {
      delete roiState.polygons[key];
      roiState.currentPoints = [];
      showToast(`Đã xóa vùng đa giác của ${key}`, "info");
      redrawRoiCanvas();
    } else {
      roiState.currentPoints = [];
      redrawRoiCanvas();
    }
  });
}

// Save ROI Configuration to Backend
const saveRoiBtn = $("#btn-roi-save");
if (saveRoiBtn) {
  saveRoiBtn.addEventListener("click", async () => {
    const nodes = {};
    Object.entries(roiState.polygons).forEach(([key, points]) => {
      const [nodeId, approachId] = key.split("::");
      nodes[nodeId] = nodes[nodeId] || {};
      nodes[nodeId][approachId] = points;
    });

    const activeNode = $("#roi-node") ? $("#roi-node").value : "";
    const activeApproaches = (roiState.approaches && roiState.approaches[activeNode]) || [];
    const missing = activeApproaches.filter(a => !(nodes[activeNode] && nodes[activeNode][a]));

    if (missing.length > 0) {
      showToast(`Còn thiếu đa giác cho các hướng: ${missing.join(", ")}`, "error");
      return;
    }

    saveRoiBtn.disabled = true;
    saveRoiBtn.textContent = "Đang lưu...";

    try {
      const res = await fetch("/api/roi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          camera: "local_dashboard",
          frame_size: roiState.frameSize,
          nodes: nodes
        })
      });

      const body = await res.json();
      if (res.ok) {
        showToast(`Đã lưu cấu hình ROI thành công vào ${body.path}! Pipeline đang nạp lại.`, "success");
      } else {
        showToast(`Lỗi lưu ROI: ${body.detail}`, "error");
      }
    } catch (err) {
      showToast("Lỗi kết nối khi lưu cấu hình ROI", "error");
    } finally {
      saveRoiBtn.disabled = false;
      saveRoiBtn.textContent = "Lưu cấu hình ROI";
    }
  });
}

// Initial Boot
refreshActiveHistory();
loadRoi();
