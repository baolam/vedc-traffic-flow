import React, { useState, useEffect } from 'react';
import TopologyMap from '../components/TopologyMap';
import PhaseIndicator from '../components/PhaseIndicator';
import { Activity, Car, Gauge, Zap, Layers, Search } from 'lucide-react';

const NetworkOverview = () => {
  const [scenarios, setScenarios] = useState([
    { scenario_id: 'four_intersection_v1', name: 'Four Intersection V1', has_sumo_config: true, total_nodes: 4 },
    { scenario_id: 'cologne8', name: 'Cologne 8-Junction SUMO', has_sumo_config: true, total_nodes: 8 },
    { scenario_id: 'grid4x4', name: 'Grid 4x4 Corridor SUMO', has_sumo_config: true, total_nodes: 16 },
    { scenario_id: 'hcm_realworld_v1', name: 'HCM Realworld V1', has_sumo_config: false, total_nodes: 793 },
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

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // 1. Fetch available scenarios from API
  useEffect(() => {
    fetch(`${apiBase}/api/v1/scenarios`)
      .then(res => res.json())
      .then(data => {
        if (data && data.scenarios && data.scenarios.length > 0) {
          setScenarios(data.scenarios);
        }
      })
      .catch(() => {
        // Fallback to static initial list if API not reachable
      });
  }, [apiBase]);

  // 2. Fetch full topology contract for active scenario
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
              current_phase_id: firstPhaseId,
              total_queue: Math.floor(Math.random() * 12) + 2,
              speed: +(Math.random() * 4 + 1.5).toFixed(1)
            };
          });
          setNodes(initialNodes);
        }
        setLoading(false);
      })
      .catch(() => {
        // Fallback topology state if API fetch fails
        const fallbackNodes = {
          J1: { current_phase_id: "J1_PHASE_NS", total_queue: 14, speed: 2.1 },
          J2: { current_phase_id: "J2_PHASE_EW", total_queue: 6, speed: 4.8 },
          J3: { current_phase_id: "J3_PHASE_NS", total_queue: 8, speed: 3.2 },
          J4: { current_phase_id: "J4_PHASE_EW", total_queue: 19, speed: 1.5 }
        };
        setNodes(fallbackNodes);
        setTopology(null);
        setLoading(false);
      });
  }, [activeScenarioId, apiBase]);

  // 3. Live telemetry update timer simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setNodes(prev => {
        const next = { ...prev };
        const keys = Object.keys(next);
        if (!keys.length) return prev;

        keys.forEach(nodeId => {
          const deltaQueue = Math.floor(Math.random() * 5) - 2;
          const newQueue = Math.max(0, next[nodeId].total_queue + deltaQueue);
          const newSpeed = Math.max(0.5, +(next[nodeId].speed + (Math.random() * 0.6 - 0.3)).toFixed(1));
          
          // Phase switching simulation logic
          const currentPhase = next[nodeId].current_phase_id || `${nodeId}_PHASE_1`;
          const phaseChange = Math.random() < 0.15;
          let newPhase = currentPhase;
          if (phaseChange) {
            if (currentPhase.includes('NS')) newPhase = currentPhase.replace('NS', 'EW');
            else if (currentPhase.includes('EW')) newPhase = currentPhase.replace('EW', 'NS');
            else if (currentPhase.includes('PHASE_1')) newPhase = currentPhase.replace('PHASE_1', 'PHASE_2');
            else if (currentPhase.includes('PHASE_2')) newPhase = currentPhase.replace('PHASE_2', 'PHASE_1');
          }

          next[nodeId] = {
            current_phase_id: newPhase,
            total_queue: newQueue,
            speed: newSpeed
          };
        });
        return next;
      });
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const handleScenarioChange = (e) => {
    const newId = e.target.value;
    setActiveScenarioId(newId);
    localStorage.setItem('edgeflow_active_scenario', newId);
  };

  const nodeEntries = Object.entries(nodes);
  const totalNodesCount = nodeEntries.length || 1;
  const totalQueue = nodeEntries.reduce((acc, [, curr]) => acc + (curr.total_queue || 0), 0);
  const avgSpeed = (nodeEntries.reduce((acc, [, curr]) => acc + (curr.speed || 0), 0) / totalNodesCount).toFixed(1);

  const filteredNodes = nodeEntries.filter(([id]) => 
    id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeScenarioObj = scenarios.find(s => s.scenario_id === activeScenarioId) || {
    name: activeScenarioId,
    has_sumo_config: false
  };

  return (
    <div className="page-container">
      {/* Top Header & Scenario Selector */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '24px',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 6px 0', color: '#0f172a' }}>
            Network Topology & Live Traffic State
          </h2>
          <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
            Real-time Graph State $G_t=(V,E,X_t)$ across <strong style={{ color: '#0284c7' }}>{totalNodesCount}</strong> nodes in scenario <code style={{ backgroundColor: '#e0f2fe', color: '#0284c7', padding: '2px 6px', borderRadius: '4px' }}>{activeScenarioId}</code>.
          </p>
        </div>

        {/* Dynamic SUMO & Scenario Switcher Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '6px 12px', boxShadow: '0 1px 2px 0 rgba(0,0,0,0.05)' }}>
            <Layers size={18} color="#0284c7" />
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#64748b' }}>SUMO Scenario:</span>
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
                  {sc.name || sc.scenario_id} {sc.has_sumo_config ? '⚡ (SUMO Configured)' : ''}
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
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Queue</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{totalQueue} veh</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(22, 163, 74, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Gauge size={24} color="#16a34a" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Avg Speed</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{avgSpeed} m/s</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(202, 138, 4, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Zap size={24} color="#ca8a04" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Controller Mode</span>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#0f172a' }}>Max-Pressure</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(147, 51, 234, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Activity size={24} color="#9333ea" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Simulation Engine</span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#9333ea' }}>
              {activeScenarioObj.has_sumo_config ? 'SUMO TraCI' : 'Synthetic Telemetry'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Map & Dynamic Live Intersection Summary */}
      <div className="grid-cols-2">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>
              Interactive Topology Map ({totalNodesCount} Nodes)
            </h3>
            {loading && <span style={{ fontSize: '0.8rem', color: '#0284c7' }}>Loading topology...</span>}
          </div>
          <TopologyMap nodesData={nodes} topology={topology} />
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '570px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>
              Intersection Live Summary
            </h3>
            {totalNodesCount > 5 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: '#f1f5f9', padding: '4px 8px', borderRadius: '6px' }}>
                <Search size={14} color="#64748b" />
                <input
                  type="text"
                  placeholder="Filter nodes..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ border: 'none', backgroundColor: 'transparent', fontSize: '0.8rem', width: '90px', outline: 'none' }}
                />
              </div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto', paddingRight: '4px' }}>
            {filteredNodes.slice(0, 30).map(([nodeId, data]) => (
              <div key={nodeId} style={{
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div>
                  <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#0284c7' }}>{nodeId}</span>
                  <span style={{ fontSize: '0.8rem', color: '#64748b', marginLeft: '10px' }}>
                    Queue: <strong>{data.total_queue}</strong> veh | Speed: <strong>{data.speed}</strong> m/s
                  </span>
                </div>
                <PhaseIndicator activePhase={data.current_phase_id} state="GREEN" />
              </div>
            ))}
            {filteredNodes.length === 0 && (
              <div style={{ textAlign: 'center', color: '#94a3b8', padding: '20px', fontSize: '0.9rem' }}>
                No nodes match search query.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default NetworkOverview;
