import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

/**
 * SafeStopOverlay
 *
 * Mounted once at the App root (above <Routes>) so it interrupts whichever page the operator
 * is on -- the physical emergency button on a board is a safety event, not something that should
 * wait for someone to open that node's detail page.
 *
 * Strictly mirrors the board's physical switch: visible for exactly as long as
 * device_health.actuator.raw_safe_stop is true for some node, nothing else closes it (no dismiss
 * button, no timer) and nothing else makes it reappear. raw_safe_stop is the undebounced "what did
 * the board last say" flag (services/api/main.py compute_node_device_health) -- deliberately NOT
 * the coarser actuator.status/overall_status, which can briefly read HEARTBEAT_LOST instead of
 * SAFE_STOP right at the edge of the board's 5s health period and would otherwise make this flicker
 * off while the button is still physically held.
 */
const SafeStopOverlay = () => {
  const navigate = useNavigate();
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const [safeStopNodes, setSafeStopNodes] = useState([]); // [{ node_id, name }]

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      fetch(`${apiBase}/api/v1/network/state`)
        .then(res => res.json())
        .then(data => {
          if (cancelled || !data?.nodes) return;
          const stopped = data.nodes
            .filter(n => n.device_health?.actuator?.raw_safe_stop)
            .map(n => ({ node_id: n.node_id, name: n.name || n.node_id }));
          setSafeStopNodes(stopped);
        })
        .catch(() => {});
    };

    poll();
    const interval = setInterval(poll, 1000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [apiBase]);

  if (safeStopNodes.length === 0) return null;

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
        <ShieldAlert size={56} color="#d97706" style={{ marginBottom: '12px' }} />

        <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#92400e', marginBottom: '8px' }}>
          🛑 NÚT DỪNG KHẨN CẤP ĐANG ĐƯỢC NHẤN
        </div>

        <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#b45309', marginBottom: '10px' }}>
          {safeStopNodes.map(n => n.name).join(' · ')}
        </div>

        <div style={{ fontSize: '0.88rem', color: '#78350f', lineHeight: 1.5, marginBottom: '10px' }}>
          Cả hai hướng đèn đang nhấp nháy vàng. Mọi ControlCommand (tự động hoặc tay) đều bị ESP32
          từ chối cho tới khi nhả nút. Đây là hành động chủ ý của người vận hành, không phải lỗi
          thiết bị. Nhả nút → ALL_RED 2s → đèn trở lại xanh bình thường.
        </div>

        <div style={{ fontSize: '0.76rem', color: '#92400e', fontWeight: 600, marginBottom: '22px' }}>
          Màn hình này chỉ tự tắt khi board báo đã nhả nút -- không có nút đóng.
        </div>

        <button
          onClick={() => navigate(`/intersections/${safeStopNodes[0].node_id}`)}
          style={{
            padding: '10px 18px', borderRadius: '10px', border: 'none',
            backgroundColor: '#d97706', color: '#fff', fontWeight: 700,
            cursor: 'pointer', fontSize: '0.88rem'
          }}
        >
          Xem chi tiết {safeStopNodes[0].node_id}
        </button>
      </div>
    </div>
  );
};

export default SafeStopOverlay;
