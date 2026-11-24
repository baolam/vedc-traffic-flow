import React, { useState, useEffect } from 'react';
import { Activity, ShieldCheck, Clock, Server, Layers } from 'lucide-react';
import { useActiveScenario } from '../hooks/useActiveScenario';
import { useLanguage } from '../hooks/useLanguage';
import { getStatusToken } from '../utils/statusTokens';
import StatusBadge from './StatusBadge';
import AlertBellDropdown from './AlertBellDropdown';
import GlobalDeviceSearch from './GlobalDeviceSearch';

const COPY = {
  en: {
    tocOperations: 'TOC Operations',
    tagline: 'Adaptive Traffic Signal Control & Safety Assurance',
    map: 'Map:',
    controller: 'Controller:',
    syncLt: 'Sync <1s',
    syncSec: (s) => `Sync ${s}s`
  },
  vi: {
    tocOperations: 'Vận Hành TOC',
    tagline: 'Điều Khiển Tín Hiệu Thích Ứng & Đảm Bảo An Toàn',
    map: 'Bản đồ:',
    controller: 'Bộ điều khiển:',
    syncLt: 'Đồng bộ <1s',
    syncSec: (s) => `Đồng bộ ${s}s`
  }
};

const Header = () => {
  const [timeStr, setTimeStr] = useState('');
  const [timeZoneStr, setTimeZoneStr] = useState('');
  const [activeScenario, setActiveScenario] = useActiveScenario();
  const [activeController, setActiveController] = useState('max_pressure');
  // Raw status from /health ("healthy", "disconnected", ...) -- resolved through statusTokens
  // below so its color can never again drift out of sync with its tier (see the bug this
  // replaced: comparing it against the literal string 'ONLINE' meant "HEALTHY" itself rendered
  // as a red/danger badge, since "HEALTHY" !== "ONLINE").
  const [systemStatus, setSystemStatus] = useState('HEALTHY');
  const [lastSyncSec, setLastSyncSec] = useState(0);
  const [lang, setLang] = useLanguage();
  const t = COPY[lang] || COPY.en;

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
            // applied_controller = what graph-control's commands say it runs; requested policy until then
            if (data.applied_controller || data.active_controller) {
              setActiveController(data.applied_controller || data.active_controller);
            }
            if (data.active_topology) {
              setActiveScenario(data.active_topology);
            }
            if (data.status) {
              setSystemStatus(data.status.toUpperCase());
            }
            setLastSyncSec(0);
          }
        })
        .catch(() => {
          setSystemStatus('DISCONNECTED');
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
      gap: '8px'
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
              {t.tocOperations}
            </span>
          </div>
          <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
            {t.tagline}
          </span>
        </div>
      </div>

      {/* Operational Indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {/* Jump to any device by ID, independent of whichever page is currently open */}
        <GlobalDeviceSearch />

        {/* Active Scenario */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem' }}>
          <Layers size={14} color="#0284c7" />
          <span style={{ color: '#64748b', fontSize: '0.74rem' }}>{t.map}</span>
          <span style={{ fontWeight: 700, color: '#0284c7', backgroundColor: '#f0f9ff', border: '1px solid #bae6fd', padding: '2px 6px', borderRadius: '4px', fontSize: '0.74rem', fontFamily: 'JetBrains Mono, monospace' }}>
            {activeScenario}
          </span>
        </div>

        {/* Active Controller */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem' }}>
          <Server size={14} color="#0284c7" />
          <span style={{ color: '#64748b', fontSize: '0.74rem' }}>{t.controller}</span>
          <span style={{ fontWeight: 700, color: '#0f172a', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', padding: '2px 7px', borderRadius: '4px', fontSize: '0.74rem' }}>
            {formatControllerName(activeController)}
          </span>
        </div>

        {/* System Health -- resolved through the same statusTokens tiers as every other status
            badge in the app, instead of a one-off comparison against the literal 'ONLINE' (which
            is how "HEALTHY" used to end up rendered in danger red: it simply isn't 'ONLINE'). */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem' }}>
          <ShieldCheck size={14} color={getStatusToken(systemStatus).dot} />
          <StatusBadge status={systemStatus} size="md" />
        </div>

        {/* Wall Clock & Stream Sync */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '6px',
          padding: '3px 8px',
          fontSize: '0.76rem',
          color: '#334155'
        }}>
          <Clock size={12} color="#64748b" />
          <span className="tabular-nums" style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
            {timeStr}
          </span>
          <span style={{ color: '#94a3b8', fontSize: '0.68rem', fontWeight: 600 }}>
            {timeZoneStr}
          </span>
          <span className="tabular-nums" style={{
            fontSize: '0.66rem',
            color: lastSyncSec < 3 ? '#16a34a' : '#ca8a04',
            backgroundColor: lastSyncSec < 3 ? '#dcfce7' : '#fef9c3',
            padding: '1px 5px',
            borderRadius: '3px',
            fontWeight: 700
          }}>
            {lastSyncSec < 3 ? t.syncLt : t.syncSec(lastSyncSec)}
          </span>
        </div>

        {/* Compact alert drawer */}
        <AlertBellDropdown />

        {/* EN | VI shell-language toggle. Drives Header/Sidebar/AlertBellDropdown/
            StationContextBar copy today; each page adopts it as it gets refactored. */}
        <div style={{
          display: 'flex', alignItems: 'center', border: '1px solid #e2e8f0',
          borderRadius: '6px', overflow: 'hidden', fontSize: '0.72rem', fontWeight: 800
        }}>
          {['en', 'vi'].map((code) => (
            <button
              key={code}
              onClick={() => setLang(code)}
              title={code === 'en' ? 'English' : 'Tiếng Việt'}
              style={{
                border: 'none',
                padding: '6px 9px',
                cursor: 'pointer',
                backgroundColor: lang === code ? '#0284c7' : 'transparent',
                color: lang === code ? '#ffffff' : '#64748b',
                textTransform: 'uppercase'
              }}
            >
              {code}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
};

export default Header;
