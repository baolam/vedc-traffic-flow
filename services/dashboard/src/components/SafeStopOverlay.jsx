import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, X } from 'lucide-react';

/**
 * SafeStopOverlay
 *
 * Mounted once at the App root (above <Routes>) so it interrupts whichever page the operator
 * is on -- the physical emergency button on a board is a safety event, not something that should
 * wait for someone to open that node's detail page. Polls the same /api/v1/network/state the rest
 * of the dashboard already uses; device_health.actuator.status === 'SAFE_STOP' is the real ESP32
 * health field (not the coarser overall_status, which intentionally also covers heartbeat-lost).
 *
 * A dismissed node stays dismissed only while it remains in Safe-Stop; once it clears, dismissal
 * resets, so the NEXT time someone presses the button it interrupts again instead of staying silent.
 */
const SafeStopOverlay = () => {
  const navigate = useNavigate();
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const [safeStopNodes, setSafeStopNodes] = useState([]); // [{ node_id, name }]
  const [dismissed, setDismissed] = useState(() => new Set());

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      fetch(`${apiBase}/api/v1/network/state`)
        .then(res => res.json())
        .then(data => {
          if (cancelled || !data?.nodes) return;
          const stopped = data.nodes
            .filter(n => n.device_health?.actuator?.status === 'SAFE_STOP')
            .map(n => ({ node_id: n.node_id, name: n.name || n.node_id }));
          setSafeStopNodes(stopped);
          setDismissed(prev => {
            const stoppedIds = new Set(stopped.map(n => n.node_id));
            const next = new Set();
            prev.forEach(id => { if (stoppedIds.has(id)) next.add(id); });
            return next.size === prev.size ? prev : next;
          });
        })
        .catch(() => {});
    };

    poll();
    const interval = setInterval(poll, 1200);
    return () => { cancelled = true; clearInterval(interval); };
  }, [apiBase]);

  const visibleNodes = safeStopNodes.filter(n => !dismissed.has(n.node_id));
  if (visibleNodes.length === 0) return null;

  const dismissAll = () => {
    setDismissed(prev => {
      const next = new Set(prev);
      visibleNodes.forEach(n => next.add(n.node_id));
      return next;
    });
  };

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
        className="safe-stop-flash"
        style={{
          animation: 'safe-stop-pop-in 0.2s ease-out, safe-stop-flash 1s steps(1) infinite',
          backgroundColor: '#fffbeb',
          border: '3px solid #f59e0b',
          borderRadius: '18px',
          padding: '32px 36px',
          maxWidth: '480px',
          width: '90%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
          textAlign: 'center',
          position: 'relative'
        }}
      >
        <button
          onClick={dismissAll}
          title="Đã xác nhận"
          style={{
            position: 'absolute', top: '12px', right: '12px',
            border: 'none', background: 'transparent', cursor: 'pointer',
            color: '#92400e', padding: '4px'
          }}
        >
          <X size={20} />
        </button>

        <ShieldAlert size={56} color="#d97706" style={{ marginBottom: '12px' }} />

        <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#92400e', marginBottom: '8px' }}>
          🛑 NÚT DỪNG KHẨN CẤP ĐANG ĐƯỢC NHẤN
        </div>

        <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#b45309', marginBottom: '10px' }}>
          {visibleNodes.map(n => n.name).join(' · ')}
        </div>

        <div style={{ fontSize: '0.88rem', color: '#78350f', lineHeight: 1.5, marginBottom: '22px' }}>
          Cả hai hướng đèn đang nhấp nháy vàng. Mọi ControlCommand (tự động hoặc tay) đều bị ESP32
          từ chối cho tới khi nhả nút. Đây là hành động chủ ý của người vận hành, không phải lỗi
          thiết bị. Nhả nút → ALL_RED 2s → đèn trở lại xanh bình thường.
        </div>

        <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
          <button
            onClick={() => navigate(`/intersections/${visibleNodes[0].node_id}`)}
            style={{
              padding: '10px 18px', borderRadius: '10px', border: 'none',
              backgroundColor: '#d97706', color: '#fff', fontWeight: 700,
              cursor: 'pointer', fontSize: '0.88rem'
            }}
          >
            Xem chi tiết {visibleNodes[0].node_id}
          </button>
          <button
            onClick={dismissAll}
            style={{
              padding: '10px 18px', borderRadius: '10px', border: '1.5px solid #f59e0b',
              backgroundColor: '#fff', color: '#92400e', fontWeight: 700,
              cursor: 'pointer', fontSize: '0.88rem'
            }}
          >
            Đã xác nhận
          </button>
        </div>
      </div>
    </div>
  );
};

export default SafeStopOverlay;
