import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Video, Radio, Car, Gauge, Wifi, Server, ExternalLink, 
  RefreshCw, Settings, AlertCircle, CheckCircle2, Globe, ShieldAlert, EyeOff
} from 'lucide-react';
import PhaseIndicator from '../components/PhaseIndicator';
import RaspberryPiAlertOverlay from '../components/RaspberryPiAlertOverlay';
import StationContextBar from '../components/StationContextBar';
import MqttPacketInspector from '../components/MqttPacketInspector';
import { useLanguage } from '../hooks/useLanguage';

const PRESET_URLS = [
  { label: '192.168.0.139:8080 (Phát hiện)', url: 'http://192.168.0.139:8080' },
  { label: 'raspberrypi.local:8080', url: 'http://raspberrypi.local:8080' },
  { label: 'raspberry.local:8080', url: 'http://raspberry.local:8080' },
  { label: 'localhost:8080', url: 'http://localhost:8080' }
];

const RaspberryPiDemo = () => {
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const [lang] = useLanguage();
  const isVi = lang === 'vi';

  // Selected node (default J3, can choose J1, J2, J4)
  const [selectedNodeId, setSelectedNodeId] = useState('J3');

  // Stream source mode: 'DIRECT_RPI' (direct from Raspberry Pi dashboard server) vs 'API_RELAY' (via port 8000)
  const [sourceMode, setSourceMode] = useState(() => {
    return localStorage.getItem('edgeflow_rpi_source_mode') || 'DIRECT_RPI';
  });

  // Raspberry Pi target base URL
  const [rpiBaseUrl, setRpiBaseUrl] = useState(() => {
    const saved = localStorage.getItem('edgeflow_rpi_stream_url');
    // Auto-migrate from unresolvable raspberry.local to confirmed IP/mDNS
    if (!saved || saved.includes('raspberry.local')) {
      return 'http://192.168.0.139:8080';
    }
    return saved;
  });

  const [customUrlInput, setCustomUrlInput] = useState(rpiBaseUrl);
  const [showConfig, setShowConfig] = useState(false);

  // RPi Dashboard Server health status
  const [rpiServerHealth, setRpiServerHealth] = useState({
    checked: false,
    online: false,
    identity: null,
    stats: null
  });

  // Stream error state
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(0);

  // Telemetry & Platform Health
  const [nodeTelemetry, setNodeTelemetry] = useState(null);
  const [deviceHealth, setDeviceHealth] = useState(null);
  const [isLive, setIsLive] = useState(false);
  const [liveAgeMs, setLiveAgeMs] = useState(null);
  const [telemetryChecked, setTelemetryChecked] = useState(false);
  const [liveStatusChecked, setLiveStatusChecked] = useState(false);

  // Persist source mode and URL
  useEffect(() => {
    localStorage.setItem('edgeflow_rpi_source_mode', sourceMode);
  }, [sourceMode]);

  useEffect(() => {
    localStorage.setItem('edgeflow_rpi_stream_url', rpiBaseUrl);
  }, [rpiBaseUrl]);

  // Probe Raspberry Pi Dashboard Server (via Backend Probe API + direct fallback)
  const checkRpiServer = useCallback(() => {
    const cleanUrl = rpiBaseUrl.replace(/\/+$/, '');
    const ctrl = new AbortController();
    const timeoutId = setTimeout(() => ctrl.abort(), 2000);

    // 1. Call Backend API Health Probe (bypasses browser CORS & updates global signal_faults)
    fetch(`${apiBase}/api/v1/vision/rpi-health-check?rpi_url=${encodeURIComponent(cleanUrl)}&node_id=${selectedNodeId}`, {
      signal: ctrl.signal
    })
      .then(res => res.json())
      .then(data => {
        clearTimeout(timeoutId);
        const isOnline = Boolean(data.online);
        setRpiServerHealth({
          checked: true,
          online: isOnline,
          identity: data.identity || null,
          stats: data.stats || null
        });
        if (!isOnline && sourceMode === 'DIRECT_RPI') {
          setStreamError(true);
        }
      })
      .catch(() => {
        clearTimeout(timeoutId);
        // 2. Direct browser fallback
        fetch(`${cleanUrl}/api/status`)
          .then(res => {
            if (res.ok) return res.json();
            throw new Error(`HTTP ${res.status}`);
          })
          .then(data => {
            setRpiServerHealth({
              checked: true,
              online: true,
              identity: data.identity || null,
              stats: data.stats || null
            });
          })
          .catch(() => {
            setRpiServerHealth(prev => ({
              ...prev,
              checked: true,
              online: false
            }));
            if (sourceMode === 'DIRECT_RPI') {
              setStreamError(true);
            }
          });
      });
  }, [rpiBaseUrl, apiBase, selectedNodeId, sourceMode]);

  // Telemetry poll from Platform API
  const refreshTelemetry = useCallback(() => {
    fetch(`${apiBase}/api/v1/telemetry/node/${selectedNodeId}`)
      .then(res => res.json())
      .then(data => {
        setNodeTelemetry(data.telemetry || null);
        setDeviceHealth(data.device_health || null);
      })
      .catch(() => {})
      .finally(() => setTelemetryChecked(true));
  }, [apiBase, selectedNodeId]);

  // Live stream status poll from Platform API
  const refreshLiveStatus = useCallback(() => {
    fetch(`${apiBase}/api/v1/vision/live-status/${selectedNodeId}`)
      .then(res => res.json())
      .then(data => {
        setIsLive(prevLive => {
          if (!prevLive && data.is_live) setStreamKey(k => k + 1);
          return Boolean(data.is_live);
        });
        setLiveAgeMs(data.age_ms);
      })
      .catch(() => setIsLive(false))
      .finally(() => setLiveStatusChecked(true));
  }, [apiBase, selectedNodeId]);

  useEffect(() => {
    refreshTelemetry();
    refreshLiveStatus();
    checkRpiServer();

    const interval = setInterval(() => {
      refreshTelemetry();
      refreshLiveStatus();
      checkRpiServer();
    }, 2000);
    return () => clearInterval(interval);
  }, [refreshTelemetry, refreshLiveStatus, checkRpiServer]);

  // Build the effective stream URL
  const cleanRpiHost = rpiBaseUrl.replace(/\/+$/, '');
  const activeStreamUrl = useMemo(() => {
    if (sourceMode === 'DIRECT_RPI') {
      return `${cleanRpiHost}/stream/${selectedNodeId}`;
    }
    return `${apiBase}/api/v1/vision/live-stream/${selectedNodeId}`;
  }, [sourceMode, cleanRpiHost, selectedNodeId, apiBase]);

  const handleApplyCustomUrl = (e) => {
    e.preventDefault();
    let url = customUrlInput.trim();
    if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
      url = `http://${url}`;
    }
    setRpiBaseUrl(url);
    setStreamError(false);
    setStreamKey(k => k + 1);
  };

  const handleSelectPreset = (url) => {
    setCustomUrlInput(url);
    setRpiBaseUrl(url);
    setStreamError(false);
    setStreamKey(k => k + 1);
  };

  const appStats = useMemo(() => nodeTelemetry?.approaches || [], [nodeTelemetry]);
  const activePhase = nodeTelemetry?.current_phase_id || `${selectedNodeId}_PHASE_NS`;
  const telemetryAgeMs = deviceHealth?.camera?.last_seen_ms_ago;
  const hasLiveTelemetry = Boolean(nodeTelemetry);

  // Accurate detection of disconnection for both Direct RPi and API Relay:
  const rpiServerLost = Boolean(rpiServerHealth.checked && !rpiServerHealth.online);
  const streamLost = Boolean(streamError || (sourceMode === 'API_RELAY' && liveStatusChecked && !isLive) || (sourceMode === 'DIRECT_RPI' && rpiServerLost));
  const telemetryLost = Boolean(telemetryChecked && (!hasLiveTelemetry || deviceHealth?.camera?.status === 'SIGNAL_LOST' || rpiServerLost));

  const cameraFault = deviceHealth?.camera?.active_fault || (deviceHealth?.active_fault?.category === 'camera' ? deviceHealth?.active_fault : null);
  const isCameraOccluded = Boolean(
    cameraFault?.fault_code === 'ERR_CAMERA_OCCLUSION' ||
    cameraFault?.fault_code === 'ERR_CAMERA_BLIND' ||
    deviceHealth?.camera?.status === 'ZERO_CONFIDENCE'
  );

  return (
    <>
      <StationContextBar activeNodeId={selectedNodeId} />
      <div className="page-container" style={{ backgroundColor: '#f8fafc', padding: '24px' }}>
        <RaspberryPiAlertOverlay
          nodeId={selectedNodeId}
          rpiHost={cleanRpiHost}
          rpiDisconnected={rpiServerLost}
          telemetryLost={telemetryLost}
          telemetryAgeMs={telemetryAgeMs}
          streamLost={streamLost}
          streamAgeMs={liveAgeMs}
          onRetry={() => {
            setStreamError(false);
            setStreamKey(k => k + 1);
            checkRpiServer();
            refreshTelemetry();
          }}
        />

        {isCameraOccluded && (
          <div style={{
            backgroundColor: '#fff1f2',
            border: '2px solid #f43f5e',
            borderRadius: '10px',
            padding: '12px 18px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            color: '#9f1239'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <EyeOff size={24} color="#e11d48" />
              <div>
                <strong style={{ fontSize: '0.92rem' }}>
                  {isVi ? `📷 CẢNH BÁO: CAMERA TẠI NÚT ${selectedNodeId} BỊ CHE KHUẤT / MẤT TẦM NHÌN!` : `📷 WARNING: CAMERA AT NODE ${selectedNodeId} IS OCCLUDED / BLINDED!`}
                </strong>
                <div style={{ fontSize: '0.8rem', marginTop: '2px', color: '#be123c' }}>
                  {cameraFault?.reason || (isVi ? 'Độ sắc nét cạnh và mật độ vi sai bằng 0. Hệ thống thị giác đã hạ độ tin cậy về 0.0 để kích hoạt bảo vệ phân bổ chu kỳ tối thiểu (Fairness Guard).' : 'Edge density zero. Perception confidence lowered to 0.0 to trigger fairness guard.')}
                </div>
              </div>
            </div>
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 800,
              fontFamily: 'JetBrains Mono, monospace',
              backgroundColor: '#ffe4e6',
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid #fecdd3'
            }}>
              {cameraFault?.fault_code || 'ERR_CAMERA_OCCLUSION'}
            </span>
          </div>
        )}

        {/* Page Title & Node Switcher Bar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 800, margin: 0, color: '#0f172a' }}>
                Raspberry Pi — Node {selectedNodeId}
              </h2>
              <span style={{
                fontSize: '0.74rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '6px',
                backgroundColor: '#e0f2fe',
                color: '#0369a1',
                border: '1px solid #bae6fd'
              }}>
                Edge Vision & Local Server
              </span>
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#64748b' }}>
              {isVi 
                ? 'Giám sát trực tiếp luồng video camera từ Raspberry Pi và kiểm tra gói tin trạng thái MQTT.' 
                : 'Direct camera video stream from Raspberry Pi and live MQTT status packet inspection.'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569' }}>
              {isVi ? 'Chọn Nút:' : 'Select Node:'}
            </span>
            {['J1', 'J2', 'J3', 'J4'].map(nid => (
              <button
                key={nid}
                onClick={() => {
                  setSelectedNodeId(nid);
                  setStreamError(false);
                  setStreamKey(k => k + 1);
                }}
                style={{
                  border: selectedNodeId === nid ? '1.5px solid #0284c7' : '1px solid #cbd5e1',
                  borderRadius: '6px',
                  padding: '4px 10px',
                  fontSize: '0.78rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  backgroundColor: selectedNodeId === nid ? '#0284c7' : '#ffffff',
                  color: selectedNodeId === nid ? '#ffffff' : '#334155',
                  transition: 'all 0.15s ease'
                }}
              >
                {nid}
              </button>
            ))}
          </div>
        </div>

        {/* 1. Stream Source & Raspberry Pi Direct Address Configuration Bar */}
        <div className="card" style={{
          marginBottom: '20px',
          padding: '14px 18px',
          borderLeft: '4px solid #0284c7',
          backgroundColor: '#ffffff'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px'
          }}>
            {/* Left: Mode Selection & Status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Globe size={18} color="#0284c7" />
                <span style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0f172a' }}>
                  {isVi ? 'Nguồn Stream Video:' : 'Video Stream Source:'}
                </span>
              </div>

              {/* Toggle Buttons: Direct RPi vs API Relay */}
              <div style={{ display: 'flex', gap: '4px', backgroundColor: '#f1f5f9', padding: '3px', borderRadius: '6px' }}>
                <button
                  onClick={() => {
                    setSourceMode('DIRECT_RPI');
                    setStreamError(false);
                    setStreamKey(k => k + 1);
                  }}
                  style={{
                    border: 'none',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    backgroundColor: sourceMode === 'DIRECT_RPI' ? '#0284c7' : 'transparent',
                    color: sourceMode === 'DIRECT_RPI' ? '#ffffff' : '#64748b'
                  }}
                >
                  🚀 {isVi ? 'Trực tiếp từ Raspberry Pi' : 'Direct Raspberry Pi'}
                </button>
                <button
                  onClick={() => {
                    setSourceMode('API_RELAY');
                    setStreamError(false);
                    setStreamKey(k => k + 1);
                  }}
                  style={{
                    border: 'none',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    backgroundColor: sourceMode === 'API_RELAY' ? '#0284c7' : 'transparent',
                    color: sourceMode === 'API_RELAY' ? '#ffffff' : '#64748b'
                  }}
                >
                  📡 {isVi ? 'Qua API Relay (:8000)' : 'API Relay Proxy'}
                </button>
              </div>

              {/* RPi Server Ping Badge */}
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.72rem',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '9999px',
                backgroundColor: rpiServerHealth.online ? '#dcfce7' : '#fef2f2',
                color: rpiServerHealth.online ? '#15803d' : '#b91c1c',
                border: `1px solid ${rpiServerHealth.online ? '#86efac' : '#fecaca'}`
              }}>
                <span style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: rpiServerHealth.online ? '#22c55e' : '#ef4444'
                }} />
                {rpiServerHealth.online 
                  ? (isVi ? `RPi Dashboard Online (${cleanRpiHost})` : `RPi Dashboard Online (${cleanRpiHost})`)
                  : (isVi ? `Chưa kết nối RPi Dashboard (${cleanRpiHost})` : `RPi Dashboard Standby (${cleanRpiHost})`)}
              </span>
            </div>

            {/* Right: Actions */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={() => setShowConfig(!showConfig)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  padding: '4px 10px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  backgroundColor: showConfig ? '#e2e8f0' : '#ffffff',
                  color: '#334155'
                }}
              >
                <Settings size={13} />
                {isVi ? 'Đổi địa chỉ IP / Host' : 'Configure Host / IP'}
              </button>

              {/* Direct Open Link to Raspberry Pi's Standalone Local Dashboard */}
              <a
                href={cleanRpiHost}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '4px 12px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  backgroundColor: '#f0fdf4',
                  color: '#16a34a',
                  border: '1px solid #86efac',
                  textDecoration: 'none'
                }}
                title={isVi ? 'Mở trực tiếp giao diện Dashboard trên Raspberry Pi (Port 8080)' : 'Open standalone Raspberry Pi dashboard'}
              >
                <ExternalLink size={13} />
                {isVi ? 'Mở Dashboard RPi (Port 8080) ↗' : 'Open RPi Dashboard ↗'}
              </a>
            </div>
          </div>

          {/* Collapsible Address Input Drawer */}
          {showConfig && (
            <div style={{
              marginTop: '12px',
              paddingTop: '12px',
              borderTop: '1px dashed #e2e8f0',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <form onSubmit={handleApplyCustomUrl} style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 700, color: '#334155' }}>
                  {isVi ? 'Địa chỉ Raspberry Pi:' : 'Raspberry Pi Address:'}
                </label>
                <input
                  type="text"
                  value={customUrlInput}
                  onChange={e => setCustomUrlInput(e.target.value)}
                  placeholder="e.g. http://raspberry.local:8080"
                  style={{
                    padding: '5px 10px',
                    fontSize: '0.78rem',
                    border: '1px solid #cbd5e1',
                    borderRadius: '6px',
                    width: '280px',
                    fontFamily: 'JetBrains Mono, monospace'
                  }}
                />
                <button
                  type="submit"
                  style={{
                    backgroundColor: '#0284c7',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '5px 12px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {isVi ? 'Áp dụng' : 'Apply'}
                </button>
              </form>

              {/* Quick Presets */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                  {isVi ? 'Gợi ý nhanh:' : 'Quick Presets:'}
                </span>
                {PRESET_URLS.map(p => (
                  <button
                    key={p.url}
                    onClick={() => handleSelectPreset(p.url)}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: '4px',
                      padding: '2px 8px',
                      fontSize: '0.7rem',
                      fontFamily: 'JetBrains Mono, monospace',
                      backgroundColor: rpiBaseUrl === p.url ? '#e0f2fe' : '#f8fafc',
                      color: rpiBaseUrl === p.url ? '#0369a1' : '#475569',
                      cursor: 'pointer'
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 2. Main Live Stream & MQTT Cards Grid */}
        <div className="grid-cols-2" style={{ gap: '20px', marginBottom: '20px' }}>
          {/* Video Stream Card */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '14px',
              borderBottom: '1px solid #e2e8f0',
              paddingBottom: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Video color="#0284c7" size={20} />
                <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                  {sourceMode === 'DIRECT_RPI' ? 'Direct Camera Stream (Raspberry Pi)' : 'Relayed Camera Stream (API)'}
                </h3>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  onClick={() => {
                    setStreamError(false);
                    setStreamKey(k => k + 1);
                  }}
                  title={isVi ? 'Tải lại luồng stream' : 'Reload stream'}
                  style={{
                    background: 'transparent',
                    border: '1px solid #e2e8f0',
                    borderRadius: '5px',
                    padding: '3px 7px',
                    color: '#64748b',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '0.7rem'
                  }}
                >
                  <RefreshCw size={11} /> {isVi ? 'Tải lại' : 'Reload'}
                </button>

                {(!streamError && (sourceMode === 'DIRECT_RPI' || isLive)) && (
                  <span style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '0.72rem',
                    fontWeight: 800,
                    padding: '3px 9px',
                    borderRadius: '6px',
                    backgroundColor: '#fef2f2',
                    color: '#dc2626',
                    border: '1px solid #fecaca'
                  }}>
                    <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#ef4444' }} />
                    LIVE
                  </span>
                )}
              </div>
            </div>

            {/* Video Container */}
            <div style={{
              position: 'relative',
              backgroundColor: '#090d16',
              borderRadius: '12px',
              flex: 1,
              minHeight: '340px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden'
            }}>
              {(!streamError && !rpiServerLost) ? (
                <img
                  key={streamKey}
                  src={activeStreamUrl}
                  alt={`Live stream from node ${selectedNodeId}`}
                  onError={() => setStreamError(true)}
                  style={{ width: '100%', height: '100%', maxHeight: '420px', objectFit: 'contain' }}
                />
              ) : (
                <div style={{
                  padding: '24px',
                  textAlign: 'center',
                  color: '#94a3b8',
                  maxWidth: '460px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '12px'
                }}>
                  <AlertCircle size={32} color="#f87171" />
                  <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#f1f5f9' }}>
                    {rpiServerLost 
                      ? (isVi ? 'Mất kết nối máy chủ Raspberry Pi (Port 8080)' : 'Raspberry Pi Server Disconnected')
                      : (isVi ? 'Không thể nạp luồng camera' : 'Stream unreachable')}
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#94a3b8', lineHeight: '1.4' }}>
                    {sourceMode === 'DIRECT_RPI' ? (
                      isVi ? (
                        <>
                          Không thể kết nối đến <code style={{ color: '#38bdf8' }}>{activeStreamUrl}</code>.
                          Tiến trình trên Raspberry Pi có thể đã dừng hoặc thiết bị mất kết nối mạng. Hãy kiểm tra nguồn điện và khởi động lại script giám sát.
                        </>
                      ) : (
                        <>
                          Cannot reach <code style={{ color: '#38bdf8' }}>{activeStreamUrl}</code>.
                          Ensure Raspberry Pi is powered on, local dashboard is running on port 8080, or switch to API Relay.
                        </>
                      )
                    ) : (
                      isVi ? 'Chưa nhận được khung hình nào qua API Relay.' : 'No live frame received via API Relay yet.'
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
                    <button
                      onClick={() => {
                        handleSelectPreset('http://192.168.0.139:8080');
                      }}
                      style={{
                        backgroundColor: '#16a34a',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '6px 12px',
                        fontSize: '0.74rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      ✓ {isVi ? 'Dùng IP 192.168.0.139' : 'Use IP 192.168.0.139'}
                    </button>
                    <button
                      onClick={() => {
                        handleSelectPreset('http://raspberrypi.local:8080');
                      }}
                      style={{
                        backgroundColor: '#0284c7',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '6px 12px',
                        fontSize: '0.74rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      🌐 raspberrypi.local
                    </button>
                    {sourceMode === 'DIRECT_RPI' && (
                      <button
                        onClick={() => {
                          setSourceMode('API_RELAY');
                          setStreamError(false);
                          setStreamKey(k => k + 1);
                        }}
                        style={{
                          backgroundColor: '#334155',
                          color: '#f8fafc',
                          border: 'none',
                          borderRadius: '6px',
                          padding: '6px 12px',
                          fontSize: '0.74rem',
                          fontWeight: 600,
                          cursor: 'pointer'
                        }}
                      >
                        {isVi ? 'Chuyển sang API Relay' : 'Switch to API Relay'}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Stream info footer */}
            <div style={{
              marginTop: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.72rem',
              color: '#64748b'
            }}>
              <span>
                URL: <code style={{ fontFamily: 'JetBrains Mono, monospace', color: '#0284c7' }}>{activeStreamUrl}</code>
              </span>
              <span>
                {sourceMode === 'DIRECT_RPI' ? 'Direct MJPEG' : 'API WebSocket / Relay'}
              </span>
            </div>
          </div>

          {/* Node Telemetry & Phase Indicator Card */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '14px',
              borderBottom: '1px solid #e2e8f0',
              paddingBottom: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Radio color="#0284c7" size={20} />
                <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                  MQTT Telemetry ({selectedNodeId})
                </h3>
              </div>
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.72rem',
                fontWeight: 800,
                padding: '4px 10px',
                borderRadius: '6px',
                backgroundColor: hasLiveTelemetry ? '#f0fdf4' : '#f1f5f9',
                color: hasLiveTelemetry ? '#16a34a' : '#64748b',
                border: `1px solid ${hasLiveTelemetry ? '#86efac' : '#cbd5e1'}`
              }}>
                <Wifi size={13} />
                {hasLiveTelemetry
                  ? (isVi
                    ? `ĐÃ NHẬN (${telemetryAgeMs != null ? `${(telemetryAgeMs / 1000).toFixed(1)}s trước` : 'vừa xong'})`
                    : `RECEIVED (${telemetryAgeMs != null ? `${(telemetryAgeMs / 1000).toFixed(1)}s ago` : 'just now'})`)
                  : (isVi ? 'CHƯA CÓ TELEMETRY' : 'NO TELEMETRY')}
              </span>
            </div>

            <div style={{ marginBottom: '14px' }}>
              <PhaseIndicator activePhase={activePhase} state="GREEN" />
            </div>

            {/* Approaches Breakdown */}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '8px' }}>
                {isVi ? 'Lưu Lượng Các Hướng Nhánh (Approaches):' : 'Approach Flows & Queues:'}
              </div>
              {appStats.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
                  {appStats.map((app, idx) => (
                    <div key={app.approach_id || idx} style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      padding: '8px 10px',
                      backgroundColor: '#ffffff'
                    }}>
                      <div style={{
                        fontSize: '0.74rem',
                        fontFamily: 'JetBrains Mono, monospace',
                        fontWeight: 700,
                        color: '#0f172a',
                        marginBottom: '4px'
                      }}>
                        {app.approach_id}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: '#475569' }}>
                        <Car size={13} color="#0284c7" /> 
                        <strong>{Math.round((app.queue_vehicles || 0) * 10) / 10}</strong> veh
                        <Gauge size={13} color="#16a34a" style={{ marginLeft: '6px' }} /> 
                        <strong>{(((app.mean_speed_mps || 0) * 3.6)).toFixed(1)}</strong> km/h
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{
                  fontSize: '0.78rem',
                  color: '#64748b',
                  backgroundColor: '#f8fafc',
                  border: '1px dashed #cbd5e1',
                  borderRadius: '8px',
                  padding: '14px',
                  textAlign: 'center'
                }}>
                  {isVi ? 'Chưa có dữ liệu telemetry cho nút này' : 'No telemetry available for this node'}
                </div>
              )}
            </div>

            {/* Hardware Status Snapshot from RPi */}
            {rpiServerHealth.online && rpiServerHealth.stats && (
              <div style={{
                marginTop: '14px',
                padding: '10px 12px',
                borderRadius: '8px',
                backgroundColor: '#f0fdf4',
                border: '1px solid #bbf7d0',
                fontSize: '0.74rem'
              }}>
                <div style={{ fontWeight: 700, color: '#166534', marginBottom: '4px' }}>
                  Raspberry Pi Runtime Stats:
                </div>
                <div style={{ display: 'flex', gap: '12px', color: '#15803d', flexWrap: 'wrap' }}>
                  <span>FPS: <strong>{rpiServerHealth.stats.fps || '15.0'}</strong></span>
                  <span>Inference: <strong>{rpiServerHealth.stats.inference_time_ms ? `${rpiServerHealth.stats.inference_time_ms} ms` : '—'}</strong></span>
                  <span>Frames: <strong>{rpiServerHealth.stats.total_frames || 0}</strong></span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 3. Realtime MQTT Status Packets for this Node & System */}
        <div style={{ marginTop: '10px' }}>
          <MqttPacketInspector
            nodeId={selectedNodeId}
            compact={false}
            maxHeight="320px"
            pollIntervalMs={1500}
            showHeader={true}
          />
        </div>
      </div>
    </>
  );
};

export default RaspberryPiDemo;
