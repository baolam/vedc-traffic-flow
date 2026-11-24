import React, { useState, useEffect, useRef } from 'react';
import { Bell } from 'lucide-react';
import StatusBadge from './StatusBadge';
import { useLanguage } from '../hooks/useLanguage';

/**
 * Compact header alert drawer: a bell icon with a count badge that expands into a dropdown of
 * the network's current active_alerts (from /api/v1/system/reports). Keeps the header itself
 * down to one icon instead of a full alerts panel competing for top-bar space.
 */
const AlertBellDropdown = () => {
  const [alerts, setAlerts] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [lang] = useLanguage();
  const isVi = lang === 'vi';
  const containerRef = useRef(null);
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    let cancelled = false;
    const fetchAlerts = () => {
      fetch(`${apiBase}/api/v1/system/reports`)
        .then((res) => res.json())
        .then((data) => {
          if (!cancelled && Array.isArray(data?.active_alerts)) {
            setAlerts(data.active_alerts);
          }
        })
        .catch(() => {});
    };
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [apiBase]);

  useEffect(() => {
    const onClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const count = alerts.length;

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen((v) => !v)}
        title="Active Alerts"
        style={{
          position: 'relative',
          background: isOpen ? '#f1f5f9' : 'transparent',
          border: '1px solid #e2e8f0',
          borderRadius: '6px',
          padding: '6px 8px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#334155'
        }}
      >
        <Bell size={15} />
        {count > 0 && (
          <span style={{
            position: 'absolute',
            top: -5,
            right: -5,
            minWidth: 15,
            height: 15,
            padding: '0 3px',
            borderRadius: '9999px',
            backgroundColor: '#dc2626',
            color: '#ffffff',
            fontSize: '0.62rem',
            fontWeight: 800,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            lineHeight: 1
          }}>
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          right: 0,
          width: '320px',
          maxHeight: '360px',
          overflowY: 'auto',
          backgroundColor: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '10px',
          boxShadow: '0 12px 28px rgba(15, 23, 42, 0.15)',
          zIndex: 50
        }}>
          <div style={{
            padding: '10px 14px',
            borderBottom: '1px solid #e2e8f0',
            fontSize: '0.78rem',
            fontWeight: 800,
            color: '#0f172a'
          }}>
            {isVi ? `Cảnh Báo Đang Hoạt Động (${count})` : `Active Alerts (${count})`}
          </div>
          {count === 0 ? (
            <div style={{ padding: '18px 14px', fontSize: '0.8rem', color: '#64748b', textAlign: 'center' }}>
              {isVi ? 'Không có cảnh báo nào. Mạng lưới ổn định.' : 'No active alerts. Network nominal.'}
            </div>
          ) : (
            alerts.map((alert, idx) => (
              <div
                key={`${alert.node_id}-${idx}`}
                style={{
                  padding: '10px 14px',
                  borderBottom: idx < alerts.length - 1 ? '1px solid #f1f5f9' : 'none',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#0f172a', fontFamily: 'JetBrains Mono, monospace' }}>
                    {alert.node_id}
                  </span>
                  <StatusBadge status={alert.severity} size="sm" />
                </div>
                <span style={{ fontSize: '0.76rem', color: '#475569' }}>{alert.message}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default AlertBellDropdown;
