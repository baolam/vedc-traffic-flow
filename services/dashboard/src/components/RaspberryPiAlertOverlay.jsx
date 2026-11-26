import React, { useState, useEffect } from 'react';
import { WifiOff, VideoOff, X, Eye, AlertTriangle, Server, RefreshCw } from 'lucide-react';
import { useLanguage } from '../hooks/useLanguage';

/**
 * RaspberryPiAlertOverlay
 *
 * Prominent alert overlay for the Raspberry Pi Demo page when the Pi or its feeds disconnect:
 * 1. rpiDisconnected: Raspberry Pi dashboard server is unreachable (port 8080 down or offline)
 * 2. streamLost: Live MJPEG camera stream stopped or failed to decode
 * 3. telemetryLost: MQTT telemetry stopped or timed out (> 3.5s)
 *
 * Provides a minimize toggle into a persistent top banner so operators can still view cached telemetry
 * and re-arms automatically as soon as feeds recover.
 */
const RaspberryPiAlertOverlay = ({
  nodeId = 'J3',
  rpiHost = '',
  rpiDisconnected = false,
  telemetryLost = false,
  telemetryAgeMs = null,
  streamLost = false,
  streamAgeMs = null,
  onRetry = null
}) => {
  const [isDismissed, setIsDismissed] = useState(false);
  const [lang] = useLanguage();
  const isVi = lang === 'vi';

  const hasAlert = Boolean(rpiDisconnected || telemetryLost || streamLost);

  // Auto re-arm when all feeds recover so that any future disconnection pops up immediately
  useEffect(() => {
    if (!hasAlert) {
      setIsDismissed(false);
    }
  }, [hasAlert]);

  // Ensure modal pops up immediately whenever a disconnection is newly detected
  useEffect(() => {
    if (rpiDisconnected || streamLost) {
      setIsDismissed(false);
    }
  }, [rpiDisconnected, streamLost]);

  if (!hasAlert) return null;

  const fmtAge = (ms) => (ms != null ? `${(ms / 1000).toFixed(1)}s ${isVi ? 'trước' : 'ago'}` : (isVi ? 'chưa từng nhận được' : 'never received'));

  // Minimized Banner Mode (when operator dismissed modal dialog)
  if (isDismissed) {
    return (
      <div style={{
        backgroundColor: '#fef2f2',
        border: '1.5px solid #ef4444',
        borderRadius: '8px',
        padding: '12px 16px',
        marginBottom: '16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        color: '#991b1b',
        fontSize: '0.86rem',
        fontWeight: 700,
        boxShadow: '0 2px 8px rgba(239, 68, 68, 0.15)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <AlertTriangle size={20} color="#dc2626" />
          <span>
            {isVi 
              ? `⚠️ CẢNH BÁO MẤT KẾT NỐI: Raspberry Pi (${rpiHost || `Node ${nodeId}`}) không phản hồi! Kiểm tra nguồn điện và mạng.` 
              : `⚠️ DISCONNECT ALERT: Raspberry Pi (${rpiHost || `Node ${nodeId}`}) is unreachable! Check power and network.`}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {onRetry && (
            <button
              onClick={onRetry}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                backgroundColor: '#ffffff',
                border: '1px solid #cbd5e1',
                color: '#334155',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.76rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={13} /> {isVi ? 'Thử lại' : 'Retry'}
            </button>
          )}
          <button
            onClick={() => setIsDismissed(false)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              backgroundColor: '#dc2626',
              border: 'none',
              color: '#ffffff',
              borderRadius: '6px',
              padding: '4px 12px',
              fontSize: '0.76rem',
              fontWeight: 800,
              cursor: 'pointer'
            }}
          >
            <Eye size={13} /> {isVi ? 'Xem Chi Tiết' : 'View Details'}
          </button>
        </div>
      </div>
    );
  }

  // Full Modal Alert Dialog
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
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(3px)'
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
          maxWidth: '480px',
          width: '90%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
          textAlign: 'center',
          position: 'relative'
        }}
      >
        <button
          onClick={() => setIsDismissed(true)}
          title={isVi ? "Thu gọn cảnh báo xuống thanh trên" : "Dismiss dialog"}
          style={{
            position: 'absolute',
            top: '14px',
            right: '14px',
            background: 'none',
            border: 'none',
            color: '#991b1b',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: '4px'
          }}
        >
          <X size={20} />
        </button>

        <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#991b1b', marginBottom: '14px' }}>
          {isVi ? `⚠️ CẢNH BÁO MẤT KẾT NỐI RASPBERRY PI` : `⚠️ RASPBERRY PI DISCONNECTED`}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
          {/* Raspberry Pi Hardware / Server Offline */}
          {rpiDisconnected && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left',
              backgroundColor: '#ffffff', border: '1.5px solid #fecaca', borderRadius: '10px', padding: '12px 14px'
            }}>
              <Server size={24} color="#dc2626" style={{ flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 800, color: '#991b1b', fontSize: '0.88rem' }}>
                  {isVi ? 'Không phản hồi máy chủ Raspberry Pi (Port 8080)' : 'Raspberry Pi Server Unreachable'}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#7f1d1d', marginTop: '2px' }}>
                  {isVi 
                    ? `Không thể kết nối đến ${rpiHost || 'Raspberry Pi'}. Thiết bị có thể đã tắt nguồn hoặc mất mạng Wi-Fi/LAN.` 
                    : `Cannot reach server at ${rpiHost || 'Raspberry Pi'}. Device may be powered off or disconnected from network.`}
                </div>
              </div>
            </div>
          )}

          {/* Video Stream Disconnected */}
          {streamLost && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left',
              backgroundColor: '#ffffff', border: '1.5px solid #fecaca', borderRadius: '10px', padding: '12px 14px'
            }}>
              <VideoOff size={24} color="#dc2626" style={{ flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 800, color: '#991b1b', fontSize: '0.88rem' }}>
                  {isVi ? 'Mất luồng video camera (Camera Stream)' : 'Video Stream Disconnected'}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#7f1d1d', marginTop: '2px' }}>
                  {isVi 
                    ? `Không nhận được khung hình video từ Node ${nodeId} (${fmtAge(streamAgeMs)}).` 
                    : `No active video frames received from Node ${nodeId} (${fmtAge(streamAgeMs)}).`}
                </div>
              </div>
            </div>
          )}

          {/* MQTT Telemetry Lost */}
          {telemetryLost && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left',
              backgroundColor: '#ffffff', border: '1.5px solid #fecaca', borderRadius: '10px', padding: '12px 14px'
            }}>
              <WifiOff size={24} color="#dc2626" style={{ flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 800, color: '#991b1b', fontSize: '0.88rem' }}>
                  {isVi ? 'Mất gói tin MQTT Telemetry' : 'MQTT Telemetry Signal Lost'}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#7f1d1d', marginTop: '2px' }}>
                  {isVi 
                    ? `Không có bản tin telemetry mới từ Node ${nodeId} — lần cuối: ${fmtAge(telemetryAgeMs)}.` 
                    : `No new telemetry received from Node ${nodeId} — last seen: ${fmtAge(telemetryAgeMs)}.`}
                </div>
              </div>
            </div>
          )}
        </div>

        <div style={{ fontSize: '0.76rem', color: '#991b1b', fontWeight: 600, marginBottom: '16px' }}>
          {isVi 
            ? 'Cảnh báo này sẽ tự động đóng ngay khi thiết bị kết nối và gửi dữ liệu trở lại.' 
            : 'This alert will automatically close when connection is restored.'}
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          {onRetry && (
            <button
              onClick={onRetry}
              style={{
                flex: 1,
                padding: '10px',
                borderRadius: '8px',
                backgroundColor: '#ffffff',
                color: '#dc2626',
                border: '1.5px solid #fca5a5',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              {isVi ? 'Thử Lại Kết Nối' : 'Retry'}
            </button>
          )}
          <button
            onClick={() => setIsDismissed(true)}
            style={{
              flex: 1,
              padding: '10px',
              borderRadius: '8px',
              backgroundColor: '#dc2626',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '0.85rem',
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(220, 38, 38, 0.25)'
            }}
          >
            {isVi ? 'Thu Gọn Cảnh Báo' : 'Minimize Alert'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RaspberryPiAlertOverlay;
