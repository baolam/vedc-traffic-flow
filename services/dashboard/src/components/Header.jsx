import React, { useState, useEffect } from 'react';
import { Activity, ShieldCheck, Clock, Server, Layers } from 'lucide-react';

const Header = () => {
  const [time, setTime] = useState(new Date().toLocaleTimeString());
  const [activeScenario, setActiveScenario] = useState(
    localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1'
  );
  const [activeController, setActiveController] = useState('max_pressure');
  const [systemStatus, setSystemStatus] = useState('ONLINE');

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
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
          }
        })
        .catch(() => {
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
      padding: '12px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          backgroundColor: '#0284c7',
          padding: '8px',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <Activity color="white" size={24} />
        </div>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, letterSpacing: '0.3px', color: '#0f172a' }}>
            EdgeFlow AI <span style={{ color: '#0284c7', fontWeight: 600, fontSize: '0.9rem' }}>| Integrated Operations Center</span>
          </h1>
          <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Real-time Adaptive Traffic Signal Control System</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}>
          <Layers size={16} color="#0284c7" />
          <span style={{ color: '#64748b' }}>Scenario:</span>
          <span style={{ fontWeight: 700, color: '#0284c7', backgroundColor: '#e0f2fe', padding: '2px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>
            {activeScenario}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}>
          <Server size={16} color="#0284c7" />
          <span style={{ color: '#64748b' }}>Controller:</span>
          <span style={{ fontWeight: 600, color: '#0f172a' }}>{formatControllerName(activeController)}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}>
          <ShieldCheck size={16} color="#16a34a" />
          <span className="badge badge-green">{systemStatus}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#64748b' }}>
          <Clock size={16} />
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>{time}</span>
        </div>
      </div>
    </header>
  );
};

export default Header;
