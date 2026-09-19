import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Camera, Network, BarChart3, Sliders, Cpu } from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { to: '/', label: 'Overview Map', icon: LayoutDashboard },
    { to: '/hcm-cameras', label: 'HCM Geo SUMO Map', icon: Camera },
    { to: '/intersections/J1', label: 'Intersection J1', icon: Network },
    { to: '/intersections/J2', label: 'Intersection J2', icon: Network },
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

      <div style={{ marginTop: 'auto', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <Cpu size={16} color="#0284c7" />
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#0f172a' }}>Graph Twin $G=(V,E)$</span>
        </div>
        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
          Nodes: 4 Intersections<br />
          Edges: 8 Directional Lanes<br />
          Telemetry: SUMO / Vision
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
