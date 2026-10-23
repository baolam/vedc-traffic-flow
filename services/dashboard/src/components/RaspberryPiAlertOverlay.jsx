import React from 'react';
import { WifiOff, VideoOff } from 'lucide-react';

/**
 * RaspberryPiAlertOverlay
 *
 * Page-scoped alert for the Raspberry Pi Demo page only (mounted inside RaspberryPiDemo, NOT at
 * the App root) -- independent of SafeStopOverlay, which is a different signal (the physical
 * emergency button) for the real controlled intersections. Here there is no physical switch to
 * mirror, only two channels that can silently go quiet: MQTT telemetry and the live video push.
 * Visible for exactly as long as either is actually missing/stale; no dismiss button, since a
 * closed alert for a connection that is still down would be misleading.
 */
const RaspberryPiAlertOverlay = ({ nodeId, telemetryLost, telemetryAgeMs, streamLost, streamAgeMs }) => {
  if (!telemetryLost && !streamLost) return null;

  const fmtAge = (ms) => (ms != null ? `${(ms / 1000).toFixed(1)}s trước` : 'chưa từng nhận được');

  return (
    <div
      role="alertdialog"
      aria-live="assertive"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(15, 23, 42, 0.55)',
        backdropFilter: 'blur(2px)'
      }}
    >
      <div
        className="rpi-alert-flash"
        style={{
          animation: 'rpi-alert-pop-in 0.2s ease-out',
          backgroundColor: '#fef2f2',
          border: '3px solid #ef4444',
          borderRadius: '18px',
          padding: '28px 32px',
          maxWidth: '440px',
          width: '90%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
          textAlign: 'center'
        }}
      >
        <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#991b1b', marginBottom: '14px' }}>
          ⚠️ MẤT TÍN HIỆU NODE {nodeId}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '14px' }}>
          {telemetryLost && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px', textAlign: 'left',
              backgroundColor: '#ffffff', border: '1px solid #fecaca', borderRadius: '10px', padding: '10px 12px'
            }}>
              <WifiOff size={22} color="#dc2626" style={{ flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 700, color: '#991b1b', fontSize: '0.88rem' }}>Mất tín hiệu MQTT</div>
                <div style={{ fontSize: '0.78rem', color: '#7f1d1d' }}>
                  Chưa nhận telemetry mới — lần cuối: {fmtAge(telemetryAgeMs)}
                </div>
              </div>
            </div>
          )}
          {streamLost && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px', textAlign: 'left',
              backgroundColor: '#ffffff', border: '1px solid #fecaca', borderRadius: '10px', padding: '10px 12px'
            }}>
              <VideoOff size={22} color="#dc2626" style={{ flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 700, color: '#991b1b', fontSize: '0.88rem' }}>Mất kết nối video stream</div>
                <div style={{ fontSize: '0.78rem', color: '#7f1d1d' }}>
                  Chưa nhận khung hình mới — lần cuối: {fmtAge(streamAgeMs)}
                </div>
              </div>
            </div>
          )}
        </div>

        <div style={{ fontSize: '0.76rem', color: '#991b1b', fontWeight: 600 }}>
          Màn hình này tự tắt ngay khi {telemetryLost && streamLost ? 'cả hai' : 'kênh đó'} nhận dữ liệu trở lại.
        </div>
      </div>
    </div>
  );
};

export default RaspberryPiAlertOverlay;
