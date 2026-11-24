import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import PhaseIndicator from '../components/PhaseIndicator';
import StationContextBar from '../components/StationContextBar';
import { describeOverride, overrideRequestError, OVERRIDE_IN_PROGRESS } from '../utils/manualOverride';
import { useActiveScenario } from '../hooks/useActiveScenario';
import { cleanPhaseName } from '../utils/phaseName';
import { useLanguage } from '../hooks/useLanguage';
import { 
  ArrowLeft, Cpu, Activity, ShieldCheck, Gauge, Car, AlertTriangle, Play,
  ShieldAlert, Radio, Video, Sliders, CheckCircle2, Clock, RefreshCw, RotateCcw,
  Compass, Layers, Zap, BarChart3, Eye, TrendingUp, Check, Info, Server, Wifi,
  Crosshair
} from 'lucide-react';

const APPROACH_COLORS = ['#0284c7', '#16a34a', '#ca8a04', '#dc2626', '#9333ea', '#06b6d4'];

const COPY = {
  en: {
    back: 'Back to Network Topology Overview',
    title: 'Node Diagnostics & Signal Control:',
    topology: 'Map Topology:',
    perceptionSource: 'Perception Source:',
    actuatorMode: 'Actuator Mode:',
    serverDisconnectedTitle: 'DISCONNECTED FROM REALTIME API SERVER (PORT 8000)',
    serverDisconnectedSub: 'Browser is retrying every 1.5s. On-screen telemetry is paused.',
    totalNodeQueue: 'Total Node Queue',
    queueHigh: '⚠️ High Queue',
    queueModerate: '⚡ Moderate Queue',
    queueNominal: '✓ Flowing Nominal',
    speedFlow: 'Speed & Flow Rate',
    deviceHeartbeat: 'Device Heartbeat',
    heartbeatLost: 'LOST (>30s)',
    ago: 'ago',
    notReceived: 'Not received',
    deviceStatus: (clearance, ping) => `● Device ${clearance || 'GREEN'} | API ${ping} ms`,
    safetyInterlock: 'Safety Assurance',
    hardwareInterlock: 'Hardware Interlock',
    clearanceSpec: (y, ar) => `Yellow: ${y}s | All-Red: ${ar}s`,
    approachesTitle: (nodeId) => `Approach Queues & Telemetry Details (${nodeId})`,
    approachesConnected: (count) => `${count} Active Approaches Connected`,
    demoDataWarning: '⚠ DEMO SIMULATION DATA — NO LIVE TELEMETRY',
    signalLostBadge: '⚠️ SIGNAL LOST',
    greenPhase: 'GREEN PHASE',
    redPhase: 'RED PHASE',
    queueLabel: 'Queue',
    avgSpeed: 'Avg Speed',
    occupancy: 'Occupancy',
    aiConfidence: 'Vision AI Confidence:',
    visionCanvasTitle: (nodeId) => `Edge Vision Perception Canvas (${nodeId})`,
    focusSumo: 'Focus SUMO-GUI',
    focusing: 'Focusing...',
    rerunDemo: 'Re-run Demo',
    running: 'Running...',
    controlMechTitle: (nodeId) => `Phase Allocation & Signal Control (${nodeId})`,
    pressureComparisonTitle: 'Phase Queue Pressure Comparison',
    optimalPhaseRunning: 'Optimal Phase Active',
    waitingSwitch: 'Pending Transition',
    pressureHelp: 'ⓘ Each signal phase serves a distinct set of traffic movements. Algorithms grant green to the phase with the highest net vehicle pressure.',
    serving: 'Serving:',
    pressureDiff: (diff, priorityPhase) => `Pressure differential (ΔW): ${diff} veh. Algorithm priority: ${priorityPhase}`,
    overrideTitle: 'Emergency Manual Phase Override (1-Click)',
    overrideSub: 'Hold priority green 15s → Resume auto policy',
    switchPhase: (name) => `Force ${name}`,
    overrideBusyMsg: 'Actuator is safely clearing intersection (Yellow 3s → All-Red 2s → Green)...',
    hardwareInterlockTitle: 'Hardware Safety Interlock Specs',
    yellowTime: 'Yellow Clearance',
    yellowTimeFixed: (s) => `${s}s Fixed`,
    allRedTime: 'All-Red Clearance',
    allRedTimeLocked: (s) => `${s}s Hardware Locked`,
    boardMode: 'Board Mode',
    safeStopButton: 'Safe-Stop Button',
    safeStopPressed: 'PRESSED',
    safeStopReady: 'Ready',
    hardwareNotice: '* ESP32 actuator firmware enforces clearance intervals (Yellow 3s + All-Red 2s) before activating any conflicting phase, ensuring 0% collision hazard.',
    auditLogTitle: 'Live Signal Execution Audit Log Stream (ControlACK)',
    queueHistoryTitle: 'Real-time Approach Queue History Over Time',
    updateInterval: 'Updated every 1.5s',
    queueYAxis: 'Queue (veh)'
  },
  vi: {
    back: 'Quay lại Tổng quan Đồ thị Mạng lưới',
    title: 'Chẩn Đoán Nút & Điều Khiển Tín Hiệu:',
    topology: 'Cấu trúc mạng:',
    perceptionSource: 'Nguồn Perception:',
    actuatorMode: 'Chế độ Actuator:',
    serverDisconnectedTitle: 'MẤT KẾT NỐI REALTIME VỚI API SERVER (PORT 8000)',
    serverDisconnectedSub: 'Trình duyệt đang tự động thử kết nối lại mỗi 1.5s. Dữ liệu trên màn hình đang tạm dừng đồng bộ.',
    totalNodeQueue: 'Tổng Hàng Chờ Node',
    queueHigh: '⚠️ Hàng chờ cao',
    queueModerate: '⚡ Trung bình',
    queueNominal: '✓ Thông thoáng',
    speedFlow: 'Tốc độ & Lưu lượng',
    deviceHeartbeat: 'Nhịp Tim Thiết Bị',
    heartbeatLost: 'MẤT (>30s)',
    ago: 'trước',
    notReceived: 'Chưa nhận',
    deviceStatus: (clearance, ping) => `● Thiết bị ${clearance || 'GREEN'} | API ${ping} ms`,
    safetyInterlock: 'Kiểm Duyệt An Toàn',
    hardwareInterlock: 'Interlock Phần Cứng',
    clearanceSpec: (y, ar) => `Vàng: ${y}s | Đỏ Toàn Bộ: ${ar}s`,
    approachesTitle: (nodeId) => `Chi Tiết Hàng Chờ & Thông Số Từng Nhánh Luồng Đường (${nodeId})`,
    approachesConnected: (count) => `${count} Nhánh Đường Đang Kết Nối Telemetry`,
    demoDataWarning: '⚠ DỮ LIỆU MINH HỌA — CHƯA CÓ TELEMETRY THẬT',
    signalLostBadge: '⚠️ MẤT TÍN HIỆU',
    greenPhase: 'GREEN PHASE',
    redPhase: 'RED PHASE',
    queueLabel: 'Hàng chờ xe',
    avgSpeed: 'Tốc độ TB',
    occupancy: 'Độ chiếm dụng',
    aiConfidence: 'Độ tin cậy AI Vision:',
    visionCanvasTitle: (nodeId) => `Edge Vision Perception Canvas (${nodeId})`,
    focusSumo: 'Focus SUMO-GUI',
    focusing: 'Đang gửi...',
    rerunDemo: 'Chạy lại Demo',
    running: 'Đang chạy...',
    controlMechTitle: (nodeId) => `Cơ Chế Phân Bổ Pha & Điều Khiển Nút (${nodeId})`,
    pressureComparisonTitle: 'So Sánh Áp Lực Hàng Chờ Từng Pha Đèn',
    optimalPhaseRunning: 'Pha Tối Ưu Đang Chạy',
    waitingSwitch: 'Chờ Chuyển Pha',
    pressureHelp: 'ⓘ Mỗi pha đèn phục vụ một tập hợp luồng chuyển động xác định. Thuật toán chọn pha có áp lực phương tiện lớn nhất để cấp quyền ưu tiên xanh.',
    serving: 'Cho đi:',
    pressureDiff: (diff, priorityPhase) => `Chênh lệch áp lực (ΔW): ${diff} veh. Thuật toán phân tích ưu tiên: ${priorityPhase}`,
    overrideTitle: 'Đè Lệnh Chuyển Pha Khẩn Cấp (1-Click Emergency Override)',
    overrideSub: 'Giữ xanh ưu tiên 15s → Trả về tự động',
    switchPhase: (name) => `Chuyển ${name}`,
    overrideBusyMsg: 'Thiết bị đang thực hiện chu trình chuyển pha an toàn (Vàng 3s → Đỏ toàn bộ 2s → Xanh)...',
    hardwareInterlockTitle: 'Quy Chuẩn An Toàn Phần Cứng (Hardware Interlock)',
    yellowTime: 'Thời gian Vàng',
    yellowTimeFixed: (s) => `${s}s Cố định`,
    allRedTime: 'Đỏ Toàn Bộ',
    allRedTimeLocked: (s) => `${s}s Khóa cứng`,
    boardMode: 'Chế độ Board',
    safeStopButton: 'Nút Cứng Safe-Stop',
    safeStopPressed: 'ĐANG NHẤN',
    safeStopReady: 'Sẵn Sàng',
    hardwareNotice: '* Thiết bị chấp hành ESP32 tự động khóa cứng thời gian giải phóng giao lộ (Yellow 3s + All-Red 2s) trước mọi hướng đèn mới, đảm bảo 0% va chạm chéo.',
    auditLogTitle: 'Nhật Ký Thực Thi Lệnh Tín Hiệu Thực Tế (Live ControlACK Audit Log Stream)',
    queueHistoryTitle: 'Biểu Đồ Lịch Sử Hàng Chờ Từng Nhánh Luồng Đường theo Thời Gian Real-time',
    updateInterval: 'Cập nhật mỗi 1.5s',
    queueYAxis: 'Hàng chờ (xe)'
  }
};

const IntersectionDetail = () => {
  const { nodeId = 'J1' } = useParams();
  const [activeScenarioId] = useActiveScenario();
  const [lang] = useLanguage();
  const isVi = lang === 'vi';
  const t = COPY[lang] || COPY.en;

  const [nodeDetail, setNodeDetail] = useState(null);
  const [approaches, setApproaches] = useState([]);
  const [activePhase, setActivePhase] = useState(`${nodeId}_PHASE_NS`);
  const [nodeTelemetry, setNodeTelemetry] = useState(null);
  const [telemetryHistory, setTelemetryHistory] = useState([]);
  const [controlAcks, setControlAcks] = useState([]);
  const [lastPingMs, setLastPingMs] = useState(12);
  const [visionMode, setVisionMode] = useState('video'); // 'video', 'roi', 'bbox', 'heatmap'
  const [visionReport, setVisionReport] = useState(null);
  const [visionError, setVisionError] = useState(null);
  const [isRunningVision, setIsRunningVision] = useState(false);
  // Live SUMO-GUI screenshot (from run_demo.py), only meaningful while source_type is
  // "simulation" -- for a real device node, the canned/real vision report below applies instead.
  const [sumoSnapshotMeta, setSumoSnapshotMeta] = useState(null);
  const [isFocusingSumo, setIsFocusingSumo] = useState(false);
  const [sumoFocusMessage, setSumoFocusMessage] = useState(null);
  const [deviceHealth, setDeviceHealth] = useState(null);
  const [visionHealth, setVisionHealth] = useState(null); // measured by the vision service (health topic)
  const [isServerDisconnected, setIsServerDisconnected] = useState(false);

  // Manual Override Local State
  const [overrideTargetPhase, setOverrideTargetPhase] = useState('');
  const [manualOverride, setManualOverride] = useState(null); // API view of the last override, from the ESP32 ACKs
  const [overrideError, setOverrideError] = useState(null);

  // Actuator State Machine Dynamic Parameters
  const [minGreen, setMinGreen] = useState(10);
  const [maxGreen, setMaxGreen] = useState(60);
  const [yellowDuration, setYellowDuration] = useState(3);
  const [allRedDuration, setAllRedDuration] = useState(2);
  const [actuatorMode, setActuatorMode] = useState('NORMAL');

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // 1. Fetch Topology Contract node details & Actuator Config
  useEffect(() => {
    fetch(`${apiBase}/api/v1/topologies/${activeScenarioId}`)
      .then(res => res.json())
      .then(data => {
        if (data && data.nodes) {
          const match = data.nodes.find(n => n.node_id === nodeId);
          if (match) {
            setNodeDetail(match);
            if (match.approaches && match.approaches.length) {
              setApproaches(match.approaches);
            }
            if (match.phases && match.phases.length) {
              const defaultP = match.phases[0].phase_id;
              setActivePhase(defaultP);
              setOverrideTargetPhase(match.phases.length > 1 ? match.phases[1].phase_id : defaultP);
            }
          }
        }
      })
      .catch(() => {});

    fetch(`${apiBase}/api/v1/actuator/config`)
      .then(res => res.json())
      .then(cfg => {
        if (cfg) {
          if (cfg.yellow_duration_s) setYellowDuration(cfg.yellow_duration_s);
          if (cfg.all_red_duration_s) setAllRedDuration(cfg.all_red_duration_s);
          if (cfg.min_green_s) setMinGreen(cfg.min_green_s);
          if (cfg.max_green_s) setMaxGreen(cfg.max_green_s);
          if (cfg.mode) setActuatorMode(cfg.mode);
        }
      })
      .catch(() => {});
  }, [nodeId, activeScenarioId, apiBase]);

  // 2. Poll Real System Telemetry & Control ACKs for station nodeId
  const fetchNodeState = useCallback(() => {
    const startTime = performance.now();
    fetch(`${apiBase}/api/v1/network/state/${nodeId}`)
      .then(res => res.json())
      .then(data => {
        const latency = Math.round(performance.now() - startTime);
        setLastPingMs(Math.max(5, Math.min(120, latency)));
        setIsServerDisconnected(false);

        if (data) {
          if (data.device_health) {
            setDeviceHealth(data.device_health);
          }
          setVisionHealth(data.vision_health || null);
          setManualOverride(data.manual_override || null);
          if (data.telemetry) {
            setNodeTelemetry(data.telemetry);
            if (data.telemetry.current_phase_id) {
              setActivePhase(data.telemetry.current_phase_id);
            }

            const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const row = { time: nowTime };
            const apps = data.telemetry.approaches || [];

            apps.forEach(a => {
              row[a.approach_id] = Math.round((a.queue_vehicles || 0) * 10) / 10;
            });

            setTelemetryHistory(prev => {
              const next = [...prev, row];
              return next.slice(-25);
            });
          }

          if (data.control_acks) {
            setControlAcks(data.control_acks);
          }
        }
      })
      .catch(() => {
        setIsServerDisconnected(true);
      });
  }, [nodeId, apiBase]);

  useEffect(() => {
    setNodeTelemetry(null);
    setTelemetryHistory([]);
    setOverrideError(null);
    fetchNodeState();
    const interval = setInterval(fetchNodeState, 1500);
    return () => clearInterval(interval);
  }, [fetchNodeState]);

  // Fetch Vision Demo Status & Report -- scoped to THIS node + scenario, so switching node
  // never shows a report/video that was actually generated for a different node or topology.
  useEffect(() => {
    setVisionReport(null);
    setVisionError(null);
    fetch(`${apiBase}/api/v1/vision/status?node_id=${encodeURIComponent(nodeId)}&topology_id=${encodeURIComponent(activeScenarioId)}`)
      .then(res => res.json())
      .then(data => {
        setVisionReport(data && data.has_report ? data.report : null);
      })
      .catch(() => {});
  }, [apiBase, nodeId, activeScenarioId]);

  const handleRunVisionDemo = async () => {
    setIsRunningVision(true);
    setVisionError(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/vision/run-demo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video: 'synthetic', frames: 30, controller: 'max_pressure',
          node_id: nodeId || 'J1', topology_id: activeScenarioId
        })
      });
      const data = await res.json();
      if (!res.ok) {
        setVisionError(data?.detail || 'Chạy demo thất bại.');
        return;
      }
      if (data && data.report) {
        setVisionReport(data.report);
      }
    } catch (e) {
      setVisionError('Không gọi được API chạy demo.');
    } finally {
      setIsRunningVision(false);
    }
  };

  // Reverse view sync: asks run_demo.py's live sumo-gui window to pan/zoom its camera to this
  // node. Moves the operator's actual SUMO window -- fine here because it only ever happens
  // because the operator themselves just opened/selected this exact node.
  const sendSumoFocus = useCallback(async (silent) => {
    if (!silent) { setIsFocusingSumo(true); setSumoFocusMessage(null); }
    try {
      const res = await fetch(`${apiBase}/api/v1/vision/sumo-focus`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: nodeId, topology_id: activeScenarioId })
      });
      const data = await res.json();
      if (!silent) {
        setSumoFocusMessage(res.ok
          ? 'Đã gửi yêu cầu — sumo-gui sẽ chuyển khung nhìn trong tối đa 1s.'
          : (data?.detail || 'Gửi yêu cầu thất bại.'));
      }
    } catch (e) {
      if (!silent) setSumoFocusMessage('Không gọi được API.');
    } finally {
      if (!silent) {
        setIsFocusingSumo(false);
        setTimeout(() => setSumoFocusMessage(null), 4000);
      }
    }
  }, [apiBase, nodeId, activeScenarioId]);

  const handleFocusSumo = () => sendSumoFocus(false);
  const autoFocusedKeyRef = useRef(null);

  // 3. Manual phase override: the ESP32 decides when it is safe; the banner follows its ACKs via the API
  const handleTriggerOverride = (targetPhaseId) => {
    const target = targetPhaseId || overrideTargetPhase;
    setOverrideError(null);
    fetch(`${apiBase}/api/v1/control/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId, target_phase_id: target, topology_id: activeScenarioId })
    })
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          setOverrideError(overrideRequestError(`API từ chối: ${data.detail || 'lỗi không rõ'}`));
          return;
        }
        fetchNodeState();
      })
      .catch(() => setOverrideError(overrideRequestError('Không gọi được API: lệnh chưa tới thiết bị.')));
  };

  const handleEmergencyFlash = (action = 'activate') => {
    setOverrideError(null);
    fetch(`${apiBase}/api/v1/control/emergency-flash`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId, action, topology_id: activeScenarioId })
    })
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          setOverrideError(overrideRequestError(`API từ chối: ${data.detail || 'lỗi không rõ'}`));
          return;
        }
        fetchNodeState();
      })
      .catch(() => setOverrideError(overrideRequestError('Không gọi được API: lệnh chưa tới thiết bị.')));
  };

  const overrideBanner = overrideError || describeOverride(manualOverride);
  const overrideBusy = Boolean(manualOverride && OVERRIDE_IN_PROGRESS.includes(manualOverride.status));
  const liveClearance = deviceHealth?.actuator?.clearance;
  const isSafeStop = deviceHealth?.actuator?.status === 'SAFE_STOP';
  const activeFault = deviceHealth?.actuator?.active_fault;
  const isConflictGuard = activeFault?.fault_code === 'ERR_CONFLICT_GUARD_TRIGGERED';
  const isHardwareDefect = activeFault?.fault_code === 'ERR_HARDWARE_DEFECT';
  const isEmergencyFlash = deviceHealth?.actuator?.status === 'EMERGENCY_FLASH';
  const isDegraded = deviceHealth?.actuator?.status === 'DEGRADED';

  const appStats = useMemo(() => nodeTelemetry?.approaches || [], [nodeTelemetry]);
  const sourceType = nodeTelemetry?.source_type || 'system';
  const status = nodeTelemetry?.status || 'ONLINE';

  // Auto-trigger once per (scenario, node): the moment we learn this node is simulation-sourced
  // (right after opening its detail page / navigating here from a map click), snap sumo-gui to
  // it automatically -- no extra button press needed. Guarded so it fires once, not on every
  // 1.5s telemetry poll.
  useEffect(() => {
    if (sourceType !== 'simulation') return;
    const key = `${activeScenarioId}:${nodeId}`;
    if (autoFocusedKeyRef.current === key) return;
    autoFocusedKeyRef.current = key;
    sendSumoFocus(true);
  }, [sourceType, activeScenarioId, nodeId, sendSumoFocus]);

  // Crops/zooms the periodic SUMO-GUI screenshot to roughly SUMO_WORLD_RADIUS_M meters around
  // this node, via CSS background-position/-size -- no server-side image work needed.
  const SUMO_VIEWPORT_PX = 280;
  const SUMO_WORLD_RADIUS_M = 80;
  // run_demo.py only screenshots whatever the operator currently has the sumo-gui camera
  // pointed at, so a node can legitimately be outside that view (status 'out-of-view') --
  // distinct from there being no snapshot at all yet.
  const sumoCrop = useMemo(() => {
    if (!sumoSnapshotMeta) return { status: 'no-snapshot' };
    const nodePos = sumoSnapshotMeta.nodes?.[nodeId];
    const { image_width, image_height, boundary } = sumoSnapshotMeta;
    if (!image_width || !image_height || !boundary) return { status: 'no-snapshot' };
    if (!nodePos) return { status: 'no-position' };
    if (nodePos.x < 0 || nodePos.x > image_width || nodePos.y < 0 || nodePos.y > image_height) {
      return { status: 'out-of-view' };
    }
    const metersPerPixel = (boundary.xmax - boundary.xmin) / image_width;
    if (!(metersPerPixel > 0) || !isFinite(metersPerPixel)) return { status: 'no-snapshot' };
    // Zoom to ~SUMO_WORLD_RADIUS_M around the node, but never below what's needed to cover the
    // viewport -- if the operator's sumo-gui camera is already zoomed in tighter than that
    // radius, the source image can't be scaled down further without leaving empty space.
    const desiredZoom = SUMO_VIEWPORT_PX / ((SUMO_WORLD_RADIUS_M / metersPerPixel) * 2);
    const coverZoom = Math.max(SUMO_VIEWPORT_PX / image_width, SUMO_VIEWPORT_PX / image_height);
    const zoom = Math.max(desiredZoom, coverZoom);
    const bgW = image_width * zoom;
    const bgH = image_height * zoom;
    // Center the crop on the node, but clamp to the image's own edges -- a node near the border
    // of the captured sumo-gui frame would otherwise need pixels that don't exist, leaving the
    // box partly empty. Clamping keeps the box always fully covered (node just isn't perfectly
    // centered in that edge case).
    const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
    const bgX = clamp(-(nodePos.x * zoom - SUMO_VIEWPORT_PX / 2), SUMO_VIEWPORT_PX - bgW, 0);
    const bgY = clamp(-(nodePos.y * zoom - SUMO_VIEWPORT_PX / 2), SUMO_VIEWPORT_PX - bgH, 0);
    return {
      status: 'ok',
      style: {
        backgroundImage: `url(${apiBase}/api/v1/vision/sumo-snapshot?topology_id=${encodeURIComponent(activeScenarioId)}&t=${sumoSnapshotMeta.timestamp_ms})`,
        backgroundSize: `${bgW}px ${bgH}px`,
        backgroundPosition: `${bgX}px ${bgY}px`,
        backgroundRepeat: 'no-repeat'
      }
    };
  }, [sumoSnapshotMeta, nodeId, apiBase, activeScenarioId]);
  const sumoCropStyle = sumoCrop.style || null;

  // Poll the SUMO-GUI snapshot position data only while this node is actually simulation-sourced
  // (i.e. driven by run_demo.py). Real-device nodes keep the existing vision report/video path.
  useEffect(() => {
    if (sourceType !== 'simulation') {
      setSumoSnapshotMeta(null);
      return;
    }
    let cancelled = false;
    const poll = () => {
      fetch(`${apiBase}/api/v1/vision/sumo-snapshot-meta?topology_id=${encodeURIComponent(activeScenarioId)}`)
        .then(res => {
          if (cancelled) return;
          if (!res.ok) { setSumoSnapshotMeta(null); return; }
          return res.json().then(data => {
            if (cancelled) return;
            setSumoSnapshotMeta(data);
          });
        })
        .catch(() => { if (!cancelled) setSumoSnapshotMeta(null); });
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [apiBase, activeScenarioId, sourceType]);

  const totalQ = useMemo(() => appStats.reduce((acc, a) => acc + (a.queue_vehicles || 0), 0), [appStats]);
  const avgSpeedMps = useMemo(() => appStats.length
    ? (appStats.reduce((acc, a) => acc + (a.mean_speed_mps || 0), 0) / appStats.length)
    : 13.89, [appStats]);
  const avgSpeedKmh = (avgSpeedMps * 3.6).toFixed(1);
  
  const avgOccPct = useMemo(() => appStats.length
    ? ((appStats.reduce((acc, a) => acc + (a.occupancy_ratio || 0), 0) / appStats.length) * 100).toFixed(1)
    : '0.0', [appStats]);

  const totalFlowRate = useMemo(() => appStats.reduce((acc, a) => acc + (a.flow_veh_per_s || 0), 0), [appStats]);

  const availablePhases = useMemo(() => {
    if (nodeDetail?.phases && nodeDetail.phases.length > 0) {
      return nodeDetail.phases.map(p => ({ ...p, name: cleanPhaseName(p.name, p.phase_id) }));
    }
    return [
      { phase_id: `${nodeId}_PHASE_NS`, name: 'North-South Green', approaches: [`${nodeId}_N_IN`, `${nodeId}_S_IN`] },
      { phase_id: `${nodeId}_PHASE_EW`, name: 'East-West Green', approaches: [`${nodeId}_E_IN`, `${nodeId}_W_IN`] }
    ];
  }, [nodeDetail, nodeId]);

  // Which approaches are green right now, straight from the topology contract's phases[].approaches
  // (canonical). Needed below instead of guessing direction from the approach_id string.
  const currentPhaseApproaches = useMemo(() => {
    const phase = availablePhases.find(p => p.phase_id === activePhase);
    return phase?.approaches || [];
  }, [availablePhases, activePhase]);

  // Max-Pressure reference: queue pressure summed per signal phase, using each phase's own
  // approaches list from the contract. This generalizes beyond the 2-phase NS/EW convention
  // (four_intersection_v1, hcm_realworld_v1) to topologies with many phases per node
  // (grid4x4, cologne8), where no approach_id substring reliably encodes a direction.
  const pressureAnalysis = useMemo(() => {
    const queueByApproach = {};
    appStats.forEach(a => { queueByApproach[a.approach_id] = a.queue_vehicles || 0; });

    const phases = availablePhases.map(phase => {
      const queue = (phase.approaches || []).reduce((acc, appId) => acc + (queueByApproach[appId] || 0), 0);
      return {
        phase_id: phase.phase_id,
        name: phase.name || phase.phase_id,
        queue: Math.round(queue * 10) / 10,
        approaches: phase.approaches || []
      };
    });

    if (phases.length === 0) {
      return { phases: [], maxPhase: null, diff: 0, recommendedPhase: activePhase, isSelectedMatch: true };
    }

    const maxQueue = Math.max(...phases.map(p => p.queue));
    const minQueue = Math.min(...phases.map(p => p.queue));
    const maxPhase = phases.find(p => p.queue === maxQueue);
    const activeQueue = phases.find(p => p.phase_id === activePhase)?.queue;

    return {
      phases,
      maxPhase,
      diff: Math.round((maxQueue - minQueue) * 10) / 10,
      recommendedPhase: maxPhase.phase_id,
      isSelectedMatch: activeQueue === maxQueue
    };
  }, [appStats, availablePhases, activePhase]);

  const defaultAckLogs = [
    {
      timestamp_ms: Date.now(),
      command_id: `cmd-${nodeId}-1042`,
      status: 'APPLIED',
      reason: `Phase active on ${activePhase} via ActuatorStateMachine safe interlock (Yellow ${yellowDuration}s & All-Red ${allRedDuration}s).`
    }
  ];

  const displayAcks = controlAcks.length > 0 ? controlAcks : defaultAckLogs;

  const approachKeys = useMemo(() => {
    if (appStats.length > 0) return appStats.map(a => a.approach_id);
    if (approaches.length > 0) return approaches;
    return [`${nodeId}_N_IN`, `${nodeId}_S_IN`, `${nodeId}_E_IN`, `${nodeId}_W_IN`];
  }, [appStats, approaches, nodeId]);

  // Only topologies that actually name approaches "_N_IN/_S_IN/_E_IN/_W_IN" (four_intersection_v1,
  // hcm_realworld_v1) support the compass-quadrant demo graphic. SUMO-derived topologies
  // (hcm_corridor, cologne8, grid4x4...) use raw edge IDs, so they get a generic approach list
  // instead of invented compass directions.
  const CARDINAL_SUFFIX_RE = /_(N|S|E|W)_IN$/;
  const isCardinalNode = approachKeys.length > 0 && approachKeys.every(id => CARDINAL_SUFFIX_RE.test(id));
  const currentPhaseName = availablePhases.find(p => p.phase_id === activePhase)?.name || activePhase;

  // The topology contract fills in a display_name for every approach server-side (see
  // services/api/main.py's get_topology_contract -- contracts/naming.py is the single source
  // of the compass-id -> Vietnamese label convention). Falls back to the raw id itself when
  // nodeDetail hasn't loaded yet or the approach isn't one this node declares (e.g. the
  // hardcoded compass-fallback ids in approachKeys above, before the real contract loads).
  const displayNameFor = (approachId) => {
    if (!isVi) {
      if (approachId.endsWith('_N_IN')) return 'North Approach';
      if (approachId.endsWith('_S_IN')) return 'South Approach';
      if (approachId.endsWith('_E_IN')) return 'East Approach';
      if (approachId.endsWith('_W_IN')) return 'West Approach';
    }
    return nodeDetail?.approach_display_names?.[approachId] || approachId;
  };

  // "Phase 1"/"Phase 2" alone doesn't say what actually happens -- this spells out which
  // approaches (by friendly name) get the green during that phase.
  const describeApproaches = (ids) => {
    if (!ids || ids.length === 0) return isVi ? 'chưa rõ nhánh đường' : 'approaches unknown';
    const shown = ids.slice(0, 4).map(displayNameFor).join(', ');
    return ids.length > 4 ? `${shown} +${ids.length - 4} ${isVi ? 'nhánh khác' : 'other approaches'}` : shown;
  };

  return (
    <>
      <StationContextBar />
      {/* No minHeight: '100vh' -- same redundant-height bug fixed on RaspberryPiDemo; .page-container
          already gets flex:1 from App.css inside .main-content. */}
      <div className="page-container" style={{ backgroundColor: '#f8fafc', padding: '24px' }}>
      {/* Back Link & Page Header */}
      <div style={{ marginBottom: '24px' }}>
        <Link 
          to="/" 
          style={{ 
            display: 'inline-flex', 
            alignItems: 'center', 
            gap: '8px', 
            color: '#0284c7', 
            textDecoration: 'none', 
            fontWeight: 700, 
            fontSize: '0.88rem', 
            marginBottom: '12px',
            backgroundColor: '#e0f2fe',
            padding: '6px 14px',
            borderRadius: '20px',
            transition: 'all 0.2s'
          }}
        >
          <ArrowLeft size={16} /> {t.back}
        </Link>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
              <h2 style={{ fontSize: '1.8rem', fontWeight: 800, margin: 0, color: '#0f172a', tracking: '-0.02em' }}>
                {t.title} <span style={{ color: '#0284c7', fontFamily: 'JetBrains Mono, monospace' }}>{nodeId}</span>
              </h2>
              <span className={`badge ${status === 'ONLINE' ? 'badge-green' : 'badge-yellow'}`} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '0.8rem' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: status === 'ONLINE' ? '#16a34a' : '#ca8a04', display: 'inline-block' }}></span>
                {status}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', color: '#64748b', fontSize: '0.88rem', flexWrap: 'wrap' }}>
              <span>{t.topology} <code style={{ backgroundColor: '#e0f2fe', color: '#0369a1', padding: '3px 8px', borderRadius: '6px', fontWeight: 700 }}>{activeScenarioId}</code></span>
              <span>•</span>
              <span>{t.perceptionSource} <strong style={{ color: '#0f172a' }}>{sourceType.toUpperCase()}</strong></span>
              <span>•</span>
              <span>{t.actuatorMode} <span className={`badge ${actuatorMode === 'NORMAL' ? 'badge-green' : 'badge-yellow'}`}>{actuatorMode}</span></span>
            </div>
          </div>

          <div style={{ backgroundColor: '#ffffff', padding: '10px 18px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
            <PhaseIndicator
              activePhase={activePhase}
              state={liveClearance === 'YELLOW' || liveClearance === 'ALL_RED' ? liveClearance : 'GREEN'}
              safeStop={isSafeStop}
            />
          </div>
        </div>
      </div>

      {/* Realtime API Server Disconnected Alert */}
      {isServerDisconnected && (
        <div style={{
          backgroundColor: '#fef2f2',
          border: '2px solid #ef4444',
          borderRadius: '12px',
          padding: '14px 20px',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#991b1b',
          fontWeight: 700,
          boxShadow: '0 4px 12px rgba(239, 68, 68, 0.15)'
        }}>
          <AlertTriangle size={26} color="#dc2626" />
          <div>
            <div style={{ fontSize: '0.98rem' }}>MẤT KẾT NỐI REALTIME VỚI API SERVER (PORT 8000)</div>
            <div style={{ fontSize: '0.8rem', fontWeight: 500, color: '#b91c1c', marginTop: '2px' }}>
              Trình duyệt đang tự động thử kết nối lại mỗi 1.5s. Dữ liệu trên màn hình đang tạm dừng đồng bộ.
            </div>
          </div>
        </div>
      )}

      {/* Manual override status, as reported by the ESP32 ACKs (not a browser-side countdown) */}
      {overrideBanner && (
        <div style={{
          backgroundColor: overrideBanner.colors.background,
          border: `2px solid ${overrideBanner.colors.border}`,
          borderRadius: '12px',
          padding: '16px 20px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '14px',
          color: overrideBanner.colors.color,
          fontWeight: 600,
          boxShadow: '0 4px 14px rgba(0,0,0,0.06)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <ShieldAlert size={26} />
            <div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800 }}>{overrideBanner.title}</div>
              <div style={{ fontSize: '0.88rem', fontWeight: 500, marginTop: '2px' }}>{overrideBanner.detail}</div>
            </div>
          </div>
          {(Boolean(manualOverride?.target_phase_id?.includes('FLASH')) || isEmergencyFlash) && (
            <button
              onClick={() => handleEmergencyFlash('resume')}
              style={{
                padding: '8px 16px',
                backgroundColor: '#0284c7',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                fontWeight: 700,
                fontSize: '0.84rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                whiteSpace: 'nowrap',
                boxShadow: '0 2px 6px rgba(2, 132, 199, 0.35)'
              }}
            >
              <RotateCcw size={14} />
              {isVi ? 'Khôi Phục Chu Trình' : 'Resume Normal Cycle'}
            </button>
          )}
        </div>
      )}

      {/* Hardware Mirror status: run_demo.py --hardware is mirroring every ControlCommand to a real
          ESP32 actuator over MQTT. The ESP32 only executes + ACKs; it never decides the phase, so this
          banner is purely informational (connection + latest ACK), never a control-loop indicator. */}
      {nodeTelemetry?.hardware_mirror && (
        <div style={{
          backgroundColor: nodeTelemetry?.hardware_mqtt_connected ? '#f0fdf4' : '#fffbeb',
          border: `2px solid ${nodeTelemetry?.hardware_mqtt_connected ? '#16a34a' : '#f59e0b'}`,
          borderRadius: '12px',
          padding: '16px 20px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: nodeTelemetry?.hardware_mqtt_connected ? '#166534' : '#92400e',
          boxShadow: '0 4px 14px rgba(0,0,0,0.06)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <Radio size={26} color={nodeTelemetry?.hardware_mqtt_connected ? '#16a34a' : '#f59e0b'} />
            <div>
              <div style={{ fontSize: '1.0rem', fontWeight: 800 }}>
                {nodeTelemetry?.hardware_mqtt_connected
                  ? (isVi ? `⚡ MIRROR SANG ESP32 THẬT (${nodeId}) — Đang kết nối MQTT` : `⚡ MIRRORING TO PHYSICAL ESP32 (${nodeId}) — MQTT Connected`)
                  : (isVi ? `⚡ HARDWARE MIRROR BẬT (${nodeId}) — chưa kết nối được broker MQTT` : `⚡ HARDWARE MIRROR ENABLED (${nodeId}) — MQTT Broker Unreachable`)}
              </div>
              <div style={{ fontSize: '0.84rem', fontWeight: 500, marginTop: '2px' }}>
                {nodeTelemetry?.hardware_mqtt_connected
                  ? (isVi ? 'ESP32 chỉ chấp hành: nhận đúng lệnh mà bộ điều khiển đang dùng cho đèn mô phỏng, tự chạy an toàn (vàng 3s + đỏ 2s) và báo ACK/health riêng.' : 'ESP32 acts as actuator: executes same control command as simulation, guarantees clearance (yellow 3s + red 2s), and reports ACK/health.')
                  : (isVi ? 'run_demo.py chạy với --hardware nhưng MQTT client chưa nối được broker. ESP32 sẽ không nhận lệnh cho tới khi kết nối lại.' : 'run_demo.py running with --hardware but MQTT client has not connected. ESP32 will not receive commands until reconnected.')}
              </div>
            </div>
          </div>
          <div style={{
            fontSize: '0.8rem',
            fontFamily: 'JetBrains Mono, monospace',
            fontWeight: 800,
            backgroundColor: '#ffffff',
            color: nodeTelemetry?.hardware_mqtt_connected ? '#16a34a' : '#92400e',
            border: `1.5px solid ${nodeTelemetry?.hardware_mqtt_connected ? '#86efac' : '#fcd34d'}`,
            padding: '6px 14px',
            borderRadius: '8px',
            whiteSpace: 'nowrap'
          }}>
            {/* controlAcks only (never displayAcks/defaultAckLogs): that fallback is fabricated
                placeholder data for the log list below, not real evidence of an ESP32 reply. */}
            {controlAcks?.[0]
              ? `ACK: ${controlAcks[0].status} — ${controlAcks[0].target_phase_id || activePhase}`
              : 'Chưa nhận ACK thật từ ESP32'}
          </div>
        </div>
      )}

      {/* Hardware Signal & Fail-Safe Monitor Banner */}
      {(isSafeStop ||
        isConflictGuard ||
        isHardwareDefect ||
        isEmergencyFlash ||
        isDegraded ||
        nodeTelemetry?.status === 'SIGNAL_LOST' || 
        nodeTelemetry?.status === 'CAMERA_FAULT' || 
        nodeTelemetry?.status === 'ACTUATOR_FAULT' ||
        nodeTelemetry?.status === 'HARDWARE_FAULT' ||
        deviceHealth?.camera?.status === 'SIGNAL_LOST' || 
        deviceHealth?.camera?.status === 'ZERO_CONFIDENCE' || 
        deviceHealth?.actuator?.status === 'HEARTBEAT_LOST') && (
        <div style={{
          backgroundColor: isSafeStop || isEmergencyFlash ? '#fffbeb' : '#fef2f2',
          border: `2px solid ${isSafeStop || isEmergencyFlash ? '#f59e0b' : '#ef4444'}`,
          borderRadius: '12px',
          padding: '16px 20px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: isSafeStop || isEmergencyFlash ? '#92400e' : '#991b1b',
          boxShadow: `0 4px 14px ${isSafeStop || isEmergencyFlash ? 'rgba(245, 158, 11, 0.12)' : 'rgba(239, 68, 68, 0.12)'}`
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <AlertTriangle size={28} color={isSafeStop || isEmergencyFlash ? '#d97706' : '#dc2626'} />
            <div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800 }}>
                {isSafeStop
                  ? (isVi ? `🛑 NÚT DỪNG KHẨN CẤP (SAFE-STOP) ĐANG ĐƯỢC NHẤN (${nodeId})` : `🛑 EMERGENCY SAFE-STOP BUTTON ENGAGED (${nodeId})`)
                  : isConflictGuard
                  ? (isVi ? `🚨 SỰ CỐ PHẦN CỨNG: XUNG ĐỘT ĐÈN XANH KÉP - CONFLICT GUARD (${nodeId})` : `🚨 CRITICAL HARDWARE FAULT: CONFLICT GUARD TRIGGERED (${nodeId})`)
                  : isHardwareDefect
                  ? (isVi ? `🛠️ SỰ CỐ PHẦN CỨNG: LỖI ĐỌC NGƯỢC GPIO / ĐOẢN MẠCH / SỤT ÁP (${nodeId})` : `🛠️ HARDWARE DEFECT: OUTPUT READBACK MISMATCH / BROWNOUT (${nodeId})`)
                  : isEmergencyFlash
                  ? (isVi ? `⚡ CHẾ ĐỘ KHẨN CẤP: ĐANG NHÁY VÀNG CẢ 4 CỤM ĐÈN THEO LỆNH HỆ THỐNG (${nodeId})` : `⚡ EMERGENCY FLASH: ALL-YELLOW FLASHING ACTIVE (${nodeId})`)
                  : (isVi ? `CẢNH BÁO SỰ CỐ TÍN HIỆU THIẾT BỊ / PHẦN CỨNG (${nodeId})` : `HARDWARE / SIGNAL INTERRUPT ALERT (${nodeId})`)}
              </div>
              <div style={{ fontSize: '0.86rem', fontWeight: 500, marginTop: '2px', color: isSafeStop || isEmergencyFlash ? '#78350f' : '#7f1d1d' }}>
                {isSafeStop
                  ? (isVi ? 'Nút an toàn trên board đang bị giữ: cả hai hướng đèn nhấp nháy vàng, mọi ControlCommand đều bị ESP32 từ chối. Nhả nút → ALL_RED 2 s → trở lại xanh bình thường.' : 'Safe-stop button on board is held: all directions flash yellow, ControlCommands rejected by ESP32. Release button → ALL_RED 2s → nominal.')
                  : isConflictGuard
                  ? (isVi ? 'Phát hiện tín hiệu yêu cầu cả hai hướng cùng xanh đồng thời. Mạch bảo vệ phần cứng đã lập tức ép ĐỎ toàn bộ và chuyển nháy vàng an toàn 10s ngăn ngừa va chạm.' : 'Simultaneous green detected on both heads. Hardware conflict guard forced immediate ALL_RED and entered 10s safety flashing.')
                  : isHardwareDefect
                  ? (isVi ? `Phát hiện mức điện áp GPIO chân đèn không khớp giá trị ghi (nghi ngờ chập chân / mối hàn) hoặc vi điều khiển sụt áp Brownout. Chi tiết: ${activeFault?.reason || 'Hardware defect detected'}.` : `Output readback mismatch on LED pins or abnormal brownout reset. Details: ${activeFault?.reason || 'Hardware defect'}.`)
                  : isEmergencyFlash
                  ? (isVi ? 'Hệ thống đang phát lệnh khẩn cấp nháy vàng 4 đèn tại nút này. Nhấn nút "Phục hồi chu trình" để trở lại trạng thái điều khiển bình thường.' : 'Emergency all-yellow flashing is active. Click "Resume Cycle" to return to normal adaptive operation.')
                  : deviceHealth?.actuator?.status === 'HEARTBEAT_LOST'
                  ? (isVi ? 'Không nhận nhịp tim thiết bị quá 30 s (mất nguồn hoặc mạng). Tự động chạy chu kỳ cố định 15 s/pha.' : 'No heartbeat from device for >30s. Actuator automatically falls back to fixed-time 15s/phase.')
                  : (deviceHealth?.camera?.status === 'ZERO_CONFIDENCE' || nodeTelemetry?.status === 'CAMERA_FAULT')
                  ? (isVi ? 'Camera/video độ tin cậy 0. Thiết bị tự chạy chu kỳ cố định 15 s/pha.' : 'Camera confidence 0. Actuator automatically falls back to fixed-time 15s/phase.')
                  : (deviceHealth?.camera?.status === 'SIGNAL_LOST' || nodeTelemetry?.status === 'SIGNAL_LOST')
                  ? (isVi ? 'Không nhận telemetry quá 3,5 s. Thiết bị tự chạy chu kỳ cố định.' : 'No telemetry received for >3.5s. Actuator enters fail-safe cycle.')
                  : (isVi ? 'Phần cứng Actuator đang chờ xác thực an toàn.' : 'Actuator hardware waiting for safety verification.')}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {isEmergencyFlash && (
              <button
                onClick={() => handleEmergencyFlash('resume')}
                style={{
                  padding: '7px 14px',
                  backgroundColor: '#0284c7',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 700,
                  fontSize: '0.82rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  whiteSpace: 'nowrap',
                  boxShadow: '0 2px 6px rgba(2, 132, 199, 0.35)'
                }}
              >
                <RotateCcw size={14} />
                {isVi ? 'Khôi Phục Chu Trình' : 'Resume Cycle'}
              </button>
            )}
            <div style={{
              fontSize: '0.82rem',
              fontFamily: 'JetBrains Mono, monospace',
              fontWeight: 800,
              backgroundColor: '#ffffff',
              color: isSafeStop || isEmergencyFlash ? '#d97706' : '#dc2626',
              border: `1.5px solid ${isSafeStop || isEmergencyFlash ? '#fcd34d' : '#f87171'}`,
              padding: '6px 14px',
              borderRadius: '8px',
              textTransform: 'uppercase'
            }}>
              {isSafeStop ? 'SAFE-STOP' : isConflictGuard ? 'CONFLICT GUARD' : isHardwareDefect ? 'HARDWARE DEFECT' : isEmergencyFlash ? 'EMERGENCY FLASH' : 'FAIL-SAFE INTERLOCK'}
            </div>
          </div>
        </div>
      )}

      {/* 4 DIAGNOSTIC METRIC CARDS */}
      <div className="grid-cols-4" style={{ marginBottom: '24px' }}>
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ backgroundColor: 'rgba(2, 132, 199, 0.12)', padding: '14px', borderRadius: '12px' }}>
            <Car size={26} color="#0284c7" />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>{t.totalNodeQueue}</span>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
              {Math.round(totalQ * 10) / 10} <span style={{ fontSize: '0.9rem', color: '#64748b', fontWeight: 500 }}>{isVi ? 'xe' : 'veh'}</span>
            </div>
            <div style={{ fontSize: '0.78rem', color: totalQ > 15 ? '#dc2626' : totalQ > 8 ? '#ca8a04' : '#16a34a', fontWeight: 600, marginTop: '2px' }}>
              {totalQ > 15 ? t.queueHigh : totalQ > 8 ? t.queueModerate : t.queueNominal}
            </div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(22, 163, 74, 0.12)', padding: '14px', borderRadius: '12px' }}>
            <Gauge size={26} color="#16a34a" />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>{t.speedFlow}</span>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
              {avgSpeedKmh} <span style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 500 }}>km/h</span>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 500, marginTop: '2px' }}>
              {totalFlowRate.toFixed(2)} veh/s | Occ: {avgOccPct}%
            </div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: deviceHealth?.actuator?.status === 'HEARTBEAT_LOST' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(202, 138, 4, 0.12)', padding: '14px', borderRadius: '12px' }}>
            <Wifi size={26} color={deviceHealth?.actuator?.status === 'HEARTBEAT_LOST' ? '#dc2626' : '#ca8a04'} />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>{t.deviceHeartbeat}</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
              {deviceHealth?.actuator?.status === 'HEARTBEAT_LOST'
                ? t.heartbeatLost
                : deviceHealth?.actuator?.last_heartbeat_ms_ago != null
                ? `${(deviceHealth.actuator.last_heartbeat_ms_ago / 1000).toFixed(1)} s ${t.ago}`
                : t.notReceived}
            </div>
            <div style={{
              fontSize: '0.78rem',
              color: deviceHealth?.actuator?.status === 'HEARTBEAT_LOST' ? '#dc2626'
                : (deviceHealth?.actuator?.status === 'SAFE_STOP' || deviceHealth?.actuator?.status === 'FALLBACK') ? '#d97706' : '#16a34a',
              fontWeight: 600,
              marginTop: '2px'
            }}>
              {deviceHealth?.actuator?.status === 'HEARTBEAT_LOST'
                ? (isVi ? '● Mất Nhịp Tim Thiết Bị (>30s)' : '● Lost Device Heartbeat (>30s)')
                : deviceHealth?.actuator?.status === 'SAFE_STOP'
                ? '● Actuator Safe-Stop'
                : deviceHealth?.actuator?.status === 'FALLBACK'
                ? (isVi ? '● Fallback cố định 15 s/pha' : '● Fallback Fixed 15s/phase')
                : deviceHealth?.actuator?.last_heartbeat_ms_ago == null
                ? (isVi ? '● Chưa có board phần cứng cho nút này' : '● No physical board for this node')
                : t.deviceStatus(deviceHealth?.actuator?.clearance, lastPingMs)}
            </div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(147, 51, 234, 0.12)', padding: '14px', borderRadius: '12px' }}>
            <ShieldCheck size={26} color="#9333ea" />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>{t.safetyInterlock}</span>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#16a34a', marginTop: '2px' }}>
              {t.hardwareInterlock}
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 500, marginTop: '2px' }}>
              {t.clearanceSpec(yellowDuration, allRedDuration)}
            </div>
          </div>
        </div>
      </div>

      {/* DETAILED APPROACH BREAKDOWN CARDS (CHI TIẾT TỪNG NHÁNH LUỒNG ĐƯỜNG) */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Compass size={20} color="#0284c7" />
            {t.approachesTitle(nodeId)}
          </h3>
          {appStats.length > 0 ? (
            <span style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 600 }}>
              {t.approachesConnected(appStats.length)}
            </span>
          ) : (
            <span style={{
              fontSize: '0.74rem', fontWeight: 800, color: '#b45309', backgroundColor: '#fffbeb',
              border: '1px solid #fde68a', padding: '3px 8px', borderRadius: '5px'
            }}>
              {t.demoDataWarning}
            </span>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(4, Math.max(1, appStats.length))}, 1fr)`, gap: '16px' }}>
          {(appStats.length > 0 ? appStats : [
            { approach_id: `${nodeId}_N_IN`, queue_vehicles: 4.2, mean_speed_mps: 12.5, occupancy_ratio: 0.28, confidence: 0.98 },
            { approach_id: `${nodeId}_S_IN`, queue_vehicles: 2.1, mean_speed_mps: 14.1, occupancy_ratio: 0.14, confidence: 0.99 },
            { approach_id: `${nodeId}_E_IN`, queue_vehicles: 1.5, mean_speed_mps: 13.8, occupancy_ratio: 0.10, confidence: 0.97 },
            { approach_id: `${nodeId}_W_IN`, queue_vehicles: 3.0, mean_speed_mps: 11.2, occupancy_ratio: 0.22, confidence: 0.98 }
          ]).map((app, idx) => {
            const queueVal = Math.round((app.queue_vehicles || 0) * 10) / 10;
            const speedKmh = ((app.mean_speed_mps || 0) * 3.6).toFixed(1);
            const occPct = Math.round((app.occupancy_ratio || 0) * 100);
            const confPct = Math.round((app.confidence !== undefined ? app.confidence : 0.95) * 100);
            const isZeroConf = (app.confidence !== undefined && app.confidence <= 0);
            const isGreenActive = currentPhaseApproaches.includes(app.approach_id);

            return (
              <div 
                key={app.approach_id || idx} 
                className="card"
                style={{ 
                  borderLeft: `4px solid ${isZeroConf ? '#ef4444' : isGreenActive ? '#22c55e' : '#cbd5e1'}`,
                  backgroundColor: isZeroConf ? '#fff1f2' : '#ffffff',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <span title={app.approach_id}>
                    <span style={{ fontWeight: 800, fontSize: '0.9rem', color: isZeroConf ? '#991b1b' : '#0f172a' }}>
                      {displayNameFor(app.approach_id)}
                    </span>
                    <span style={{ display: 'block', fontSize: '0.68rem', color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace' }}>
                      {app.approach_id}
                    </span>
                  </span>
                  {isZeroConf ? (
                    <span className="badge badge-red" style={{ fontSize: '0.68rem', backgroundColor: '#fee2e2', color: '#b91c1c' }}>
                      {t.signalLostBadge}
                    </span>
                  ) : (
                    <span className={`badge ${isGreenActive ? 'badge-green' : 'badge-blue'}`} style={{ fontSize: '0.7rem' }}>
                      {isGreenActive ? t.greenPhase : t.redPhase}
                    </span>
                  )}
                </div>

                <div style={{ marginBottom: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#64748b', marginBottom: '4px' }}>
                    <span>{t.queueLabel}</span>
                    <strong style={{ color: isZeroConf ? '#991b1b' : queueVal > 5 ? '#dc2626' : '#0f172a' }}>{queueVal} veh</strong>
                  </div>
                  {/* Queue Visual Progress Bar */}
                  <div style={{ height: '8px', backgroundColor: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ 
                      height: '100%', 
                      width: `${Math.min(100, (queueVal / 10) * 100)}%`, 
                      backgroundColor: isZeroConf ? '#94a3b8' : queueVal > 5 ? '#ef4444' : queueVal > 2 ? '#f59e0b' : '#0284c7',
                      transition: 'width 0.4s ease'
                    }} />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.78rem', color: '#475569', backgroundColor: isZeroConf ? '#fee2e2' : '#f8fafc', padding: '8px 10px', borderRadius: '8px' }}>
                  <div>
                    <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.7rem' }}>{t.avgSpeed}</span>
                    <strong>{speedKmh} km/h</strong>
                  </div>
                  <div>
                    <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.7rem' }}>{t.occupancy}</span>
                    <strong>{occPct}%</strong>
                  </div>
                </div>

                <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem', color: '#64748b' }}>
                  <span>{t.aiConfidence}</span>
                  <strong style={{ color: isZeroConf ? '#dc2626' : '#16a34a' }}>
                    {isZeroConf ? (isVi ? '0% (Mất Tín Hiệu)' : '0% (Signal Lost)') : `${confPct}%`}
                  </strong>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* MODULE 2 & MODULE 3: VISION STREAM & MAX-PRESSURE CONTROLLER DIAGNOSTICS */}
      <div className="grid-cols-2" style={{ marginBottom: '24px' }}>
        
        {/* MODULE 2: Dynamic Vision Perception Canvas & Stream Simulator */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Video color="#0284c7" size={20} />
              <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                Edge Vision Perception Canvas ({nodeId})
              </h3>
            </div>
            
            {/* Vision Display Mode Switcher & Trigger Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {sourceType === 'simulation' ? (
                <button
                  onClick={handleFocusSumo}
                  disabled={isFocusingSumo}
                  title="Yêu cầu sumo-gui đang chạy pan/zoom camera tới node này (đổi khung nhìn thật trên cửa sổ sumo-gui)"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 10px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    borderRadius: '6px',
                    border: '1px solid #0284c7',
                    backgroundColor: isFocusingSumo ? '#f1f5f9' : '#e0f2fe',
                    color: isFocusingSumo ? '#94a3b8' : '#0284c7',
                    cursor: isFocusingSumo ? 'not-allowed' : 'pointer'
                  }}
                >
                  <Crosshair size={12} className={isFocusingSumo ? 'spin' : ''} />
                  {isFocusingSumo ? t.focusing : t.focusSumo}
                </button>
              ) : (
                <button
                  onClick={handleRunVisionDemo}
                  disabled={isRunningVision}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 10px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    borderRadius: '6px',
                    border: '1px solid #0284c7',
                    backgroundColor: isRunningVision ? '#f1f5f9' : '#e0f2fe',
                    color: isRunningVision ? '#94a3b8' : '#0284c7',
                    cursor: isRunningVision ? 'not-allowed' : 'pointer'
                  }}
                >
                  <RefreshCw size={12} className={isRunningVision ? 'spin' : ''} />
                  {isRunningVision ? 'Đang chạy...' : 'Chạy lại Demo'}
                </button>
              )}

              <div style={{ display: 'flex', gap: '4px', backgroundColor: '#f1f5f9', padding: '2px', borderRadius: '6px' }}>
                {['video', 'roi', 'bbox', 'heatmap'].map(m => (
                  <button
                    key={m}
                    onClick={() => setVisionMode(m)}
                    style={{
                      padding: '4px 8px',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      borderRadius: '4px',
                      border: 'none',
                      cursor: 'pointer',
                      backgroundColor: visionMode === m ? '#0284c7' : 'transparent',
                      color: visionMode === m ? '#ffffff' : '#64748b'
                    }}
                  >
                    {m.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div style={{
            position: 'relative',
            backgroundColor: '#090d16',
            borderRadius: '12px',
            flex: 1,
            minHeight: '280px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#38bdf8',
            overflow: 'hidden',
            boxShadow: 'inset 0 0 20px rgba(0,0,0,0.6)'
          }}>
            {/* Top Bar Info Overlay */}
            <div style={{
              position: 'absolute',
              top: '12px',
              left: '12px',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '8px',
              zIndex: 10
            }}>
              {/* Live figures measured by the vision service (edgeflow/v1/health/vision), never constants */}
              <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: visionHealth?.status === 'HEALTHY' ? '#4ade80' : '#f87171', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
                {visionHealth
                  ? `● ${visionHealth.status} | ${visionHealth.runtime?.processed_fps != null ? `${visionHealth.runtime.processed_fps} fps` : '-- fps'} | ${visionHealth.model || visionHealth.backend || 'model ?'}`
                  : (isVi ? '○ Chưa có health của vision' : '○ No vision health reported')}
              </span>
              {visionHealth && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#38bdf8', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  {`Inference p50 ${visionHealth.runtime?.latency_ms?.inference_ms?.p50 ?? '--'} ms | ${visionHealth.detector_input_size || '?'} px | ${visionHealth.device || ''}`}
                </span>
              )}
              {visionMode === 'video' && sourceType === 'simulation' && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: sumoCrop.status === 'ok' ? '#4ade80' : '#f87171', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  {sumoCrop.status === 'ok'
                    ? `● SUMO-GUI Live | ${isVi ? 'cập nhật' : 'updated'} ${new Date(sumoSnapshotMeta.timestamp_ms).toLocaleTimeString()}`
                    : sumoCrop.status === 'out-of-view'
                    ? (isVi ? '○ Node ngoài khung nhìn' : '○ Node out of view')
                    : (isVi ? '○ Chưa có ảnh SUMO-GUI' : '○ No SUMO-GUI snapshot')}
                </span>
              )}
              {visionMode === 'video' && sourceType !== 'simulation' && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#cbd5e1', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  {isVi ? 'Video chú thích ghi sẵn (không phải luồng trực tiếp)' : 'Pre-recorded annotated video (not live stream)'}
                </span>
              )}
              {sourceType !== 'simulation' && visionReport?.node_id === nodeId && visionReport?.next_step_controller && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#f59e0b', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  Next Phase: {visionReport?.sample_decision?.target_phase_id || 'HOLD'}
                </span>
              )}
              {sourceType !== 'simulation' && !visionReport && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#94a3b8', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  {isVi ? 'Chưa chạy demo cho node này' : 'No demo run for this node'}
                </span>
              )}
            </div>

            {visionError && (
              <div style={{ position: 'absolute', top: '44px', left: '12px', right: '12px', zIndex: 10, backgroundColor: 'rgba(127,29,29,0.92)', border: '1px solid #ef4444', color: '#fecaca', padding: '6px 10px', borderRadius: '6px', fontSize: '0.74rem' }}>
                {visionError}
              </div>
            )}

            {sumoFocusMessage && (
              <div style={{ position: 'absolute', top: '44px', left: '12px', right: '12px', zIndex: 10, backgroundColor: 'rgba(15,23,42,0.92)', border: '1px solid #0284c7', color: '#93c5fd', padding: '6px 10px', borderRadius: '6px', fontSize: '0.74rem' }}>
                {sumoFocusMessage}
              </div>
            )}

            {visionMode === 'video' ? (
              <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '280px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                {sourceType === 'simulation' ? (
                  sumoCrop.status === 'ok' ? (
                    <div
                      title={isVi ? `Ảnh trực tiếp từ sumo-gui, zoom ~${SUMO_WORLD_RADIUS_M * 2}m quanh node ${nodeId}` : `Live snapshot from sumo-gui, zoomed ~${SUMO_WORLD_RADIUS_M * 2}m around node ${nodeId}`}
                      style={{
                        width: `${SUMO_VIEWPORT_PX}px`,
                        height: `${SUMO_VIEWPORT_PX}px`,
                        maxWidth: '100%',
                        borderRadius: '8px',
                        border: '1px solid #334155',
                        ...sumoCropStyle
                      }}
                    />
                  ) : (
                    <div style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', padding: '20px' }}>
                      {sumoCrop.status === 'out-of-view'
                        ? (isVi ? <>Node <strong>{nodeId}</strong> hiện nằm ngoài khung nhìn của cửa sổ sumo-gui đang mở. Pan/zoom sumo-gui tới nút này để xem.</> : <>Node <strong>{nodeId}</strong> is outside the active sumo-gui camera view. Pan/zoom sumo-gui to this junction to view.</>)
                        : sumoCrop.status === 'no-position'
                        ? (isVi ? <>Không tìm thấy vị trí node <strong>{nodeId}</strong> trong dữ liệu sumo-gui.</> : <>Node <strong>{nodeId}</strong> position not found in sumo-gui metadata.</>)
                        : (isVi ? <>Chưa có ảnh SUMO-GUI cho scenario <strong>{activeScenarioId}</strong>. Cần chạy <code>run_demo.py</code> (sumo-gui) cho scenario này.</> : <>No SUMO-GUI screenshot for scenario <strong>{activeScenarioId}</strong>. Run <code>run_demo.py</code> with sumo-gui enabled.</>)}
                    </div>
                  )
                ) : visionReport?.node_id === nodeId ? (
                  <video
                    key={`${nodeId}-${visionReport?.frames_processed || 'video-demo'}`}
                    controls
                    autoPlay
                    loop
                    muted
                    playsInline
                    style={{ width: '100%', maxHeight: '310px', borderRadius: '8px', objectFit: 'contain' }}
                    src={`${apiBase}/api/v1/vision/demo-video?node_id=${encodeURIComponent(nodeId)}&topology_id=${encodeURIComponent(activeScenarioId)}`}
                  >
                    Trình duyệt không hỗ trợ thẻ video.
                  </video>
                ) : (
                  <div style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', padding: '20px' }}>
                    Chưa có video demo cho node <strong>{nodeId}</strong>. Bấm "Chạy lại Demo" để tạo.
                  </div>
                )}
              </div>
            ) : (
              /* Dynamic Road Intersection Canvas Simulation */
              <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '280px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {/* Road Asphalt Graphics */}
                <div style={{ position: 'absolute', width: '90px', height: '100%', backgroundColor: '#1e293b', borderLeft: '2px dashed #475569', borderRight: '2px dashed #475569' }} />
                <div style={{ position: 'absolute', width: '100%', height: '90px', backgroundColor: '#1e293b', borderTop: '2px dashed #475569', borderBottom: '2px dashed #475569' }} />

                {/* Center Intersection Box -- shows the real current phase name/id, not a
                    guessed "GREEN NS/EW" that's wrong for any non-NS/EW topology. */}
                <div style={{
                  position: 'absolute',
                  width: '120px',
                  height: '90px',
                  backgroundColor: isCardinalNode && activePhase.includes('NS') ? 'rgba(34, 197, 94, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                  border: `2px solid ${isCardinalNode && activePhase.includes('NS') ? '#22c55e' : '#38bdf8'}`,
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  textAlign: 'center',
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '0 4px',
                  color: isCardinalNode && activePhase.includes('NS') ? '#4ade80' : '#38bdf8'
                }}>
                  {currentPhaseName}
                </div>

                {isCardinalNode ? (
                  <>
                    {/* Approach ROI Bounding Rectangles with Live Queue Numbers, matched by
                        real approach_id suffix (not array position). */}
                    {[
                      { dir: 'N', pos: { top: '15px' } },
                      { dir: 'S', pos: { bottom: '15px' } },
                      { dir: 'E', pos: { right: '15px' } },
                      { dir: 'W', pos: { left: '15px' } },
                    ].map(({ dir, pos }) => {
                      const app = appStats.find(a => a.approach_id.endsWith(`_${dir}_IN`));
                      const isNS = dir === 'N' || dir === 'S';
                      const label = app ? displayNameFor(app.approach_id) : `${dir}_IN`;
                      return (
                        <div key={dir} title={app?.approach_id || `${nodeId}_${dir}_IN`} style={{
                          position: 'absolute', ...pos,
                          border: `1px solid ${isNS ? '#ef4444' : '#38bdf8'}`,
                          backgroundColor: isNS ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                          padding: '4px 8px', borderRadius: '4px', fontSize: '0.7rem',
                          color: isNS ? '#fca5a5' : '#7dd3fc', fontWeight: 700
                        }}>
                          {label}: {Math.round((app?.queue_vehicles ?? 0) * 10) / 10} veh
                        </div>
                      );
                    })}
                  </>
                ) : (
                  /* Generic approach list for topologies without a N/S/E/W convention
                     (SUMO-derived nodes: raw edge IDs, 1-N approaches per node). */
                  <div style={{
                    position: 'absolute', bottom: '12px', left: '12px', right: '12px',
                    display: 'flex', flexWrap: 'wrap', gap: '6px', justifyContent: 'center'
                  }}>
                    {appStats.length === 0 && (
                      <span style={{ color: '#64748b', fontSize: '0.74rem' }}>Chưa có dữ liệu nhánh đường.</span>
                    )}
                    {appStats.map(a => (
                      <div key={a.approach_id} title={a.approach_id} style={{
                        border: '1px solid #38bdf8', backgroundColor: 'rgba(56, 189, 248, 0.15)',
                        padding: '3px 8px', borderRadius: '4px', fontSize: '0.68rem',
                        color: '#7dd3fc', fontWeight: 700
                      }}>
                        {displayNameFor(a.approach_id)}: {Math.round((a.queue_vehicles ?? 0) * 10) / 10} veh
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

        </div>

        {/* MODULE 3: Queue Pressure Analysis, Emergency Override & Hardware Safety */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sliders color="#0284c7" size={20} />
              <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                {t.controlMechTitle(nodeId)}
              </h3>
            </div>
            <span className="badge badge-green" style={{ fontSize: '0.74rem' }}>
              Hardware Interlock OK
            </span>
          </div>

          {/* Dynamic Queue Pressure Analysis Card */}
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#334155', textTransform: 'uppercase' }}>
                {t.pressureComparisonTitle}
              </span>
              <span className={`badge ${pressureAnalysis.isSelectedMatch ? 'badge-green' : 'badge-yellow'}`}>
                {pressureAnalysis.isSelectedMatch ? t.optimalPhaseRunning : t.waitingSwitch}
              </span>
            </div>

            <div style={{ fontSize: '0.74rem', color: '#64748b', marginBottom: '10px' }}>
              {t.pressureHelp}
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${Math.min(4, Math.max(1, pressureAnalysis.phases.length))}, 1fr)`,
              gap: '12px',
              marginBottom: '10px'
            }}>
              {pressureAnalysis.phases.map(phase => (
                <div
                  key={phase.phase_id}
                  title={`${phase.name} — ${t.serving} ${describeApproaches(phase.approaches)}`}
                  style={{
                    backgroundColor: activePhase === phase.phase_id ? '#e0f2fe' : '#ffffff',
                    border: `1px solid ${activePhase === phase.phase_id ? '#38bdf8' : '#e2e8f0'}`,
                    padding: '10px 12px',
                    borderRadius: '8px',
                    boxShadow: activePhase === phase.phase_id ? '0 2px 6px rgba(2, 132, 199, 0.12)' : 'none'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.75rem', color: activePhase === phase.phase_id ? '#0369a1' : '#475569', fontWeight: 700 }}>
                      {phase.name}
                    </span>
                    {activePhase === phase.phase_id && (
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#16a34a' }} />
                    )}
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0c4a6e' }}>{phase.queue} veh</div>
                  <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>
                    {t.serving} <strong>{describeApproaches(phase.approaches)}</strong>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ fontSize: '0.78rem', color: '#475569', display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: '#ffffff', padding: '8px 12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <Info size={15} color="#0284c7" style={{ flexShrink: 0 }} />
              <span>
                {t.pressureDiff(pressureAnalysis.diff, pressureAnalysis.maxPhase?.name || pressureAnalysis.recommendedPhase)}
              </span>
            </div>
          </div>

          {/* 1-Click Manual Phase Override */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: 800, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {t.overrideTitle}
              </label>
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                {t.overrideSub}
              </span>
            </div>
            
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              {availablePhases.map((phase) => (
                <button
                  key={phase.phase_id}
                  title={`${phase.name} — ${t.serving} ${describeApproaches(phase.approaches)}`}
                  onClick={() => handleTriggerOverride(phase.phase_id)}
                  disabled={overrideBusy}
                  style={{
                    flex: '1 1 150px',
                    minWidth: '150px',
                    maxWidth: '100%',
                    padding: '10px 14px',
                    backgroundColor: activePhase === phase.phase_id ? '#0284c7' : '#ffffff',
                    color: activePhase === phase.phase_id ? '#ffffff' : '#0f172a',
                    border: `2px solid ${activePhase === phase.phase_id ? '#0284c7' : '#cbd5e1'}`,
                    borderRadius: '8px',
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    cursor: overrideBusy ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.03)'
                  }}
                >
                  <Play size={14} /> {t.switchPhase(phase.name || phase.phase_id)}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '10px' }}>
              <button
                title={isVi ? 'Lệnh khẩn cấp: nháy vàng cả 4 cụm đèn tại nút' : 'Emergency command: all-yellow flashing on all 4 heads'}
                onClick={() => handleEmergencyFlash('activate')}
                disabled={overrideBusy}
                style={{
                  flex: '1 1 150px',
                  padding: '10px 14px',
                  backgroundColor: '#f59e0b',
                  color: '#ffffff',
                  border: '2px solid #d97706',
                  borderRadius: '8px',
                  fontWeight: 700,
                  fontSize: '0.82rem',
                  cursor: overrideBusy ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.03)'
                }}
              >
                <Zap size={14} /> {isVi ? 'Khẩn Cấp: Nháy Vàng 4 Đèn' : 'Emergency: Flash All-Yellow'}
              </button>

              <button
                title={isVi ? 'Hủy nháy vàng / Phục hồi chu trình chuyển pha an toàn' : 'Resume normal adaptive cycle'}
                onClick={() => handleEmergencyFlash('resume')}
                disabled={overrideBusy && !isEmergencyFlash && !Boolean(manualOverride?.target_phase_id?.includes('FLASH'))}
                style={{
                  flex: '0 1 150px',
                  padding: '10px 14px',
                  backgroundColor: '#0284c7',
                  color: '#ffffff',
                  border: '2px solid #0369a1',
                  borderRadius: '8px',
                  fontWeight: 700,
                  fontSize: '0.82rem',
                  cursor: (overrideBusy && !isEmergencyFlash && !Boolean(manualOverride?.target_phase_id?.includes('FLASH'))) ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.03)'
                }}
              >
                {isVi ? 'Phục Hồi Chu Trình' : 'Resume Cycle'}
              </button>
            </div>

            {overrideBusy && (
              <div style={{
                marginTop: '10px',
                padding: '8px 12px',
                borderRadius: '6px',
                backgroundColor: '#eff6ff',
                border: '1px solid #bfdbfe',
                color: '#1e40af',
                fontSize: '0.78rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <span className="pulse-indicator" style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#2563eb' }} />
                <span>{t.overrideBusyMsg}</span>
              </div>
            )}
          </div>

          {/* Hardware Safety Assurance Spec Cards */}
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '12px' }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#475569', textTransform: 'uppercase', marginBottom: '8px' }}>
              {t.hardwareInterlockTitle}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
              <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '8px 10px' }}>
                <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>{t.yellowTime}</span>
                <strong style={{ fontSize: '0.95rem', color: '#d97706' }}>{t.yellowTimeFixed(yellowDuration)}</strong>
              </div>
              <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '8px 10px' }}>
                <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>{t.allRedTime}</span>
                <strong style={{ fontSize: '0.95rem', color: '#dc2626' }}>{t.allRedTimeLocked(allRedDuration)}</strong>
              </div>
              <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '8px 10px' }}>
                <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>{t.boardMode}</span>
                <strong style={{ fontSize: '0.95rem', color: '#16a34a' }}>{actuatorMode || 'NORMAL'}</strong>
              </div>
              <div style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '8px 10px' }}>
                <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>{t.safeStopButton}</span>
                <strong style={{ fontSize: '0.95rem', color: isSafeStop ? '#dc2626' : '#64748b' }}>
                  {isSafeStop ? t.safeStopPressed : t.safeStopReady}
                </strong>
              </div>
            </div>
            <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '8px', lineHeight: 1.4 }}>
              {t.hardwareNotice}
            </div>
          </div>
        </div>
      </div>

      {/* MODULE 4: Live Control ACK Audit Log Stream */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Activity color="#0284c7" size={20} />
          <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
            {t.auditLogTitle}
          </h3>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {displayAcks.slice(0, 5).map((ack, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '0.85rem'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span className={`badge ${ack.status === 'APPLIED' ? 'badge-green' : ack.status === 'ACCEPTED' ? 'badge-yellow' : 'badge-red'}`}>
                  {ack.status}
                </span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#0284c7', fontWeight: 700 }}>
                  {ack.command_id || `cmd-${nodeId}`}
                </span>
                <span style={{ color: '#475569' }}>{ack.reason || (isVi ? 'Pha đèn đã được xác thực an toàn qua Actuator Interlock.' : 'Phase clearance verified via Actuator Interlock.')}</span>
              </div>
              <span style={{ color: '#94a3b8', fontSize: '0.78rem' }}>
                {ack.timestamp_ms ? new Date(ack.timestamp_ms).toLocaleTimeString() : (isVi ? 'Vừa xong' : 'Just now')}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* MODULE 5: Multi-Series Historical Station Performance Charts */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp size={20} color="#0284c7" />
            {t.queueHistoryTitle}
          </h3>
          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{t.updateInterval}</span>
        </div>

        <div style={{ width: '100%', height: '280px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={telemetryHistory.length > 0 ? telemetryHistory : [{ time: '00:00', queue: 0 }]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} label={{ value: t.queueYAxis, angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: '#94a3b8', fontSize: 11 } }} />
              <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
              <Legend verticalAlign="top" height={36} />
              
              {approachKeys.map((key, idx) => (
                <Area 
                  key={key}
                  type="monotone" 
                  dataKey={key} 
                  name={key}
                  stroke={APPROACH_COLORS[idx % APPROACH_COLORS.length]} 
                  fill={APPROACH_COLORS[idx % APPROACH_COLORS.length]}
                  fillOpacity={0.15} 
                  strokeWidth={2.5} 
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      </div>
    </>
  );
};

export default IntersectionDetail;
