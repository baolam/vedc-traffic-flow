import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import PhaseIndicator from '../components/PhaseIndicator';
import { describeOverride, overrideRequestError, OVERRIDE_IN_PROGRESS } from '../utils/manualOverride';
import { useActiveScenario } from '../hooks/useActiveScenario';
import { cleanPhaseName } from '../utils/phaseName';
import { 
  ArrowLeft, Cpu, Activity, ShieldCheck, Gauge, Car, AlertTriangle, Play,
  ShieldAlert, Radio, Video, Sliders, CheckCircle2, Clock, RefreshCw,
  Compass, Layers, Zap, BarChart3, Eye, TrendingUp, Check, Info, Server, Wifi,
  Crosshair
} from 'lucide-react';

const APPROACH_COLORS = ['#0284c7', '#16a34a', '#ca8a04', '#dc2626', '#9333ea', '#06b6d4'];

const IntersectionDetail = () => {
  const { nodeId = 'J1' } = useParams();
  const [activeScenarioId] = useActiveScenario();

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
      body: JSON.stringify({ node_id: nodeId, target_phase_id: target })
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

  // "Phase 1"/"Phase 2" alone doesn't say what actually happens -- this spells out which
  // approaches (real contract approach_ids) get the green during that phase.
  const describeApproaches = (ids) => {
    if (!ids || ids.length === 0) return 'chưa rõ nhánh đường';
    const shown = ids.slice(0, 4).join(', ');
    return ids.length > 4 ? `${shown} +${ids.length - 4} nhánh khác` : shown;
  };

  return (
    <div className="page-container" style={{ backgroundColor: '#f8fafc', minHeight: '100vh', padding: '24px' }}>
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
          <ArrowLeft size={16} /> Quay lại Tổng quan Đồ thị Mạng lưới
        </Link>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
              <h2 style={{ fontSize: '1.8rem', fontWeight: 800, margin: 0, color: '#0f172a', tracking: '-0.02em' }}>
                Node Diagnostics & Signal Control: <span style={{ color: '#0284c7', fontFamily: 'JetBrains Mono, monospace' }}>{nodeId}</span>
              </h2>
              <span className={`badge ${status === 'ONLINE' ? 'badge-green' : 'badge-yellow'}`} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '0.8rem' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: status === 'ONLINE' ? '#16a34a' : '#ca8a04', display: 'inline-block' }}></span>
                {status}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', color: '#64748b', fontSize: '0.88rem', flexWrap: 'wrap' }}>
              <span>Map Topology: <code style={{ backgroundColor: '#e0f2fe', color: '#0369a1', padding: '3px 8px', borderRadius: '6px', fontWeight: 700 }}>{activeScenarioId}</code></span>
              <span>•</span>
              <span>Nguồn Perception: <strong style={{ color: '#0f172a' }}>{sourceType.toUpperCase()}</strong></span>
              <span>•</span>
              <span>Chế độ Actuator: <span className={`badge ${actuatorMode === 'NORMAL' ? 'badge-green' : 'badge-yellow'}`}>{actuatorMode}</span></span>
            </div>
          </div>

          <div style={{ backgroundColor: '#ffffff', padding: '10px 18px', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
            <PhaseIndicator activePhase={activePhase} state={liveClearance === 'YELLOW' || liveClearance === 'ALL_RED' ? liveClearance : 'GREEN'} />
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
          gap: '14px',
          color: overrideBanner.colors.color,
          fontWeight: 600,
          boxShadow: '0 4px 14px rgba(0,0,0,0.06)'
        }}>
          <ShieldAlert size={26} />
          <div>
            <div style={{ fontSize: '1.05rem', fontWeight: 800 }}>{overrideBanner.title}</div>
            <div style={{ fontSize: '0.88rem', fontWeight: 500, marginTop: '2px' }}>{overrideBanner.detail}</div>
          </div>
        </div>
      )}

      {/* Hardware Signal & Fail-Safe Monitor Banner */}
      {(nodeTelemetry?.status === 'SIGNAL_LOST' || 
        nodeTelemetry?.status === 'CAMERA_FAULT' || 
        nodeTelemetry?.status === 'ACTUATOR_FAULT' ||
        deviceHealth?.camera?.status === 'SIGNAL_LOST' || 
        deviceHealth?.camera?.status === 'ZERO_CONFIDENCE' || 
        deviceHealth?.actuator?.status === 'HEARTBEAT_LOST' || 
        deviceHealth?.actuator?.status === 'SAFE_STOP') && (
        <div style={{
          backgroundColor: '#fef2f2',
          border: '2px solid #ef4444',
          borderRadius: '12px',
          padding: '16px 20px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: '#991b1b',
          boxShadow: '0 4px 14px rgba(239, 68, 68, 0.12)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <AlertTriangle size={28} color="#dc2626" />
            <div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800 }}>
                CẢNH BÁO SỰ CỐ TÍN HIỆU THIẾT BỊ / PHẦN CỨNG ({nodeId})
              </div>
              <div style={{ fontSize: '0.86rem', fontWeight: 500, marginTop: '2px', color: '#7f1d1d' }}>
                {deviceHealth?.actuator?.status === 'HEARTBEAT_LOST'
                  ? 'Không nhận nhịp tim thiết bị quá 6 s (mất nguồn hoặc mạng). Nếu thiết bị vẫn chạy mà không nhận lệnh quá 5 s, nó tự chạy chu kỳ cố định 15 s/pha.'
                  : (deviceHealth?.camera?.status === 'ZERO_CONFIDENCE' || nodeTelemetry?.status === 'CAMERA_FAULT')
                  ? 'Camera/video không cho quan sát (độ tin cậy 0). Graph-control ngừng gửi lệnh cho nút này; sau 5 s thiết bị tự chạy chu kỳ cố định 15 s/pha.'
                  : (deviceHealth?.camera?.status === 'SIGNAL_LOST' || nodeTelemetry?.status === 'SIGNAL_LOST')
                  ? 'Không nhận telemetry quá 3,5 s (dịch vụ vision hoặc mạng). Không có telemetry thì graph-control không ra lệnh; sau 5 s thiết bị tự chạy chu kỳ cố định.'
                  : 'Phần cứng Actuator đang trong chế độ Safe-Stop hoặc chờ xác thực an toàn.'}
              </div>
            </div>
          </div>
          <div style={{
            fontSize: '0.82rem',
            fontFamily: 'JetBrains Mono, monospace',
            fontWeight: 800,
            backgroundColor: '#ffffff',
            color: '#dc2626',
            border: '1.5px solid #f87171',
            padding: '6px 14px',
            borderRadius: '8px',
            textTransform: 'uppercase'
          }}>
            FAIL-SAFE INTERLOCK
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
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>Tổng Hàng Chờ Node</span>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
              {Math.round(totalQ * 10) / 10} <span style={{ fontSize: '0.9rem', color: '#64748b', fontWeight: 500 }}>xe</span>
            </div>
            <div style={{ fontSize: '0.78rem', color: totalQ > 15 ? '#dc2626' : totalQ > 8 ? '#ca8a04' : '#16a34a', fontWeight: 600, marginTop: '2px' }}>
              {totalQ > 15 ? '⚠️ Hàng chờ cao' : totalQ > 8 ? '⚡ Trung bình' : '✓ Thông thoáng'}
            </div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(22, 163, 74, 0.12)', padding: '14px', borderRadius: '12px' }}>
            <Gauge size={26} color="#16a34a" />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>Tốc độ & Lưu lượng</span>
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
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>Nhịp Tim Thiết Bị</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
              {deviceHealth?.actuator?.status === 'HEARTBEAT_LOST'
                ? 'LOST (>6s)'
                : deviceHealth?.actuator?.last_heartbeat_ms_ago != null
                ? `${(deviceHealth.actuator.last_heartbeat_ms_ago / 1000).toFixed(1)} s trước`
                : 'Chưa nhận'}
            </div>
            <div style={{
              fontSize: '0.78rem',
              color: deviceHealth?.actuator?.status === 'HEARTBEAT_LOST' ? '#dc2626'
                : (deviceHealth?.actuator?.status === 'SAFE_STOP' || deviceHealth?.actuator?.status === 'FALLBACK') ? '#d97706' : '#16a34a',
              fontWeight: 600,
              marginTop: '2px'
            }}>
              {deviceHealth?.actuator?.status === 'HEARTBEAT_LOST'
                ? '● Mất Nhịp Tim Thiết Bị (>6s)'
                : deviceHealth?.actuator?.status === 'SAFE_STOP'
                ? '● Actuator Safe-Stop'
                : deviceHealth?.actuator?.status === 'FALLBACK'
                ? '● Fallback cố định 15 s/pha'
                : `● Thiết bị ${deviceHealth?.actuator?.clearance || 'GREEN'} | API ${lastPingMs} ms`}
            </div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(147, 51, 234, 0.12)', padding: '14px', borderRadius: '12px' }}>
            <ShieldCheck size={26} color="#9333ea" />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>Kiểm Duyệt An Toàn</span>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#16a34a', marginTop: '2px' }}>
              Interlock Phần Cứng
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 500, marginTop: '2px' }}>
              Vàng: {yellowDuration}s | Đỏ Toàn Bộ: {allRedDuration}s
            </div>
          </div>
        </div>
      </div>

      {/* DETAILED APPROACH BREAKDOWN CARDS (CHI TIẾT TỪNG NHÁNH LUỒNG ĐƯỜNG) */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyBetween: 'space-between', marginBottom: '14px' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Compass size={20} color="#0284c7" />
            Chi Tiết Hàng Chờ & Thông Số Từng Nhánh Luồng Đường ({nodeId})
          </h3>
          {appStats.length > 0 ? (
            <span style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 500 }}>{appStats.length} Nhánh Đường Đang Kết Nối Telemetry</span>
          ) : (
            <span style={{
              fontSize: '0.74rem', fontWeight: 800, color: '#b45309', backgroundColor: '#fffbeb',
              border: '1px solid #fde68a', padding: '3px 8px', borderRadius: '5px'
            }}>
              ⚠ DỮ LIỆU MINH HỌA — CHƯA CÓ TELEMETRY THẬT
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
                  <span style={{ fontWeight: 800, fontSize: '0.9rem', color: isZeroConf ? '#991b1b' : '#0f172a', fontFamily: 'JetBrains Mono, monospace' }}>
                    {app.approach_id}
                  </span>
                  {isZeroConf ? (
                    <span className="badge badge-red" style={{ fontSize: '0.68rem', backgroundColor: '#fee2e2', color: '#b91c1c' }}>
                      ⚠️ MẤT TÍN HIỆU
                    </span>
                  ) : (
                    <span className={`badge ${isGreenActive ? 'badge-green' : 'badge-blue'}`} style={{ fontSize: '0.7rem' }}>
                      {isGreenActive ? 'GREEN PHASE' : 'RED PHASE'}
                    </span>
                  )}
                </div>

                <div style={{ marginBottom: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#64748b', marginBottom: '4px' }}>
                    <span>Hàng chờ xe</span>
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
                    <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.7rem' }}>Tốc độ TB</span>
                    <strong>{speedKmh} km/h</strong>
                  </div>
                  <div>
                    <span style={{ color: '#94a3b8', display: 'block', fontSize: '0.7rem' }}>Độ chiếm dụng</span>
                    <strong>{occPct}%</strong>
                  </div>
                </div>

                <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem', color: '#64748b' }}>
                  <span>Độ tin cậy AI Vision:</span>
                  <strong style={{ color: isZeroConf ? '#dc2626' : '#16a34a' }}>
                    {isZeroConf ? '0% (Mất Tín Hiệu)' : `${confPct}%`}
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
                  {isFocusingSumo ? 'Đang gửi...' : 'Focus SUMO-GUI'}
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
                  : '○ Chưa có health của vision'}
              </span>
              {visionHealth && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#38bdf8', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  {`Inference p50 ${visionHealth.runtime?.latency_ms?.inference_ms?.p50 ?? '--'} ms | ${visionHealth.detector_input_size || '?'} px | ${visionHealth.device || ''}`}
                </span>
              )}
              {visionMode === 'video' && sourceType === 'simulation' && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: sumoCrop.status === 'ok' ? '#4ade80' : '#f87171', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  {sumoCrop.status === 'ok'
                    ? `● SUMO-GUI Live | cập nhật ${new Date(sumoSnapshotMeta.timestamp_ms).toLocaleTimeString()}`
                    : sumoCrop.status === 'out-of-view'
                    ? '○ Node ngoài khung nhìn'
                    : '○ Chưa có ảnh SUMO-GUI'}
                </span>
              )}
              {visionMode === 'video' && sourceType !== 'simulation' && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#cbd5e1', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  Video chú thích ghi sẵn (không phải luồng trực tiếp)
                </span>
              )}
              {sourceType !== 'simulation' && visionReport?.node_id === nodeId && visionReport?.next_step_controller && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#f59e0b', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  Next Phase: {visionReport?.sample_decision?.target_phase_id || 'HOLD'}
                </span>
              )}
              {sourceType !== 'simulation' && !visionReport && (
                <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#94a3b8', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                  Chưa chạy demo cho node này
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
                      title={`Ảnh trực tiếp từ sumo-gui, zoom ~${SUMO_WORLD_RADIUS_M * 2}m quanh node ${nodeId}`}
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
                        ? <>Node <strong>{nodeId}</strong> hiện nằm ngoài khung nhìn của cửa sổ sumo-gui đang mở. Pan/zoom sumo-gui tới nút này để xem.</>
                        : sumoCrop.status === 'no-position'
                        ? <>Không tìm thấy vị trí node <strong>{nodeId}</strong> trong dữ liệu sumo-gui.</>
                        : <>Chưa có ảnh SUMO-GUI cho scenario <strong>{activeScenarioId}</strong>. Cần chạy <code>run_demo.py</code> (sumo-gui) cho scenario này.</>}
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
                      return (
                        <div key={dir} style={{
                          position: 'absolute', ...pos,
                          border: `1px solid ${isNS ? '#ef4444' : '#38bdf8'}`,
                          backgroundColor: isNS ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                          padding: '4px 8px', borderRadius: '4px', fontSize: '0.7rem',
                          color: isNS ? '#fca5a5' : '#7dd3fc', fontWeight: 700
                        }}>
                          {dir}_IN: {Math.round((app?.queue_vehicles ?? 0) * 10) / 10} veh
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
                      <div key={a.approach_id} style={{
                        border: '1px solid #38bdf8', backgroundColor: 'rgba(56, 189, 248, 0.15)',
                        padding: '3px 8px', borderRadius: '4px', fontSize: '0.68rem',
                        color: '#7dd3fc', fontWeight: 700, fontFamily: 'JetBrains Mono, monospace'
                      }}>
                        {a.approach_id}: {Math.round((a.queue_vehicles ?? 0) * 10) / 10} veh
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

        </div>

        {/* MODULE 3: queue pressure (max-pressure reference) & actuator controls */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
            <Sliders color="#0284c7" size={20} />
            <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
              Áp Lực Hàng Chờ & Lệnh Actuator ({nodeId})
            </h3>
          </div>

          {/* Max-Pressure Live Comparison Card */}
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>
                So Sánh Áp Lực Hàng Chờ Theo Pha (Max-Pressure)
              </span>
              <span className={`badge ${pressureAnalysis.isSelectedMatch ? 'badge-green' : 'badge-yellow'}`}>
                {pressureAnalysis.isSelectedMatch ? 'Pha Tối Ưu Active' : 'Chờ Chuyển Pha'}
              </span>
            </div>

            {/* Chú thích: "Phase N" là số thứ tự pha trong firmware/ESP32 của riêng node này,
                không phải hướng Bắc-Nam/Đông-Tây cố định -- mỗi pha cho đi một tổ hợp nhánh
                đường khác nhau, liệt kê ngay dưới mỗi thẻ. */}
            <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '10px', fontStyle: 'italic' }}>
              ⓘ "Phase N" là số thứ tự pha đèn của riêng node này (không phải hướng cố định) — mỗi pha cho đi một tổ hợp nhánh đường khác nhau, xem "Cho đi" bên dưới mỗi thẻ.
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
                  title={`${phase.name} — cho đi: ${describeApproaches(phase.approaches)}`}
                  style={{
                    backgroundColor: activePhase === phase.phase_id ? '#e0f2fe' : '#ffffff',
                    border: '1px solid #bae6fd',
                    padding: '8px 12px',
                    borderRadius: '8px'
                  }}
                >
                  <span style={{ fontSize: '0.75rem', color: '#0369a1', fontWeight: 700, overflowWrap: 'anywhere' }}>{phase.name}</span>
                  <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0c4a6e' }}>{phase.queue} veh</div>
                  <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '4px', overflowWrap: 'anywhere' }}>
                    Cho đi: {describeApproaches(phase.approaches)}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ fontSize: '0.78rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Info size={14} color="#0284c7" />
              <span>Chênh lệch áp lực (ΔW, pha cao nhất − pha thấp nhất): <strong style={{ color: '#0f172a' }}>{pressureAnalysis.diff} veh</strong>. Max-pressure sẽ chọn (tham khảo, không phải thuật toán đang chạy): <strong style={{ color: '#0284c7' }}>{pressureAnalysis.maxPhase?.name || pressureAnalysis.recommendedPhase}</strong></span>
            </div>
          </div>

          {/* 1-Click Manual Phase Override */}
          <div>
            <label style={{ fontSize: '0.78rem', fontWeight: 800, color: '#475569', textTransform: 'uppercase', marginBottom: '8px', display: 'block', letterSpacing: '0.04em' }}>
              Đè Lệnh Chuyển Pha Khẩn Cấp (1-Click Emergency Override)
            </label>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              {availablePhases.map((phase) => (
                <button
                  key={phase.phase_id}
                  title={`${phase.name} — cho đi: ${describeApproaches(phase.approaches)}`}
                  onClick={() => handleTriggerOverride(phase.phase_id)}
                  disabled={overrideBusy}
                  style={{
                    flex: '1 1 140px',
                    minWidth: '140px',
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
                    boxShadow: '0 2px 4px rgba(0,0,0,0.03)',
                    overflowWrap: 'anywhere',
                    wordBreak: 'break-word'
                  }}
                >
                  <Play size={14} /> Chuyển {phase.name || phase.phase_id}
                </button>
              ))}
            </div>
          </div>

          {/* Timing and safe modes live on the actuator device (yellow 3 s, all-red 2 s; safe-stop = hardware button).
              These controls only changed an API value, so they are disabled rather than shown as acting on the lights. */}
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
            Vàng 3 s / đỏ toàn bộ 2 s cố định trong thiết bị chấp hành. Lệnh tay chỉ được nhận khi hướng đang xanh đã đủ 5 s; pha được ép giữ xanh 15 s rồi thuật toán điều khiển lại. Safe-stop (chớp vàng) bằng nút cứng trên mạch; dashboard không điều khiển được.
          </div>

          {/* Clearance Timing Sliders */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ backgroundColor: '#f8fafc', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#475569', fontWeight: 600, marginBottom: '4px' }}>
                <span>Thời gian Đèn Vàng (t_yellow)</span>
                <strong style={{ color: '#d97706' }}>{yellowDuration}s</strong>
              </div>
              <input
                type="range"
                disabled
                min="1"
                max="8"
                value={yellowDuration}
                readOnly
                style={{ accentColor: '#d97706', width: '100%' }}
              />
            </div>

            <div style={{ backgroundColor: '#f8fafc', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#475569', fontWeight: 600, marginBottom: '4px' }}>
                <span>Thời gian Đỏ Toàn Bộ (t_all_red)</span>
                <strong style={{ color: '#dc2626' }}>{allRedDuration}s</strong>
              </div>
              <input
                type="range"
                disabled
                min="1"
                max="8"
                value={allRedDuration}
                readOnly
                style={{ accentColor: '#dc2626', width: '100%' }}
              />
            </div>
          </div>

          {/* Safety Mode Control Buttons */}
          <div>
            <label style={{ fontSize: '0.78rem', fontWeight: 800, color: '#475569', textTransform: 'uppercase', marginBottom: '8px', display: 'block' }}>
              Chế Độ An Toàn Phần Cứng Actuator
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                disabled
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid #16a34a',
                  backgroundColor: actuatorMode === 'NORMAL' ? '#16a34a' : '#ffffff',
                  color: actuatorMode === 'NORMAL' ? '#ffffff' : '#16a34a',
                  fontWeight: 700,
                  fontSize: '0.78rem',
                  cursor: 'not-allowed', opacity: 0.6
                }}
              >
                Normal Auto
              </button>

              <button
                disabled
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid #d97706',
                  backgroundColor: actuatorMode === 'FLASHING_YELLOW' ? '#d97706' : '#ffffff',
                  color: actuatorMode === 'FLASHING_YELLOW' ? '#ffffff' : '#d97706',
                  fontWeight: 700,
                  fontSize: '0.78rem',
                  cursor: 'not-allowed', opacity: 0.6
                }}
              >
                Chớp Vàng (Safe-Stop)
              </button>

              <button
                disabled
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid #dc2626',
                  backgroundColor: actuatorMode === 'ALL_RED' ? '#dc2626' : '#ffffff',
                  color: actuatorMode === 'ALL_RED' ? '#ffffff' : '#dc2626',
                  fontWeight: 700,
                  fontSize: '0.78rem',
                  cursor: 'not-allowed', opacity: 0.6
                }}
              >
                Đỏ Toàn Bộ (All-Red)
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* MODULE 4: Live Control ACK Audit Log Stream */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Activity color="#0284c7" size={20} />
          <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
            Nhật Ký Thực Thi Lệnh Tín Hiệu Thực Tế (Live ControlACK Audit Log Stream)
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
                <span style={{ color: '#475569' }}>{ack.reason || 'Pha đèn đã được xác thực an toàn qua Actuator Interlock.'}</span>
              </div>
              <span style={{ color: '#94a3b8', fontSize: '0.78rem' }}>
                {ack.timestamp_ms ? new Date(ack.timestamp_ms).toLocaleTimeString() : 'Vừa xong'}
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
            Biểu Đồ Lịch Sử Hàng Chờ Từng Nhánh Luồng Đường theo Thời Gian Real-time
          </h3>
          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Cập nhật mỗi 1.5s</span>
        </div>

        <div style={{ width: '100%', height: '280px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={telemetryHistory.length > 0 ? telemetryHistory : [{ time: '00:00', queue: 0 }]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} label={{ value: 'Hàng chờ (veh)', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: '#94a3b8', fontSize: 11 } }} />
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
  );
};

export default IntersectionDetail;
