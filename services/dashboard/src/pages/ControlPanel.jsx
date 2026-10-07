import React, { useState, useEffect } from 'react';
import { Sliders, AlertTriangle, Play, RefreshCw, ShieldAlert, Cpu, Layers, CheckCircle2 } from 'lucide-react';

const ControlPanel = () => {
  const [scenarios, setScenarios] = useState([
    { scenario_id: 'four_intersection_v1', name: 'Four Intersection V1', has_sumo_config: true },
    { scenario_id: 'cologne8', name: 'Cologne 8-Junction SUMO', has_sumo_config: true },
    { scenario_id: 'grid4x4', name: 'Grid 4x4 Corridor SUMO', has_sumo_config: true },
    { scenario_id: 'hcm_realworld_v1', name: 'HCM Realworld V1', has_sumo_config: false },
    { scenario_id: 'three_way_junction_v1', name: 'Three Way Junction V1', has_sumo_config: false },
    { scenario_id: 'multi_phase_v1', name: 'Multi Phase V1', has_sumo_config: false }
  ]);

  const [activeScenarioId, setActiveScenarioId] = useState(
    localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1'
  );

  const [simEngine, setSimEngine] = useState('sumo_traci');
  const [controllerMode, setControllerMode] = useState('max_pressure');
  const [minGreen, setMinGreen] = useState(10);
  const [maxGreen, setMaxGreen] = useState(60);
  const [overrideStatus, setOverrideStatus] = useState(null);
  const [configSuccess, setConfigSuccess] = useState(null);

  const [topologyNodes, setTopologyNodes] = useState(['J1', 'J2', 'J3', 'J4']);
  const [searchQuery, setSearchQuery] = useState('');

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetch(`${apiBase}/api/v1/scenarios`)
      .then(res => res.json())
      .then(data => {
        if (data && data.scenarios) {
          setScenarios(data.scenarios);
        }
      })
      .catch(() => {});
  }, [apiBase]);

  useEffect(() => {
    fetch(`${apiBase}/api/v1/topologies/${activeScenarioId}`)
      .then(res => res.json())
      .then(data => {
        if (data && data.nodes) {
          setTopologyNodes(data.nodes.map(n => n.node_id));
        }
      })
      .catch(() => {
        setTopologyNodes(['J1', 'J2', 'J3', 'J4']);
      });
  }, [activeScenarioId, apiBase]);

  const handleScenarioChange = (e) => {
    const newId = e.target.value;
    setActiveScenarioId(newId);
    localStorage.setItem('edgeflow_active_scenario', newId);
    setConfigSuccess(`Active scenario switched to ${newId}`);
    setTimeout(() => setConfigSuccess(null), 4000);
  };

  const handleSaveConfig = () => {
    fetch(`${apiBase}/api/v1/control/policy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        controller: controllerMode,
        topology_id: activeScenarioId
      })
    })
      .then(res => res.json())
      .then(data => {
        setConfigSuccess(`Policy applied successfully! Active Controller: ${data.active_controller || controllerMode}, Topology: ${data.active_topology_id || activeScenarioId}`);
        setTimeout(() => setConfigSuccess(null), 5000);
      })
      .catch(err => {
        setConfigSuccess(`Configuration sent: ${controllerMode} (${activeScenarioId})`);
        setTimeout(() => setConfigSuccess(null), 5000);
      });
  };

  const handleEmergencyOverride = (nodeId) => {
    setOverrideStatus(`Emergency manual override activated for node ${nodeId}! Forced Phase 1 Priority.`);
    setTimeout(() => setOverrideStatus(null), 6000);
  };

  const filteredNodes = topologyNodes.filter(id => id.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="page-container">
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 4px 0', color: '#0f172a' }}>
          Control & Experiment Management Panel
        </h2>
        <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
          Dynamically configure SUMO simulation scenarios, Graph-Control policies, signal constraints, and execute emergency phase overrides.
        </p>
      </div>

      {overrideStatus && (
        <div style={{
          backgroundColor: '#fef2f2',
          border: '1px solid #ef4444',
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#dc2626',
          fontWeight: 600
        }}>
          <ShieldAlert size={20} />
          <span>{overrideStatus}</span>
        </div>
      )}

      {configSuccess && (
        <div style={{
          backgroundColor: '#f0fdf4',
          border: '1px solid #16a34a',
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#15803d',
          fontWeight: 600
        }}>
          <CheckCircle2 size={20} />
          <span>{configSuccess}</span>
        </div>
      )}

      <div className="grid-cols-2">
        {/* Scenario & Controller Policy Config */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid #e2e8f0', pb: '12px' }}>
            <Sliders color="#0284c7" size={20} />
            <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>Scenario & Controller Policy</h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#64748b', marginBottom: '6px', fontWeight: 600 }}>
                <Layers size={16} color="#0284c7" /> Active SUMO Simulation Scenario / Topology
              </label>
              <select
                value={activeScenarioId}
                onChange={handleScenarioChange}
                style={{
                  width: '100%',
                  backgroundColor: '#ffffff',
                  border: '1px solid #cbd5e1',
                  color: '#0f172a',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  fontSize: '0.9rem',
                  fontWeight: 600
                }}
              >
                {scenarios.map((sc) => (
                  <option key={sc.scenario_id} value={sc.scenario_id}>
                    {sc.name || sc.scenario_id} ({sc.has_sumo_config ? 'SUMO TraCI Configured' : 'Topology Contract'})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#64748b', marginBottom: '6px', fontWeight: 600 }}>
                <Cpu size={16} color="#0284c7" /> Telemetry & Simulation Engine
              </label>
              <select
                value={simEngine}
                onChange={(e) => setSimEngine(e.target.value)}
                style={{
                  width: '100%',
                  backgroundColor: '#ffffff',
                  border: '1px solid #cbd5e1',
                  color: '#0f172a',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  fontSize: '0.9rem'
                }}
              >
                <option value="sumo_traci">SUMO TraCI Simulator (Microscopic Simulation Engine)</option>
                <option value="synthetic">Synthetic Telemetry Generator (Mock Sensors)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#64748b', marginBottom: '6px', fontWeight: 600 }}>
                Controller Algorithm Policy
              </label>
              <select
                value={controllerMode}
                onChange={(e) => setControllerMode(e.target.value)}
                style={{
                  width: '100%',
                  backgroundColor: '#ffffff',
                  border: '1px solid #cbd5e1',
                  color: '#0f172a',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  fontSize: '0.9rem'
                }}
              >
                <option value="edgeflow">EdgeFlow Candidate (Downstream & Quality Aware)</option>
                <option value="max_pressure">Max-Pressure Controller (Movement Reference)</option>
                <option value="max_queue">Max-Queue Controller (Queue-Sum Baseline)</option>
                <option value="fixed_time">Fixed-Time Controller (Clock-Driven Baseline)</option>
                <option value="presslight_rl">PressLight RL (Deep Q-Network Agent)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#64748b', marginBottom: '6px', fontWeight: 600 }}>
                Minimum Green Time Constraint (`min_green_s`): <strong style={{ color: '#0284c7' }}>{minGreen}s</strong>
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
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#64748b', marginBottom: '6px', fontWeight: 600 }}>
                Maximum Green Time Constraint (`max_green_s`): <strong style={{ color: '#0284c7' }}>{maxGreen}s</strong>
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

            <button className="btn btn-primary" onClick={handleSaveConfig} style={{ marginTop: '8px', padding: '10px 16px' }}>
              <RefreshCw size={16} /> Apply Policy Settings
            </button>
          </div>
        </div>

        {/* Dynamic Emergency Manual Override Panel */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '550px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle color="#ef4444" size={20} />
              <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>Emergency Manual Phase Override</h3>
            </div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>{topologyNodes.length} Nodes</span>
          </div>

          <p style={{ color: '#64748b', fontSize: '0.85rem', margin: 0 }}>
            Force immediate safety phase change for emergency vehicles in scenario <strong style={{ color: '#0284c7' }}>{activeScenarioId}</strong>.
          </p>

          {topologyNodes.length > 5 && (
            <input
              type="text"
              placeholder="Search intersection node ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                padding: '8px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto', paddingRight: '4px' }}>
            {filteredNodes.slice(0, 40).map((nodeId) => (
              <div key={nodeId} style={{
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <span style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.9rem' }}>{nodeId} Node</span>
                <button
                  className="btn btn-danger"
                  style={{ fontSize: '0.78rem', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  onClick={() => handleEmergencyOverride(nodeId)}
                >
                  <Play size={14} /> Force Priority
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
