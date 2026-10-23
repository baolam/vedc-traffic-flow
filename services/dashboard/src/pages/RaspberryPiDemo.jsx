import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Cpu, Video, RefreshCw, AlertTriangle, Radio, Play, Car, Gauge,
  CheckCircle2, Info, Wifi
} from 'lucide-react';
import PhaseIndicator from '../components/PhaseIndicator';

// This page is a self-contained demo: a single virtual node (contract rpi_demo_v1 / J3) that does
// not correspond to any real intersection. Its purpose is to show the exact Raspberry Pi 5 edge
// pipeline (video -> YOLO detection -> ROI telemetry -> canonical MQTT topic) end to end, without
// needing real Pi hardware wired up. It deliberately does NOT touch the global active scenario
// (useActiveScenario) used by NetworkOverview/IntersectionDetail -- see /api/v1/telemetry/node/{id}.
const DEMO_TOPOLOGY_ID = 'rpi_demo_v1';
const DEMO_NODE_ID = 'J3';

const VIDEO_SOURCES = [
  { value: 'synthetic', label: 'Synthetic Test Pattern (luôn chạy được, không cần file)' },
  { value: 'data/demo_video/video_demo_150s.mp4', label: 'data/demo_video/video_demo_150s.mp4 (sa bàn)' },
  { value: 'presentation/Camera_reality.mp4', label: 'presentation/Camera_reality.mp4 (camera thực tế)' }
];

const RaspberryPiDemo = () => {
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const [videoSource, setVideoSource] = useState(VIDEO_SOURCES[0].value);
  const [frames, setFrames] = useState(60);
  const [controller, setController] = useState('max_pressure');

  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState(null);
  const [visionStatus, setVisionStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [nodeTelemetry, setNodeTelemetry] = useState(null);
  const [deviceHealth, setDeviceHealth] = useState(null);
  const [telemetryTopic, setTelemetryTopic] = useState(null);
  const [isLive, setIsLive] = useState(false);
  const [liveAgeMs, setLiveAgeMs] = useState(null);
  const [streamKey, setStreamKey] = useState(0);

  // Vision demo video/report: whatever was last synced to the platform for (rpi_demo_v1, J3)
  const refreshVisionStatus = useCallback(() => {
    fetch(`${apiBase}/api/v1/vision/status?node_id=${DEMO_NODE_ID}&topology_id=${DEMO_TOPOLOGY_ID}`)
      .then(res => res.json())
      .then(data => {
        setVisionStatus(data);
        if (data && data.report) setReport(data.report);
      })
      .catch(() => {});
  }, [apiBase]);

  // Live telemetry for J3 specifically (not gated behind the operator's globally active scenario)
  const refreshTelemetry = useCallback(() => {
    fetch(`${apiBase}/api/v1/telemetry/node/${DEMO_NODE_ID}`)
      .then(res => res.json())
      .then(data => {
        setNodeTelemetry(data.telemetry || null);
        setDeviceHealth(data.device_health || null);
        setTelemetryTopic(data.telemetry_topic || null);
      })
      .catch(() => {});
  }, [apiBase]);

  // Real live view (MJPEG) pushed by an actual Pi running services/vision with
  // VIDEO_SYNC_ENABLED=true -- independent of the server-side simulate button below.
  const refreshLiveStatus = useCallback(() => {
    fetch(`${apiBase}/api/v1/vision/live-status/${DEMO_NODE_ID}`)
      .then(res => res.json())
      .then(data => {
        setIsLive(prevLive => {
          if (!prevLive && data.is_live) setStreamKey(k => k + 1); // (re)connect the <img> stream
          return Boolean(data.is_live);
        });
        setLiveAgeMs(data.age_ms);
      })
      .catch(() => setIsLive(false));
  }, [apiBase]);

  useEffect(() => {
    refreshVisionStatus();
    refreshTelemetry();
    refreshLiveStatus();
    const interval = setInterval(() => {
      refreshVisionStatus();
      refreshTelemetry();
      refreshLiveStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, [refreshVisionStatus, refreshTelemetry, refreshLiveStatus]);

  const handleRunDemo = async () => {
    setIsRunning(true);
    setRunError(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/vision/run-demo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video: videoSource,
          frames,
          controller,
          node_id: DEMO_NODE_ID,
          topology_id: DEMO_TOPOLOGY_ID,
          publish_mqtt: true
        })
      });
      const data = await res.json();
      if (!res.ok) {
        setRunError(data?.detail || 'Chạy demo thất bại.');
        return;
      }
      setReport(data.report || null);
      refreshVisionStatus();
      refreshTelemetry();
    } catch (e) {
      setRunError('Không gọi được API chạy demo (kiểm tra API service có đang chạy ở port 8000).');
    } finally {
      setIsRunning(false);
    }
  };

  const hasVideo = Boolean(visionStatus?.has_video);
  const videoUrl = hasVideo
    ? `${apiBase}/api/v1/vision/demo-video?node_id=${DEMO_NODE_ID}&topology_id=${DEMO_TOPOLOGY_ID}&t=${visionStatus?.video_size_bytes}`
    : null;

  const appStats = useMemo(() => nodeTelemetry?.approaches || [], [nodeTelemetry]);
  const activePhase = nodeTelemetry?.current_phase_id || report?.sample_decision?.target_phase_id || 'J3_PHASE_NS';
  const telemetryAgeMs = deviceHealth?.camera?.last_seen_ms_ago;
  const hasLiveTelemetry = Boolean(nodeTelemetry);

  return (
    <div className="page-container" style={{ backgroundColor: '#f8fafc', minHeight: '100vh', padding: '24px' }}>
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0, color: '#0f172a' }}>
            Raspberry Pi 5 Edge Vision Demo
          </h2>
          <span style={{
            fontSize: '0.72rem', fontWeight: 800, color: '#b45309', backgroundColor: '#fffbeb',
            border: '1px solid #fde68a', padding: '4px 10px', borderRadius: '6px', textTransform: 'uppercase'
          }}>
            Demo — Node {DEMO_NODE_ID} không phải giao lộ thật
          </span>
        </div>
        <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem', maxWidth: '760px' }}>
          Trang riêng cho kịch bản demo trên Raspberry Pi 5. Khi chạy <code>services/vision</code> thật
          trên Pi (<code>VISION_NODE_ID=J3</code>), thiết bị tự động: (1) phát telemetry qua MQTT theo
          đúng chuẩn như mọi node khác (<code style={{ backgroundColor: '#e0f2fe', color: '#0369a1', padding: '1px 6px', borderRadius: '4px' }}>{telemetryTopic || `edgeflow/v1/telemetry/${DEMO_NODE_ID}`}</code>),
          và (2) nếu bật <code>VIDEO_SYNC_ENABLED=true</code>, tự đẩy từng khung hình đã chú thích lên
          nền tảng qua HTTP (<code>POST /api/v1/vision/live-frame</code>), được phát lại ngay dưới
          dạng luồng trực tiếp (MJPEG) — trang này chỉ hiển thị lại, không cần bấm nút gì cả.
          Topology contract:{' '}
          <code style={{ backgroundColor: '#e0f2fe', color: '#0369a1', padding: '1px 6px', borderRadius: '4px' }}>{DEMO_TOPOLOGY_ID}</code>.
        </p>
      </div>

      {/* Info banner clarifying this is a virtual/no-hardware node */}
      <div style={{
        backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '12px',
        padding: '12px 16px', marginBottom: '20px', display: 'flex', alignItems: 'flex-start', gap: '12px', color: '#1e3a8a'
      }}>
        <Info size={20} color="#2563eb" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div style={{ fontSize: '0.84rem', lineHeight: 1.5 }}>
          Node <strong>{DEMO_NODE_ID}</strong> trong topology <strong>{DEMO_TOPOLOGY_ID}</strong> là một
          trạm <strong>ảo/mô phỏng</strong> dùng riêng cho trang demo này — không gắn với bất kỳ giao lộ
          vật lý nào, và hoàn toàn độc lập với kịch bản (scenario) bạn đang chọn ở trang Tổng quan.
          Nó tồn tại để minh hoạ trọn vẹn luồng dữ liệu mà một Raspberry Pi 5 thật sẽ gửi lên: nhận
          khung hình video → nhận diện phương tiện → trích xuất telemetry theo đúng schema → phát lên
          MQTT broker, giống hệt một thiết bị thật.
        </div>
      </div>

      <div className="grid-cols-2" style={{ marginBottom: '24px', gap: '20px' }}>
        {/* LEFT: Controls + Video Playback */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Video color="#0284c7" size={20} />
              <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                {isLive ? 'Live Stream Từ Raspberry Pi' : 'Video Đã Đồng Bộ Lên Nền Tảng'}
              </h3>
            </div>
            {isLive && (
              <span style={{
                display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', fontWeight: 800,
                padding: '3px 9px', borderRadius: '6px', backgroundColor: '#fef2f2', color: '#dc2626',
                border: '1px solid #fecaca'
              }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#ef4444' }} />
                LIVE {liveAgeMs != null ? `(${(liveAgeMs / 1000).toFixed(1)}s)` : ''}
              </span>
            )}
          </div>
          <div style={{ fontSize: '0.76rem', color: '#94a3b8', marginBottom: '12px' }}>
            Nếu Pi thật đang chạy & đẩy stream lên, nó hiện thẳng bên dưới — không cần bấm gì.
            Phần điều khiển dưới đây chỉ để <strong>mô phỏng server-side khi chưa có Pi thật</strong>.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '14px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569' }}>
              Nguồn video (giả lập camera gắn trên Raspberry Pi)
              <select
                value={videoSource}
                onChange={(e) => setVideoSource(e.target.value)}
                style={{ display: 'block', width: '100%', marginTop: '4px', padding: '8px 10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
              >
                {VIDEO_SOURCES.map(v => (
                  <option key={v.value} value={v.value}>{v.label}</option>
                ))}
              </select>
            </label>

            <div style={{ display: 'flex', gap: '10px' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569', flex: 1 }}>
                Số khung hình
                <input
                  type="number" min={10} max={450} value={frames}
                  onChange={(e) => setFrames(Math.max(10, Math.min(450, Number(e.target.value) || 60)))}
                  style={{ display: 'block', width: '100%', marginTop: '4px', padding: '8px 10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
                />
              </label>
              <label style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569', flex: 1 }}>
                Controller
                <select
                  value={controller}
                  onChange={(e) => setController(e.target.value)}
                  style={{ display: 'block', width: '100%', marginTop: '4px', padding: '8px 10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.84rem' }}
                >
                  <option value="max_pressure">Max-Pressure</option>
                  <option value="edgeflow">EdgeFlow</option>
                  <option value="fixed_time">Fixed-Time</option>
                  <option value="none">Không điều khiển (chỉ telemetry)</option>
                </select>
              </label>
            </div>

            <button
              onClick={handleRunDemo}
              disabled={isRunning}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                padding: '10px 16px', fontSize: '0.88rem', fontWeight: 700, borderRadius: '8px',
                border: 'none', cursor: isRunning ? 'not-allowed' : 'pointer',
                backgroundColor: isRunning ? '#94a3b8' : '#0284c7', color: '#ffffff'
              }}
            >
              {isRunning ? <RefreshCw size={16} className="spin" /> : <Play size={16} />}
              {isRunning ? 'Đang xử lý video trên pipeline edge vision...' : 'Mô Phỏng Server-Side (Không Cần Pi Thật)'}
            </button>

            {runError && (
              <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '8px 12px', borderRadius: '8px', fontSize: '0.8rem' }}>
                {runError}
              </div>
            )}
          </div>

          {/* Video Player */}
          <div style={{
            position: 'relative', backgroundColor: '#090d16', borderRadius: '12px', flex: 1,
            minHeight: '260px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden'
          }}>
            {isLive ? (
              // MJPEG multipart stream: the browser renders this as a plain live-updating image,
              // no polling/reload needed. streamKey forces a fresh connection whenever the device
              // transitions from offline -> live (a stale open connection would otherwise freeze).
              <img
                key={streamKey}
                src={`${apiBase}/api/v1/vision/live-stream/${DEMO_NODE_ID}`}
                alt={`Live stream from node ${DEMO_NODE_ID}`}
                style={{ width: '100%', height: '100%', maxHeight: '340px', objectFit: 'contain' }}
              />
            ) : hasVideo ? (
              <video
                key={videoUrl}
                src={videoUrl}
                controls
                autoPlay
                muted
                loop
                style={{ width: '100%', height: '100%', maxHeight: '340px', objectFit: 'contain' }}
              />
            ) : (
              <div style={{ color: '#64748b', fontSize: '0.84rem', textAlign: 'center', padding: '20px' }}>
                <Cpu size={32} style={{ marginBottom: '8px', opacity: 0.6 }} />
                <div>Chưa có live stream hoặc video nào cho node {DEMO_NODE_ID}.</div>
                <div style={{ marginTop: '4px' }}>
                  Bật Pi thật (VIDEO_SYNC_ENABLED=true) để nó tự đẩy stream lên, hoặc nhấn nút mô
                  phỏng server-side bên trên.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: Live telemetry synced via MQTT */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Radio color="#0284c7" size={20} />
              <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                Telemetry Qua MQTT ({DEMO_NODE_ID})
              </h3>
            </div>
            <span style={{
              display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', fontWeight: 800,
              padding: '4px 10px', borderRadius: '6px',
              backgroundColor: hasLiveTelemetry ? '#f0fdf4' : '#f1f5f9',
              color: hasLiveTelemetry ? '#16a34a' : '#64748b',
              border: `1px solid ${hasLiveTelemetry ? '#86efac' : '#cbd5e1'}`
            }}>
              <Wifi size={13} />
              {hasLiveTelemetry
                ? `ĐÃ NHẬN (${telemetryAgeMs != null ? `${(telemetryAgeMs / 1000).toFixed(1)}s trước` : 'vừa xong'})`
                : 'CHƯA CÓ TELEMETRY'}
            </span>
          </div>

          <div style={{ marginBottom: '14px' }}>
            <PhaseIndicator activePhase={activePhase} state="GREEN" />
          </div>

          {appStats.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px', marginBottom: '14px' }}>
              {appStats.map((app, idx) => (
                <div key={app.approach_id || idx} style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '8px 10px' }}>
                  <div style={{ fontSize: '0.74rem', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                    {app.approach_id}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: '#475569' }}>
                    <Car size={13} /> {Math.round((app.queue_vehicles || 0) * 10) / 10} veh
                    <Gauge size={13} style={{ marginLeft: '6px' }} /> {(((app.mean_speed_mps || 0) * 3.6)).toFixed(1)} km/h
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{
              fontSize: '0.78rem', color: '#64748b', backgroundColor: '#f8fafc', border: '1px dashed #cbd5e1',
              borderRadius: '8px', padding: '14px', textAlign: 'center', marginBottom: '14px'
            }}>
              Chưa có approach telemetry nào — chạy demo để pipeline phát dữ liệu qua MQTT.
            </div>
          )}

          {report && (
            <div style={{ fontSize: '0.78rem', color: '#475569', backgroundColor: '#f8fafc', borderRadius: '8px', padding: '10px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                <CheckCircle2 size={14} color="#16a34a" /> Báo cáo chạy demo gần nhất
              </div>
              <div>Backend: {report.detector_backend || 'opencv_dnn'}</div>
              {report.mqtt && (
                <div>MQTT: {report.mqtt.published ? `Đã phát tới ${report.mqtt.host}:${report.mqtt.port}` : 'Không phát (chạy standalone)'}</div>
              )}
            </div>
          )}

          <div style={{ marginTop: 'auto', paddingTop: '14px' }}>
            <div style={{ fontSize: '0.74rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertTriangle size={13} />
              Trạng thái vòng tròn an toàn (ActuatorStateMachine) không áp dụng cho node ảo này — đây chỉ là demo nhận diện & telemetry.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RaspberryPiDemo;
