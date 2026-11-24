import React, { useState } from 'react';
import { WifiOff, VideoOff, X, Eye, AlertTriangle } from 'lucide-react';
import { useLanguage } from '../hooks/useLanguage';

/**
 * RaspberryPiAlertOverlay
 *
 * Page-scoped alert for the Raspberry Pi Demo page only.
 * Provides a dismiss/minimize toggle so operators are never trapped on the page and can
 * inspect the telemetry/MQTT data and navigate freely, while maintaining prominent visual awareness.
 */
const RaspberryPiAlertOverlay = ({ nodeId, telemetryLost, telemetryAgeMs, streamLost, streamAgeMs }) => {
  const [isDismissed, setIsDismissed] = useState(false);
  const [lang] = useLanguage();
  const isVi = lang === 'vi';

  if (!telemetryLost && !streamLost) return null;

  const fmtAge = (ms) => (ms != null ? `${(ms / 1000).toFixed(1)}s ${isVi ? 'trước' : 'ago'}` : (isVi ? 'chưa từng nhận được' : 'never received'));

  if (isDismissed) {
    return (
      <div style={{
        backgroundColor: '#fef2f2',
        border: '1px solid #f87171',
        borderRadius: '8px',
        padding: '10px 16px',
        marginBottom: '16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        color: '#991b1b',
        fontSize: '0.85rem',
        fontWeight: 600
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle size={18} color="#dc2626" />
          <span>
            {isVi 
              ? `⚠️ Cảnh báo: ${telemetryLost && streamLost ? 'Mất tín hiệu MQTT & Video stream' : streamLost ? 'Mất kết nối video stream' : 'Mất tín hiệu MQTT'} (Node ${nodeId}). Đang hiển thị dữ liệu telemetry hiện có.`
              : `⚠️ Warning: ${telemetryLost && streamLost ? 'MQTT & Video stream disconnected' : streamLost ? 'Video stream disconnected' : 'MQTT telemetry disconnected'} (Node ${nodeId}). Showing available telemetry.`}
          </span>
        </div>
        <button
          onClick={() => setIsDismissed(false)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            backgroundColor: '#ffffff',
            border: '1px solid #fca5a5',
            color: '#b91c1c',
            borderRadius: '6px',
            padding: '4px 10px',
            fontSize: '0.78rem',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          <Eye size={14} /> {isVi ? 'Xem Chi Tiết' : 'View Details'}
        </button>
      </div>
    );
  }

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
          maxWidth: '460px',
          width: '90%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
          textAlign: 'center',
          position: 'relative'
        }}
      >
        <button
          onClick={() => setIsDismissed(true)}
          title={isVi ? "Đóng bảng thông báo và tiếp tục xem dữ liệu" : "Dismiss dialog and continue viewing data"}
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

        <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#991b1b', marginBottom: '14px' }}>
          {isVi ? `⚠️ MẤT TÍN HIỆU NODE ${nodeId}` : `⚠️ SIGNAL LOST - NODE ${nodeId}`}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
          {telemetryLost && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px', textAlign: 'left',
              backgroundColor: '#ffffff', border: '1px solid #fecaca', borderRadius: '10px', padding: '10px 12px'
            }}>
              <WifiOff size={22} color="#dc2626" style={{ flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 700, color: '#991b1b', fontSize: '0.88rem' }}>
                  {isVi ? 'Mất tín hiệu MQTT' : 'MQTT Telemetry Disconnected'}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#7f1d1d' }}>
                  {isVi ? `Chưa nhận telemetry mới — lần cuối: ${fmtAge(telemetryAgeMs)}` : `No new telemetry received — last seen: ${fmtAge(telemetryAgeMs)}`}
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
                <div style={{ fontWeight: 700, color: '#991b1b', fontSize: '0.88rem' }}>
                  {isVi ? 'Mất kết nối video stream' : 'Video Stream Disconnected'}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#7f1d1d' }}>
                  {isVi ? `Chưa nhận khung hình mới — lần cuối: ${fmtAge(streamAgeMs)}` : `No new frames received — last seen: ${fmtAge(streamAgeMs)}`}
                </div>
              </div>
            </div>
          )}
        </div>

        <div style={{ fontSize: '0.76rem', color: '#991b1b', fontWeight: 600, marginBottom: '16px' }}>
          {isVi 
            ? `Màn hình này tự tắt ngay khi ${telemetryLost && streamLost ? 'cả hai' : 'kênh đó'} nhận dữ liệu trở lại.`
            : `This dialog will automatically close when feeds recover.`}
        </div>

        <button
          onClick={() => setIsDismissed(true)}
          style={{
            width: '100%',
            padding: '10px',
            borderRadius: '8px',
            backgroundColor: '#dc2626',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: '0.88rem',
            border: 'none',
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(220, 38, 38, 0.2)'
          }}
        >
          {isVi ? 'Đóng & Tiếp Tục Xem Dữ Liệu MQTT' : 'Close & Continue Viewing MQTT Data'}
        </button>
      </div>
    </div>
  );
};

export default RaspberryPiAlertOverlay;
