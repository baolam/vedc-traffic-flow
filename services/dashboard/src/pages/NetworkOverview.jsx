import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import TopologyMap from '../components/TopologyMap';
import PhaseIndicator from '../components/PhaseIndicator';
import { useWebSocket } from '../hooks/useWebSocket';
import { Activity, Car, Gauge, Radio, Search, ChevronRight, ShieldCheck, Terminal, FileText, CheckCircle } from 'lucide-react';

const NetworkOverview = () => {
  const navigate = useNavigate();

  const [scenarios, setScenarios] = useState([
    { scenario_id: 'four_intersection_v1', name: 'Four Intersection V1', has_sumo_config: true, total_nodes: 4 },
    { scenario_id: 'cologne8', name: 'Cologne 8-Junction SUMO', has_sumo_config: true, total_nodes: 8 },
    { scenario_id: 'grid4x4', name: 'Grid 4x4 Corridor SUMO', has_sumo_config: true, total_nodes: 16 },
    { scenario_id: 'three_way_junction_v1', name: 'Three Way Junction V1', has_sumo_config: false, total_nodes: 3 },
    { scenario_id: 'multi_phase_v1', name: 'Multi Phase V1', has_sumo_config: false, total_nodes: 5 }
  ]);

  const [activeScenarioId, setActiveScenarioId] = useState(
    localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1'
  );

  const [topology, setTopology] = useState(null);
  const [nodes, setNodes] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeController, setActiveController] = useState('edgeflow');
  const [sourceMode, setSourceMode] = useState('system');
  const [systemReports, setSystemReports] = useState({
    mean_network_wait_time_s: 3.8,
    total_throughput_veh_per_min: 120.0,
    safety_compliance_rate_pct: 100.0,
    recent_system_logs: []
  });

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // Fallback REST fetch function
  const fetchLiveStateREST = async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/network/state`);
      const data = await res.json();
      return data;
    } catch {
      return null;
    }
  };

  // WebSocket connection for real-time <50ms updates
  const { data: wsData, isConnected: wsConnected } = useWebSocket(
    `${apiBase}/ws/telemetry`,
    fetchLiveStateREST,
    1000
  );

  const formatControllerName = (ctrl) => {
    if (!ctrl) return 'EdgeFlow AI';
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

  // 1. Fetch available map scenarios
  useEffect(() => {
    fetch(`${apiBase}/api/v1/scenarios`)
      .then(res => res.json())
      .then(data => {
        if (data && data.scenarios && data.scenarios.length > 0) {
          const mapScenarios = data.scenarios.filter(s => s.scenario_id !== 'hcm_realworld_v1');
          if (mapScenarios.length > 0) setScenarios(mapScenarios);
        }
      })
      .catch(() => {});
  }, [apiBase]);

  // 2. Fetch active map topology contract
  useEffect(() => {
    setLoading(true);
    fetch(`${apiBase}/api/v1/topologies/${activeScenarioId}`)
      .then(res => res.json())
      .then(data => {
        setTopology(data);
        if (data && data.nodes) {
          const initialNodes = {};
          data.nodes.forEach(n => {
            const nodeId = n.node_id;
            const phases = n.phases || [];
            const firstPhaseId = phases.length ? phases[0].phase_id : `${nodeId}_PHASE_1`;
            initialNodes[nodeId] = {
              node_id: nodeId,
              name: n.name || nodeId,
              current_phase_id: firstPhaseId,
              total_queue: 0,
              speed: 13.95,
              flow: 0.0,
              occupancy: 0.0,
              confidence: 100,
              source_type: 'system',
              status: 'ONLINE',
              approaches: (n.approaches || []).map(appId => ({
                approach_id: appId,
                queue_vehicles: 0,
                flow_veh_per_s: 0,
                mean_speed_mps: 13.89,
                occupancy_ratio: 0.0,
                confidence: 1.0
              }))
            };
          });
          setNodes(initialNodes);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [activeScenarioId, apiBase]);

  // 3. Fetch aggregated system log reports
  useEffect(() => {
    const fetchReports = () => {
      fetch(`${apiBase}/api/v1/system/reports`)
        .then(res => res.json())
        .then(data => {
          if (data) setSystemReports(data);
        })
        .catch(() => {});
    };
    fetchReports();
    const interval = setInterval(fetchReports, 3000);
    return () => clearInterval(interval);
  }, [apiBase]);

  // Handle incoming live telemetry state (WebSocket or Polling)
  useEffect(() => {
    if (wsData) {
      if (wsData.controller) setActiveController(wsData.controller);
      if (wsData.source_mode) setSourceMode(wsData.source_mode);
      if (wsData.nodes && wsData.nodes.length > 0) {
        const updated = {};
        wsData.nodes.forEach(n => {
          const approaches = n.approaches || [];
          const totalQ = approaches.reduce((acc, a) => acc + (a.queue_vehicles || 0), 0);
          const totalF = approaches.reduce((acc, a) => acc + (a.flow_veh_per_s || 0), 0);
          const avgSpd = approaches.length 
            ? (approaches.reduce((acc, a) => acc + (a.mean_speed_mps || 0), 0) / approaches.length)
            : 13.89;
          const avgOcc = approaches.length
            ? (approaches.reduce((acc, a) => acc + (a.occupancy_ratio || 0), 0) / approaches.length) * 100
            : 0.0;
          const avgConf = approaches.length
            ? (approaches.reduce((acc, a) => acc + (a.confidence != null ? a.confidence : 1.0), 0) / approaches.length) * 100
            : 100;

          updated[n.node_id] = {
            node_id: n.node_id,
            name: n.name || n.node_id,
            current_phase_id: n.current_phase_id || `${n.node_id}_PHASE_1`,
            total_queue: Math.round(totalQ * 10) / 10,
            speed: Math.round(avgSpd * 10) / 10,
            flow: Math.round(totalF * 100) / 100,
            occupancy: Math.round(avgOcc * 10) / 10,
            confidence: Math.round(avgConf),
            source_type: n.source_type || 'system',
            status: n.status || 'ONLINE',
            approaches: approaches
          };
        });
        setNodes(updated);
      }
    }
  }, [wsData]);

  const handleScenarioChange = (e) => {
    const newId = e.target.value;
    setActiveScenarioId(newId);
    localStorage.setItem('edgeflow_active_scenario', newId);
  };

  const nodeEntries = Object.entries(nodes);
  const totalNodesCount = topology?.nodes?.length || nodeEntries.length;
  const filteredNodes = nodeEntries.filter(([id]) => id.toLowerCase().includes(searchQuery.toLowerCase()));

  const totalQueue = nodeEntries.reduce((acc, [_, d]) => acc + (d.total_queue || 0), 0);
  const avgSpeed = nodeEntries.length 
    ? (nodeEntries.reduce((acc, [_, d]) => acc + (d.speed || 0), 0) / nodeEntries.length).toFixed(1)
    : '13.9';
  const avgOcc = nodeEntries.length
    ? (nodeEntries.reduce((acc, [_, d]) => acc + (d.occupancy || 0), 0) / nodeEntries.length).toFixed(1)
    : '0.0';

  return (
    <div className="page-container">
      {/* Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 4px 0', color: '#0f172a' }}>
            EdgeFlow AI Global Network Overview
          </h2>
          <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
            System-wide aggregated telemetry and high-level reports pushed from service execution logs.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: wsConnected ? '#f0fdf4' : '#fffbeb',
            border: `1px solid ${wsConnected ? '#86efac' : '#fde68a'}`,
            padding: '6px 12px',
            borderRadius: '20px',
            fontSize: '0.78rem',
            fontWeight: 600,
            color: wsConnected ? '#15803d' : '#b45309'
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: wsConnected ? '#22c55e' : '#f59e0b',
              display: 'inline-block'
            }}></span>
            {wsConnected ? 'WebSocket Live (<50ms)' : 'Polling Fallback'}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '6px 12px' }}>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>Active Map:</span>
            <select
              value={activeScenarioId}
              onChange={handleScenarioChange}
              style={{
                border: 'none',
                backgroundColor: 'transparent',
                fontSize: '0.9rem',
                fontWeight: 700,
                color: '#0f172a',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {scenarios.map((sc) => (
                <option key={sc.scenario_id} value={sc.scenario_id}>
                  {sc.name || sc.scenario_id} ({sc.total_nodes || '?'} stations)
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div className="grid-cols-4" style={{ marginBottom: '24px' }}>
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(2, 132, 199, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Car size={24} color="#0284c7" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Network Queue</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{Math.round(totalQueue * 10) / 10} veh</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(22, 163, 74, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Gauge size={24} color="#16a34a" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Mean Network Delay</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{systemReports.mean_network_wait_time_s}s</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(202, 138, 4, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Activity size={24} color="#ca8a04" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>System Throughput</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{systemReports.total_throughput_veh_per_min} veh/m</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(147, 51, 234, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Radio size={24} color="#9333ea" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Safety Compliance</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#16a34a', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ShieldCheck size={20} /> {systemReports.safety_compliance_rate_pct}%
            </div>
          </div>
        </div>
      </div>

      {/* Main Interactive Clean Map & Station Selector */}
      <div className="grid-cols-2" style={{ marginBottom: '24px' }}>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>
                Clean Topology Map ({totalNodesCount} Stations)
              </h3>
              <span style={{ fontSize: '0.78rem', color: '#64748b' }}>Click any node to inspect detailed status & control</span>
            </div>
            {loading && <span style={{ fontSize: '0.8rem', color: '#0284c7' }}>Loading topology...</span>}
          </div>
          <TopologyMap
            nodesData={nodes}
            topology={topology}
            onSelectNode={(nodeId) => navigate(`/intersections/${nodeId}`)}
          />
        </div>

        {/* Station Selector List */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '570px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>
              Select Device to Inspect ({activeScenarioId})
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: '#f1f5f9', padding: '4px 8px', borderRadius: '6px' }}>
              <Search size={14} color="#64748b" />
              <input
                type="text"
                placeholder="Search device..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ border: 'none', backgroundColor: 'transparent', fontSize: '0.8rem', width: '110px', outline: 'none' }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto', paddingRight: '4px' }}>
            {filteredNodes.slice(0, 30).map(([nodeId, data]) => (
              <div
                key={nodeId}
                onClick={() => navigate(`/intersections/${nodeId}`)}
                style={{
                  backgroundColor: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '12px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 800, fontSize: '0.9rem', color: '#0284c7', fontFamily: 'JetBrains Mono, monospace' }}>
                      Station {nodeId}
                    </span>
                    <span className="badge badge-blue" style={{ fontSize: '0.68rem' }}>
                      {String(data.source_type || 'system').toUpperCase()}
                    </span>
                    {data.status === 'WAITING_FOR_TELEMETRY' ? (
                      <span className="badge badge-yellow" style={{ fontSize: '0.68rem' }}>WAITING TELEMETRY</span>
                    ) : (
                      <span className="badge badge-green" style={{ fontSize: '0.68rem' }}>ONLINE</span>
                    )}
                  </div>
                  
                  <div style={{ fontSize: '0.78rem', color: '#475569', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                    <span>Queue: <strong style={{ color: data.total_queue > 10 ? '#dc2626' : '#0f172a' }}>{data.total_queue}</strong> veh</span>
                    <span>Speed: <strong>{data.speed}</strong> m/s</span>
                    <span>Flow: <strong>{data.flow}</strong> veh/s</span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <PhaseIndicator activePhase={data.current_phase_id} state="GREEN" />
                  <ChevronRight size={18} color="#94a3b8" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Aggregated System Log Stream Report Panel */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
          <Terminal size={20} color="#0284c7" />
          <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>
            System Log & Aggregated Execution Reports Stream
          </h3>
        </div>

        <div style={{ backgroundColor: '#0f172a', borderRadius: '8px', padding: '16px', color: '#38bdf8', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '200px', overflowY: 'auto' }}>
          {(systemReports.recent_system_logs || []).map((log, idx) => (
            <div key={idx} style={{ display: 'flex', gap: '12px' }}>
              <span style={{ color: '#64748b' }}>[{log.timestamp}]</span>
              <span style={{ color: '#f59e0b', fontWeight: 600 }}>[{log.service.toUpperCase()}]</span>
              <span style={{ color: '#e2e8f0' }}>{log.message}</span>
            </div>
          ))}
          {(!systemReports.recent_system_logs || systemReports.recent_system_logs.length === 0) && (
            <div style={{ color: '#64748b' }}>[System] Aggregated system event stream active...</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NetworkOverview;
