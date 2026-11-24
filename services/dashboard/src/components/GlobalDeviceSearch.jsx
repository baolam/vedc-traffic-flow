import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { useActiveScenario, MAP_ONLY_SCENARIOS } from '../hooks/useActiveScenario';
import { useLanguage } from '../hooks/useLanguage';

/**
 * Header-level "jump to any device" search. Independent of which page is currently open --
 * an operator on the Benchmark page who needs to check J17 shouldn't have to navigate to
 * Overview first to find it. Scoped to the active topology's node list (not the geo camera
 * inventory: MAP_ONLY_SCENARIOS have no per-node operations page to jump to).
 */
const GlobalDeviceSearch = () => {
  const navigate = useNavigate();
  const [activeScenarioId] = useActiveScenario();
  const [lang] = useLanguage();
  const isVi = lang === 'vi';
  const [nodes, setNodes] = useState([]);
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const isMapOnly = MAP_ONLY_SCENARIOS.includes(activeScenarioId);

  useEffect(() => {
    if (isMapOnly) {
      setNodes([]);
      return;
    }
    let cancelled = false;
    fetch(`${apiBase}/api/v1/topologies/${activeScenarioId}`)
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled && Array.isArray(data?.nodes)) {
          setNodes(data.nodes.map((n) => ({ id: n.node_id, name: n.name || n.street_name || '' })));
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [apiBase, activeScenarioId, isMapOnly]);

  useEffect(() => {
    const onClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const q = query.trim().toLowerCase();
  const matches = q
    ? nodes.filter((n) => n.id.toLowerCase().includes(q) || n.name.toLowerCase().includes(q)).slice(0, 8)
    : [];

  const goTo = (nodeId) => {
    navigate(`/intersections/${nodeId}`);
    setQuery('');
    setIsOpen(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && matches.length > 0) {
      goTo(matches[0].id);
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  if (isMapOnly) return null; // geo camera inventories have no per-node page to search into

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '6px',
        backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px',
        padding: '5px 10px', minWidth: '180px'
      }}>
        <Search size={13} color="#94a3b8" />
        <input
          value={query}
          onChange={(e) => { setQuery(e.target.value); setIsOpen(true); }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={isVi ? "Nhảy tới ID nút..." : "Jump to node ID..."}
          style={{ border: 'none', outline: 'none', backgroundColor: 'transparent', fontSize: '0.78rem', width: '100%', color: '#0f172a' }}
        />
        {query && (
          <button
            onClick={() => { setQuery(''); setIsOpen(false); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: '#94a3b8' }}
            title="Clear"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {isOpen && q && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0,
          backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '8px',
          boxShadow: '0 12px 28px rgba(15, 23, 42, 0.15)', zIndex: 50, overflow: 'hidden'
        }}>
          {matches.length === 0 ? (
            <div style={{ padding: '12px 14px', fontSize: '0.78rem', color: '#94a3b8' }}>
              No node matches "{query}" in {activeScenarioId}.
            </div>
          ) : (
            matches.map((n) => (
              <button
                key={n.id}
                onClick={() => goTo(n.id)}
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'flex-start', width: '100%',
                  textAlign: 'left', padding: '8px 14px', border: 'none', borderBottom: '1px solid #f1f5f9',
                  backgroundColor: '#ffffff', cursor: 'pointer'
                }}
                onMouseDown={(e) => e.preventDefault()}
              >
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#0f172a', fontFamily: 'JetBrains Mono, monospace' }}>
                  {n.id}
                </span>
                {n.name && (
                  <span style={{ fontSize: '0.72rem', color: '#64748b' }}>{n.name}</span>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default GlobalDeviceSearch;
