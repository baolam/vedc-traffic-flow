import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Network, Sliders, Cpu, ChevronLeft, ChevronRight, Activity, Trophy, Camera, Video } from 'lucide-react';
import { useActiveScenario } from '../hooks/useActiveScenario';

const Sidebar = ({ collapsed = false, onToggleCollapse }) => {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const [activeScenarioId] = useActiveScenario();

  const [topologyStats, setTopologyStats] = useState({
    total_nodes: 4,
    total_edges: 8,
    topology_id: activeScenarioId,
    nodes: ['J1', 'J2', 'J3', 'J4']
  });

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const toggleCollapse = () => {
    const next = !isCollapsed;
    setIsCollapsed(next);
    if (onToggleCollapse) onToggleCollapse(next);
  };

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
    { to: '/', label: 'Overview Operations', icon: LayoutDashboard },
    { to: `/intersections/${firstNode}`, label: 'Station Details', icon: Network },
    { to: '/benchmark', label: 'Benchmark Campaign', icon: Trophy },
    { to: '/experiments', label: 'Control & Tuning', icon: Sliders },
    { to: '/cameras', label: 'HCM Camera Network', icon: Camera },
    { to: '/raspberry-pi-demo', label: 'Raspberry Pi Demo', icon: Video },
  ];

  return (
    <aside style={{
      width: isCollapsed ? '64px' : '230px',
      backgroundColor: '#ffffff',
      borderRight: '1px solid #e2e8f0',
      display: 'flex',
      flexDirection: 'column',
      padding: isCollapsed ? '16px 8px' : '16px 12px',
      transition: 'width 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
      flexShrink: 0
    }}>
      {/* Sidebar Header & Collapse Toggle */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: isCollapsed ? 'center' : 'space-between',
        padding: isCollapsed ? '0 0 14px' : '0 8px 14px',
        borderBottom: '1px solid #e2e8f0',
        marginBottom: '14px'
      }}>
        {!isCollapsed && (
          <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#94a3b8', fontWeight: 800, letterSpacing: '1px' }}>
            Operations TOC
          </span>
        )}
        <button
          onClick={toggleCollapse}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          style={{
            background: 'transparent',
            border: '1px solid #e2e8f0',
            borderRadius: '6px',
            padding: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#64748b'
          }}
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Main Navigation Links */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              title={isCollapsed ? item.label : undefined}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                justifyContent: isCollapsed ? 'center' : 'flex-start',
                gap: '12px',
                padding: isCollapsed ? '10px 0' : '9px 12px',
                borderRadius: '8px',
                color: isActive ? '#0284c7' : '#64748b',
                backgroundColor: isActive ? '#e0f2fe' : 'transparent',
                borderLeft: isCollapsed ? 'none' : (isActive ? '3px solid #0284c7' : '3px solid transparent'),
                textDecoration: 'none',
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.88rem',
                transition: 'all 0.15s ease'
              })}
            >
              <Icon size={18} />
              {!isCollapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Quick Junction Station Selectors */}
      {!isCollapsed && (
        <div style={{ marginTop: '20px', padding: '0 4px' }}>
          <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', color: '#94a3b8', fontWeight: 800, letterSpacing: '0.5px', marginBottom: '8px' }}>
            Active Stations ({topologyStats.nodes.length})
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '110px', overflowY: 'auto' }}>
            {topologyStats.nodes.slice(0, 16).map(nodeId => (
              <NavLink
                key={nodeId}
                to={`/intersections/${nodeId}`}
                style={({ isActive }) => ({
                  padding: '3px 7px',
                  borderRadius: '4px',
                  fontSize: '0.74rem',
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
      )}

      {/* Graph Digital Twin summary footer */}
      {!isCollapsed ? (
        <div style={{ marginTop: 'auto', padding: '10px 12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <Cpu size={15} color="#0284c7" />
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#0f172a' }}>Graph Twin G=(V,E)</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: '#64748b', lineHeight: '1.4' }}>
            Map: <strong style={{ color: '#0284c7' }}>{topologyStats.topology_id}</strong><br />
            Nodes: <strong>{topologyStats.total_nodes}</strong> | Links: <strong>{topologyStats.total_edges}</strong>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'center' }} title={`Graph Twin: ${topologyStats.topology_id}`}>
          <Cpu size={18} color="#0284c7" />
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
