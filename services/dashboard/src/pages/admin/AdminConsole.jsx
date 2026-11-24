import React, { useState, useEffect } from 'react';
import { 
  HardDrive, SlidersHorizontal, BellRing, Users, Database, 
  Layers, Server, ShieldCheck, Activity, CheckCircle2 
} from 'lucide-react';
import { useLanguage } from '../../hooks/useLanguage';
import { useActiveScenario } from '../../hooks/useActiveScenario';
import DeviceManagement from './DeviceManagement';
import SystemConfig from './SystemConfig';
import AlertRules from './AlertRules';
import UserManagement from './UserManagement';
import DatabaseLogs from './DatabaseLogs';

const COPY = {
  en: {
    title: 'Traffic System Management Console',
    subtitle: 'Unified operational governance: persistent audit database, station topology, controller policies, and access control.',
    systemSummary: {
      topology: 'Active Network Map',
      controller: 'Control Algorithm',
      interlock: 'Safety Clearance Interlock',
      interlockActive: 'ACTIVE (0% Hazard)',
      dbState: 'Persistent Storage',
      dbLive: 'SQLite Operational'
    },
    groups: {
      operations: 'OPERATIONS & AUDIT',
      control: 'POLICIES & SAFETY',
      governance: 'ACCESS & GOVERNANCE'
    },
    tabs: {
      db_logs: {
        title: 'Database Audit Logs',
        desc: 'Persistent faults, commands & ACKs'
      },
      devices: {
        title: 'Station Fleet & Topology',
        desc: 'Junction assets & camera inventory'
      },
      config: {
        title: 'System & Timing Config',
        desc: 'Controllers, Yellow/All-Red interlocks'
      },
      alerts: {
        title: 'Alert Rules & Thresholds',
        desc: 'Queue congestion & fault triggers'
      },
      users: {
        title: 'Users & Permissions',
        desc: 'Role-based access & privileges'
      }
    }
  },
  vi: {
    title: 'Trung Tâm Quản Trị Hệ Thống Giao Thông',
    subtitle: 'Quản trị điều hành tập trung: kiểm toán CSDL bền vững, danh mục trạm, chính sách điều khiển và phân quyền.',
    systemSummary: {
      topology: 'Bản Đồ Mạng Đang Chạy',
      controller: 'Thuật Toán Điều Khiển',
      interlock: 'Khóa Cứng An Toàn (Interlock)',
      interlockActive: 'KÍCH HOẠT (0% Xung Đột)',
      dbState: 'Cơ Sở Dữ Liệu Bền Vững',
      dbLive: 'SQLite Đang Ghi'
    },
    groups: {
      operations: 'VẬN HÀNH & KIỂM TOÁN',
      control: 'CHÍNH SÁCH & AN TOÀN',
      governance: 'HỆ THỐNG & PHÂN QUYỀN'
    },
    tabs: {
      db_logs: {
        title: 'Nhật Ký Cơ Sở Dữ Liệu',
        desc: 'Tra cứu sự cố, lệnh & ACK từ SQLite'
      },
      devices: {
        title: 'Thiết Bị & Danh Mục Trạm',
        desc: 'Quản lý nút giao, nhánh đường & camera'
      },
      config: {
        title: 'Cấu Hình & Tham Số An Toàn',
        desc: 'Bộ điều khiển & Thời gian Vàng/Đỏ'
      },
      alerts: {
        title: 'Quy Tắc & Ngưỡng Cảnh Báo',
        desc: 'Giám sát hàng chờ ùn tắc & sự cố'
      },
      users: {
        title: 'Người Dùng & Phân Quyền',
        desc: 'Phân quyền Admin, Operator, Viewer'
      }
    }
  }
};

const TAB_CONFIG = [
  { 
    key: 'db_logs', 
    group: 'operations', 
    icon: Database, 
    Component: DatabaseLogs,
    badge: 'SQLite'
  },
  { 
    key: 'devices', 
    group: 'operations', 
    icon: HardDrive, 
    Component: DeviceManagement,
    badge: 'Fleet'
  },
  { 
    key: 'config', 
    group: 'control', 
    icon: SlidersHorizontal, 
    Component: SystemConfig,
    badge: 'Policies'
  },
  { 
    key: 'alerts', 
    group: 'control', 
    icon: BellRing, 
    Component: AlertRules,
    badge: 'Rules'
  },
  { 
    key: 'users', 
    group: 'governance', 
    icon: Users, 
    Component: UserManagement,
    badge: 'RBAC'
  }
];

const AdminConsole = () => {
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.en;
  const isVi = lang === 'vi';
  const [activeScenarioId] = useActiveScenario();

  const [activeTab, setActiveTab] = useState('db_logs');
  const [activeController, setActiveController] = useState('Max-Pressure');
  const [dbStats, setDbStats] = useState(null);

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    // Fetch live controller policy
    fetch(`${apiBase}/api/v1/control/policy`)
      .then((res) => res.json())
      .then((data) => {
        if (data?.active_controller) {
          const map = {
            'max_pressure': 'Max-Pressure',
            'max_queue': 'Max-Queue',
            'fixed_time': 'Fixed-Time',
            'flow_theory': 'FlowTheory CTM',
            'actuated': 'Actuated'
          };
          setActiveController(map[data.active_controller] || data.active_controller);
        }
      })
      .catch(() => {});

    // Fetch DB stats summary for the top bar
    fetch(`${apiBase}/api/v1/history/stats`)
      .then((res) => res.json())
      .then((data) => {
        if (data) setDbStats(data);
      })
      .catch(() => {});
  }, [apiBase]);

  const activeTabMeta = TAB_CONFIG.find((tab) => tab.key === activeTab) || TAB_CONFIG[0];
  const ActiveComponent = activeTabMeta.Component;

  return (
    <div className="page-container" style={{ padding: '24px', backgroundColor: '#f8fafc', minHeight: '100vh' }}>
      {/* 1. Header & Title */}
      <div style={{ marginBottom: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span style={{ 
                backgroundColor: '#0284c7', color: '#ffffff', fontSize: '0.68rem', 
                fontWeight: 800, padding: '3px 8px', borderRadius: '4px', letterSpacing: '0.5px' 
              }}>
                MANAGEMENT CONSOLE
              </span>
              <h2 style={{ fontSize: '1.45rem', fontWeight: 800, margin: 0, color: '#0f172a' }}>
                {t.title}
              </h2>
            </div>
            <p style={{ color: '#64748b', margin: 0, fontSize: '0.84rem' }}>
              {t.subtitle}
            </p>
          </div>
        </div>

        {/* 2. Executive Quick-Status Ribbon */}
        <div style={{ 
          marginTop: '16px', display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', 
          gap: '12px', backgroundColor: '#ffffff', 
          padding: '12px 16px', borderRadius: '10px', 
          border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ backgroundColor: '#f0f9ff', padding: '8px', borderRadius: '8px' }}>
              <Layers size={18} color="#0284c7" />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 600 }}>{t.systemSummary.topology}</div>
              <div style={{ fontSize: '0.88rem', fontWeight: 800, color: '#0284c7', fontFamily: 'JetBrains Mono, monospace' }}>
                {activeScenarioId}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ backgroundColor: '#f0fdf4', padding: '8px', borderRadius: '8px' }}>
              <Server size={18} color="#16a34a" />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 600 }}>{t.systemSummary.controller}</div>
              <div style={{ fontSize: '0.88rem', fontWeight: 800, color: '#0f172a' }}>
                {activeController}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ backgroundColor: '#fef2f2', padding: '8px', borderRadius: '8px' }}>
              <ShieldCheck size={18} color="#dc2626" />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 600 }}>{t.systemSummary.interlock}</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#16a34a', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={13} color="#16a34a" /> {t.systemSummary.interlockActive}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ backgroundColor: '#f5f3ff', padding: '8px', borderRadius: '8px' }}>
              <Database size={18} color="#8b5cf6" />
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 600 }}>{t.systemSummary.dbState}</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#6b21a8' }}>
                {dbStats ? `${dbStats.total_faults} ${isVi ? 'lỗi' : 'faults'} · ${dbStats.total_commands.toLocaleString()} ${isVi ? 'lệnh' : 'cmds'}` : t.systemSummary.dbLive}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Reorganized Navigation Tabs with Badges & Explanations */}
      <div style={{ 
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '10px', marginBottom: '22px' 
      }}>
        {TAB_CONFIG.map(({ key, icon: Icon, badge }) => {
          const isActive = activeTab === key;
          const meta = t.tabs[key];
          return (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                textAlign: 'left',
                padding: '12px 14px',
                borderRadius: '9px',
                border: isActive ? '1.5px solid #0284c7' : '1px solid #e2e8f0',
                backgroundColor: isActive ? '#ffffff' : '#f8fafc',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: isActive ? '0 3px 8px rgba(2, 132, 199, 0.12)' : 'none',
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              {isActive && (
                <div style={{ 
                  position: 'absolute', top: 0, left: 0, right: 0, 
                  height: '3px', backgroundColor: '#0284c7' 
                }} />
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Icon size={17} color={isActive ? '#0284c7' : '#64748b'} />
                  <span style={{ 
                    fontSize: '0.88rem', fontWeight: 800, 
                    color: isActive ? '#0284c7' : '#1e293b' 
                  }}>
                    {meta.title}
                  </span>
                </div>
                <span style={{ 
                  fontSize: '0.64rem', fontWeight: 800, 
                  backgroundColor: isActive ? '#e0f2fe' : '#e2e8f0', 
                  color: isActive ? '#0369a1' : '#475569', 
                  padding: '2px 6px', borderRadius: '4px' 
                }}>
                  {badge}
                </span>
              </div>
              <span style={{ fontSize: '0.74rem', color: '#64748b', lineHeight: '1.3' }}>
                {meta.desc}
              </span>
            </button>
          );
        })}
      </div>

      {/* 4. Active Tab Component Container */}
      <div style={{ 
        backgroundColor: '#ffffff', borderRadius: '12px', 
        padding: '20px', border: '1px solid #e2e8f0', 
        boxShadow: '0 2px 8px rgba(0,0,0,0.02)' 
      }}>
        <ActiveComponent />
      </div>
    </div>
  );
};

export default AdminConsole;
