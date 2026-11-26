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
const currentTheme = localStorage.getItem("edgeflow_vision_theme") || "light";
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
    } else if (btn.dataset.tab === "live") {
      knownNodeIds.forEach(id => {
        if (window.reloadStream) window.reloadStream(id);
      });
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
let lastSeenAlertIds = new Set();
let lastObservedStatus = null;

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

    const isBlind = data.confidence === 0.0;

    return `
      <div class="approach-card ${isBlind ? 'blind' : ''}">
        <span class="app-name" title="${appId}">${displayName}</span>
        <span class="app-queue">${q} <small style="font-size:0.65rem;font-weight:600;color:var(--text-dim)">xe</small></span>
        <div class="app-meta">
          <span>Vận tốc: ${speed}</span>
          ${isBlind ? '<span style="color:#ef4444;font-weight:700;">CHE KHUẤT</span>' : '<span style="color:var(--accent-green)">OK</span>'}
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

    // Camera Occlusion & Tamper Alert Banner
    const activeAlerts = data.active_alerts || [];
    const alertBanner = $("#camera-alert-banner");

    // Check for newly triggered or resolved alerts and notify operator
    const currentAlertIds = new Set(activeAlerts.map(a => a.alert_id));
    for (const a of activeAlerts) {
      if (!lastSeenAlertIds.has(a.alert_id)) {
        showToast(`🚨 CẢNH BÁO SỰ CỐ [${(a.tamper_type || "CAMERA").toUpperCase()}]: ${a.reason || "Phát hiện camera bị che khuất!"}`, "error");
      }
    }
    if (lastSeenAlertIds.size > 0 && activeAlerts.length === 0) {
      showToast("✅ Sự cố che khuất camera đã được khắc phục/giải tỏa bình thường.", "success");
    }
    lastSeenAlertIds = currentAlertIds;

    // Service status transitions notification
    const currentHealthStatus = (data.last_health && data.last_health.status) || "running";
    if (lastObservedStatus && lastObservedStatus !== currentHealthStatus) {
      if (currentHealthStatus === "DEGRADED") {
        showToast(`⚠️ CẢNH BÁO: Dịch vụ chuyển sang trạng thái GIẢM HIỆU NĂNG (${data.last_health?.reason || "Kiểm tra camera"})`, "warning");
      } else if (currentHealthStatus === "OFFLINE") {
        showToast("❌ LỖI: Dịch vụ thị giác bị MẤT KẾT NỐI (OFFLINE)!", "error");
      } else if (currentHealthStatus === "HEALTHY" && (lastObservedStatus === "DEGRADED" || lastObservedStatus === "OFFLINE")) {
        showToast("✅ Dịch vụ thị giác đã phục hồi trạng thái HOẠT ĐỘNG TỐT.", "success");
      }
    }
    lastObservedStatus = currentHealthStatus;

    if (alertBanner) {
      if (activeAlerts.length > 0) {
        alertBanner.classList.remove("hidden");
        const top = activeAlerts[0];
        const isCritical = top.severity === "CRITICAL";
        alertBanner.className = `alert-banner ${isCritical ? "critical" : "warning"}`;
        const titleEl = $("#alert-title");
        const descEl = $("#alert-desc");
        const sevEl = $("#alert-severity");
        if (titleEl) titleEl.textContent = `CẢNH BÁO: PHÁT HIỆN CAMERA BỊ CHE KHUẤT [${(top.tamper_type || "").toUpperCase()}]`;
        if (descEl) descEl.textContent = top.reason || "--";
        if (sevEl) {
          sevEl.textContent = top.severity || "WARNING";
          sevEl.className = isCritical ? "badge-critical" : "badge-warning";
        }
      } else if (data.last_health && data.last_health.status === "DEGRADED") {
        alertBanner.classList.remove("hidden");
        alertBanner.className = "alert-banner warning";
        const titleEl = $("#alert-title");
        const descEl = $("#alert-desc");
        const sevEl = $("#alert-severity");
        if (titleEl) titleEl.textContent = "CẢNH BÁO: PHẦN CỨNG CAMERA GẶP SỰ CỐ / MẤT TÍN HIỆU";
        if (descEl) descEl.textContent = data.last_health.reason || "Camera bị gián đoạn hoặc không có khung hình";
        if (sevEl) {
          sevEl.textContent = "DEGRADED";
          sevEl.className = "badge-warning";
        }
      } else if (data.last_health && data.last_health.status === "OFFLINE") {
        alertBanner.classList.remove("hidden");
        alertBanner.className = "alert-banner critical";
        const titleEl = $("#alert-title");
        const descEl = $("#alert-desc");
        const sevEl = $("#alert-severity");
        if (titleEl) titleEl.textContent = "LỖI: DỊCH VỤ THỊ GIÁC ĐÃ DỪNG / NGOẠI TUYẾN";
        if (descEl) descEl.textContent = data.last_health.reason || "Tiến trình giám sát bị ngắt kết nối";
        if (sevEl) {
          sevEl.textContent = "OFFLINE";
          sevEl.className = "badge-critical";
        }
      } else {
        alertBanner.classList.add("hidden");
      }
    }

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

    // Sync occlusion simulation status
    const occMode = data.occlusion_mode || "none";
    const occBadge = $("#occlusion-status-badge");
    const occSelect = $("#occlusion-sim-select");
    const occRoiPicker = $("#occlusion-roi-picker-row");
    const occRoiSelect = $("#occlusion-roi-select");

    if (occBadge) {
      if (occMode === "none") {
        occBadge.textContent = "Bình thường";
        occBadge.style.color = "var(--accent-green)";
        occBadge.style.borderColor = "var(--accent-green)";
      } else {
        occBadge.textContent = `ĐANG GIẢ LẬP: ${occMode.toUpperCase()}`;
        occBadge.style.color = "var(--accent-red)";
        occBadge.style.borderColor = "var(--accent-red)";
      }
    }
    if (occSelect && !occSelect.dataset.userInteracted) {
      occSelect.value = occMode;
      if (occRoiPicker) {
        occRoiPicker.style.display = occMode === "roi_occlusion" ? "flex" : "none";
      }
    }

    // Populate ROI approaches into picker if available
    if (occRoiSelect && data.last_telemetry && data.last_telemetry.approaches) {
      const apps = data.last_telemetry.approaches;
      const currentOpts = new Set(Array.from(occRoiSelect.options).map(o => o.value));
      for (const app of apps) {
        if (app.approach_id && !currentOpts.has(app.approach_id)) {
          const opt = document.createElement("option");
          opt.value = app.approach_id;
          opt.textContent = `Nhánh: ${app.approach_id}`;
          occRoiSelect.appendChild(opt);
        }
      }
    }

    // Sync video source badge
    if (data.identity && data.identity.video_source) {
      const srcName = String(data.identity.video_source).split("/").pop().split("\\").pop();
      const vBadge = $("#video-source-badge");
      if (vBadge) {
        vBadge.textContent = srcName;
        vBadge.title = data.identity.video_source;
      }
    }

    // Refresh telemetry cards
    if (roiState && roiState.approaches) {
      renderApproachCards(data.last_telemetry, roiState.approaches, roiState.approachDisplayNames);
    }
  } catch (e) {
    if (lastObservedStatus !== "unreachable") {
      showToast("❌ Mất kết nối tới máy chủ Local Dashboard (Unreachable)", "error");
      lastObservedStatus = "unreachable";
    }
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

// Video Source Switching
const applyVideoBtn = $("#btn-apply-video-source");
const videoSelect = $("#video-source-select");
if (applyVideoBtn && videoSelect) {
  applyVideoBtn.addEventListener("click", async () => {
    const src = videoSelect.value;
    applyVideoBtn.disabled = true;
    showToast(`Đang chuyển nguồn video sang: ${src}...`, "info");
    try {
      const res = await fetch("/api/control/video-source", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_source: src }),
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Đã chuyển nguồn video sang: ${src}`, "success");
        setTimeout(() => {
          const activeNode = knownNodeIds[0] || "J1";
          window.reloadStream(activeNode);
        }, 1200);
      } else {
        showToast(`Đổi nguồn video thất bại: ${data.detail || ""}`, "error");
      }
    } catch (err) {
      showToast("Lỗi kết nối", "error");
    } finally {
      applyVideoBtn.disabled = false;
    }
  });
}

// Occlusion Simulation Handling
const occlusionSelect = $("#occlusion-sim-select");
const applyOcclusionBtn = $("#btn-apply-occlusion");
const occlusionRoiPicker = $("#occlusion-roi-picker-row");
const occlusionRoiSelect = $("#occlusion-roi-select");

if (occlusionSelect) {
  occlusionSelect.addEventListener("change", () => {
    occlusionSelect.dataset.userInteracted = "true";
    if (occlusionRoiPicker) {
      occlusionRoiPicker.style.display = occlusionSelect.value === "roi_occlusion" ? "flex" : "none";
    }
  });
}

if (applyOcclusionBtn && occlusionSelect) {
  applyOcclusionBtn.addEventListener("click", async () => {
    const mode = occlusionSelect.value;
    const targetRoi = occlusionRoiSelect ? occlusionRoiSelect.value : "";
    applyOcclusionBtn.disabled = true;
    showToast(`Đang chuyển trạng thái giả lập sang: ${mode}...`, "info");
    try {
      const res = await fetch("/api/control/occlusion-simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: mode, target_roi: targetRoi }),
      });
      const data = await res.json();
      if (res.ok) {
        delete occlusionSelect.dataset.userInteracted;
        if (mode === "none") {
          showToast("✅ Đã tắt giả lập che khuất. Khôi phục luồng camera bình thường.", "success");
        } else {
          showToast(`🚨 Đã kích hoạt giả lập che khuất: [${mode.toUpperCase()}]`, "warning");
        }
      } else {
        showToast(`Lỗi kích hoạt giả lập: ${data.detail || ""}`, "error");
      }
    } catch (e) {
      showToast("Lỗi kết nối khi gửi lệnh giả lập", "error");
    } finally {
      applyOcclusionBtn.disabled = false;
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

async function refreshDbStats() {
  try {
    const res = await fetch("/api/database/stats");
    if (!res.ok) return;
    const stats = await res.json();

    const sizeEl = $("#db-stat-size");
    if (sizeEl) sizeEl.textContent = stats.file_size_formatted || "--";

    const walEl = $("#db-stat-wal");
    if (walEl) walEl.textContent = `WAL: ${stats.wal_size_formatted || "0 KB"}`;

    const recEl = $("#db-stat-records");
    if (recEl) recEl.textContent = (stats.total_records != null ? stats.total_records.toLocaleString() : "--") + " bản ghi";

    const counts = stats.table_counts || {};
    const countsEl = $("#db-stat-counts");
    if (countsEl) {
      countsEl.textContent = `Telem: ${counts.telemetry_history || 0} | Health: ${counts.health_history || 0} | Cảnh báo: ${counts.alert_log || 0}`;
    }

    const retEl = $("#db-stat-retention");
    if (retEl) retEl.textContent = `${stats.retention_days || 14} ngày`;

    const pathEl = $("#db-stat-path");
    if (pathEl) {
      pathEl.textContent = stats.db_path || "vision.db";
      pathEl.title = stats.db_path || "";
    }
  } catch (err) {
    console.error("Failed to load db stats:", err);
  }
}

// Database Action Buttons
const dbPruneBtn = $("#btn-db-prune");
if (dbPruneBtn) {
  dbPruneBtn.addEventListener("click", async () => {
    if (!confirm("Bạn có chắc chắn muốn dọn dẹp các bản ghi cũ hơn số ngày lưu trữ không?")) return;
    dbPruneBtn.disabled = true;
    try {
      const res = await fetch("/api/database/prune", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        showToast(`Đã dọn dẹp ${data.deleted?.total_deleted || 0} bản ghi cũ thành công!`, "success");
        refreshActiveHistory();
      } else {
        showToast(`Lỗi dọn dẹp: ${data.detail || "Thất bại"}`, "error");
      }
    } catch (e) {
      showToast("Không thể kết nối đến máy chủ", "error");
    } finally {
      dbPruneBtn.disabled = false;
    }
  });
}

const dbVacuumBtn = $("#btn-db-vacuum");
if (dbVacuumBtn) {
  dbVacuumBtn.addEventListener("click", async () => {
    dbVacuumBtn.disabled = true;
    showToast("Đang tối ưu hóa database (VACUUM)...", "info");
    try {
      const res = await fetch("/api/database/vacuum", { method: "POST" });
      if (res.ok) {
        showToast("Tối ưu hóa Database (VACUUM) thành công!", "success");
        refreshDbStats();
      } else {
        showToast("Tối ưu hóa thất bại", "error");
      }
    } catch (e) {
      showToast("Lỗi kết nối", "error");
    } finally {
      dbVacuumBtn.disabled = false;
    }
  });
}

const dbDownloadBtn = $("#btn-db-download");
if (dbDownloadBtn) {
  dbDownloadBtn.addEventListener("click", () => {
    window.location.href = "/api/database/download";
    showToast("Đang tải tệp database SQLite xuống...", "info");
  });
}

async function refreshActiveHistory() {
  const limit = (historyLimitSelect && historyLimitSelect.value) || 50;
  await Promise.all([refreshDbStats(), refreshTelemetry(limit), refreshHealth(limit), refreshEvents(limit), refreshAlerts(limit)]);
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

async function refreshAlerts(limit = 50) {
  const res = await fetch(`/api/alerts?limit=${limit}`);
  const { records } = await res.json();
  const tbody = $("#alerts-table tbody");
  if (!tbody) return;

  if (!records || !records.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-muted" style="text-align:center;padding:24px;">Không có sự cố hoặc cảnh báo camera nào.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => {
    const sevClass = r.severity === "CRITICAL" ? "offline" : "degraded";
    const statusClass = r.status === "ACTIVE" ? "offline" : "healthy";
    return `
      <tr>
        <td>${fmtDate(r.timestamp_ms)}</td>
        <td><strong class="mono">${r.node_id}</strong></td>
        <td><span class="mono">${r.tamper_type}</span></td>
        <td><span class="table-badge ${sevClass}">${r.severity}</span></td>
        <td><span class="table-badge ${statusClass}">${r.status}</span></td>
        <td>${r.reason || "--"}</td>
      </tr>
    `;
  }).join("");
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
  drawMode: "poly", // "poly" | "rect"
  mousePos: null, // [x, y] in frame coordinates
  draggingVertex: null, // { isCurrent, key, index }
  hoverVertex: null,
  isBoxing: false,
  boxStart: null,
  boxCurrent: null,
};

function getApproachColor(index) {
  return APPROACH_COLORS[index % APPROACH_COLORS.length];
}

function roiKey() {
  const nodeEl = $("#roi-node");
  const appEl = $("#roi-approach");
  return `${nodeEl ? nodeEl.value : ""}::${appEl ? appEl.value : ""}`;
}

window.selectRoiApproach = function(approachId) {
  const appSel = $("#roi-approach");
  if (appSel) {
    appSel.value = approachId;
    roiState.currentPoints = [];
    redrawRoiCanvas();
  }
};

function isPointInPolygon(px, py, polygon) {
  if (!polygon || polygon.length < 3) return false;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0], yi = polygon[i][1];
    const xj = polygon[j][0], yj = polygon[j][1];
    const intersect = ((yi > py) !== (yj > py)) &&
                      (px < (xj - xi) * (py - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function findPolygonAt(frameX, frameY) {
  const activeNode = $("#roi-node") ? $("#roi-node").value : "";
  const approaches = (roiState.approaches && roiState.approaches[activeNode]) || [];
  const currentKey = roiKey();

  // Prioritize activeKey if clicked inside it
  const currentPoly = roiState.polygons[currentKey];
  if (currentPoly && currentPoly.length >= 3) {
    if (isPointInPolygon(frameX, frameY, currentPoly)) {
      const [, appId] = currentKey.split("::");
      return { key: currentKey, appId, polygon: currentPoly };
    }
  }

  // Check all other approach polygons
  for (const appId of approaches) {
    const key = `${activeNode}::${appId}`;
    if (key === currentKey) continue;
    const poly = roiState.polygons[key];
    if (poly && poly.length >= 3) {
      if (isPointInPolygon(frameX, frameY, poly)) {
        return { key, appId, polygon: poly };
      }
      // Also hit test near centroid badge (within 24px)
      let cx = 0, cy = 0;
      poly.forEach(([px, py]) => { cx += px; cy += py; });
      cx /= poly.length;
      cy /= poly.length;
      if (Math.hypot(frameX - cx, frameY - cy) < 24) {
        return { key, appId, polygon: poly };
      }
    }
  }
  return null;
}

function findVertexNear(canvasX, canvasY, thresholdPx = 14) {
  const canvas = $("#roi-canvas");
  if (!canvas || !roiState.frameSize[0]) return null;
  const sx = canvas.width / roiState.frameSize[0];
  const sy = canvas.height / roiState.frameSize[1];

  // 1. Check current drawing points
  for (let i = 0; i < roiState.currentPoints.length; i++) {
    const [px, py] = roiState.currentPoints[i];
    const cx = px * sx, cy = py * sy;
    if (Math.hypot(canvasX - cx, canvasY - cy) <= thresholdPx) {
      return { isCurrent: true, key: null, index: i, cx, cy };
    }
  }

  // 2. Check active approach polygon vertices first
  const activeNode = $("#roi-node") ? $("#roi-node").value : "";
  const approaches = (roiState.approaches && roiState.approaches[activeNode]) || [];
  const activeKey = roiKey();

  if (roiState.polygons[activeKey]) {
    const poly = roiState.polygons[activeKey];
    for (let i = 0; i < poly.length; i++) {
      const [px, py] = poly[i];
      const cx = px * sx, cy = py * sy;
      if (Math.hypot(canvasX - cx, canvasY - cy) <= thresholdPx) {
        return { isCurrent: false, key: activeKey, index: i, cx, cy };
      }
    }
  }

  // 3. Check all other approach polygon vertices
  for (const appId of approaches) {
    const key = `${activeNode}::${appId}`;
    if (key === activeKey) continue;
    const poly = roiState.polygons[key];
    if (poly) {
      for (let i = 0; i < poly.length; i++) {
        const [px, py] = poly[i];
        const cx = px * sx, cy = py * sy;
        if (Math.hypot(canvasX - cx, canvasY - cy) <= thresholdPx) {
          return { isCurrent: false, key, index: i, cx, cy };
        }
      }
    }
  }

  return null;
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
      <li class="${isCurrent ? 'current' : ''}" onclick="window.selectRoiApproach('${a}')" title="Nhấp để chuyển sang hướng ${name}">
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
  const wrap = $("#roi-canvas-wrap");
  if (!canvas || !img) return;

  if (wrap && roiState.frameSize && roiState.frameSize[0] > 0) {
    wrap.style.aspectRatio = `${roiState.frameSize[0]} / ${roiState.frameSize[1]}`;
  }

  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width || roiState.frameSize[0];
  canvas.height = rect.height || roiState.frameSize[1];

  const sx = canvas.width / roiState.frameSize[0];
  const sy = canvas.height / roiState.frameSize[1];
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const activeNode = $("#roi-node") ? $("#roi-node").value : "";
  const approaches = (roiState.approaches && roiState.approaches[activeNode]) || [];
  const currentKey = roiKey();

  const drawPolygon = (points, strokeColor, fillColor, closed = true, isSelected = false, key = null) => {
    if (!points || !points.length) return;
    ctx.save();
    ctx.strokeStyle = strokeColor;
    ctx.fillStyle = fillColor;
    ctx.lineWidth = isSelected ? 3.0 : 2.0;
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

    // Draw vertex handles for all polygons (so any vertex is visibly interactive)
    points.forEach(([x, y], idx) => {
      const px = x * sx, py = y * sy;
      const isHovered = roiState.hoverVertex &&
                        ((roiState.hoverVertex.isCurrent && points === roiState.currentPoints && roiState.hoverVertex.index === idx) ||
                         (!roiState.hoverVertex.isCurrent && roiState.hoverVertex.key === key && roiState.hoverVertex.index === idx));

      ctx.beginPath();
      ctx.arc(px, py, isHovered ? 8.0 : (isSelected ? 6.0 : 4.5), 0, Math.PI * 2);
      ctx.fillStyle = isHovered ? "#ffffff" : (isSelected ? strokeColor : "#ffffff");
      ctx.fill();
      ctx.strokeStyle = isHovered ? strokeColor : (isSelected ? "#ffffff" : strokeColor);
      ctx.lineWidth = isHovered ? 3.0 : 2.0;
      ctx.stroke();
    });
    ctx.restore();
  };

  // 1. Draw completed polygons
  approaches.forEach((appId, idx) => {
    const key = `${activeNode}::${appId}`;
    const poly = roiState.polygons[key];
    if (poly && poly.length >= 3) {
      const color = getApproachColor(idx);
      const isSelected = key === currentKey;
      drawPolygon(poly, color, isSelected ? `${color}45` : `${color}18`, true, isSelected, key);

      // Centroid label badge
      let cx = 0, cy = 0;
      poly.forEach(([px, py]) => { cx += px * sx; cy += py * sy; });
      cx /= poly.length;
      cy /= poly.length;

      const label = (roiState.approachDisplayNames[activeNode] && roiState.approachDisplayNames[activeNode][appId]) || appId;
      ctx.save();
      ctx.font = "bold 11px system-ui, -apple-system, sans-serif";
      const tm = ctx.measureText(label);
      const tw = tm.width;
      const bw = tw + 14, bh = 20;

      ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
      ctx.strokeStyle = color;
      ctx.lineWidth = isSelected ? 2.0 : 1.2;
      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(cx - bw / 2, cy - bh / 2, bw, bh, 4);
      } else {
        ctx.rect(cx - bw / 2, cy - bh / 2, bw, bh);
      }
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, cx, cy);
      ctx.restore();
    }
  });

  // 2. Draw currently drawing points (Polygon Mode)
  if (roiState.currentPoints.length) {
    drawPolygon(roiState.currentPoints, "#ef4444", "rgba(239, 68, 68, 0.25)", false, true);

    // Rubber-band guideline to mouse position
    if (roiState.mousePos) {
      const [lastX, lastY] = roiState.currentPoints[roiState.currentPoints.length - 1];
      const startX = lastX * sx, startY = lastY * sy;
      let targetX = roiState.mousePos[0] * sx, targetY = roiState.mousePos[1] * sy;

      // Check if near starting point (Snap-to-start)
      const [firstX, firstY] = roiState.currentPoints[0];
      const firstCanvasX = firstX * sx, firstCanvasY = firstY * sy;
      const isNearStart = roiState.currentPoints.length >= 3 &&
                          Math.hypot(targetX - firstCanvasX, targetY - firstCanvasY) < 18;

      if (isNearStart) {
        targetX = firstCanvasX;
        targetY = firstCanvasY;
      }

      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = isNearStart ? "#22c55e" : "#ef4444";
      ctx.lineWidth = 2.0;
      ctx.beginPath();
      ctx.moveTo(startX, startY);
      ctx.lineTo(targetX, targetY);
      ctx.stroke();

      if (isNearStart) {
        // Pulsing close halo
        ctx.beginPath();
        ctx.arc(firstCanvasX, firstCanvasY, 12, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(34, 197, 94, 0.35)";
        ctx.fill();
        ctx.strokeStyle = "#22c55e";
        ctx.lineWidth = 2.5;
        ctx.stroke();

        ctx.font = "bold 11px sans-serif";
        ctx.fillStyle = "#22c55e";
        ctx.fillText("Nhấp để khép góc", firstCanvasX + 16, firstCanvasY - 6);
      }
      ctx.restore();
    }
  }

  // 3. Draw live box drag preview (Rect Mode)
  if (roiState.isBoxing && roiState.boxStart && roiState.boxCurrent) {
    const x1 = roiState.boxStart[0] * sx, y1 = roiState.boxStart[1] * sy;
    const x2 = roiState.boxCurrent[0] * sx, y2 = roiState.boxCurrent[1] * sy;
    const bx = Math.min(x1, x2), by = Math.min(y1, y2);
    const bw = Math.abs(x2 - x1), bh = Math.abs(y2 - y1);

    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = "#38bdf8";
    ctx.fillStyle = "rgba(56, 189, 248, 0.25)";
    ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, bw, bh);
    ctx.fillRect(bx, by, bw, bh);
    ctx.restore();
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
  const rawToggle = $("#roi-raw-frame-toggle");
  const isRaw = rawToggle ? rawToggle.checked : true;
  if (img) {
    img.src = `/snapshot/${nodeId}?raw=${isRaw}&t=${Date.now()}`;
    img.onload = () => {
      redrawRoiCanvas();
    };
  }
}

const rawFrameToggle = $("#roi-raw-frame-toggle");
if (rawFrameToggle) {
  rawFrameToggle.addEventListener("change", () => {
    refreshRoiSnapshot();
    showToast(rawFrameToggle.checked ? "Đã chuyển sang ảnh gốc sạch (không viền HUD)" : "Đang hiển thị ảnh kèm khung nhận diện HUD", "info");
  });
}

const btnToolPoly = $("#btn-tool-poly");
const btnToolRect = $("#btn-tool-rect");
if (btnToolPoly && btnToolRect) {
  btnToolPoly.addEventListener("click", () => {
    roiState.drawMode = "poly";
    btnToolPoly.classList.add("active");
    btnToolRect.classList.remove("active");
    showToast("Chế độ: Đa giác tự do (Bấm từng điểm, có đường ngắm preview)", "info");
  });
  btnToolRect.addEventListener("click", () => {
    roiState.drawMode = "rect";
    btnToolRect.classList.add("active");
    btnToolPoly.classList.remove("active");
    roiState.currentPoints = [];
    redrawRoiCanvas();
    showToast("Chế độ: Kéo hình hộp (Nhấp giữ và kéo thả chuột để tạo 1 làn đường)", "info");
  });
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

function markUnsaved(hasChanges) {
  roiState.hasUnsavedChanges = hasChanges;
  const saveBtn = $("#btn-roi-save");
  if (!saveBtn) return;
  if (hasChanges) {
    saveBtn.classList.add("btn-save-unsaved");
    saveBtn.innerHTML = `
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      <span>Lưu cấu hình ROI (Cần bấm để áp dụng vào video)</span>
    `;
  } else {
    saveBtn.classList.remove("btn-save-unsaved");
    saveBtn.innerHTML = `
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      <span>Lưu cấu hình ROI</span>
    `;
  }
}

// Canvas Interactive Event Handling (Click, Drag Vertices, Box Drag, Guidelines)
const canvas = $("#roi-canvas");
if (canvas) {
  function getCanvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    const sx = roiState.frameSize[0] / canvas.width;
    const sy = roiState.frameSize[1] / canvas.height;
    const canvasX = e.clientX - rect.left;
    const canvasY = e.clientY - rect.top;
    const frameX = Math.round(canvasX * sx);
    const frameY = Math.round(canvasY * sy);
    return { canvasX, canvasY, frameX, frameY };
  }

  canvas.addEventListener("mousedown", (e) => {
    if (e.button === 2) return; // Right click handled by contextmenu
    const { canvasX, canvasY, frameX, frameY } = getCanvasCoords(e);

    // 1. Check if user clicked on any vertex (corner) of ANY bounding box
    const nearVertex = findVertexNear(canvasX, canvasY, 14);
    if (nearVertex) {
      if (!nearVertex.isCurrent && nearVertex.key) {
        const [, appId] = nearVertex.key.split("::");
        selectRoiApproach(appId);
        roiState.currentPoints = [];
      }
      roiState.draggingVertex = nearVertex;
      canvas.style.cursor = "grabbing";
      return;
    }

    // 2. Check if user clicked inside ANY existing bounding box / polygon to drag/move it
    const hitPoly = findPolygonAt(frameX, frameY);
    if (hitPoly) {
      selectRoiApproach(hitPoly.appId);
      roiState.currentPoints = [];
      roiState.draggingPolygon = {
        key: hitPoly.key,
        startX: frameX,
        startY: frameY,
        origPoints: hitPoly.polygon.map(p => [...p])
      };
      canvas.style.cursor = "move";
      redrawRoiCanvas();
      return;
    }

    // 3. Box Mode: start drag-box on empty space
    if (roiState.drawMode === "rect") {
      roiState.isBoxing = true;
      roiState.boxStart = [frameX, frameY];
      roiState.boxCurrent = [frameX, frameY];
      return;
    }

    // 4. Polygon Mode: Snap to first point to close
    if (roiState.currentPoints.length >= 3) {
      const [fx, fy] = roiState.currentPoints[0];
      const sx = canvas.width / roiState.frameSize[0];
      const sy = canvas.height / roiState.frameSize[1];
      if (Math.hypot(canvasX - fx * sx, canvasY - fy * sy) < 18) {
        const key = roiKey();
        roiState.polygons[key] = [...roiState.currentPoints];
        roiState.currentPoints = [];
        markUnsaved(true);
        showToast(`Đã khép góc đa giác cho ${key}! Nhớ bấm "Lưu cấu hình ROI" để áp dụng.`, "success");
        redrawRoiCanvas();
        return;
      }
    }

    // Otherwise add new vertex point
    roiState.currentPoints.push([frameX, frameY]);
    redrawRoiCanvas();
  });

  canvas.addEventListener("mousemove", (e) => {
    const { canvasX, canvasY, frameX, frameY } = getCanvasCoords(e);
    roiState.mousePos = [frameX, frameY];

    const coords = $("#roi-coords");
    if (coords) coords.textContent = `Tọa độ: X: ${frameX} | Y: ${frameY}`;

    // A. Dragging active vertex
    if (roiState.draggingVertex) {
      const { isCurrent, key, index } = roiState.draggingVertex;
      if (isCurrent && roiState.currentPoints[index]) {
        roiState.currentPoints[index] = [frameX, frameY];
      } else if (!isCurrent && roiState.polygons[key] && roiState.polygons[key][index]) {
        roiState.polygons[key][index] = [frameX, frameY];
      }
      markUnsaved(true);
      redrawRoiCanvas();
      return;
    }

    // B. Dragging entire bounding box / polygon
    if (roiState.draggingPolygon) {
      const { key, startX, startY, origPoints } = roiState.draggingPolygon;
      const dx = frameX - startX;
      const dy = frameY - startY;
      const [w, h] = roiState.frameSize;
      roiState.polygons[key] = origPoints.map(([ox, oy]) => [
        Math.max(0, Math.min(w, ox + dx)),
        Math.max(0, Math.min(h, oy + dy))
      ]);
      markUnsaved(true);
      redrawRoiCanvas();
      return;
    }

    // C. Dragging box rectangle
    if (roiState.isBoxing) {
      roiState.boxCurrent = [frameX, frameY];
      redrawRoiCanvas();
      return;
    }

    // D. Hover detection for vertices & bounding boxes
    const nearVertex = findVertexNear(canvasX, canvasY, 14);
    roiState.hoverVertex = nearVertex;
    const hitPoly = findPolygonAt(frameX, frameY);

    if (nearVertex) {
      canvas.style.cursor = "grab";
    } else if (hitPoly) {
      canvas.style.cursor = "move";
    } else {
      canvas.style.cursor = roiState.drawMode === "rect" ? "crosshair" : "crosshair";
    }

    redrawRoiCanvas();
  });

  canvas.addEventListener("mouseup", (e) => {
    const { frameX, frameY } = getCanvasCoords(e);

    // End vertex dragging
    if (roiState.draggingVertex) {
      roiState.draggingVertex = null;
      canvas.style.cursor = "crosshair";
      markUnsaved(true);
      showToast("Đã đổi tọa độ đỉnh. Hãy bấm 'Lưu cấu hình ROI' để nạp vào video!", "info");
      redrawRoiCanvas();
      return;
    }

    // End polygon dragging
    if (roiState.draggingPolygon) {
      roiState.draggingPolygon = null;
      canvas.style.cursor = "crosshair";
      markUnsaved(true);
      showToast("Đã di chuyển vùng làn đường. Hãy bấm 'Lưu cấu hình ROI' để nạp vào video!", "info");
      redrawRoiCanvas();
      return;
    }

    // End box dragging
    if (roiState.isBoxing) {
      roiState.isBoxing = false;
      if (roiState.boxStart) {
        const [x1, y1] = roiState.boxStart;
        const [x2, y2] = [frameX, frameY];
        if (Math.abs(x2 - x1) > 12 && Math.abs(y2 - y1) > 12) {
          const minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
          const minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
          const key = roiKey();
          roiState.polygons[key] = [
            [minX, minY],
            [maxX, minY],
            [maxX, maxY],
            [minX, maxY]
          ];
          markUnsaved(true);
          showToast(`Đã tạo hình hộp cho hướng ${key}! Bạn có thể kéo 4 đỉnh để nắn chỉnh.`, "success");
        }
      }
      roiState.boxStart = null;
      roiState.boxCurrent = null;
      redrawRoiCanvas();
    }
  });

  // Right-click cancels any unfinished drawing points
  canvas.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    if (roiState.currentPoints.length > 0) {
      roiState.currentPoints = [];
      showToast("Đã hủy các điểm đang vẽ dở", "info");
      redrawRoiCanvas();
    }
  });

  canvas.addEventListener("dblclick", (e) => {
    e.preventDefault();
    if (roiState.currentPoints.length < 3) {
      showToast("Một vùng đa giác cần tối thiểu 3 điểm đỉnh để khép góc", "info");
      return;
    }
    const key = roiKey();
    roiState.polygons[key] = [...roiState.currentPoints];
    roiState.currentPoints = [];
    markUnsaved(true);
    showToast(`Đã khép góc đa giác cho ${key}! Nhớ bấm "Lưu cấu hình ROI" để áp dụng.`, "success");
    redrawRoiCanvas();
  });

  canvas.addEventListener("mouseleave", () => {
    roiState.mousePos = null;
    roiState.hoverVertex = null;
    if (roiState.isBoxing) {
      roiState.isBoxing = false;
      roiState.boxStart = null;
      roiState.boxCurrent = null;
    }
    roiState.draggingVertex = null;
    const coords = $("#roi-coords");
    if (coords) coords.textContent = "Tọa độ: X: -- | Y: --";
    redrawRoiCanvas();
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
    markUnsaved(true);
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

// Cancel In-progress Drawing Points (Button & Escape Key)
const cancelDrawBtn = $("#btn-roi-cancel-draw");
if (cancelDrawBtn) {
  cancelDrawBtn.addEventListener("click", () => {
    if (roiState.currentPoints.length > 0) {
      roiState.currentPoints = [];
      showToast("Đã hủy các điểm đang vẽ dở", "info");
      redrawRoiCanvas();
    } else {
      showToast("Không có điểm nào đang vẽ dở", "info");
    }
  });
}

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (roiState.currentPoints.length > 0) {
      roiState.currentPoints = [];
      showToast("Đã hủy các điểm đang vẽ dở", "info");
      redrawRoiCanvas();
    }
  }
});

// Clear Single Approach Polygon
const clearApproachBtn = $("#btn-roi-clear-approach");
if (clearApproachBtn) {
  clearApproachBtn.addEventListener("click", () => {
    const key = roiKey();
    if (roiState.polygons[key]) {
      delete roiState.polygons[key];
      roiState.currentPoints = [];
      markUnsaved(true);
      showToast(`Đã xóa vùng đa giác của ${key}`, "info");
      redrawRoiCanvas();
    } else {
      roiState.currentPoints = [];
      redrawRoiCanvas();
    }
  });
}

// Clear All Polygons for Current Node
const clearAllBtn = $("#btn-roi-clear-all");
if (clearAllBtn) {
  clearAllBtn.addEventListener("click", () => {
    const activeNode = $("#roi-node") ? $("#roi-node").value : "";
    if (!confirm(`Bạn có chắc muốn xóa tất cả các vùng đa giác của nút ${activeNode}?`)) return;

    const approaches = (roiState.approaches && roiState.approaches[activeNode]) || [];
    approaches.forEach(a => {
      delete roiState.polygons[`${activeNode}::${a}`];
    });
    roiState.currentPoints = [];
    markUnsaved(true);
    showToast(`Đã xóa tất cả vùng của nút ${activeNode}`, "info");
    redrawRoiCanvas();
  });
}

// Preset Default Layout (Auto-generate 4 standard perspective lanes)
const presetBtn = $("#btn-roi-preset-default");
if (presetBtn) {
  presetBtn.addEventListener("click", () => {
    const activeNode = $("#roi-node") ? $("#roi-node").value : "";
    const approaches = (roiState.approaches && roiState.approaches[activeNode]) || [];
    if (!approaches.length) {
      showToast("Không tìm thấy danh sách hướng tiếp cận", "error");
      return;
    }

    const [w, h] = roiState.frameSize;
    const presets = {};

    // Map cardinal approaches if matching names exist
    const findApp = (needle) => approaches.find(a => a.toLowerCase().includes(needle));
    const northApp = findApp("_n_") || approaches[0];
    const southApp = findApp("_s_") || approaches[1] || approaches[0];
    const eastApp = findApp("_e_") || approaches[2] || approaches[0];
    const westApp = findApp("_w_") || approaches[3] || approaches[0];

    if (northApp) {
      presets[northApp] = [
        [Math.round(w * 0.25), 0],
        [Math.round(w * 0.75), 0],
        [Math.round(w * 0.62), Math.round(h * 0.38)],
        [Math.round(w * 0.38), Math.round(h * 0.38)],
      ];
    }
    if (southApp && southApp !== northApp) {
      presets[southApp] = [
        [Math.round(w * 0.35), Math.round(h * 0.62)],
        [Math.round(w * 0.65), Math.round(h * 0.62)],
        [Math.round(w * 0.85), h],
        [Math.round(w * 0.15), h],
      ];
    }
    if (westApp && westApp !== northApp && westApp !== southApp) {
      presets[westApp] = [
        [0, Math.round(h * 0.25)],
        [Math.round(w * 0.38), Math.round(h * 0.38)],
        [Math.round(w * 0.35), Math.round(h * 0.62)],
        [0, Math.round(h * 0.75)],
      ];
    }
    if (eastApp && eastApp !== northApp && eastApp !== southApp && eastApp !== westApp) {
      presets[eastApp] = [
        [Math.round(w * 0.62), Math.round(h * 0.38)],
        [w, Math.round(h * 0.25)],
        [w, Math.round(h * 0.75)],
        [Math.round(w * 0.65), Math.round(h * 0.62)],
      ];
    }

    // Fallback for any unmapped approaches
    approaches.forEach((app, idx) => {
      if (!presets[app]) {
        const top = Math.round((idx / approaches.length) * h);
        const bottom = Math.round(((idx + 1) / approaches.length) * h);
        presets[app] = [
          [Math.round(w * 0.2), top],
          [Math.round(w * 0.8), top],
          [Math.round(w * 0.8), bottom],
          [Math.round(w * 0.2), bottom],
        ];
      }
    });

    Object.entries(presets).forEach(([app, poly]) => {
      roiState.polygons[`${activeNode}::${app}`] = poly;
    });

    roiState.currentPoints = [];
    markUnsaved(true);
    showToast(`Đã thiết lập mẫu mặc định cho nút ${activeNode}! Bạn có thể kéo các đỉnh để điều chỉnh.`, "success");
    redrawRoiCanvas();
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

    // Auto-fill any missing approach with safe default so save never fails
    const [w, h] = roiState.frameSize;
    const nodeIds = Object.keys(roiState.approaches || {});
    for (const nId of nodeIds) {
      nodes[nId] = nodes[nId] || {};
      const expectedApps = roiState.approaches[nId] || [];
      const missing = expectedApps.filter(a => !(nodes[nId] && nodes[nId][a]));
      if (missing.length > 0) {
        missing.forEach((app, idx) => {
          const top = Math.round((idx / missing.length) * h * 0.4);
          const bottom = Math.round(((idx + 1) / missing.length) * h * 0.4);
          nodes[nId][app] = [
            [Math.round(w * 0.2), top],
            [Math.round(w * 0.8), top],
            [Math.round(w * 0.8), bottom],
            [Math.round(w * 0.2), bottom]
          ];
          roiState.polygons[`${nId}::${app}`] = nodes[nId][app];
        });
      }
    }

    saveRoiBtn.disabled = true;
    saveRoiBtn.textContent = "Đang lưu & nạp vào video...";

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
        markUnsaved(false);
        showToast(`Đã lưu cấu hình ROI thành công! Video nhận diện đang nạp lại tọa độ mới.`, "success");
        setTimeout(() => {
          knownNodeIds.forEach(id => {
            if (window.reloadStream) window.reloadStream(id);
          });
          refreshRoiSnapshot();
        }, 1200);
      } else {
        showToast(`Lỗi lưu ROI: ${body.detail}`, "error");
      }
    } catch (err) {
      showToast("Lỗi kết nối khi lưu cấu hình ROI", "error");
    } finally {
      saveRoiBtn.disabled = false;
      markUnsaved(roiState.hasUnsavedChanges || false);
    }
  });
}

// Initial Boot
refreshActiveHistory();
loadRoi();
