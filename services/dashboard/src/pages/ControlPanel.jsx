import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Sliders, AlertTriangle, Play, RefreshCw, Cpu, Layers, CheckCircle2, Camera } from 'lucide-react';
import { describeOverride, overrideRequestError, OVERRIDE_IN_PROGRESS } from '../utils/manualOverride';
import { useActiveScenario, MAP_ONLY_SCENARIOS } from '../hooks/useActiveScenario';

const OVERRIDE_FOLLOW_MAX_POLLS = 60; // 1 s each: covers the 25 s wait + 15 s hold

const ControlPanel = () => {
  const [scenarios, setScenarios] = useState([
    { scenario_id: 'four_intersection_v1', name: 'Four Intersection V1', has_sumo_config: true },
    { scenario_id: 'cologne8', name: 'Cologne 8-Junction SUMO', has_sumo_config: true },
    { scenario_id: 'grid4x4', name: 'Grid 4x4 Corridor SUMO', has_sumo_config: true },
    { scenario_id: 'hcm_realworld_v1', name: 'HCM Realworld V1', has_sumo_config: false },
    { scenario_id: 'three_way_junction_v1', name: 'Three Way Junction V1', has_sumo_config: false },
    { scenario_id: 'multi_phase_v1', name: 'Multi Phase V1', has_sumo_config: false }
  ]);

  const [activeScenarioId, setActiveScenarioId] = useActiveScenario();

  const [simEngine, setSimEngine] = useState('live_mqtt');
  const [controllerMode, setControllerMode] = useState('max_pressure');
  const [minGreen, setMinGreen] = useState(10);
  const [maxGreen, setMaxGreen] = useState(60);
  const [overrideViews, setOverrideViews] = useState({}); // nodeId -> banner built from the ESP32 ACKs
  const overrideTimers = useRef({});
  const [configSuccess, setConfigSuccess] = useState(null);

  const [topologyNodes, setTopologyNodes] = useState(['J1', 'J2', 'J3', 'J4']);
  // node_id -> its first contract phase_id, used as the "priority" phase for emergency override
  // instead of assuming every node has a literal "_PHASE_NS" (only true for the NS/EW-named topologies).
  const [nodeDefaultPhase, setNodeDefaultPhase] = useState({});
  const [searchQuery, setSearchQuery] = useState('');

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // Start the policy selector on the controller that is running, not on a fixed default
  useEffect(() => {
    fetch(`${apiBase}/health`)
      .then(res => res.json())
      .then(data => {
        const running = data && (data.applied_controller || data.active_controller);
        if (running && running !== 'edgeflow') {
          setControllerMode(running);
        } else {
          setControllerMode('max_pressure');
        }
      })
      .catch(() => {});
  }, [apiBase]);

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
          const defaultPhases = {};
          data.nodes.forEach(n => {
            if (n.phases && n.phases.length > 0) defaultPhases[n.node_id] = n.phases[0].phase_id;
          });
          setNodeDefaultPhase(defaultPhases);
        }
      })
      .catch(() => {
        setTopologyNodes(['J1', 'J2', 'J3', 'J4']);
        setNodeDefaultPhase({});
      });
  }, [activeScenarioId, apiBase]);

  const handleScenarioChange = (e) => {
    const newId = e.target.value;
    setActiveScenarioId(newId);
    setConfigSuccess(`Active scenario switched to ${newId}`);
    setTimeout(() => setConfigSuccess(null), 4000);
  };

  const isMapOnlyScenario = MAP_ONLY_SCENARIOS.includes(activeScenarioId);

  const handleSaveConfig = () => {
    fetch(`${apiBase}/api/v1/control/policy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        controller: controllerMode,
        topology_id: activeScenarioId
      })
    })
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        setConfigSuccess(ok
          ? `Policy requested: ${data.active_controller}. Graph-control switches within ~2 s; the header shows the controller its commands report.`
          : `Rejected: ${data.detail || 'unknown error'}`);
        setTimeout(() => setConfigSuccess(null), 6000);
      })
      .catch(() => {
        setConfigSuccess(`API unreachable: policy not changed (${controllerMode})`);
        setTimeout(() => setConfigSuccess(null), 6000);
      });
  };

  useEffect(() => () => Object.values(overrideTimers.current).forEach(clearInterval), []);

  const showOverride = (nodeId, view) => setOverrideViews(prev => ({ ...prev, [nodeId]: view }));

  // Follow one node's override until the ESP32 has settled it (the API view is built from the device ACKs)
  const followOverride = (nodeId) => {
    clearInterval(overrideTimers.current[nodeId]);
    let polls = 0;
    overrideTimers.current[nodeId] = setInterval(() => {
      polls += 1;
      fetch(`${apiBase}/api/v1/network/state/${nodeId}`)
        .then(res => res.json())
        .then(data => {
          const override = data && data.manual_override;
          showOverride(nodeId, describeOverride(override));
          const settled = !override || !(OVERRIDE_IN_PROGRESS.includes(override.status) || override.status === 'APPLIED');
          if (settled || polls >= OVERRIDE_FOLLOW_MAX_POLLS) clearInterval(overrideTimers.current[nodeId]);
        })
        .catch(() => {
          if (polls >= OVERRIDE_FOLLOW_MAX_POLLS) clearInterval(overrideTimers.current[nodeId]);
        });
    }, 1000);
  };

  // Emergency priority = this node's first contract phase (its default/primary green), under the
  // ESP32 safety rules. Falls back to the NS/EW convention only when the contract phase list
  // hasn't loaded yet; using "_PHASE_NS" unconditionally 400s on topologies that don't name phases
  // that way (grid4x4, cologne8 use PHASE_1..PHASE_10).
  const handleEmergencyOverride = (nodeId) => {
    const targetPhaseId = nodeDefaultPhase[nodeId] || `${nodeId}_PHASE_NS`;
    showOverride(nodeId, null);
    fetch(`${apiBase}/api/v1/control/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId, target_phase_id: targetPhaseId })
    })
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          showOverride(nodeId, overrideRequestError(`API từ chối: ${data.detail || 'lỗi không rõ'}`));
          return;
        }
        showOverride(nodeId, describeOverride({ status: 'SENT', target_phase_id: data.target_phase_id }));
        followOverride(nodeId);
      })
      .catch(() => showOverride(nodeId, overrideRequestError('Không gọi được API: lệnh chưa tới thiết bị.')));
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
                disabled
                title="Display only: telemetry currently comes from the vision service"
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
                <option value="live_mqtt">Live MQTT telemetry (vision service)</option>
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
                <option value="max_pressure">Max-Pressure Controller (Movement Reference)</option>
                <option value="max_queue">Max-Queue Controller (Queue-Sum Baseline)</option>
                <option value="fixed_time">Fixed-Time Controller (Clock-Driven Baseline)</option>
              </select>
            </div>

            {/* Not sent anywhere yet: the controller puts min/max green in every command and the ESP32
                enforces them (max green capped at 60 s on the device). Disabled so a click is not mistaken
                for a change on the lights. */}
            <div style={{ opacity: 0.55 }} title="Not connected: the controller sets min/max green per command (10 s / 60 s); the actuator device enforces them">
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#64748b', marginBottom: '6px', fontWeight: 600 }}>
                Minimum Green Time Constraint (`min_green_s`): <strong style={{ color: '#0284c7' }}>{minGreen}s</strong>
              </label>
              <input
                type="range"
                min="5"
                max="30"
                value={minGreen}
                disabled
                readOnly
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ opacity: 0.55 }} title="Not connected: the actuator device caps max green at 60 s">
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#64748b', marginBottom: '6px', fontWeight: 600 }}>
                Maximum Green Time Constraint (`max_green_s`): <strong style={{ color: '#0284c7' }}>{maxGreen}s</strong>
              </label>
              <input
                type="range"
                min="30"
                max="60"
                value={maxGreen}
                disabled
                readOnly
                style={{ width: '100%' }}
              />
              <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>
                Min/max green come from the controller in each command and are enforced on the actuator device; not adjustable here yet.
              </div>
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
            Emergency priority: each node's default contract phase in scenario <strong style={{ color: '#0284c7' }}>{activeScenarioId}</strong>. The actuator device switches once its current green has run 5 s (yellow 3 s, all-red 2 s), then holds it 15 s before the controller resumes. The status below is the device's own answer.
          </p>

          {isMapOnlyScenario ? (
            <div style={{
              backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px',
              padding: '14px 16px', display: 'flex', alignItems: 'center', gap: '12px'
            }}>
              <Camera size={22} color="#0284c7" />
              <div style={{ fontSize: '0.84rem', color: '#1e3a8a' }}>
                <strong>{activeScenarioId}</strong> là mạng camera địa lý ({topologyNodes.length} trạm), không phải kịch bản vận hành trực tiếp — không có panel override theo từng trạm ở đây.{' '}
                <Link to="/cameras" style={{ color: '#0284c7', fontWeight: 700, textDecoration: 'underline' }}>
                  Xem Bản đồ Camera HCM
                </Link>
              </div>
            </div>
          ) : (
          <>
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
              <div key={nodeId}>
              <div style={{
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
                  disabled={Boolean(overrideViews[nodeId] && ['info', 'warn'].includes(overrideViews[nodeId].tone))}
                >
                  <Play size={14} /> Force Priority Phase
                </button>
              </div>
              {overrideViews[nodeId] && (
                <div style={{
                  marginTop: '6px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: `1px solid ${overrideViews[nodeId].colors.border}`,
                  backgroundColor: overrideViews[nodeId].colors.background,
                  color: overrideViews[nodeId].colors.color,
                  fontSize: '0.8rem'
                }}>
                  <div style={{ fontWeight: 700 }}>{overrideViews[nodeId].title}</div>
                  <div>{overrideViews[nodeId].detail}</div>
                </div>
              )}
              </div>
            ))}
          </div>
          </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;
