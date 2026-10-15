import React, { useState, useEffect } from 'react';
import { Activity, ShieldCheck, Clock, Server, Layers, Wifi, Radio } from 'lucide-react';

const Header = () => {
  const [timeStr, setTimeStr] = useState('');
  const [timeZoneStr, setTimeZoneStr] = useState('');
  const [activeScenario, setActiveScenario] = useState(
    localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1'
  );
  const [activeController, setActiveController] = useState('max_pressure');
  const [systemStatus, setSystemStatus] = useState('ONLINE');
  const [lastSyncSec, setLastSyncSec] = useState(0);

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      // Calculate timezone abbreviation or offset
      try {
        const tzName = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const offsetMin = -now.getTimezoneOffset();
        const sign = offsetMin >= 0 ? '+' : '-';
        const hours = Math.floor(Math.abs(offsetMin) / 60);
        setTimeZoneStr(`UTC${sign}${hours}`);
      } catch {
        setTimeZoneStr('Local');
      }
    };
    updateClock();
    const timer = setInterval(() => {
      updateClock();
      setLastSyncSec(s => (s < 10 ? s + 1 : s));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const fetchStatus = () => {
      fetch(`${apiBase}/health`)
        .then(res => res.json())
        .then(data => {
          if (data) {
            if (data.active_controller) {
              setActiveController(data.active_controller);
            }
            if (data.active_topology) {
              setActiveScenario(data.active_topology);
              localStorage.setItem('edgeflow_active_scenario', data.active_topology);
            }
            if (data.status) {
              setSystemStatus(data.status.toUpperCase());
            }
            setLastSyncSec(0);
          }
        })
        .catch(() => {
          setSystemStatus('DISCONNECTED');
          const current = localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1';
          setActiveScenario(current);
        });
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [apiBase]);

  const formatControllerName = (ctrl) => {
    if (!ctrl) return 'Max-Pressure';
    const mapping = {
      'fixed_time': 'Fixed-Time',
      'max_pressure': 'Max-Pressure',
      'max_queue': 'Max-Queue',
      'edgeflow': 'EdgeFlow AI',
      'presslight_rl': 'PressLight RL',
      'rl': 'RL Agent'
    };
    return mapping[ctrl.toLowerCase()] || ctrl.replace('_', ' ').toUpperCase();
  };

  return (
    <header style={{
      backgroundColor: '#ffffff',
      borderBottom: '1px solid #e2e8f0',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03)',
      flexWrap: 'wrap',
      gap: '12px'
    }}>
      {/* Brand & Center Identification */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{
          backgroundColor: '#0284c7',
          padding: '6px 8px',
          borderRadius: '7px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 2px 4px rgba(2, 132, 199, 0.25)'
        }}>
          <Activity color="white" size={20} />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, letterSpacing: '-0.3px', color: '#0f172a' }}>
              EdgeFlow AI
            </h1>
            <span style={{
              backgroundColor: '#e0f2fe',
              color: '#0369a1',
              fontSize: '0.68rem',
              fontWeight: 800,
              padding: '2px 6px',
              borderRadius: '4px',
              letterSpacing: '0.4px',
              textTransform: 'uppercase'
            }}>
              TOC Operations
            </span>
          </div>
          <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
            Adaptive Traffic Signal Control & Safety Assurance
          </span>
        </div>
      </div>

      {/* Operational Indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
        {/* Active Scenario */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.8rem' }}>
          <Layers size={14} color="#0284c7" />
          <span style={{ color: '#64748b', fontSize: '0.75rem' }}>Map:</span>
          <span style={{ fontWeight: 700, color: '#0284c7', backgroundColor: '#f0f9ff', border: '1px solid #bae6fd', padding: '2px 7px', borderRadius: '4px', fontSize: '0.76rem', fontFamily: 'JetBrains Mono, monospace' }}>
            {activeScenario}
          </span>
        </div>

        {/* Active Controller */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.8rem' }}>
          <Server size={14} color="#0284c7" />
          <span style={{ color: '#64748b', fontSize: '0.75rem' }}>Controller:</span>
          <span style={{ fontWeight: 700, color: '#0f172a', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', padding: '2px 8px', borderRadius: '4px', fontSize: '0.76rem' }}>
            {formatControllerName(activeController)}
          </span>
        </div>

        {/* System Health */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.8rem' }}>
          <ShieldCheck size={15} color={systemStatus === 'ONLINE' ? '#16a34a' : '#dc2626'} />
          <span className={`badge ${systemStatus === 'ONLINE' ? 'badge-green' : 'badge-red'}`} style={{ fontSize: '0.7rem', padding: '3px 8px', backgroundColor: systemStatus === 'ONLINE' ? undefined : '#fee2e2', color: systemStatus === 'ONLINE' ? undefined : '#b91c1c' }}>
            {systemStatus}
          </span>
        </div>

        {/* Wall Clock & Stream Sync */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '6px',
          padding: '4px 10px',
          fontSize: '0.78rem',
          color: '#334155'
        }}>
          <Clock size={13} color="#64748b" />
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
            {timeStr}
          </span>
          <span style={{ color: '#94a3b8', fontSize: '0.7rem', fontWeight: 600 }}>
            {timeZoneStr}
          </span>
          <span style={{
            fontSize: '0.68rem',
            color: lastSyncSec < 3 ? '#16a34a' : '#ca8a04',
            backgroundColor: lastSyncSec < 3 ? '#dcfce7' : '#fef9c3',
            padding: '1px 5px',
            borderRadius: '3px',
            fontWeight: 700
          }}>
            {lastSyncSec < 3 ? 'Sync <1s' : `Sync ${lastSyncSec}s`}
          </span>
        </div>
      </div>
    </header>
  );
};

export default Header;
