import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Network, Sliders, Cpu, ChevronLeft, ChevronRight, Trophy, Camera, Video, PlayCircle, Database, ShieldCheck } from 'lucide-react';
import { useActiveScenario } from '../hooks/useActiveScenario';
import { useLanguage } from '../hooks/useLanguage';

const COPY = {
  en: {
    sectionTitle: 'Operations TOC',
    groups: {
      live: 'Live Operations',
      sim: 'Simulation & Benchmarks',
      system: 'System & Hardware',
      admin: 'Management'
    },
    graphTwin: 'Graph Twin G=(V,E)',
    map: 'Map',
    nodes: 'Nodes',
    links: 'Links'
  },
  vi: {
    sectionTitle: 'Trung Tâm Điều Hành',
    groups: {
      live: 'Vận Hành Trực Tiếp',
      sim: 'Mô Phỏng & Benchmark',
      system: 'Hệ Thống & Phần Cứng',
      admin: 'Quản Lý'
    },
    graphTwin: 'Mô Hình Số Digital Twin',
    map: 'Bản đồ',
    nodes: 'Nút giao',
    links: 'Nhánh đường'
  }
};

// Nav items grouped into operational categories with bilingual labels.
const NAV_GROUPS = (firstNode, isVi = false) => [
  {
    key: 'live',
    items: [
      { to: '/', label: isVi ? 'Tổng Quan Mạng Lưới' : 'Overview Operations', icon: LayoutDashboard },
      { to: `/intersections/${firstNode}`, label: isVi ? 'Chi Tiết Nút Giao' : 'Station Details', icon: Network },
      { to: '/cameras', label: isVi ? 'Bản Đồ Camera HCM' : 'HCM Camera Network', icon: Camera }
    ]
  },
  {
    key: 'sim',
    items: [
      { to: '/flowtheory-demo', label: isVi ? 'Mô Phỏng CTM (FlowTheory)' : 'FlowTheory CTM Demo', icon: PlayCircle },
      { to: '/benchmark', label: isVi ? 'Báo Cáo Benchmark' : 'Benchmark Campaign', icon: Trophy }
    ]
  },
  {
    key: 'system',
    items: [
      { to: '/experiments', label: isVi ? 'Điều Khiển & Thuật Toán' : 'Control & Tuning', icon: Sliders },
      { to: '/raspberry-pi-demo', label: isVi ? 'Trực Quan Raspberry Pi' : 'Raspberry Pi Demo', icon: Video },
      { to: '/stations', label: isVi ? 'Danh Mục Trạm & Nút' : 'Station Registry', icon: Database }
    ]
  },
  {
    key: 'admin',
    items: [
      { to: '/admin', label: isVi ? 'Quản Trị Hệ Thống' : 'Management Console', icon: ShieldCheck }
    ]
  }
];

const Sidebar = ({ collapsed = false, onToggleCollapse }) => {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const [activeScenarioId] = useActiveScenario();
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.en;

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
  const isVi = lang === 'vi';
  const navGroups = NAV_GROUPS(firstNode, isVi);

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
            {t.sectionTitle}
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

      {/* Main Navigation Links, grouped by operational category. The per-junction quick-switcher
          that used to live here moved to StationContextBar, a sticky sub-header mounted directly
          on station-scoped pages -- it's more useful right above the content it switches than
          buried at the bottom of a nav the operator may have scrolled away from. */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto' }}>
        {navGroups.map((group) => (
          <div key={group.key}>
            {!isCollapsed && (
              <div style={{
                fontSize: '0.64rem', textTransform: 'uppercase', color: '#94a3b8',
                fontWeight: 800, letterSpacing: '0.6px', padding: '0 12px', marginBottom: '6px'
              }}>
                {t.groups[group.key]}
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {group.items.map((item) => {
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
            </div>
          </div>
        ))}
      </nav>

      {/* Graph Digital Twin summary footer */}
      {!isCollapsed ? (
        <div style={{ marginTop: 'auto', padding: '10px 12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <Cpu size={15} color="#0284c7" />
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#0f172a' }}>{t.graphTwin}</span>
          </div>
          <div className="tabular-nums" style={{ fontSize: '0.72rem', color: '#64748b', lineHeight: '1.4' }}>
            {t.map}: <strong style={{ color: '#0284c7' }}>{topologyStats.topology_id}</strong><br />
            {t.nodes}: <strong>{topologyStats.total_nodes}</strong> | {t.links}: <strong>{topologyStats.total_edges}</strong>
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
