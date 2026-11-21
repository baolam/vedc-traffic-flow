import React, { useState, useEffect, useMemo } from 'react';
import { Database, Search } from 'lucide-react';

/**
 * Cross-scenario station registry: every node/station across every scenario in
 * contracts/topology/, read from the read-only materialized cache the API rebuilds from
 * contracts/ at startup (GET /api/v1/stations). Purely a reference listing -- unlike
 * NetworkOverview/IntersectionDetail this isn't scoped to whichever scenario is currently
 * active, so rows intentionally don't link into per-node operations pages.
 */
const Stations = () => {
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState('');
  const [scenarioFilter, setScenarioFilter] = useState('');

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

  const grouped = useMemo(() => {
    const groups = {};
    filtered.forEach((s) => {
      if (!groups[s.topology_id]) groups[s.topology_id] = [];
      groups[s.topology_id].push(s);
    });
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  return (
    <div className="page-container" style={{ padding: '24px' }}>
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{
          fontSize: '1.4rem', fontWeight: 800, margin: '0 0 4px 0', color: '#0f172a',
          display: 'flex', alignItems: 'center', gap: '8px'
        }}>
          <Database size={22} color="#0284c7" /> Station Registry
        </h2>
        <p style={{ color: '#64748b', margin: 0, fontSize: '0.84rem' }}>
          Every station across every scenario in <code style={{ color: '#0284c7', backgroundColor: '#e0f2fe', padding: '2px 6px', borderRadius: '4px' }}>contracts/topology/</code>, flattened into one table from a cache rebuilt at API startup.
        </p>
      </div>

      <div style={{ display: 'flex', gap: '10px', marginBottom: '18px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0', borderRadius: '6px', padding: '6px 10px', minWidth: '220px'
        }}>
          <Search size={13} color="#94a3b8" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by id, name, street..."
            style={{ border: 'none', outline: 'none', backgroundColor: 'transparent', fontSize: '0.8rem', width: '100%' }}
          />
        </div>
        <select
          value={scenarioFilter}
          onChange={(e) => setScenarioFilter(e.target.value)}
          style={{
            fontSize: '0.8rem', padding: '6px 10px', borderRadius: '6px',
            border: '1px solid #e2e8f0', backgroundColor: '#ffffff', color: '#334155'
          }}
        >
          <option value="">All scenarios ({scenarioIds.length})</option>
          {scenarioIds.map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
        <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600 }}>
          {filtered.length} / {stations.length} stations
        </span>
      </div>

      {loading && <div className="card">Loading station registry...</div>}
      {!loading && error && <div className="card">Could not load the station registry from the API.</div>}
      {!loading && !error && grouped.length === 0 && (
        <div className="card" style={{ textAlign: 'center', color: '#64748b' }}>
          No station matches "{query}".
        </div>
      )}

      {grouped.map(([topologyId, rows]) => (
        <div key={topologyId} className="card" style={{ marginBottom: '16px', padding: 0, overflow: 'hidden' }}>
          <div style={{
            padding: '10px 16px', borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8fafc',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
          }}>
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 800, fontSize: '0.86rem', color: '#0f172a' }}>
              {topologyId}
            </span>
            <span style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 700 }}>
              {rows.length} station{rows.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: '#94a3b8', textTransform: 'uppercase', fontSize: '0.66rem' }}>
                  <th style={{ padding: '8px 16px' }}>Node ID</th>
                  <th style={{ padding: '8px 16px' }}>Name</th>
                  <th style={{ padding: '8px 16px' }}>Street</th>
                  <th style={{ padding: '8px 16px' }}>Lat / Lng</th>
                  <th style={{ padding: '8px 16px' }}>Type</th>
                  <th style={{ padding: '8px 16px' }}>Approaches</th>
                  <th style={{ padding: '8px 16px' }}>Phases</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.node_id} style={{ borderTop: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '7px 16px', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: '#0f172a' }}>
                      {s.node_id}
                    </td>
                    <td style={{ padding: '7px 16px', color: '#334155' }}>{s.name || '—'}</td>
                    <td style={{ padding: '7px 16px', color: '#64748b' }}>{s.street_name || '—'}</td>
                    <td style={{ padding: '7px 16px', color: '#64748b', fontFamily: 'JetBrains Mono, monospace' }}>
                      {s.lat != null && s.lng != null ? `${s.lat.toFixed(5)}, ${s.lng.toFixed(5)}` : '—'}
                    </td>
                    <td style={{ padding: '7px 16px', color: '#64748b' }}>{s.type || '—'}</td>
                    <td style={{ padding: '7px 16px', color: '#64748b' }}>{s.approach_count}</td>
                    <td style={{ padding: '7px 16px', color: '#64748b' }}>{s.phase_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
};

export default Stations;
