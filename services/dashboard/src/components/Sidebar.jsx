import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Network, BarChart3, Sliders, Cpu } from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { to: '/', label: 'Overview Map', icon: LayoutDashboard },
    { to: '/intersections/J1', label: 'Intersection J1', icon: Network },
    { to: '/intersections/J2', label: 'Intersection J2', icon: Network },
    { to: '/analytics', label: 'Benchmark Analytics', icon: BarChart3 },
    { to: '/experiments', label: 'Control & Experiments', icon: Sliders },
  ];

  return (
    <aside style={{
      width: '240px',
      backgroundColor: '#1e293b',
      borderRight: '1px solid #334155',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px 12px'
    }}>
      <div style={{ padding: '0 12px 16px', borderBottom: '1px solid #334155', marginBottom: '16px' }}>
        <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 700, letterSpacing: '1px' }}>
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
                color: isActive ? '#38bdf8' : '#94a3b8',
                backgroundColor: isActive ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                borderLeft: isActive ? '3px solid #38bdf8' : '3px solid transparent',
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

      <div style={{ marginTop: 'auto', padding: '12px', backgroundColor: '#0f172a', borderRadius: '8px', border: '1px solid #334155' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <Cpu size={16} color="#38bdf8" />
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f8fafc' }}>Graph Twin $G=(V,E)$</span>
        </div>
        <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
          Nodes: 4 Intersections<br />
          Edges: 8 Directional Lanes<br />
          Telemetry: SUMO / Vision
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
