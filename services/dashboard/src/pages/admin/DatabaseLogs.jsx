import React, { useState, useEffect, useCallback } from 'react';
import { Database, AlertTriangle, CheckCircle2, RefreshCw, FileText, Activity } from 'lucide-react';
import { useLanguage } from '../../hooks/useLanguage';

const COPY = {
  en: {
    title: 'Persistent Database Logs & Audit',
    subtitle: 'Historical telemetry, signal faults, control decisions, and actuator safety ACKs stored in SQLite.',
    stats: {
      faults: 'Logged Faults',
      commands: 'Total Commands',
      acks: 'Actuator ACKs',
      successRate: 'ACK Success Rate'
    },
    subtabs: {
      faults: 'Signal Faults & Safety',
      acks: 'Actuator ACKs & Clearance',
      commands: 'Controller Commands'
    },
    filters: {
      nodePlaceholder: 'Filter by Node ID (e.g. J1)...',
      allStatuses: 'All Statuses',
      refresh: 'Refresh Data',
      loading: 'Loading from database...',
      empty: 'No database log records found matching the criteria.'
    },
    columns: {
      time: 'Time',
      node: 'Node ID',
      category: 'Category / Type',
      status: 'Status / Severity',
      details: 'Log Reason & Details',
      phase: 'Phase'
    }
  },
  vi: {
    title: 'Nhật Ký & Dữ Liệu Kiểm Toán Từ Cơ Sở Dữ Liệu',
    subtitle: 'Lưu trữ bền vững các sự cố tín hiệu, quyết định điều khiển và phản hồi an toàn từ SQLite (edgeflow.db).',
    stats: {
      faults: 'Sự Cố Đã Ghi Nhận',
      commands: 'Tổng Lệnh Điều Khiển',
      acks: 'Phản Hồi Actuator',
      successRate: 'Tỷ Lệ Thực Thi Thành Công'
    },
    subtabs: {
      faults: 'Sự Cố Tín Hiệu & An Toàn',
      acks: 'Phản Hồi Chấp Hành (ACKs)',
      commands: 'Lịch Sử Lệnh Điều Khiển'
    },
    filters: {
      nodePlaceholder: 'Lọc theo Node ID (ví dụ: J1)...',
      allStatuses: 'Tất cả trạng thái',
      refresh: 'Làm Mới Dữ Liệu',
      loading: 'Đang tải từ cơ sở dữ liệu...',
      empty: 'Không tìm thấy bản ghi nhật ký nào trong cơ sở dữ liệu.'
    },
    columns: {
      time: 'Thời Gian',
      node: 'Nút Giao',
      category: 'Phân Loại',
      status: 'Trạng Thái / Mức Độ',
      details: 'Chi Tiết & Lý Do Thực Thi',
      phase: 'Pha Đèn'
    }
  }
};

const formatTime = (tsMs, fallbackStr) => {
  if (tsMs) {
    const d = new Date(tsMs);
    return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
  }
  return fallbackStr || '--:--:--';
};

const DatabaseLogs = () => {
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.en;
  const isVi = lang === 'vi';

  const [activeCategory, setActiveCategory] = useState('faults'); // 'faults', 'acks', 'commands'
  const [stats, setStats] = useState(null);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [nodeFilter, setNodeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // 1. Fetch DB Stats
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/history/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.warn('Failed to fetch DB stats:', err);
    }
  }, [apiBase]);

  // 2. Fetch Records based on active category
  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      let endpoint = '';
      if (activeCategory === 'faults') {
        const nodeParam = nodeFilter ? `&node_id=${encodeURIComponent(nodeFilter.trim())}` : '';
        const sevParam = statusFilter !== 'ALL' ? `&severity=${encodeURIComponent(statusFilter)}` : '';
        endpoint = `${apiBase}/api/v1/history/faults?limit=50${nodeParam}${sevParam}`;
      } else if (activeCategory === 'acks') {
        const nodeParam = nodeFilter ? `?node_id=${encodeURIComponent(nodeFilter.trim())}&limit=50` : '?limit=50';
        endpoint = `${apiBase}/api/v1/history/acks${nodeParam}`;
      } else if (activeCategory === 'commands') {
        const nodeParam = nodeFilter ? `?node_id=${encodeURIComponent(nodeFilter.trim())}&limit=50` : '?limit=50';
        endpoint = `${apiBase}/api/v1/history/commands${nodeParam}`;
      }

      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        const list = data.faults || data.acks || data.commands || [];
        setRecords(list);
      } else {
        setRecords([]);
      }
    } catch (err) {
      console.warn('Failed to fetch DB logs:', err);
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [activeCategory, nodeFilter, statusFilter, apiBase]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Header KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
        <div style={{ backgroundColor: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>{t.stats.faults}</span>
            <AlertTriangle size={18} color="#dc2626" />
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a' }}>
            {stats ? stats.total_faults : '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#dc2626', marginTop: '4px', fontWeight: 600 }}>
            {isVi ? 'Ghi nhận trong SQLite' : 'Recorded in SQLite'}
          </div>
        </div>

        <div style={{ backgroundColor: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>{t.stats.commands}</span>
            <Activity size={18} color="#0284c7" />
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a' }}>
            {stats ? stats.total_commands.toLocaleString() : '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#0284c7', marginTop: '4px', fontWeight: 600 }}>
            {isVi ? 'Lệnh điều phối pha' : 'Phase control decisions'}
          </div>
        </div>

        <div style={{ backgroundColor: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>{t.stats.acks}</span>
            <CheckCircle2 size={18} color="#16a34a" />
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a' }}>
            {stats ? stats.total_acks.toLocaleString() : '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#16a34a', marginTop: '4px', fontWeight: 600 }}>
            {isVi ? 'Xác nhận chấp hành' : 'Hardware safety ACKs'}
          </div>
        </div>

        <div style={{ backgroundColor: '#ffffff', borderRadius: '10px', padding: '16px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>{t.stats.successRate}</span>
            <Database size={18} color="#8b5cf6" />
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a' }}>
            {stats ? `${stats.command_success_rate_percent}%` : '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '4px', fontWeight: 600 }}>
            {isVi ? 'Tuân thủ interlock 0% va chạm' : 'Interlock clearance verified'}
          </div>
        </div>
      </div>

      {/* 2. Sub-Category Tabs & Filter Bar */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '10px', border: '1px solid #e2e8f0', padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', borderBottom: '1px solid #f1f5f9', paddingBottom: '14px', marginBottom: '16px' }}>
          {/* Sub-tab selection */}
          <div style={{ display: 'flex', gap: '8px' }}>
            {[
              { key: 'faults', label: t.subtabs.faults, icon: AlertTriangle },
              { key: 'acks', label: t.subtabs.acks, icon: CheckCircle2 },
              { key: 'commands', label: t.subtabs.commands, icon: FileText }
            ].map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => {
                  setActiveCategory(key);
                  setStatusFilter('ALL');
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 14px',
                  borderRadius: '6px',
                  border: activeCategory === key ? '1px solid #0284c7' : '1px solid #e2e8f0',
                  backgroundColor: activeCategory === key ? '#f0f9ff' : '#ffffff',
                  color: activeCategory === key ? '#0284c7' : '#475569',
                  fontWeight: 700,
                  fontSize: '0.82rem',
                  cursor: 'pointer'
                }}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </div>

          {/* Filter Toolbar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <input
              type="text"
              placeholder={t.filters.nodePlaceholder}
              value={nodeFilter}
              onChange={(e) => setNodeFilter(e.target.value)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.8rem',
                outline: 'none',
                minWidth: '180px'
              }}
            />

            {activeCategory === 'faults' && (
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.8rem',
                  outline: 'none',
                  backgroundColor: '#ffffff'
                }}
              >
                <option value="ALL">{t.filters.allStatuses}</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="WARNING">WARNING</option>
                <option value="INFO">INFO</option>
              </select>
            )}

            <button
              onClick={() => {
                fetchStats();
                fetchRecords();
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '6px',
                backgroundColor: '#0284c7',
                color: '#ffffff',
                border: 'none',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              {t.filters.refresh}
            </button>
          </div>
        </div>

        {/* 3. Database Table Stream */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569' }}>
                <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.time}</th>
                <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.node}</th>
                <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.category}</th>
                <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.status}</th>
                <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.details}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} style={{ padding: '30px', textAlign: 'center', color: '#64748b' }}>
                    <RefreshCw size={20} className="spin" style={{ display: 'inline', marginRight: '8px' }} />
                    {t.filters.loading}
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '30px', textAlign: 'center', color: '#94a3b8' }}>
                    {t.filters.empty}
                  </td>
                </tr>
              ) : (
                records.map((r, idx) => {
                  if (activeCategory === 'faults') {
                    const isCrit = r.severity === 'CRITICAL';
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '10px 14px', whiteSpace: 'nowrap', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.76rem', color: '#64748b' }}>
                          {formatTime(r.timestamp_ms, r.created_at)}
                        </td>
                        <td style={{ padding: '10px 14px', fontWeight: 800, color: '#0284c7' }}>
                          {r.node_id}
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <span style={{ backgroundColor: '#f1f5f9', padding: '3px 8px', borderRadius: '4px', fontSize: '0.74rem', fontWeight: 700, color: '#334155' }}>
                            {r.category?.toUpperCase() || 'FAULT'}
                          </span>
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <span style={{
                            backgroundColor: isCrit ? '#fee2e2' : '#fef3c7',
                            color: isCrit ? '#dc2626' : '#d97706',
                            padding: '3px 8px',
                            borderRadius: '4px',
                            fontSize: '0.74rem',
                            fontWeight: 800
                          }}>
                            {r.severity}
                          </span>
                        </td>
                        <td style={{ padding: '10px 14px', color: '#1e293b' }}>
                          <div style={{ fontWeight: 600, fontSize: '0.78rem', color: '#0f172a' }}>{r.fault_code}</div>
                          <div style={{ fontSize: '0.74rem', color: '#64748b' }}>{r.reason}</div>
                        </td>
                      </tr>
                    );
                  }

                  if (activeCategory === 'acks') {
                    const isApplied = r.status === 'APPLIED';
                    const isAccepted = r.status === 'ACCEPTED';
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '10px 14px', whiteSpace: 'nowrap', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.76rem', color: '#64748b' }}>
                          {formatTime(r.timestamp_ms, r.created_at)}
                        </td>
                        <td style={{ padding: '10px 14px', fontWeight: 800, color: '#0284c7' }}>
                          {r.node_id}
                        </td>
                        <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.76rem', color: '#0369a1' }}>
                          {r.target_phase_id || '—'}
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <span style={{
                            backgroundColor: isApplied ? '#dcfce7' : isAccepted ? '#e0f2fe' : '#fee2e2',
                            color: isApplied ? '#16a34a' : isAccepted ? '#0284c7' : '#dc2626',
                            padding: '3px 8px',
                            borderRadius: '4px',
                            fontSize: '0.74rem',
                            fontWeight: 800
                          }}>
                            {r.status}
                          </span>
                        </td>
                        <td style={{ padding: '10px 14px', color: '#475569', fontSize: '0.78rem' }}>
                          {r.reason || `ACK for ${r.command_id}`}
                        </td>
                      </tr>
                    );
                  }

                  // Default commands
                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '10px 14px', whiteSpace: 'nowrap', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.76rem', color: '#64748b' }}>
                        {formatTime(r.timestamp_ms, r.created_at)}
                      </td>
                      <td style={{ padding: '10px 14px', fontWeight: 800, color: '#0284c7' }}>
                        {r.node_id}
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ backgroundColor: '#f0f9ff', color: '#0284c7', padding: '3px 8px', borderRadius: '4px', fontSize: '0.74rem', fontWeight: 700 }}>
                          {r.controller || 'Max-Pressure'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.76rem', color: '#16a34a', fontWeight: 700 }}>
                        {r.target_phase_id}
                      </td>
                      <td style={{ padding: '10px 14px', color: '#475569', fontSize: '0.76rem' }}>
                        Min Green: <strong>{r.min_green_s ?? 10}s</strong> | Max Green: <strong>{r.max_green_s ?? 60}s</strong> (ID: {r.command_id})
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DatabaseLogs;
