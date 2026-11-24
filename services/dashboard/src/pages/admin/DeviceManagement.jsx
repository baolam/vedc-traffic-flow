import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Search, ExternalLink, Layers, ChevronLeft, ChevronRight } from 'lucide-react';
import { useLanguage } from '../../hooks/useLanguage';

const COPY = {
  en: {
    searchPlaceholder: 'Filter stations by ID, name, or street...',
    allScenarios: (count) => `All Network Maps (${count})`,
    stationCount: (filtered, total) => `${filtered} / ${total} stations monitored`,
    loading: 'Loading station asset registry...',
    error: 'Could not connect to API to load station registry.',
    empty: (q) => `No stations found matching "${q}".`,
    columns: {
      nodeId: 'Station Node ID',
      name: 'Station Name',
      scenario: 'Topology Scenario',
      street: 'Intersection Street',
      approaches: 'Approaches',
      phases: 'Phases',
      actions: 'Diagnostics'
    },
    viewLink: 'View Live Node',
    pageInfo: (curr, total, count) => `Showing page ${curr} of ${total} (${count} total stations)`,
    prev: 'Previous',
    next: 'Next',
    schemaNotice: 'Station records originate directly from contracts/topology/ and are read-only here. To add, rename, or re-wire junctions, update the canonical topology contract and re-run make contracts.'
  },
  vi: {
    searchPlaceholder: 'Tìm trạm theo ID nút, tên gọi hoặc tên đường...',
    allScenarios: (count) => `Tất Cả Bản Đồ Mạng (${count})`,
    stationCount: (filtered, total) => `Đang hiển thị ${filtered} / ${total} trạm nút giao`,
    loading: 'Đang tải danh mục tài sản trạm nút giao...',
    error: 'Không thể kết nối API để tải danh mục trạm.',
    empty: (q) => `Không tìm thấy trạm nào khớp với từ khóa "${q}".`,
    columns: {
      nodeId: 'ID Nút Giao',
      name: 'Tên Trạm / Nút',
      scenario: 'Cấu Trúc Mạng',
      street: 'Tuyến Đường Giao Nhau',
      approaches: 'Nhánh Đường',
      phases: 'Pha Đèn',
      actions: 'Chẩn Đoán'
    },
    viewLink: 'Xem Trực Tiếp',
    pageInfo: (curr, total, count) => `Trang ${curr} / ${total} (Tổng cộng ${count} trạm)`,
    prev: 'Trang Trước',
    next: 'Trang Sau',
    schemaNotice: 'Dữ liệu trạm xuất phát trực tiếp từ hợp đồng contracts/topology/ và là dữ liệu chỉ đọc. Để thêm mới hoặc sửa cấu hình nút, hãy chỉnh sửa tệp hợp đồng và chạy make contracts.'
  }
};

const DeviceManagement = () => {
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.en;

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState('');
  const [scenarioFilter, setScenarioFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  useEffect(() => {
    fetch(`${apiBase}/api/v1/stations`)
      .then((res) => res.json())
      .then((data) => {
        setStations(Array.isArray(data?.stations) ? data.stations : []);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, [apiBase]);

  const scenarioIds = useMemo(
    () => Array.from(new Set(stations.map((s) => s.topology_id))).sort(),
    [stations]
  );

  const q = query.trim().toLowerCase();
  const filtered = useMemo(() => stations.filter((s) => {
    if (scenarioFilter && s.topology_id !== scenarioFilter) return false;
    if (!q) return true;
    return (
      s.node_id.toLowerCase().includes(q) ||
      (s.name || '').toLowerCase().includes(q) ||
      (s.street_name || '').toLowerCase().includes(q)
    );
  }), [stations, scenarioFilter, q]);

  useEffect(() => {
    setCurrentPage(1);
  }, [query, scenarioFilter]);

  const totalPages = Math.ceil(filtered.length / pageSize) || 1;
  const paginated = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, currentPage, pageSize]);

  return (
    <div>
      {/* Search & Filter Bar */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', flex: 1 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#f8fafc',
            border: '1px solid #cbd5e1', borderRadius: '7px', padding: '6px 12px', minWidth: '240px', maxWidth: '380px', flex: 1
          }}>
            <Search size={14} color="#94a3b8" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.searchPlaceholder}
              style={{ border: 'none', outline: 'none', backgroundColor: 'transparent', fontSize: '0.82rem', width: '100%' }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={14} color="#64748b" />
            <select
              value={scenarioFilter}
              onChange={(e) => setScenarioFilter(e.target.value)}
              style={{
                fontSize: '0.8rem', padding: '6px 12px', borderRadius: '7px',
                border: '1px solid #cbd5e1', backgroundColor: '#ffffff', color: '#1e293b', fontWeight: 600, outline: 'none'
              }}
            >
              <option value="">{t.allScenarios(scenarioIds.length)}</option>
              {scenarioIds.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
          </div>
        </div>

        <span style={{ fontSize: '0.8rem', color: '#0284c7', fontWeight: 700, backgroundColor: '#f0f9ff', border: '1px solid #bae6fd', padding: '4px 10px', borderRadius: '6px' }}>
          {t.stationCount(filtered.length, stations.length)}
        </span>
      </div>

      {loading && <div className="card" style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>{t.loading}</div>}
      {!loading && error && <div className="card" style={{ padding: '24px', textAlign: 'center', color: '#dc2626' }}>{t.error}</div>}
      {!loading && !error && filtered.length === 0 && (
        <div className="card" style={{ textAlign: 'center', color: '#64748b', padding: '30px' }}>
          {t.empty(query)}
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: 'hidden', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', backgroundColor: '#f8fafc', color: '#475569', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.nodeId}</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.name}</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.scenario}</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.street}</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.approaches}</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.phases}</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700 }}>{t.columns.actions}</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((s) => (
                  <tr key={`${s.topology_id}-${s.node_id}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '9px 14px', fontFamily: 'JetBrains Mono, monospace', fontWeight: 800, color: '#0284c7' }}>
                      {s.node_id}
                    </td>
                    <td style={{ padding: '9px 14px', color: '#0f172a', fontWeight: 600 }}>{s.name || '—'}</td>
                    <td style={{ padding: '9px 14px', color: '#64748b', fontFamily: 'JetBrains Mono, monospace' }}>
                      <span style={{ backgroundColor: '#f1f5f9', padding: '2px 6px', borderRadius: '4px', fontSize: '0.74rem' }}>
                        {s.topology_id}
                      </span>
                    </td>
                    <td style={{ padding: '9px 14px', color: '#475569' }}>{s.street_name || '—'}</td>
                    <td style={{ padding: '9px 14px', color: '#475569', fontWeight: 600 }}>{s.approach_count}</td>
                    <td style={{ padding: '9px 14px', color: '#475569', fontWeight: 600 }}>{s.phase_count}</td>
                    <td style={{ padding: '9px 14px' }}>
                      <Link
                        to={`/intersections/${s.node_id}`}
                        style={{ 
                          display: 'inline-flex', alignItems: 'center', gap: '4px', 
                          color: '#0284c7', backgroundColor: '#e0f2fe', padding: '3px 8px', 
                          borderRadius: '5px', fontWeight: 700, textDecoration: 'none', fontSize: '0.74rem' 
                        }}
                      >
                        {t.viewLink} <ExternalLink size={12} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0', flexWrap: 'wrap', gap: '8px' }}>
            <span style={{ fontSize: '0.76rem', color: '#64748b' }}>
              {t.pageInfo(currentPage, totalPages, filtered.length)}
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                style={{
                  display: 'flex', alignItems: 'center', gap: '4px',
                  padding: '4px 10px', fontSize: '0.76rem', fontWeight: 700,
                  borderRadius: '6px', border: '1px solid #cbd5e1',
                  backgroundColor: currentPage <= 1 ? '#f1f5f9' : '#ffffff',
                  color: currentPage <= 1 ? '#94a3b8' : '#334155',
                  cursor: currentPage <= 1 ? 'not-allowed' : 'pointer'
                }}
              >
                <ChevronLeft size={14} /> {t.prev}
              </button>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                style={{
                  display: 'flex', alignItems: 'center', gap: '4px',
                  padding: '4px 10px', fontSize: '0.76rem', fontWeight: 700,
                  borderRadius: '6px', border: '1px solid #cbd5e1',
                  backgroundColor: currentPage >= totalPages ? '#f1f5f9' : '#ffffff',
                  color: currentPage >= totalPages ? '#94a3b8' : '#334155',
                  cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer'
                }}
              >
                {t.next} <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ marginTop: '14px', padding: '10px 14px', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '7px', fontSize: '0.74rem', color: '#64748b' }}>
        ℹ️ {t.schemaNotice}
      </div>
    </div>
  );
};

export default DeviceManagement;
