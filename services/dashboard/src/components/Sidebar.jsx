import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Network, BarChart3, Sliders, Cpu } from 'lucide-react';

const Sidebar = () => {
  const [activeScenarioId, setActiveScenarioId] = useState(
    localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1'
  );
  
  const [topologyStats, setTopologyStats] = useState({
    total_nodes: 4,
    total_edges: 8,
    topology_id: activeScenarioId,
    nodes: ['J1', 'J2', 'J3', 'J4']
  });

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const timer = setInterval(() => {
      const current = localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1';
      if (current !== activeScenarioId) {
        setActiveScenarioId(current);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [activeScenarioId]);

  useEffect(() => {
    fetch(`${apiBase}/api/v1/topologies/${activeScenarioId}`)
      .then(res => res.json())
      .then(data => {
        if (data) {
          const nodeIds = data.nodes ? data.nodes.map(n => n.node_id) : ['J1', 'J2', 'J3', 'J4'];
          setTopologyStats({
            total_nodes: nodeIds.length,
            total_edges: data.edges ? data.edges.length : 8,
            topology_id: data.topology_id || activeScenarioId,
            nodes: nodeIds
          });
        }
      })
      .catch(() => {});
  }, [activeScenarioId, apiBase]);

  const firstNode = topologyStats.nodes.length > 0 ? topologyStats.nodes[0] : 'J1';

  const navItems = [
    { to: '/', label: 'Overview Map', icon: LayoutDashboard },
    { to: `/intersections/${firstNode}`, label: 'Station Details', icon: Network },
    { to: '/analytics', label: 'Benchmark Analytics', icon: BarChart3 },
    { to: '/experiments', label: 'Control & Experiments', icon: Sliders },
  ];

  return (
    <aside style={{
      width: '240px',
      backgroundColor: '#ffffff',
      borderRight: '1px solid #e2e8f0',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px 12px'
    }}>
      <div style={{ padding: '0 12px 16px', borderBottom: '1px solid #e2e8f0', marginBottom: '16px' }}>
        <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#94a3b8', fontWeight: 700, letterSpacing: '1px' }}>
          Navigation
        </span>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 12px',
                borderRadius: '8px',
                color: isActive ? '#0284c7' : '#64748b',
                backgroundColor: isActive ? '#e0f2fe' : 'transparent',
                borderLeft: isActive ? '3px solid #0284c7' : '3px solid transparent',
                textDecoration: 'none',
                fontWeight: isActive ? 600 : 500,
                fontSize: '0.9rem',
                transition: 'all 0.15s ease'
              })}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Topology Stations Quick Picker */}
      <div style={{ marginTop: '20px', padding: '0 4px' }}>
        <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#94a3b8', fontWeight: 700, letterSpacing: '0.5px', marginBottom: '8px' }}>
          Active Map Stations ({topologyStats.nodes.length})
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '120px', overflowY: 'auto' }}>
          {topologyStats.nodes.slice(0, 16).map(nodeId => (
            <NavLink
              key={nodeId}
              to={`/intersections/${nodeId}`}
              style={({ isActive }) => ({
                padding: '3px 8px',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontWeight: 600,
                textDecoration: 'none',
                backgroundColor: isActive ? '#0284c7' : '#f1f5f9',
                color: isActive ? '#ffffff' : '#334155',
                border: '1px solid',
                borderColor: isActive ? '#0284c7' : '#cbd5e1'
              })}
            >
              {nodeId}
            </NavLink>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 'auto', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <Cpu size={16} color="#0284c7" />
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#0f172a' }}>Graph Twin G = (V, E)</span>
        </div>
        <div style={{ fontSize: '0.75rem', color: '#64748b', lineHeight: '1.5' }}>
          Topology: <strong style={{ color: '#0284c7' }}>{topologyStats.topology_id}</strong><br />
          Stations: <strong>{topologyStats.total_nodes}</strong> Intersections<br />
          Lanes: <strong>{topologyStats.total_edges}</strong> Directed Edges<br />
          Telemetry: Live System Stream
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
