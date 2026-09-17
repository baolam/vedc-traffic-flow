import React from 'react';
import { Sliders, AlertTriangle, Play, RefreshCw, ShieldAlert } from 'lucide-react';

const ControlPanel = () => {
  const [controllerMode, setControllerMode] = React.useState('max_pressure');
  const [minGreen, setMinGreen] = React.useState(10);
  const [maxGreen, setMaxGreen] = React.useState(60);
  const [overrideStatus, setOverrideStatus] = React.useState(null);

  const handleSaveConfig = () => {
    alert(`Config Saved! Mode: ${controllerMode}, min_green: ${minGreen}s, max_green: ${maxGreen}s`);
  };

  const handleEmergencyOverride = (nodeId) => {
    setOverrideStatus(`Emergency manual override activated for ${nodeId}! Target phase forced to ${nodeId}_PHASE_NS.`);
  };

  return (
    <div className="page-container">
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight 700, margin: '0 0 4px 0' }}>
          Control & Experiment Management Panel
        </h2>
        <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.9rem' }}>
          Dynamically tune Graph-Control policies, signal timing constraints, and execute manual overrides.
        </p>
      </div>

      {overrideStatus && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid #ef4444',
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#f87171'
        }}>
          <ShieldAlert size={20} />
          <span>{overrideStatus}</span>
        </div>
      )}

      <div className="grid-cols-2">
        {/* Controller Policy Config */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Sliders color="#38bdf8" size={20} />
            <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 600 }}>Active Controller Configuration</h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '6px' }}>
                Controller Algorithm Policy
              </label>
              <select
                value={controllerMode}
                onChange={(e) => setControllerMode(e.target.value)}
                style={{
                  width: '100%',
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  fontSize: '0.9rem'
                }}
              >
                <option value="max_pressure">Max-Pressure Controller (Network Adaptive)</option>
                <option value="fixed_time">Fixed-Time Controller (Sequential Baseline)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '6px' }}>
                Minimum Green Time Constraint (`min_green_s`): <strong style={{ color: '#38bdf8' }}>{minGreen}s</strong>
              </label>
              <input
                type="range"
                min="5"
                max="30"
                value={minGreen}
                onChange={(e) => setMinGreen(Number(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '6px' }}>
                Maximum Green Time Constraint (`max_green_s`): <strong style={{ color: '#38bdf8' }}>{maxGreen}s</strong>
              </label>
              <input
                type="range"
                min="30"
                max="120"
                value={maxGreen}
                onChange={(e) => setMaxGreen(Number(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>

            <button className="btn btn-primary" onClick={handleSaveConfig} style={{ marginTop: '8px' }}>
              <RefreshCw size={16} /> Apply Policy Settings
            </button>
          </div>
        </div>

        {/* Emergency Manual Override Panel */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <AlertTriangle color="#ef4444" size={20} />
            <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 600 }}>Emergency Manual Phase Override</h3>
          </div>

          <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '16px' }}>
            Force immediate safety phase change for emergency vehicle priority or incident clearance.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {['J1', 'J2', 'J3', 'J4'].map((nodeId) => (
              <div key={nodeId} style={{
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                padding: '10px 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <span style={{ fontWeight: 700, color: '#f8fafc' }}>{nodeId} Intersection</span>
                <button
                  className="btn btn-danger"
                  style={{ fontSize: '0.8rem', padding: '6px 12px' }}
                  onClick={() => handleEmergencyOverride(nodeId)}
                >
                  <Play size={14} /> Force NS Priority
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;
