import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertOctagon, Wrench, ShieldAlert, ArrowRight, X, WifiOff, Server, EyeOff } from 'lucide-react';
import { useLanguage } from '../hooks/useLanguage';

/**
 * HardwareFaultOverlay
 *
 * Intercepts and displays critical hardware faults reported by ESP32 or Vision microservices:
 * 1. ERR_CONFLICT_GUARD_TRIGGERED: Dual-green conflict guard triggered on hardware.
 * 2. ERR_HARDWARE_DEFECT: GPIO output readback mismatch (shorted/bridged pin) or abnormal brownout/panic reset.
 * 3. ERR_DISCONNECT_TIMEOUT: Remote Edge Station (Raspberry Pi) heartbeat or API probe timeout.
 * 4. ERR_CAMERA_OCCLUSION: Camera lens covered/occluded or tampering detected.
 * 5. ERR_CAMERA_BLIND: Camera optical sensor blinded (glare, blur, blackout).
 *
 * Mounted at App root so operators immediately see physical hardware and vision safety issues.
 */
const HardwareFaultOverlay = () => {
  const navigate = useNavigate();
  const [lang] = useLanguage();
  const isVi = lang === 'vi';
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const [activeFaults, setActiveFaults] = useState([]);
  const [dismissedEvents, setDismissedEvents] = useState(new Set());

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      fetch(`${apiBase}/api/v1/network/state`)
        .then(res => res.json())
        .then(data => {
          if (cancelled) return;
          const faults = [];

          // 1. From signal_faults dictionary
          if (data?.signal_faults) {
            for (const [nid, f] of Object.entries(data.signal_faults)) {
              if (
                f &&
                (f.fault_code === 'ERR_CONFLICT_GUARD_TRIGGERED' ||
                 f.fault_code === 'ERR_HARDWARE_DEFECT' ||
                 f.fault_code === 'ERR_DISCONNECT_TIMEOUT' ||
                 f.fault_code === 'ERR_CAMERA_OCCLUSION' ||
                 f.fault_code === 'ERR_CAMERA_BLIND' ||
                 f.category === 'camera')
              ) {
                faults.push({
                  node_id: nid,
                  event_id: f.event_id || `${nid}-${f.fault_code}`,
                  fault_code: f.fault_code,
                  category: f.category,
                  severity: f.severity || 'CRITICAL',
                  reason: f.reason,
                  details: f.details || {},
                  timestamp_ms: f.timestamp_ms || Date.now()
                });
              }
            }
          }

          // 2. From node device_health
          if (data?.nodes) {
            data.nodes.forEach(node => {
              const act = node.device_health?.actuator;
              const cam = node.device_health?.camera;
              const f = act?.active_fault || cam?.active_fault || node.device_health?.active_fault;
              if (
                f &&
                (f.fault_code === 'ERR_CONFLICT_GUARD_TRIGGERED' ||
                 f.fault_code === 'ERR_HARDWARE_DEFECT' ||
                 f.fault_code === 'ERR_DISCONNECT_TIMEOUT' ||
                 f.fault_code === 'ERR_CAMERA_OCCLUSION' ||
                 f.fault_code === 'ERR_CAMERA_BLIND' ||
                 f.category === 'camera') &&
                !faults.some(existing => existing.node_id === node.node_id)
              ) {
                faults.push({
                  node_id: node.node_id,
                  event_id: f.event_id || `${node.node_id}-${f.fault_code}`,
                  fault_code: f.fault_code,
                  category: f.category,
                  severity: f.severity || 'CRITICAL',
                  reason: f.reason,
                  details: f.details || {},
                  timestamp_ms: f.timestamp_ms || Date.now()
                });
              }
            });
          }

          setActiveFaults(faults);
        })
        .catch(() => {});
    };

    poll();
    const interval = setInterval(poll, 1500);
    return () => { cancelled = true; clearInterval(interval); };
  }, [apiBase]);

  // Filter out acknowledged faults
  const pendingFaults = activeFaults.filter(f => !dismissedEvents.has(f.event_id));

  if (pendingFaults.length === 0) return null;

  const currentFault = pendingFaults[0];
  const isConflict = currentFault.fault_code === 'ERR_CONFLICT_GUARD_TRIGGERED';
  const isDisconnect = currentFault.fault_code === 'ERR_DISCONNECT_TIMEOUT';
  const isCameraOcclusion = currentFault.fault_code === 'ERR_CAMERA_OCCLUSION';
  const isCameraBlind = currentFault.fault_code === 'ERR_CAMERA_BLIND';
  const isCameraFault = currentFault.category === 'camera' || isCameraOcclusion || isCameraBlind;

  const accentColor = (isConflict || isDisconnect)
    ? '#dc2626'
    : isCameraFault
    ? '#e11d48'
    : '#ea580c';

  const handleDismiss = (eventId) => {
    setDismissedEvents(prev => new Set([...prev, eventId]));
  };

  return (
    <div
      role="alertdialog"
      aria-live="assertive"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9998, // just below safe-stop (9999)
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(3px)'
      }}
    >
      <div
        style={{
          backgroundColor: '#fff',
          border: `3px solid ${accentColor}`,
          borderRadius: '16px',
          padding: '28px 32px',
          maxWidth: '520px',
          width: '90%',
          boxShadow: '0 25px 60px rgba(0,0,0,0.4)',
          position: 'relative'
        }}
      >
        <button
          onClick={() => handleDismiss(currentFault.event_id)}
          title={isVi ? 'Tạm đóng cảnh báo' : 'Acknowledge alert'}
          style={{
            position: 'absolute',
            top: 14,
            right: 14,
            background: 'none',
            border: 'none',
            color: '#64748b',
            cursor: 'pointer',
            padding: 4
          }}
        >
          <X size={20} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '14px' }}>
          {isConflict ? (
            <AlertOctagon size={44} color="#dc2626" style={{ flexShrink: 0 }} />
          ) : isDisconnect ? (
            <WifiOff size={44} color="#dc2626" style={{ flexShrink: 0 }} />
          ) : isCameraFault ? (
            <EyeOff size={44} color="#e11d48" style={{ flexShrink: 0 }} />
          ) : (
            <Wrench size={44} color="#ea580c" style={{ flexShrink: 0 }} />
          )}
          <div>
            <div style={{
              fontSize: '0.75rem',
              fontWeight: 800,
              color: accentColor,
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}>
              {isDisconnect
                ? (isVi ? 'CẢNH BÁO MẤT KẾT NỐI TRẠM GIÁM SÁT' : 'EDGE STATION DISCONNECTED')
                : isCameraFault
                ? (isVi ? 'CẢNH BÁO SỰ CỐ CAMERA THỊ GIÁC' : 'VISION CAMERA FAULT ALERT')
                : (isVi ? 'CẢNH BÁO PHẦN CỨNG THIẾT BỊ ESP32' : 'HARDWARE FAULT ALERT')}
            </div>
            <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#0f172a' }}>
              {isConflict
                ? (isVi ? 'Xung Đột Đèn Xanh Kép (Conflict Guard)' : 'Conflicting Green Guard Triggered')
                : isDisconnect
                ? (isVi ? `Mất Kết Nối Thiết Bị Trạm ${currentFault.node_id}` : `Station ${currentFault.node_id} Disconnected`)
                : isCameraOcclusion
                ? (isVi ? `Camera Bị Che Khuất / Mất Tầm Nhìn (Trạm ${currentFault.node_id})` : `Camera Occlusion Detected (Station ${currentFault.node_id})`)
                : isCameraBlind
                ? (isVi ? `Camera Mất Tầm Nhìn / Lóa Sáng / Mờ Đục (Trạm ${currentFault.node_id})` : `Camera Blind / Glare / Blur Detected (Station ${currentFault.node_id})`)
                : (isVi ? 'Hỏng Hóc Phần Cứng / Chập Chân GPIO' : 'Hardware Defect / Output Mismatch')}
            </h3>
          </div>
        </div>

        <div style={{
          backgroundColor: (isConflict || isDisconnect) ? '#fef2f2' : isCameraFault ? '#fff1f2' : '#fff7ed',
          border: `1px solid ${(isConflict || isDisconnect) ? '#fecaca' : isCameraFault ? '#fecdd3' : '#fed7aa'}`,
          borderRadius: '10px',
          padding: '12px 14px',
          marginBottom: '16px',
          fontSize: '0.88rem',
          color: (isConflict || isDisconnect) ? '#991b1b' : isCameraFault ? '#9f1239' : '#9a3412',
          lineHeight: 1.5
        }}>
          {isDisconnect ? (
            isVi ? (
              <>
                <strong>Nguyên nhân:</strong> {currentFault.reason || `Không thể liên lạc với Raspberry Pi hoặc camera tại trạm ${currentFault.node_id}.`}<br />
                <strong>Phản ứng an toàn:</strong> Hệ thống tự động chuyển trạng thái camera sang <strong>SIGNAL_LOST</strong> và phát cảnh báo toàn mạng.
              </>
            ) : (
              <>
                <strong>Cause:</strong> {currentFault.reason || `Raspberry Pi vision station ${currentFault.node_id} is unreachable.`}<br />
                <strong>Safe Action:</strong> System marked camera status as <strong>SIGNAL_LOST</strong>.
              </>
            )
          ) : isCameraFault ? (
            isVi ? (
              <>
                <strong>Nguyên nhân:</strong> {currentFault.reason || 'Ống kính camera bị che lấp hoặc cảm biến quang học mất tầm nhìn (độ sắc nét cạnh = 0).'}<br />
                <strong>Phản ứng an toàn:</strong> Hệ thống thị giác tự động hạ độ tin cậy (confidence) về <strong>0.0</strong>, kích hoạt chế độ an toàn phân bổ chu kỳ tối thiểu (Fairness Guard / Min Green), ngăn chặn bẫy đói tín hiệu đèn giao thông.
              </>
            ) : (
              <>
                <strong>Cause:</strong> {currentFault.reason || 'Camera lens occluded or optical sensor lost visibility (zero edge variance).'}<br />
                <strong>Safe Action:</strong> Perception confidence reduced to <strong>0.0</strong>, activating min-green fairness guard to prevent starvation.
              </>
            )
          ) : isConflict ? (
            isVi ? (
              <>
                <strong>Nguyên nhân:</strong> Vi điều khiển phát hiện tín hiệu yêu cầu cả 2 hướng Bắc-Nam và Đông-Tây cùng xanh.<br />
                <strong>Phản ứng an toàn:</strong> ESP32 đã cưỡng bức <strong>ĐỎ TOÀN BỘ</strong> và chuyển sang <strong>nháy vàng cảnh báo</strong> (10.0s) để ngăn ngừa va chạm giao thông.
              </>
            ) : (
              <>
                <strong>Cause:</strong> Signal controller detected concurrent green request on both phases.<br />
                <strong>Safe Action:</strong> Enforced immediate ALL_RED and transitioned to 10.0s flashing yellow.
              </>
            )
          ) : (
            isVi ? (
              <>
                <strong>Nguyên nhân:</strong> Phát hiện mức điện áp chân LED không khớp (chập chân / mối hàn) hoặc vi điều khiển sụt áp Brownout/Watchdog Reset.<br />
                <strong>Phản ứng an toàn:</strong> Chuyển sang chế độ nháy vàng cảnh báo hỏng hóc phần cứng.
              </>
            ) : (
              <>
                <strong>Cause:</strong> Output readback pin mismatch (shorted/bridged pin) or abnormal reset/brownout.<br />
                <strong>Safe Action:</strong> Actuator entered fault flashing yellow mode.
              </>
            )
          )}
        </div>

        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.82rem',
          color: '#64748b',
          marginBottom: '20px'
        }}>
          <span>Nút giao: <strong style={{ color: '#0f172a' }}>{currentFault.node_id}</strong></span>
          <span>Mã lỗi: <strong style={{ fontFamily: 'monospace', color: '#0f172a' }}>{currentFault.fault_code}</strong></span>
        </div>

        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
          <button
            onClick={() => handleDismiss(currentFault.event_id)}
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #cbd5e1',
              backgroundColor: '#f8fafc',
              color: '#475569',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            {isVi ? 'Đã Nhận Thông Tin' : 'Acknowledge'}
          </button>
          <button
            onClick={() => {
              handleDismiss(currentFault.event_id);
              if (isDisconnect || isCameraFault) {
                navigate('/raspberry-pi-demo');
              } else {
                navigate(`/intersections/${currentFault.node_id}`);
              }
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: accentColor,
              color: '#fff',
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            {isDisconnect || isCameraFault
              ? (isVi ? 'Xem Luồng Camera / Raspberry Pi' : 'View Camera / Raspberry Pi Feed')
              : (isVi ? `Kiểm Tra ${currentFault.node_id}` : `Inspect ${currentFault.node_id}`)}
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default HardwareFaultOverlay;
