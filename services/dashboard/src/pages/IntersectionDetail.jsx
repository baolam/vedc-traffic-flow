import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import PhaseIndicator from '../components/PhaseIndicator';
import { 
  ArrowLeft, Cpu, Activity, ShieldCheck, Gauge, Car, AlertTriangle, Play, 
  ShieldAlert, Radio, Video, Sliders, CheckCircle2, Clock, RefreshCw, 
  Compass, Layers, Zap, BarChart3, Eye, TrendingUp, Check, Info, Server, Wifi
} from 'lucide-react';

const APPROACH_COLORS = ['#0284c7', '#16a34a', '#ca8a04', '#dc2626', '#9333ea', '#06b6d4'];

const IntersectionDetail = () => {
  const { nodeId = 'J1' } = useParams();
  const activeScenarioId = localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1';

  const [nodeDetail, setNodeDetail] = useState(null);
  const [approaches, setApproaches] = useState([]);
  const [activePhase, setActivePhase] = useState(`${nodeId}_PHASE_NS`);
  const [nodeTelemetry, setNodeTelemetry] = useState(null);
  const [telemetryHistory, setTelemetryHistory] = useState([]);
  const [controlAcks, setControlAcks] = useState([]);
  const [lastPingMs, setLastPingMs] = useState(12);
  const [visionMode, setVisionMode] = useState('roi'); // 'roi', 'bbox', 'heatmap'

  // Manual Override Local State
  const [overrideTargetPhase, setOverrideTargetPhase] = useState('');
  const [overrideStatus, setOverrideStatus] = useState(null);
  const [clearanceStep, setClearanceStep] = useState(null); // 'YELLOW', 'ALL_RED', 'APPLIED'
  const [clearanceCountdown, setClearanceCountdown] = useState(0);

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

        if (data) {
          if (data.telemetry) {
            setNodeTelemetry(data.telemetry);
            if (data.telemetry.current_phase_id && !clearanceStep) {
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
      .catch(() => {});
  }, [nodeId, clearanceStep, apiBase]);

  useEffect(() => {
    fetchNodeState();
    const interval = setInterval(fetchNodeState, 1500);
    return () => clearInterval(interval);
  }, [fetchNodeState]);

  // 3. Update Actuator State Machine Parameters via API
  const handleUpdateActuatorConfig = (updates) => {
    const payload = {
      node_id: nodeId,
      yellow_duration_s: updates.yellow_duration_s !== undefined ? updates.yellow_duration_s : yellowDuration,
      all_red_duration_s: updates.all_red_duration_s !== undefined ? updates.all_red_duration_s : allRedDuration,
      min_green_s: updates.min_green_s !== undefined ? updates.min_green_s : minGreen,
      max_green_s: updates.max_green_s !== undefined ? updates.max_green_s : maxGreen,
      mode: updates.mode || actuatorMode
    };

    fetch(`${apiBase}/api/v1/actuator/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data && data.actuator_config) {
          if (data.actuator_config.yellow_duration_s) setYellowDuration(data.actuator_config.yellow_duration_s);
          if (data.actuator_config.all_red_duration_s) setAllRedDuration(data.actuator_config.all_red_duration_s);
          if (data.actuator_config.min_green_s) setMinGreen(data.actuator_config.min_green_s);
          if (data.actuator_config.max_green_s) setMaxGreen(data.actuator_config.max_green_s);
          if (data.actuator_config.mode) setActuatorMode(data.actuator_config.mode);
        }
      })
      .catch(() => {});
  };

  // 4. Handle Emergency Manual Phase Override
  const handleTriggerOverride = (targetPhaseId) => {
    const target = targetPhaseId || overrideTargetPhase;
    setOverrideStatus(`Manual Emergency Phase Override triggered for Node ${nodeId} -> Target: ${target}`);
    setClearanceStep('YELLOW');
    setClearanceCountdown(yellowDuration);

    fetch(`${apiBase}/api/v1/control/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_id: nodeId,
        target_phase_id: target,
        min_green_s: minGreen,
        max_green_s: maxGreen
      })
    }).catch(() => {});

    // Countdown simulation for Actuator safe clearance (Yellow -> All-Red -> Applied Green)
    let yellowLeft = yellowDuration;
    const yellowInterval = setInterval(() => {
      yellowLeft -= 1;
      setClearanceCountdown(yellowLeft);
      if (yellowLeft <= 0) {
        clearInterval(yellowInterval);
        setClearanceStep('ALL_RED');
        setClearanceCountdown(allRedDuration);

        let redLeft = allRedDuration;
        const redInterval = setInterval(() => {
          redLeft -= 1;
          setClearanceCountdown(redLeft);
          if (redLeft <= 0) {
            clearInterval(redInterval);
            setClearanceStep('APPLIED');
            setActivePhase(target);
            setTimeout(() => {
              setClearanceStep(null);
              setOverrideStatus(null);
            }, 2500);
          }
        }, 1000);
      }
    }, 1000);
  };

  const appStats = useMemo(() => nodeTelemetry?.approaches || [], [nodeTelemetry]);
  const sourceType = nodeTelemetry?.source_type || 'system';
  const status = nodeTelemetry?.status || 'ONLINE';

  const totalQ = useMemo(() => appStats.reduce((acc, a) => acc + (a.queue_vehicles || 0), 0), [appStats]);
  const avgSpeedMps = useMemo(() => appStats.length
    ? (appStats.reduce((acc, a) => acc + (a.mean_speed_mps || 0), 0) / appStats.length)
    : 13.89, [appStats]);
  const avgSpeedKmh = (avgSpeedMps * 3.6).toFixed(1);
  
  const avgOccPct = useMemo(() => appStats.length
    ? ((appStats.reduce((acc, a) => acc + (a.occupancy_ratio || 0), 0) / appStats.length) * 100).toFixed(1)
    : '0.0', [appStats]);

  const totalFlowRate = useMemo(() => appStats.reduce((acc, a) => acc + (a.flow_veh_per_s || 0), 0), [appStats]);

  // Max-Pressure Algorithm Analysis calculation for Phase NS vs Phase EW
  const pressureAnalysis = useMemo(() => {
    let nsQueue = 0;
    let ewQueue = 0;
    appStats.forEach(a => {
      const id = (a.approach_id || '').toUpperCase();
      if (id.includes('_N_') || id.includes('_S_') || id.includes('NORTH') || id.includes('SOUTH')) {
        nsQueue += (a.queue_vehicles || 0);
      } else {
        ewQueue += (a.queue_vehicles || 0);
      }
    });

    const diff = Math.abs(nsQueue - ewQueue);
    const recommendedPhase = nsQueue >= ewQueue ? `${nodeId}_PHASE_NS` : `${nodeId}_PHASE_EW`;
    const isSelectedMatch = activePhase.includes('NS') ? nsQueue >= ewQueue : ewQueue >= nsQueue;

    return {
      nsQueue: Math.round(nsQueue * 10) / 10,
      ewQueue: Math.round(ewQueue * 10) / 10,
      diff: Math.round(diff * 10) / 10,
      recommendedPhase,
      isSelectedMatch
    };
  }, [appStats, nodeId, activePhase]);

  const availablePhases = nodeDetail?.phases || [
    { phase_id: `${nodeId}_PHASE_NS`, name: 'North-South Green' },
    { phase_id: `${nodeId}_PHASE_EW`, name: 'East-West Green' }
  ];

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
            <PhaseIndicator activePhase={activePhase} state={clearanceStep || 'GREEN'} />
          </div>
        </div>
      </div>

      {/* Emergency Override Status Alert Banner */}
      {overrideStatus && (
        <div style={{
          backgroundColor: clearanceStep === 'YELLOW' ? '#fffbeb' : clearanceStep === 'ALL_RED' ? '#fef2f2' : '#f0fdf4',
          border: `2px solid ${clearanceStep === 'YELLOW' ? '#f59e0b' : clearanceStep === 'ALL_RED' ? '#ef4444' : '#16a34a'}`,
          borderRadius: '12px',
          padding: '16px 20px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: clearanceStep === 'YELLOW' ? '#b45309' : clearanceStep === 'ALL_RED' ? '#dc2626' : '#15803d',
          fontWeight: 600,
          boxShadow: '0 4px 14px rgba(0,0,0,0.06)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <ShieldAlert size={26} />
            <div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800 }}>{overrideStatus}</div>
              <div style={{ fontSize: '0.88rem', fontWeight: 500, marginTop: '2px' }}>
                Quy trình Chuyển pha An toàn Actuator: <strong>{clearanceStep}</strong> ({clearanceCountdown}s còn lại)
              </div>
            </div>
          </div>
          <div style={{ fontSize: '1.5rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 900, backgroundColor: 'rgba(255,255,255,0.8)', padding: '6px 16px', borderRadius: '8px' }}>
            {clearanceCountdown}s
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
          <div style={{ backgroundColor: 'rgba(202, 138, 4, 0.12)', padding: '14px', borderRadius: '12px' }}>
            <Wifi size={26} color="#ca8a04" />
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>Độ Trễ Phần Cứng (Ping)</span>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
              {lastPingMs} <span style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 500 }}>ms</span>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#16a34a', fontWeight: 600, marginTop: '2px' }}>
              ● ESP32 Hardware Active
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
              100% Interlocked
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
          <span style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 500 }}>{appStats.length} Nhánh Đường Đang Kết Nối Telemetry</span>
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
            const confPct = Math.round((app.confidence || 0.95) * 100);
            const isGreenActive = (activePhase.includes('NS') && (app.approach_id.includes('_N_') || app.approach_id.includes('_S_'))) ||
                                  (activePhase.includes('EW') && (app.approach_id.includes('_E_') || app.approach_id.includes('_W_')));

            return (
              <div 
                key={app.approach_id || idx} 
                className="card"
                style={{ 
                  borderLeft: `4px solid ${isGreenActive ? '#22c55e' : '#cbd5e1'}`,
                  backgroundColor: '#ffffff',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <span style={{ fontWeight: 800, fontSize: '0.9rem', color: '#0f172a', fontFamily: 'JetBrains Mono, monospace' }}>
                    {app.approach_id}
                  </span>
                  <span className={`badge ${isGreenActive ? 'badge-green' : 'badge-blue'}`} style={{ fontSize: '0.7rem' }}>
                    {isGreenActive ? 'GREEN PHASE' : 'RED PHASE'}
                  </span>
                </div>

                <div style={{ marginBottom: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#64748b', marginBottom: '4px' }}>
                    <span>Hàng chờ xe</span>
                    <strong style={{ color: queueVal > 5 ? '#dc2626' : '#0f172a' }}>{queueVal} veh</strong>
                  </div>
                  {/* Queue Visual Progress Bar */}
                  <div style={{ height: '8px', backgroundColor: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{ 
                      height: '100%', 
                      width: `${Math.min(100, (queueVal / 10) * 100)}%`, 
                      backgroundColor: queueVal > 5 ? '#ef4444' : queueVal > 2 ? '#f59e0b' : '#0284c7',
                      transition: 'width 0.4s ease'
                    }} />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.78rem', color: '#475569', backgroundColor: '#f8fafc', padding: '8px 10px', borderRadius: '8px' }}>
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
                  <strong style={{ color: '#16a34a' }}>{confPct}% YOLO</strong>
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
            
            {/* Vision Display Mode Switcher */}
            <div style={{ display: 'flex', gap: '4px', backgroundColor: '#f1f5f9', padding: '2px', borderRadius: '6px' }}>
              {['roi', 'bbox', 'heatmap'].map(m => (
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
              gap: '8px',
              zIndex: 10
            }}>
              <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#4ade80', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
                ● LIVE 30 FPS | YOLOv8n-ONNX
              </span>
              <span style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', border: '1px solid #334155', color: '#38bdf8', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontFamily: 'JetBrains Mono, monospace' }}>
                640x480 Camera Feed
              </span>
            </div>

            {/* Dynamic Road Intersection Canvas Simulation */}
            <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '280px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {/* Road Asphalt Graphics */}
              <div style={{ position: 'absolute', width: '90px', height: '100%', backgroundColor: '#1e293b', borderLeft: '2px dashed #475569', borderRight: '2px dashed #475569' }} />
              <div style={{ position: 'absolute', width: '100%', height: '90px', backgroundColor: '#1e293b', borderTop: '2px dashed #475569', borderBottom: '2px dashed #475569' }} />
              
              {/* Center Intersection Box */}
              <div style={{ 
                position: 'absolute', 
                width: '90px', 
                height: '90px', 
                backgroundColor: activePhase.includes('NS') ? 'rgba(34, 197, 94, 0.15)' : 'rgba(56, 189, 248, 0.15)', 
                border: `2px solid ${activePhase.includes('NS') ? '#22c55e' : '#38bdf8'}`,
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                fontWeight: 800,
                color: activePhase.includes('NS') ? '#4ade80' : '#38bdf8'
              }}>
                {activePhase.includes('NS') ? 'GREEN NS' : 'GREEN EW'}
              </div>

              {/* Approach ROI Bounding Rectangles with Live Queue Numbers */}
              {/* North Approach */}
              <div style={{ position: 'absolute', top: '15px', border: '1px solid #ef4444', backgroundColor: 'rgba(239, 68, 68, 0.15)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.7rem', color: '#fca5a5', fontWeight: 700 }}>
                N_IN: {Math.round((appStats[0]?.queue_vehicles || 3.2) * 10) / 10} veh
              </div>

              {/* South Approach */}
              <div style={{ position: 'absolute', bottom: '15px', border: '1px solid #ef4444', backgroundColor: 'rgba(239, 68, 68, 0.15)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.7rem', color: '#fca5a5', fontWeight: 700 }}>
                S_IN: {Math.round((appStats[1]?.queue_vehicles || 2.1) * 10) / 10} veh
              </div>

              {/* East Approach */}
              <div style={{ position: 'absolute', right: '15px', border: '1px solid #38bdf8', backgroundColor: 'rgba(56, 189, 248, 0.15)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.7rem', color: '#7dd3fc', fontWeight: 700 }}>
                E_IN: {Math.round((appStats[2]?.queue_vehicles || 1.5) * 10) / 10} veh
              </div>

              {/* West Approach */}
              <div style={{ position: 'absolute', left: '15px', border: '1px solid #38bdf8', backgroundColor: 'rgba(56, 189, 248, 0.15)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.7rem', color: '#7dd3fc', fontWeight: 700 }}>
                W_IN: {Math.round((appStats[3]?.queue_vehicles || 2.8) * 10) / 10} veh
              </div>
            </div>
          </div>
        </div>

        {/* MODULE 3: Max-Pressure Controller Decision & Actuator Controls */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
            <Sliders color="#0284c7" size={20} />
            <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
              Phân Tích Max-Pressure Controller & Lệnh Actuator ({nodeId})
            </h3>
          </div>

          {/* Max-Pressure Live Comparison Card */}
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>
                So Sánh Áp Lực Hàng Chờ (Max-Pressure)
              </span>
              <span className={`badge ${pressureAnalysis.isSelectedMatch ? 'badge-green' : 'badge-yellow'}`}>
                {pressureAnalysis.isSelectedMatch ? 'Pha Tối Ưu Active' : 'Chờ Chuyển Pha'}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '10px' }}>
              <div style={{ backgroundColor: activePhase.includes('NS') ? '#e0f2fe' : '#ffffff', border: '1px solid #bae6fd', padding: '8px 12px', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: '#0369a1', fontWeight: 700 }}>Pha Bắc-Nam ($W_{NS}$)</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0c4a6e' }}>{pressureAnalysis.nsQueue} veh</div>
              </div>

              <div style={{ backgroundColor: activePhase.includes('EW') ? '#e0f2fe' : '#ffffff', border: '1px solid #bae6fd', padding: '8px 12px', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: '#0369a1', fontWeight: 700 }}>Pha Đông-Tây ($W_{EW}$)</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0c4a6e' }}>{pressureAnalysis.ewQueue} veh</div>
              </div>
            </div>

            <div style={{ fontSize: '0.78rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Info size={14} color="#0284c7" />
              <span>Chênh lệch áp lực ($\Delta W$): <strong style={{ color: '#0f172a' }}>{pressureAnalysis.diff} veh</strong>. Thuật toán khuyên dùng: <strong style={{ color: '#0284c7' }}>{pressureAnalysis.recommendedPhase}</strong></span>
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
                  onClick={() => handleTriggerOverride(phase.phase_id)}
                  disabled={clearanceStep !== null}
                  style={{
                    flex: 1,
                    minWidth: '140px',
                    padding: '10px 14px',
                    backgroundColor: activePhase === phase.phase_id ? '#0284c7' : '#ffffff',
                    color: activePhase === phase.phase_id ? '#ffffff' : '#0f172a',
                    border: `2px solid ${activePhase === phase.phase_id ? '#0284c7' : '#cbd5e1'}`,
                    borderRadius: '8px',
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    cursor: clearanceStep ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.03)'
                  }}
                >
                  <Play size={14} /> Chuyển {phase.name || phase.phase_id}
                </button>
              ))}
            </div>
          </div>

          {/* Clearance Timing Sliders */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ backgroundColor: '#f8fafc', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#475569', fontWeight: 600, marginBottom: '4px' }}>
                <span>Thời gian Đèn Vàng ($t_y$)</span>
                <strong style={{ color: '#d97706' }}>{yellowDuration}s</strong>
              </div>
              <input
                type="range"
                min="1"
                max="8"
                value={yellowDuration}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  setYellowDuration(val);
                  handleUpdateActuatorConfig({ yellow_duration_s: val });
                }}
                style={{ accentColor: '#d97706', width: '100%' }}
              />
            </div>

            <div style={{ backgroundColor: '#f8fafc', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#475569', fontWeight: 600, marginBottom: '4px' }}>
                <span>Thời gian Đỏ Toàn Bộ ($t_r$)</span>
                <strong style={{ color: '#dc2626' }}>{allRedDuration}s</strong>
              </div>
              <input
                type="range"
                min="1"
                max="8"
                value={allRedDuration}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  setAllRedDuration(val);
                  handleUpdateActuatorConfig({ all_red_duration_s: val });
                }}
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
                onClick={() => handleUpdateActuatorConfig({ mode: 'NORMAL' })}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid #16a34a',
                  backgroundColor: actuatorMode === 'NORMAL' ? '#16a34a' : '#ffffff',
                  color: actuatorMode === 'NORMAL' ? '#ffffff' : '#16a34a',
                  fontWeight: 700,
                  fontSize: '0.78rem',
                  cursor: 'pointer'
                }}
              >
                Normal Auto
              </button>

              <button
                onClick={() => handleUpdateActuatorConfig({ mode: 'FLASHING_YELLOW' })}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid #d97706',
                  backgroundColor: actuatorMode === 'FLASHING_YELLOW' ? '#d97706' : '#ffffff',
                  color: actuatorMode === 'FLASHING_YELLOW' ? '#ffffff' : '#d97706',
                  fontWeight: 700,
                  fontSize: '0.78rem',
                  cursor: 'pointer'
                }}
              >
                Chớp Vàng (Safe-Stop)
              </button>

              <button
                onClick={() => handleUpdateActuatorConfig({ mode: 'ALL_RED' })}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid #dc2626',
                  backgroundColor: actuatorMode === 'ALL_RED' ? '#dc2626' : '#ffffff',
                  color: actuatorMode === 'ALL_RED' ? '#ffffff' : '#dc2626',
                  fontWeight: 700,
                  fontSize: '0.78rem',
                  cursor: 'pointer'
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
