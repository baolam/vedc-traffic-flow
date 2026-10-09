import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, ZoomIn, Info } from 'lucide-react';

const TopologyMap = ({ nodesData = {}, topology = null, onSelectNode }) => {
  const navigate = useNavigate();
  const [showEdges, setShowEdges] = useState(true);
  const [hoveredNode, setHoveredNode] = useState(null);

  // Extract raw nodes and edges from topology prop or nodesData keys
  const rawNodes = useMemo(() => {
    if (topology?.nodes?.length) {
      return topology.nodes.map(n => typeof n === 'string' ? { node_id: n } : n);
    }
    const dataKeys = Object.keys(nodesData);
    if (dataKeys.length) {
      return dataKeys.map(id => ({ node_id: id }));
    }
    return [{ node_id: 'J1' }, { node_id: 'J2' }, { node_id: 'J3' }, { node_id: 'J4' }];
  }, [topology, nodesData]);

  const rawEdges = useMemo(() => {
    if (topology?.edges?.length) {
      return topology.edges;
    }
    return [
      { source: 'J1', target: 'J2' },
      { source: 'J1', target: 'J3' },
      { source: 'J2', target: 'J4' },
      { source: 'J3', target: 'J4' }
    ];
  }, [topology]);

  // Calculate dynamic positions for all nodes
  const nodePositions = useMemo(() => {
    const posMap = {};
    const total = rawNodes.length;

    // 1. Standard positions for default 4-node topology J1-J4
    if (total === 4 && rawNodes.every(n => ['J1', 'J2', 'J3', 'J4'].includes(n.node_id))) {
      return {
        J1: { x: 200, y: 140, name: "Intersection 1 (NW)" },
        J2: { x: 520, y: 140, name: "Intersection 2 (NE)" },
        J3: { x: 200, y: 360, name: "Intersection 3 (SW)" },
        J4: { x: 520, y: 360, name: "Intersection 4 (SE)" }
      };
    }

    // 2. Smart Layout for grid4x4 (32 nodes: 4x4 core + 16 boundary nodes)
    const isGrid4x4 = rawNodes.some(n => n.node_id === 'A0') && rawNodes.some(n => n.node_id === 'D3');
    if (isGrid4x4) {
      const gridMap = {
        top0: { col: 1, row: 0 }, top1: { col: 2, row: 0 }, top2: { col: 3, row: 0 }, top3: { col: 4, row: 0 },
        left0: { col: 0, row: 1 }, left1: { col: 0, row: 2 }, left2: { col: 0, row: 3 }, left3: { col: 0, row: 4 },
        A0: { col: 1, row: 1 }, A1: { col: 2, row: 1 }, A2: { col: 3, row: 1 }, A3: { col: 4, row: 1 },
        B0: { col: 1, row: 2 }, B1: { col: 2, row: 2 }, B2: { col: 3, row: 2 }, B3: { col: 4, row: 2 },
        C0: { col: 1, row: 3 }, C1: { col: 2, row: 3 }, C2: { col: 3, row: 3 }, C3: { col: 4, row: 3 },
        D0: { col: 1, row: 4 }, D1: { col: 2, row: 4 }, D2: { col: 3, row: 4 }, D3: { col: 4, row: 4 },
        right0: { col: 5, row: 1 }, right1: { col: 5, row: 2 }, right2: { col: 5, row: 3 }, right3: { col: 5, row: 4 },
        bottom0: { col: 1, row: 5 }, bottom1: { col: 2, row: 5 }, bottom2: { col: 3, row: 5 }, bottom3: { col: 4, row: 5 },
      };

      const startX = 65;
      const startY = 48;
      const stepX = 115;
      const stepY = 80;

      rawNodes.forEach(n => {
        const g = gridMap[n.node_id];
        if (g) {
          posMap[n.node_id] = {
            x: startX + g.col * stepX,
            y: startY + g.row * stepY,
            name: n.name || n.node_id
          };
        }
      });

      if (Object.keys(posMap).length === total) {
        return posMap;
      }
    }

    // 3. Geographic lat/lng mapping if available
    const hasLatLng = rawNodes.every(n => n.lat != null && n.lng != null);
    if (hasLatLng && total > 0) {
      const lats = rawNodes.map(n => n.lat);
      const lngs = rawNodes.map(n => n.lng);
      const minLat = Math.min(...lats), maxLat = Math.max(...lats);
      const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
      const latSpan = (maxLat - minLat) || 1;
      const lngSpan = (maxLng - minLng) || 1;

      rawNodes.forEach(n => {
        const x = 70 + ((n.lng - minLng) / lngSpan) * 580;
        const y = 430 - ((n.lat - minLat) / latSpan) * 360;
        posMap[n.node_id] = { x: Math.round(x), y: Math.round(y), name: n.name || n.node_id };
      });
      return posMap;
    }

    // 4. Automatic Responsive Grid Layout Algorithm
    const aspect = 720 / 480;
    const cols = Math.ceil(Math.sqrt(total * aspect));
    const rows = Math.ceil(total / cols);
    const marginX = total > 16 ? 50 : 90;
    const marginY = total > 16 ? 45 : 75;
    const stepX = cols > 1 ? (720 - 2 * marginX) / (cols - 1) : 0;
    const stepY = rows > 1 ? (480 - 2 * marginY) / (rows - 1) : 0;

    rawNodes.forEach((n, idx) => {
      const r = Math.floor(idx / cols);
      const c = idx % cols;
      const x = cols === 1 ? 360 : Math.round(marginX + c * stepX);
      const y = rows === 1 ? 240 : Math.round(marginY + r * stepY);
      posMap[n.node_id] = { x, y, name: n.name || n.node_id };
    });

    return posMap;
  }, [rawNodes]);

  const edgesToDraw = useMemo(() => {
    const list = [];
    rawEdges.forEach(e => {
      const src = e.source || e.from || e.from_node;
      const tgt = e.target || e.to || e.to_node;
      if (src && tgt && nodePositions[src] && nodePositions[tgt] && src !== tgt) {
        list.push({ src, tgt, label: e.edge_id || `${src}->${tgt}` });
      }
    });
    return list.slice(0, 80);
  }, [rawEdges, nodePositions]);

  // Dynamic node sizing based on total count
  const totalCount = rawNodes.length;
  const nodeRadius = totalCount > 40 ? 14 : totalCount > 20 ? 17 : totalCount > 8 ? 22 : 28;
  const outerRadius = totalCount > 40 ? 18 : totalCount > 20 ? 22 : totalCount > 8 ? 29 : 37;

  const formatNodeLabel = (id) => {
    if (!id) return '';
    const str = String(id);
    if (str.length <= 5) return str;
    return `..${str.slice(-4)}`;
  };

  const getFontSize = (text) => {
    const len = formatNodeLabel(text).length;
    if (totalCount > 40) return "6.5";
    if (totalCount > 20) return len > 5 ? "7.5" : "8.5";
    if (totalCount > 8) return len > 5 ? "9" : "10.5";
    return len > 5 ? "10" : "13";
  };

  return (
    <div style={{
      position: 'relative',
      width: '100%',
      backgroundColor: '#f8fafc',
      borderRadius: '12px',
      border: '1px solid #cbd5e1',
      overflow: 'hidden',
      boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.02)'
    }}>
      {/* Top Toolbar Controls */}
      <div style={{
        padding: '10px 16px',
        backgroundColor: '#ffffff',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.82rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontWeight: 700, color: '#0f172a' }}>
            Topology Graph Twin: <strong style={{ color: '#0284c7' }}>{totalCount} Nodes</strong>
          </span>
          <span style={{ color: '#64748b' }}>
            Edges: <strong>{edgesToDraw.length} Connections</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={() => setShowEdges(!showEdges)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: showEdges ? '#e0f2fe' : '#f1f5f9',
              color: showEdges ? '#0284c7' : '#64748b',
              border: '1px solid',
              borderColor: showEdges ? '#93c5fd' : '#cbd5e1',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {showEdges ? <Eye size={14} /> : <EyeOff size={14} />}
            {showEdges ? 'Hide Edges' : 'Show Edges'}
          </button>
        </div>
      </div>

      {/* Main SVG Canvas */}
      <div style={{ position: 'relative', width: '100%', height: '480px' }}>
        <svg width="100%" height="100%" viewBox="0 0 720 480" preserveAspectRatio="xMidYMid meet">
          <defs>
            {/* Soft subtle grid background pattern */}
            <pattern id="grid-pattern" width="30" height="30" patternUnits="userSpaceOnUse">
              <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#e2e8f0" strokeWidth="0.8" />
            </pattern>

            {/* Directional Edge Arrowhead */}
            <marker id="arrow" viewBox="0 0 10 10" refX={nodeRadius + 5} refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#0284c7" opacity="0.8" />
            </marker>
          </defs>

          {/* Background Grid */}
          <rect width="100%" height="100%" fill="url(#grid-pattern)" opacity="0.6" />

          {/* Draw Edges */}
          {showEdges && edgesToDraw.map((edge, idx) => {
            const p1 = nodePositions[edge.src];
            const p2 = nodePositions[edge.tgt];
            const isHovered = hoveredNode === edge.src || hoveredNode === edge.tgt;

            return (
              <g key={idx}>
                {/* Background edge track line */}
                <line
                  x1={p1.x}
                  y1={p1.y}
                  x2={p2.x}
                  y2={p2.y}
                  stroke={isHovered ? "#38bdf8" : "#cbd5e1"}
                  strokeWidth={isHovered ? "2.5" : totalCount > 30 ? "1" : "1.5"}
                  opacity={isHovered ? 0.9 : totalCount > 30 ? 0.3 : 0.45}
                />
                {/* Directional traffic flow line with arrowhead */}
                <line
                  x1={p1.x}
                  y1={p1.y}
                  x2={p2.x}
                  y2={p2.y}
                  stroke={isHovered ? "#0284c7" : "#0284c7"}
                  strokeWidth={isHovered ? "2" : totalCount > 30 ? "1" : "1.2"}
                  strokeDasharray={totalCount > 20 ? "none" : "4,2"}
                  opacity={isHovered ? 1.0 : totalCount > 30 ? 0.45 : 0.65}
                  markerEnd="url(#arrow)"
                />
              </g>
            );
          })}

          {/* Draw Nodes */}
          {Object.entries(nodePositions).map(([nodeId, pos]) => {
            const data = nodesData[nodeId] || { current_phase_id: `${nodeId}_PHASE_1`, total_queue: 0, speed: 13.9, status: 'WAITING_FOR_TELEMETRY' };
            const phaseStr = String(data.current_phase_id || "").toUpperCase();
            const isNS = phaseStr.includes("NS") || phaseStr.includes("1") || phaseStr.includes("GREEN");
            const totalQueue = data.total_queue || 0;

            const isHovered = hoveredNode === nodeId;
            const badgeColor = totalQueue >= 13 ? "#dc2626" : totalQueue >= 6 ? "#ca8a04" : "#16a34a";
            const fontSz = getFontSize(nodeId);
            const labelText = formatNodeLabel(nodeId);

            // Badge coordinates offset neatly on top-right border
            const badgeX = pos.x + nodeRadius * 0.75;
            const badgeY = pos.y - nodeRadius * 0.75;
            const badgeR = totalCount > 30 ? 7 : totalCount > 20 ? 8.5 : 10;

            return (
              <g
                key={nodeId}
                style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
                onMouseEnter={() => setHoveredNode(nodeId)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => {
                  if (onSelectNode) onSelectNode(nodeId);
                  navigate(`/intersections/${nodeId}`);
                }}
              >
                {/* Outer Active Phase Ring */}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={isHovered ? outerRadius + 3 : outerRadius}
                  fill={isNS ? "rgba(22, 163, 74, 0.12)" : "rgba(2, 132, 199, 0.12)"}
                  stroke={isNS ? "#16a34a" : "#0284c7"}
                  strokeWidth={isHovered ? "2.5" : "1.5"}
                />

                {/* Node Core Circle */}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={isHovered ? nodeRadius + 2 : nodeRadius}
                  fill="#ffffff"
                  stroke={isHovered ? "#0284c7" : "#cbd5e1"}
                  strokeWidth="1.8"
                  filter={isHovered ? "drop-shadow(0 2px 4px rgba(2, 132, 199, 0.3))" : "none"}
                />

                {/* Node Label Text */}
                <text
                  x={pos.x}
                  y={pos.y}
                  fill="#0f172a"
                  fontSize={fontSz}
                  fontWeight="700"
                  textAnchor="middle"
                  dominantBaseline="central"
                >
                  {labelText}
                </text>

                {/* Queue Severity Badge */}
                <circle
                  cx={badgeX}
                  cy={badgeY}
                  r={badgeR}
                  fill={badgeColor}
                  stroke="#ffffff"
                  strokeWidth="1.2"
                />
                <text
                  x={badgeX}
                  y={badgeY}
                  fill="#ffffff"
                  fontSize={totalCount > 30 ? "6.5" : totalCount > 20 ? "7.5" : "8.5"}
                  fontWeight="800"
                  textAnchor="middle"
                  dominantBaseline="central"
                >
                  {totalQueue}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay Card */}
        {hoveredNode && nodePositions[hoveredNode] && (
          <div style={{
            position: 'absolute',
            left: Math.min(Math.max(nodePositions[hoveredNode].x - 95, 10), 510),
            top: nodePositions[hoveredNode].y > 240 ? nodePositions[hoveredNode].y - 100 : nodePositions[hoveredNode].y + 30,
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            borderRadius: '8px',
            padding: '10px 14px',
            fontSize: '0.8rem',
            boxShadow: '0 4px 14px rgba(0, 0, 0, 0.3)',
            pointerEvents: 'none',
            zIndex: 10,
            minWidth: '200px',
            border: '1px solid #334155'
          }}>
            <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#38bdf8', marginBottom: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Station {hoveredNode}</span>
              <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '4px', backgroundColor: '#1e293b', color: '#94a3b8' }}>
                {nodesData[hoveredNode]?.source_type || 'SYSTEM'}
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '3px' }}>
              <span>Queue Length: <strong style={{ color: '#f8fafc' }}>{nodesData[hoveredNode]?.total_queue || 0} veh</strong></span>
              <span>Avg Speed: <strong style={{ color: '#f8fafc' }}>{nodesData[hoveredNode]?.speed != null ? nodesData[hoveredNode].speed : 13.9} m/s</strong></span>
              <span>Traffic Flow: <strong style={{ color: '#f8fafc' }}>{nodesData[hoveredNode]?.flow || 0.0} veh/s</strong></span>
              <span>Occupancy: <strong style={{ color: '#f8fafc' }}>{nodesData[hoveredNode]?.occupancy || 0.0}%</strong></span>
              <span>Active Phase: <strong style={{ color: '#4ade80' }}>{nodesData[hoveredNode]?.current_phase_id || `${hoveredNode}_PHASE_1`}</strong></span>
              <span style={{ color: '#38bdf8', marginTop: '2px', fontSize: '0.7rem' }}>👉 Click station for detailed analytics</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer Legend Bar */}
      <div style={{
        padding: '8px 16px',
        backgroundColor: '#ffffff',
        borderTop: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.75rem',
        color: '#64748b'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#16a34a' }}></span> Low Queue (&lt;6)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ca8a04' }}></span> Moderate (6-12)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#dc2626' }}></span> Congested (&gt;12)
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '12px', height: '2px', backgroundColor: '#16a34a' }}></span> Phase 1 Green
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '12px', height: '2px', backgroundColor: '#0284c7' }}></span> Phase 2 Green
          </span>
        </div>
      </div>
    </div>
  );
};

export default TopologyMap;
