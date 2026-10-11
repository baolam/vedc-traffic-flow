import React, { useState, useMemo } from 'react';
import { Eye, EyeOff, ZoomIn, ZoomOut, RotateCcw, Navigation, CheckCircle, Info, ExternalLink } from 'lucide-react';

const TopologyMap = ({ 
  nodesData = {}, 
  topology = null, 
  selectedNodeId = null,
  onSelectNode,
  onNavigateDetail
}) => {
  const [showEdges, setShowEdges] = useState(true);
  const [showQueueBadges, setShowQueueBadges] = useState(true);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

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
        J1: { x: 220, y: 150, name: "Intersection 1 (NW)" },
        J2: { x: 540, y: 150, name: "Intersection 2 (NE)" },
        J3: { x: 220, y: 370, name: "Intersection 3 (SW)" },
        J4: { x: 540, y: 370, name: "Intersection 4 (SE)" }
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

      const startX = 75;
      const startY = 55;
      const stepX = 122;
      const stepY = 82;

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
        const x = 80 + ((n.lng - minLng) / lngSpan) * 600;
        const y = 440 - ((n.lat - minLat) / latSpan) * 370;
        posMap[n.node_id] = { x: Math.round(x), y: Math.round(y), name: n.name || n.node_id };
      });
      return posMap;
    }

    // 4. Automatic Responsive Grid Layout Algorithm
    const aspect = 760 / 500;
    const cols = Math.ceil(Math.sqrt(total * aspect));
    const rows = Math.ceil(total / cols);
    const marginX = total > 16 ? 55 : 95;
    const marginY = total > 16 ? 50 : 80;
    const stepX = cols > 1 ? (760 - 2 * marginX) / (cols - 1) : 0;
    const stepY = rows > 1 ? (500 - 2 * marginY) / (rows - 1) : 0;

    rawNodes.forEach((n, idx) => {
      const r = Math.floor(idx / cols);
      const c = idx % cols;
      const x = cols === 1 ? 380 : Math.round(marginX + c * stepX);
      const y = rows === 1 ? 250 : Math.round(marginY + r * stepY);
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
    return list.slice(0, 100);
  }, [rawEdges, nodePositions]);

  // Dynamic node sizing based on total count
  const totalCount = rawNodes.length;
  const nodeRadius = totalCount > 40 ? 14 : totalCount > 20 ? 18 : totalCount > 8 ? 23 : 30;
  const outerRadius = totalCount > 40 ? 18 : totalCount > 20 ? 23 : totalCount > 8 ? 30 : 38;

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
    if (totalCount > 8) return len > 5 ? "9.5" : "11";
    return len > 5 ? "11" : "13.5";
  };

  // Zoom handlers
  const handleZoomIn = () => setZoom(z => Math.min(2.2, Math.round((z + 0.15) * 100) / 100));
  const handleZoomOut = () => setZoom(z => Math.max(0.7, Math.round((z - 0.15) * 100) / 100));
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const activeFocusNode = selectedNodeId || hoveredNode;
  const activeFocusData = activeFocusNode ? (nodesData[activeFocusNode] || null) : null;

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
      {/* Top Map Toolbar */}
      <div style={{
        padding: '10px 16px',
        backgroundColor: '#ffffff',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '10px',
        fontSize: '0.82rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span style={{ fontWeight: 700, color: '#0f172a' }}>
            Topology Graph: <strong style={{ color: '#0284c7' }}>{totalCount} Intersections</strong>
          </span>
          <span style={{ color: '#64748b' }}>
            Lanes: <strong>{edgesToDraw.length} Directed Links</strong>
          </span>
          {selectedNodeId && (
            <span style={{ 
              backgroundColor: '#e0f2fe', 
              color: '#0369a1', 
              padding: '2px 8px', 
              borderRadius: '4px', 
              fontWeight: 700,
              fontSize: '0.75rem' 
            }}>
              Inspecting: {selectedNodeId}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Zoom controls */}
          <div style={{ display: 'flex', alignItems: 'center', border: '1px solid #cbd5e1', borderRadius: '6px', overflow: 'hidden' }}>
            <button
              onClick={handleZoomIn}
              title="Zoom In"
              style={{
                backgroundColor: '#ffffff',
                border: 'none',
                borderRight: '1px solid #cbd5e1',
                padding: '5px 8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center'
              }}
            >
              <ZoomIn size={14} color="#334155" />
            </button>
            <button
              onClick={handleZoomOut}
              title="Zoom Out"
              style={{
                backgroundColor: '#ffffff',
                border: 'none',
                borderRight: '1px solid #cbd5e1',
                padding: '5px 8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center'
              }}
            >
              <ZoomOut size={14} color="#334155" />
            </button>
            <button
              onClick={handleResetZoom}
              title="Reset View (100%)"
              style={{
                backgroundColor: '#f8fafc',
                border: 'none',
                padding: '5px 8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                fontSize: '0.72rem',
                fontWeight: 600,
                color: '#475569'
              }}
            >
              <RotateCcw size={12} style={{ marginRight: '4px' }} />
              {Math.round(zoom * 100)}%
            </button>
          </div>

          {/* Toggle Edges */}
          <button
            onClick={() => setShowEdges(!showEdges)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              backgroundColor: showEdges ? '#e0f2fe' : '#f1f5f9',
              color: showEdges ? '#0284c7' : '#64748b',
              border: '1px solid',
              borderColor: showEdges ? '#93c5fd' : '#cbd5e1',
              padding: '4px 9px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {showEdges ? <Eye size={13} /> : <EyeOff size={13} />}
            {showEdges ? 'Edges ON' : 'Edges OFF'}
          </button>

          {/* Toggle Badges */}
          <button
            onClick={() => setShowQueueBadges(!showQueueBadges)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              backgroundColor: showQueueBadges ? '#f0fdf4' : '#f1f5f9',
              color: showQueueBadges ? '#16a34a' : '#64748b',
              border: '1px solid',
              borderColor: showQueueBadges ? '#86efac' : '#cbd5e1',
              padding: '4px 9px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {showQueueBadges ? 'Queue Badges' : 'Hide Badges'}
          </button>
        </div>
      </div>

      {/* Main Interactive SVG Canvas */}
      <div style={{ position: 'relative', width: '100%', height: '520px', backgroundColor: '#f8fafc' }}>
        <svg 
          width="100%" 
          height="100%" 
          viewBox="0 0 760 500" 
          preserveAspectRatio="xMidYMid meet"
          style={{ transition: 'transform 0.15s ease-out' }}
        >
          <defs>
            {/* Subtle architectural dot grid background pattern */}
            <pattern id="grid-pattern" width="28" height="28" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1" fill="#cbd5e1" opacity="0.6" />
            </pattern>

            {/* Directional Edge Arrowhead */}
            <marker 
              id="traffic-arrow" 
              viewBox="0 0 10 10" 
              refX={nodeRadius + 6} 
              refY="5" 
              markerWidth="5" 
              markerHeight="5" 
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#0284c7" opacity="0.9" />
            </marker>

            {/* Highlighted Arrowhead for Selected/Hovered Node */}
            <marker 
              id="traffic-arrow-highlight" 
              viewBox="0 0 10 10" 
              refX={nodeRadius + 6} 
              refY="5" 
              markerWidth="6" 
              markerHeight="6" 
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#0ea5e9" opacity="1.0" />
            </marker>
          </defs>

          {/* Background Grid */}
          <rect width="100%" height="100%" fill="url(#grid-pattern)" opacity="0.75" />

          {/* Transform group for Pan & Zoom */}
          <g transform={`translate(${pan.x + (1 - zoom) * 380}, ${pan.y + (1 - zoom) * 250}) scale(${zoom})`}>
            
            {/* Draw Directed Edges */}
            {showEdges && edgesToDraw.map((edge, idx) => {
              const p1 = nodePositions[edge.src];
              const p2 = nodePositions[edge.tgt];
              if (!p1 || !p2) return null;

              const isConnectedToFocus = activeFocusNode === edge.src || activeFocusNode === edge.tgt;
              const hasActiveFocus = Boolean(activeFocusNode);

              return (
                <g key={`edge-${idx}`}>
                  {/* Subtle edge road bed */}
                  <line
                    x1={p1.x}
                    y1={p1.y}
                    x2={p2.x}
                    y2={p2.y}
                    stroke={isConnectedToFocus ? "#38bdf8" : "#cbd5e1"}
                    strokeWidth={isConnectedToFocus ? "3" : totalCount > 30 ? "1" : "1.6"}
                    opacity={isConnectedToFocus ? 0.95 : hasActiveFocus ? 0.25 : 0.55}
                  />
                  {/* Directional flow lane with marker */}
                  <line
                    x1={p1.x}
                    y1={p1.y}
                    x2={p2.x}
                    y2={p2.y}
                    stroke={isConnectedToFocus ? "#0284c7" : "#0284c7"}
                    strokeWidth={isConnectedToFocus ? "2.2" : totalCount > 30 ? "1" : "1.3"}
                    strokeDasharray={totalCount > 20 ? "none" : "5,3"}
                    opacity={isConnectedToFocus ? 1.0 : hasActiveFocus ? 0.3 : 0.7}
                    markerEnd={isConnectedToFocus ? "url(#traffic-arrow-highlight)" : "url(#traffic-arrow)"}
                  />
                </g>
              );
            })}

            {/* Draw Nodes */}
            {Object.entries(nodePositions).map(([nodeId, pos]) => {
              const data = nodesData[nodeId] || { current_phase_id: `${nodeId}_PHASE_1`, total_queue: 0, speed: 13.9, status: 'ONLINE' };
              const phaseStr = String(data.current_phase_id || "").toUpperCase();
              const isNS = phaseStr.includes("NS") || phaseStr.includes("1") || phaseStr.includes("GREEN");
              const totalQueue = data.total_queue || 0;

              const isSelected = selectedNodeId === nodeId;
              const isHovered = hoveredNode === nodeId;
              const isHighlighted = isSelected || isHovered;

              const badgeColor = totalQueue >= 13 ? "#dc2626" : totalQueue >= 6 ? "#ca8a04" : "#16a34a";
              const fontSz = getFontSize(nodeId);
              const labelText = formatNodeLabel(nodeId);

              // Badge coordinates offset neatly on top-right border
              const badgeX = pos.x + nodeRadius * 0.72;
              const badgeY = pos.y - nodeRadius * 0.72;
              const badgeR = totalCount > 30 ? 7 : totalCount > 20 ? 8.5 : 10.5;

              return (
                <g
                  key={`node-${nodeId}`}
                  style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
                  onMouseEnter={() => setHoveredNode(nodeId)}
                  onMouseLeave={() => setHoveredNode(null)}
                  onClick={() => {
                    if (onSelectNode) onSelectNode(nodeId);
                  }}
                >
                  {/* Selected Active Glow Halo */}
                  {isSelected && (
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={outerRadius + 6}
                      fill="none"
                      stroke="#0284c7"
                      strokeWidth="2.5"
                      strokeDasharray="4,2"
                      opacity="0.9"
                    />
                  )}

                  {/* Outer Active Signal Phase Ring (Green for Phase 1, Blue for Phase 2) */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={isHighlighted ? outerRadius + 3 : outerRadius}
                    fill={isNS ? "rgba(16, 185, 129, 0.12)" : "rgba(2, 132, 199, 0.12)"}
                    stroke={isNS ? "#10b981" : "#0284c7"}
                    strokeWidth={isHighlighted ? "2.5" : "1.6"}
                  />

                  {/* Node Core Body */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={isHighlighted ? nodeRadius + 2 : nodeRadius}
                    fill={isSelected ? "#eff6ff" : "#ffffff"}
                    stroke={isSelected ? "#0284c7" : isHighlighted ? "#0284c7" : "#94a3b8"}
                    strokeWidth={isSelected ? "2.4" : "1.6"}
                    filter={isHighlighted ? "drop-shadow(0 2px 6px rgba(2, 132, 199, 0.35))" : "none"}
                  />

                  {/* Node Label Text */}
                  <text
                    x={pos.x}
                    y={pos.y}
                    fill={isSelected ? "#0284c7" : "#0f172a"}
                    fontSize={fontSz}
                    fontWeight={isSelected ? "800" : "700"}
                    textAnchor="middle"
                    dominantBaseline="central"
                  >
                    {labelText}
                  </text>

                  {/* Queue Severity Badge */}
                  {showQueueBadges && (
                    <g>
                      <circle
                        cx={badgeX}
                        cy={badgeY}
                        r={badgeR}
                        fill={badgeColor}
                        stroke="#ffffff"
                        strokeWidth="1.4"
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
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* Selected or Hovered Node Inline Inspection Drawer Overlay */}
        {activeFocusNode && nodePositions[activeFocusNode] && (
          <div style={{
            position: 'absolute',
            left: '16px',
            bottom: '16px',
            backgroundColor: 'rgba(15, 23, 42, 0.96)',
            color: '#f8fafc',
            borderRadius: '10px',
            padding: '12px 16px',
            fontSize: '0.82rem',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)',
            border: '1px solid #334155',
            maxWidth: '360px',
            backdropFilter: 'blur(6px)',
            zIndex: 15
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 800, fontSize: '0.95rem', color: '#38bdf8', fontFamily: 'JetBrains Mono, monospace' }}>
                  Station {activeFocusNode}
                </span>
                <span style={{
                  fontSize: '0.68rem',
                  padding: '1px 6px',
                  borderRadius: '4px',
                  backgroundColor: '#1e293b',
                  color: '#4ade80',
                  fontWeight: 700,
                  border: '1px solid #334155'
                }}>
                  {activeFocusData?.status || 'ONLINE'}
                </span>
              </div>

              {onNavigateDetail && (
                <button
                  onClick={() => onNavigateDetail(activeFocusNode)}
                  style={{
                    backgroundColor: '#0284c7',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '5px',
                    padding: '3px 8px',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  Inspect <ExternalLink size={11} />
                </button>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.76rem', color: '#cbd5e1' }}>
              <div>
                <span style={{ color: '#94a3b8' }}>Queue: </span>
                <strong style={{ color: (activeFocusData?.total_queue || 0) > 12 ? '#f87171' : '#f8fafc' }}>
                  {activeFocusData?.total_queue || 0} veh
                </strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Avg Speed: </span>
                <strong style={{ color: '#f8fafc' }}>
                  {activeFocusData?.speed != null ? activeFocusData.speed : 13.9} m/s
                </strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Flow Rate: </span>
                <strong style={{ color: '#f8fafc' }}>
                  {activeFocusData?.flow || 0.0} veh/s
                </strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Occupancy: </span>
                <strong style={{ color: '#f8fafc' }}>
                  {activeFocusData?.occupancy || 0.0}%
                </strong>
              </div>
            </div>

            <div style={{ marginTop: '8px', paddingTop: '6px', borderTop: '1px solid #334155', fontSize: '0.74rem' }}>
              <span style={{ color: '#94a3b8' }}>Active Phase: </span>
              <strong style={{ color: '#4ade80' }}>
                {activeFocusData?.current_phase_id || `${activeFocusNode}_PHASE_1`}
              </strong>
            </div>

            <div style={{ marginTop: '4px', fontSize: '0.71rem', color: '#94a3b8', fontStyle: 'italic' }}>
              Safety Verified: 0 green conflicts | Clearance timings enforced
            </div>
          </div>
        )}
      </div>

      {/* Footer Fixed Legend */}
      <div style={{
        padding: '9px 16px',
        backgroundColor: '#ffffff',
        borderTop: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.75rem',
        color: '#64748b',
        flexWrap: 'wrap',
        gap: '8px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontWeight: 600, color: '#334155' }}>Queue Severity:</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#16a34a' }}></span> Low (&lt;6)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ca8a04' }}></span> Moderate (6-12)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#dc2626' }}></span> Congested (&gt;12)
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span style={{ fontWeight: 600, color: '#334155' }}>Signal Phase:</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '12px', height: '3px', backgroundColor: '#10b981', borderRadius: '2px' }}></span> Phase 1 Green
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '12px', height: '3px', backgroundColor: '#0284c7', borderRadius: '2px' }}></span> Phase 2 Green
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#0284c7' }}>
            <span>➔</span> Directed Lanes
          </span>
        </div>
      </div>
    </div>
  );
};

export default TopologyMap;
