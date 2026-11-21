import React, { useState, useEffect } from 'react';
import { NavLink, useParams } from 'react-router-dom';
import { Search } from 'lucide-react';
import { getStatusToken } from '../utils/statusTokens';

// Past this many stations, rendering every chip in one unbounded horizontal row stops being a
// "quick switcher" and starts being an unscrollable wall of chips -- show a search box instead of
// (or in addition to) scrolling, and cap how many chips ever hit the DOM at once.
const SEARCH_THRESHOLD = 8;
const MAX_VISIBLE_CHIPS = 60;

/**
 * Sticky station quick-switcher for station-scoped pages (Station Details, Raspberry Pi Demo).
 * Replaces the old "Active Stations" chip list that used to live at the bottom of the sidebar:
 * keeping it here, right above the page content, lets an operator jump between junctions without
 * losing the sidebar's own scroll position or hunting for it below the nav links.
 *
 * `activeNodeId` prop is for pages like RaspberryPiDemo whose route has no `:nodeId` param (it's
 * pinned to a fixed demo node) -- falls back to the route param for pages like IntersectionDetail
 * that are actually routed per-node.
 */
const StationContextBar = ({ activeNodeId: activeNodeIdProp }) => {
  const { nodeId: routeNodeId } = useParams();
  const activeNodeId = activeNodeIdProp ?? routeNodeId;
  const [nodes, setNodes] = useState([]);
  const [query, setQuery] = useState('');
  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    let cancelled = false;
    const fetchState = () => {
      fetch(`${apiBase}/api/v1/network/state`)
        .then((res) => res.json())
        .then((data) => {
          if (!cancelled && Array.isArray(data?.nodes)) setNodes(data.nodes);
        })
        .catch(() => {});
    };
    fetchState();
    const interval = setInterval(fetchState, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [apiBase]);

  if (!nodes.length) return null;

  const q = query.trim().toLowerCase();
  const filtered = q ? nodes.filter((n) => n.node_id.toLowerCase().includes(q)) : nodes;
  const visible = filtered.slice(0, MAX_VISIBLE_CHIPS);
  const hiddenCount = filtered.length - visible.length;

  return (
    <div style={{
      position: 'sticky',
      top: 0,
      zIndex: 15,
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '8px 24px',
      backgroundColor: '#ffffff',
      borderBottom: '1px solid #e2e8f0'
    }}>
      <span style={{
        fontSize: '0.68rem', textTransform: 'uppercase', color: '#94a3b8',
        fontWeight: 800, letterSpacing: '0.5px', flexShrink: 0
      }}>
        Stations ({nodes.length})
      </span>

      {nodes.length > SEARCH_THRESHOLD && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '5px', flexShrink: 0,
          backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px',
          padding: '3px 8px', width: '140px'
        }}>
          <Search size={12} color="#94a3b8" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter ID..."
            style={{ border: 'none', outline: 'none', backgroundColor: 'transparent', fontSize: '0.74rem', width: '100%' }}
          />
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflowX: 'auto' }}>
        {visible.length === 0 && (
          <span style={{ fontSize: '0.76rem', color: '#94a3b8', flexShrink: 0 }}>No station matches "{query}".</span>
        )}
        {visible.map((n) => {
          const isActive = n.node_id === activeNodeId;
          const token = getStatusToken(n.status);
          return (
            <NavLink
              key={n.node_id}
              to={`/intersections/${n.node_id}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: '6px',
                textDecoration: 'none',
                fontSize: '0.78rem',
                fontWeight: 700,
                flexShrink: 0,
                fontFamily: 'JetBrains Mono, monospace',
                backgroundColor: isActive ? '#0284c7' : '#f8fafc',
                color: isActive ? '#ffffff' : '#334155',
                border: `1px solid ${isActive ? '#0284c7' : '#e2e8f0'}`
              }}
            >
              <span style={{
                width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                backgroundColor: isActive ? '#ffffff' : token.dot
              }} />
              {n.node_id}
            </NavLink>
          );
        })}
        {hiddenCount > 0 && (
          <span style={{ fontSize: '0.74rem', color: '#94a3b8', flexShrink: 0, whiteSpace: 'nowrap' }}>
            +{hiddenCount} more — refine filter
          </span>
        )}
      </div>
    </div>
  );
};

export default StationContextBar;
