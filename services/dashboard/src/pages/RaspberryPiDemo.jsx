import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Video, Radio, Car, Gauge, Wifi } from 'lucide-react';
import PhaseIndicator from '../components/PhaseIndicator';
import RaspberryPiAlertOverlay from '../components/RaspberryPiAlertOverlay';

const DEMO_NODE_ID = 'J3';

const RaspberryPiDemo = () => {
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const [nodeTelemetry, setNodeTelemetry] = useState(null);
  const [deviceHealth, setDeviceHealth] = useState(null);
  const [isLive, setIsLive] = useState(false);
  const [liveAgeMs, setLiveAgeMs] = useState(null);
  const [streamKey, setStreamKey] = useState(0);
  // Alerts only count from the moment this page has actually checked both channels at least once
  // -- otherwise the overlay would flash "lost" for the instant between mount and the first fetch
  // resolving, which is just this page opening, not an actual loss of signal.
  const [telemetryChecked, setTelemetryChecked] = useState(false);
  const [liveStatusChecked, setLiveStatusChecked] = useState(false);

  const refreshTelemetry = useCallback(() => {
    fetch(`${apiBase}/api/v1/telemetry/node/${DEMO_NODE_ID}`)
      .then(res => res.json())
      .then(data => {
        setNodeTelemetry(data.telemetry || null);
        setDeviceHealth(data.device_health || null);
      })
      .catch(() => {})
      .finally(() => setTelemetryChecked(true));
  }, [apiBase]);

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
      .catch(() => setIsLive(false))
      .finally(() => setLiveStatusChecked(true));
  }, [apiBase]);

  useEffect(() => {
    refreshTelemetry();
    refreshLiveStatus();
    const interval = setInterval(() => {
      refreshTelemetry();
      refreshLiveStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, [refreshTelemetry, refreshLiveStatus]);

  const appStats = useMemo(() => nodeTelemetry?.approaches || [], [nodeTelemetry]);
  const activePhase = nodeTelemetry?.current_phase_id || 'J3_PHASE_NS';
  const telemetryAgeMs = deviceHealth?.camera?.last_seen_ms_ago;
  const hasLiveTelemetry = Boolean(nodeTelemetry);
  // "Lost" covers both "never arrived yet" and "arrived before, gone stale now" -- SIGNAL_LOST is
  // the server's own stale-telemetry verdict (services/api/main.py, TELEMETRY_STALE_TIMEOUT_MS);
  // ZERO_CONFIDENCE (camera alive, nothing detected) is NOT a connection loss, so it's excluded.
  const telemetryLost = telemetryChecked && (!hasLiveTelemetry || deviceHealth?.camera?.status === 'SIGNAL_LOST');
  const streamLost = liveStatusChecked && !isLive;

  return (
    <div className="page-container" style={{ backgroundColor: '#f8fafc', minHeight: '100vh', padding: '24px' }}>
      <RaspberryPiAlertOverlay
        nodeId={DEMO_NODE_ID}
        telemetryLost={telemetryLost}
        telemetryAgeMs={telemetryAgeMs}
        streamLost={streamLost}
        streamAgeMs={liveAgeMs}
      />
      <h2 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 20px 0', color: '#0f172a' }}>
        Raspberry Pi — Node {DEMO_NODE_ID}
      </h2>

      <div className="grid-cols-2" style={{ gap: '20px' }}>
        {/* Video Stream */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Video color="#0284c7" size={20} />
              <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>Video Stream</h3>
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

          <div style={{
            position: 'relative', backgroundColor: '#090d16', borderRadius: '12px', flex: 1,
            minHeight: '320px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden'
          }}>
            {isLive ? (
              // MJPEG multipart stream: the browser renders this as a plain live-updating image,
              // no polling/reload needed. streamKey forces a fresh connection whenever the device
              // transitions from offline -> live (a stale open connection would otherwise freeze).
              <img
                key={streamKey}
                src={`${apiBase}/api/v1/vision/live-stream/${DEMO_NODE_ID}`}
                alt={`Live stream from node ${DEMO_NODE_ID}`}
                style={{ width: '100%', height: '100%', maxHeight: '420px', objectFit: 'contain' }}
              />
            ) : (
              <div style={{ color: '#64748b', fontSize: '0.84rem' }}>Chưa có live stream</div>
            )}
          </div>
        </div>

        {/* MQTT Telemetry */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Radio color="#0284c7" size={20} />
              <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                MQTT ({DEMO_NODE_ID})
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
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
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
              borderRadius: '8px', padding: '14px', textAlign: 'center'
            }}>
              Chưa có telemetry
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RaspberryPiDemo;
