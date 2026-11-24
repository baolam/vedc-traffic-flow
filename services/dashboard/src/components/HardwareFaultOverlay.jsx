import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertOctagon, Wrench, ShieldAlert, ArrowRight, X } from 'lucide-react';
import { useLanguage } from '../hooks/useLanguage';

/**
 * HardwareFaultOverlay
 *
 * Intercepts and displays critical hardware faults reported by the ESP32 actuator firmware:
 * 1. ERR_CONFLICT_GUARD_TRIGGERED: Dual-green conflict guard triggered on hardware.
 * 2. ERR_HARDWARE_DEFECT: GPIO output readback mismatch (shorted/bridged pin) or abnormal brownout/panic reset.
 *
 * Mounted at App root so operators immediately see physical hardware safety issues.
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
                 f.fault_code === 'ERR_HARDWARE_DEFECT')
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
              const f = act?.active_fault;
              if (
                f &&
                (f.fault_code === 'ERR_CONFLICT_GUARD_TRIGGERED' ||
                 f.fault_code === 'ERR_HARDWARE_DEFECT') &&
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
          border: `3px solid ${isConflict ? '#dc2626' : '#ea580c'}`,
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
          ) : (
            <Wrench size={44} color="#ea580c" style={{ flexShrink: 0 }} />
          )}
          <div>
            <div style={{
              fontSize: '0.75rem',
              fontWeight: 800,
              color: isConflict ? '#dc2626' : '#ea580c',
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}>
              {isVi ? 'CẢNH BÁO PHẦN CỨNG THIẾT BỊ ESP32' : 'HARDWARE FAULT ALERT'}
            </div>
            <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#0f172a' }}>
              {isConflict
                ? (isVi ? 'Xung Đột Đèn Xanh Kép (Conflict Guard)' : 'Conflicting Green Guard Triggered')
                : (isVi ? 'Hỏng Hóc Phần Cứng / Chập Chân GPIO' : 'Hardware Defect / Output Mismatch')}
            </h3>
          </div>
        </div>

        <div style={{
          backgroundColor: isConflict ? '#fef2f2' : '#fff7ed',
          border: `1px solid ${isConflict ? '#fecaca' : '#fed7aa'}`,
          borderRadius: '10px',
          padding: '12px 14px',
          marginBottom: '16px',
          fontSize: '0.88rem',
          color: isConflict ? '#991b1b' : '#9a3412',
          lineHeight: 1.5
        }}>
          {isConflict ? (
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
              navigate(`/intersections/${currentFault.node_id}`);
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: isConflict ? '#dc2626' : '#ea580c',
              color: '#fff',
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            {isVi ? `Kiểm Tra ${currentFault.node_id}` : `Inspect ${currentFault.node_id}`}
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default HardwareFaultOverlay;
