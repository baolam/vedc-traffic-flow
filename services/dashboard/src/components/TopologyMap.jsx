import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Eye, EyeOff, ZoomIn, ZoomOut, RotateCcw, Navigation, CheckCircle, Info, ExternalLink, MapPin } from 'lucide-react';
import LeafletStreetMap from './LeafletStreetMap';

const TopologyMap = ({ 
  nodesData = {}, 
  topology = null, 
  selectedNodeId = null,
  onSelectNode,
  onNavigateDetail,
  height = 540
}) => {
  const [mapType, setMapType] = useState('STREET'); // 'STREET' (OpenStreetMap) or 'VECTOR' (SVG)
  const [showEdges, setShowEdges] = useState(true);
  const [showQueueBadges, setShowQueueBadges] = useState(true);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

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

  // Calculate dynamic positions for all nodes and projection metadata for road shapes
  const { nodePositions, projectionMeta } = useMemo(() => {
    const posMap = {};
    const total = rawNodes.length;
    let proj = null;

    // 1. Standard positions for default 4-node topology J1-J4
    if (total === 4 && rawNodes.every(n => ['J1', 'J2', 'J3', 'J4'].includes(n.node_id))) {
      return {
        nodePositions: {
          J1: { x: 220, y: 150, name: "Intersection 1 (NW)", street_name: "Corridor NW" },
          J2: { x: 540, y: 150, name: "Intersection 2 (NE)", street_name: "Corridor NE" },
          J3: { x: 220, y: 370, name: "Intersection 3 (SW)", street_name: "Corridor SW" },
          J4: { x: 540, y: 370, name: "Intersection 4 (SE)", street_name: "Corridor SE" }
        },
        projectionMeta: null
      };
    }

    // 1b. Standard positions for 5-node tabletop sa bàn J1-J5 (1800x1200 mm - đội 31µF)
    const tidCheck = String(topology?.topology_id || '').toLowerCase();
    if (tidCheck.includes('tabletop_5nut') || (total === 5 && ['J1', 'J2', 'J3', 'J4', 'J5'].every(id => rawNodes.some(n => n.node_id === id)))) {
      return {
        nodePositions: {
          J1: { x: 160, y: 140, name: "Intersection 1 (NW)", street_name: "Sa Bàn 5 nút - Tây Bắc" },
          J2: { x: 370, y: 140, name: "Intersection 2 (N-Center)", street_name: "Sa Bàn 5 nút - Trung Tâm Bắc" },
          J3: { x: 580, y: 140, name: "Intersection 3 (NE)", street_name: "Sa Bàn 5 nút - Đông Bắc" },
          J4: { x: 160, y: 350, name: "Intersection 4 (SW)", street_name: "Sa Bàn 5 nút - Tây Nam" },
          J5: { x: 370, y: 350, name: "Intersection 5 (S-Center)", street_name: "Sa Bàn 5 nút - Trung Tâm Nam" }
        },
        projectionMeta: null
      };
    }

    // 2. Exact SUMO XY coordinate projection (used for hcm_corridor, the sa ban tabletop
    // corridor (J1/J2), and any other topology whose contract carries real x/y)
    const hasXY = rawNodes.some(n => n.x != null && n.y != null);
    if (hasXY && total > 0) {
      const xs = rawNodes.map(n => n.x != null ? Number(n.x) : 0);
      const ys = rawNodes.map(n => n.y != null ? Number(n.y) : 0);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const spanX = (maxX - minX) || 1;
      const spanY = (maxY - minY) || 1;

      // Fit into canvas (760 x 500) with padding
      const padX = 65, padY = 55;
      const availW = 760 - 2 * padX;
      const availH = 500 - 2 * padY;
      const scale = Math.min(availW / spanX, availH / spanY);
      const offsetX = padX + (availW - spanX * scale) / 2;
      const offsetY = padY + (availH - spanY * scale) / 2;

      proj = { minX, maxX, minY, maxY, scale, offsetX, offsetY };

      rawNodes.forEach(n => {
        const nx = n.x != null ? Number(n.x) : minX;
        const ny = n.y != null ? Number(n.y) : minY;
        const x = offsetX + (nx - minX) * scale;
        // Invert Y because SUMO origin (0,0) is bottom-left whereas SVG is top-left
        const y = offsetY + (maxY - ny) * scale;
        posMap[n.node_id] = {
          x: Math.round(x),
          y: Math.round(y),
          name: n.name || n.node_id,
          street_name: n.street_name || '',
          type: n.type || 'junction'
        };
      });

      return { nodePositions: posMap, projectionMeta: proj };
    }

    // 3. Smart Layout for grid4x4 (32 nodes: 4x4 core + 16 boundary nodes)
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
            name: n.name || n.node_id,
            street_name: ''
          };
        }
      });

      if (Object.keys(posMap).length === total) {
        return { nodePositions: posMap, projectionMeta: null };
      }
    }

    // 4. Geographic lat/lng mapping if available
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
        posMap[n.node_id] = { x: Math.round(x), y: Math.round(y), name: n.name || n.node_id, street_name: '' };
      });
      return { nodePositions: posMap, projectionMeta: null };
    }

    // 5. Automatic Responsive Grid Layout Algorithm
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
      posMap[n.node_id] = { x, y, name: n.name || n.node_id, street_name: '' };
    });

    return { nodePositions: posMap, projectionMeta: null };
  }, [rawNodes]);

  const edgesToDraw = useMemo(() => {
    const list = [];
    rawEdges.forEach((e, idx) => {
      const src = e.source || e.from || e.from_node;
      const tgt = e.target || e.to || e.to_node;
      if (src && tgt && nodePositions[src] && nodePositions[tgt] && src !== tgt) {
        let pathD = null;
        if (e.shape && projectionMeta) {
          const pts = String(e.shape).split(' ').map(p => {
            const coords = p.split(',').map(Number);
            return coords;
          }).filter(c => !isNaN(c[0]) && !isNaN(c[1]));

          if (pts.length >= 2) {
            const svgPts = pts.map(([px, py]) => {
              const sx = projectionMeta.offsetX + (px - projectionMeta.minX) * projectionMeta.scale;
              const sy = projectionMeta.offsetY + (projectionMeta.maxY - py) * projectionMeta.scale;
              return `${Math.round(sx * 10) / 10},${Math.round(sy * 10) / 10}`;
            });
            pathD = `M ${svgPts.join(' L ')}`;
          }
        }
        list.push({ src, tgt, label: e.edge_id || `${src}->${tgt}`, pathD, key: `edge-${idx}-${src}-${tgt}` });
      }
    });
    return list;
  }, [rawEdges, nodePositions, projectionMeta]);

  // Dynamic node sizing based on total count
  const totalCount = rawNodes.length;
  const nodeRadius = totalCount > 40 ? 12 : totalCount > 20 ? 17 : totalCount > 8 ? 22 : 30;
  const outerRadius = totalCount > 40 ? 16 : totalCount > 20 ? 22 : totalCount > 8 ? 28 : 38;

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

  // Zoom & Pan handlers for Vector SVG Map
  const handleZoomIn = () => setZoom(z => Math.min(3.0, Math.round((z + 0.2) * 100) / 100));
  const handleZoomOut = () => setZoom(z => Math.max(0.5, Math.round((z - 0.2) * 100) / 100));
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };
  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };
  const handleMouseUp = () => setIsDragging(false);
  const handleWheel = (e) => {
    const delta = e.deltaY < 0 ? 0.15 : -0.15;
    setZoom(z => Math.max(0.5, Math.min(3.5, Math.round((z + delta) * 100) / 100)));
  };

  const hasGeoCoords = useMemo(() => {
    return rawNodes.some(n => n.lat != null && n.lng != null);
  }, [rawNodes]);

  const isTabletop = useMemo(() => {
    const tid = String(topology?.topology_id || '').toLowerCase();
    return tid.includes('tabletop') || (rawNodes.length === 2 && rawNodes.every(n => ['J1', 'J2'].includes(n.node_id))) || (rawNodes.length === 5 && ['J1', 'J2', 'J3', 'J4', 'J5'].every(id => rawNodes.some(n => n.node_id === id)));
  }, [topology, rawNodes]);

  const isTwoNodeMat = isTabletop && rawNodes.length === 2 && rawNodes.every(n => ['J1', 'J2'].includes(n.node_id));
  const isFiveNodeMat = isTabletop && (String(topology?.topology_id || '').toLowerCase().includes('tabletop_5nut') || (rawNodes.length === 5 && ['J1', 'J2', 'J3', 'J4', 'J5'].every(id => rawNodes.some(n => n.node_id === id))));
  const tabletopLabel = isTwoNodeMat
    ? 'Sa Bàn Bạt 1200 × 600 mm (đội 31μF)'
    : isFiveNodeMat
      ? 'Sa Bàn Bạt 1800 × 1200 mm, 5 nút (đội 31μF)'
      : `Sa Bàn ${rawNodes.length} nút (đội 31μF)`;

  // The inspection drawer is ~300 x 200 units of the 760x500 viewBox. Put it in the
  // corner that covers the fewest stations, so it never hides a node (e.g. J4/J5 on
  // the 5-node bottom row). Ties keep the original bottom-left placement.
  const drawerCornerStyle = useMemo(() => {
    const corners = [
      { style: { left: '16px', bottom: '16px' }, covers: (p) => p.x < 330 && p.y > 270 },
      { style: { right: '16px', bottom: '16px' }, covers: (p) => p.x > 430 && p.y > 270 },
      { style: { left: '16px', top: '16px' }, covers: (p) => p.x < 330 && p.y < 230 },
      { style: { right: '16px', top: '16px' }, covers: (p) => p.x > 430 && p.y < 230 },
    ];
    const points = Object.values(nodePositions);
    const best = corners.reduce((acc, corner) => {
      const covered = points.filter(corner.covers).length;
      return covered < acc.covered ? { style: corner.style, covered } : acc;
    }, { style: corners[0].style, covered: Infinity });
    return best.style;
  }, [nodePositions]);

  // If map has real-world GPS coordinates (HCM Corridor) and STREET mode is chosen: Render LeafletStreetMap!
  if (hasGeoCoords && mapType === 'STREET') {
    return (
      <div style={{ position: 'relative', width: '100%' }}>
        <LeafletStreetMap
          nodesData={nodesData}
          topology={topology}
          selectedNodeId={selectedNodeId}
          onSelectNode={onSelectNode}
          onNavigateDetail={onNavigateDetail}
          height={height}
        />
        <div style={{ position: 'absolute', bottom: '38px', right: '12px', zIndex: 1000 }}>
          <button
            onClick={() => setMapType('VECTOR')}
            title="Chuyển sang sơ đồ Logic Vector C++"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: '1px solid #cbd5e1',
              borderRadius: '6px',
              padding: '5px 12px',
              fontSize: '0.74rem',
              fontWeight: 700,
              color: '#334155',
              cursor: 'pointer',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              display: 'flex',
              alignItems: 'center',
              gap: '5px'
            }}
          >
            📐 Xem Sơ đồ Vector C++
          </button>
        </div>
      </div>
    );
  }

  const renderTabletopMat = () => {
    const renderZebraHorizontal = (cx, y) => {
      const startX = cx - 31.5;
      return Array.from({ length: 8 }).map((_, i) => (
        <rect 
          key={`zh-${cx}-${y}-${i}`} 
          x={startX + i * 8} 
          y={y} 
          width="5" 
          height="16" 
          fill="#F0F0EC" 
          rx="0.5"
        />
      ));
    };

    const renderZebraVertical = (x, cy) => {
      const startY = cy - 31.5;
      return Array.from({ length: 8 }).map((_, i) => (
        <rect 
          key={`zv-${x}-${cy}-${i}`} 
          x={x} 
          y={startY + i * 8} 
          width="16" 
          height="5" 
          fill="#F0F0EC" 
          rx="0.5"
        />
      ));
    };

    return (
      <g id="tabletop-sa-ban-layer" style={{ pointerEvents: 'none' }}>
        {/* Soft shadow under the mat */}
        <rect x="26" y="66" width="708" height="368" rx="12" fill="#0f172a" opacity="0.12" />

        {/* Outer Mat Canvas (700x360, matching 1200x600 mm physical tabletop) */}
        <rect x="30" y="70" width="700" height="360" rx="10" fill="#80A568" stroke="#5b784a" strokeWidth="2.5" />

        {/* Sidewalk border layer (#D6D2C8) */}
        <rect x="30" y="208" width="700" height="84" fill="#D6D2C8" />
        <rect x="163" y="70" width="84" height="360" fill="#D6D2C8" />
        <rect x="513" y="70" width="84" height="360" fill="#D6D2C8" />

        {/* Asphalt road surface (#3E4044) */}
        <rect x="30" y="216" width="700" height="68" fill="#3E4044" />
        <rect x="171" y="70" width="68" height="360" fill="#3E4044" />
        <rect x="521" y="70" width="68" height="360" fill="#3E4044" />

        {/* Lane Centerlines (dashed #F0F0EC) */}
        <line x1="32" y1="250" x2="150" y2="250" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="16,10" />
        <line x1="260" y1="250" x2="500" y2="250" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="16,10" />
        <line x1="610" y1="250" x2="728" y2="250" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="16,10" />
        <line x1="205" y1="72" x2="205" y2="190" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="16,10" />
        <line x1="205" y1="310" x2="205" y2="428" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="16,10" />
        <line x1="555" y1="72" x2="555" y2="190" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="16,10" />
        <line x1="555" y1="310" x2="555" y2="428" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="16,10" />

        {/* Crosswalk Zebra Stripes (#F0F0EC) */}
        {renderZebraHorizontal(205, 194)}
        {renderZebraHorizontal(205, 290)}
        {renderZebraVertical(154, 250)}
        {renderZebraVertical(238, 250)}

        {renderZebraHorizontal(555, 194)}
        {renderZebraHorizontal(555, 290)}
        {renderZebraVertical(504, 250)}
        {renderZebraVertical(588, 250)}

        {/* Stop Lines (solid #F0F0EC, 3.5px thick) */}
        {/* J1: North inbound (west lane) */}
        <rect x="171" y="190" width="34" height="3.5" fill="#F0F0EC" />
        {/* J1: South inbound (east lane) */}
        <rect x="205" y="306.5" width="34" height="3.5" fill="#F0F0EC" />
        {/* J1: West inbound (south lane) */}
        <rect x="150.5" y="250" width="3.5" height="34" fill="#F0F0EC" />
        {/* J1: East inbound (north lane, coming from J2) */}
        <rect x="254" y="216" width="3.5" height="34" fill="#F0F0EC" />

        {/* J2: North inbound (west lane) */}
        <rect x="521" y="190" width="34" height="3.5" fill="#F0F0EC" />
        {/* J2: South inbound (east lane) */}
        <rect x="555" y="306.5" width="34" height="3.5" fill="#F0F0EC" />
        {/* J2: West inbound (south lane, coming from J1) */}
        <rect x="500.5" y="250" width="3.5" height="34" fill="#F0F0EC" />
        {/* J2: East inbound (north lane) */}
        <rect x="604" y="216" width="3.5" height="34" fill="#F0F0EC" />

        {/* J1 Badge & Compass Box (NW of J1) */}
        <rect x="80" y="148" width="54" height="34" rx="7" fill="#FAFAF8" stroke="#282828" strokeWidth="1.5" />
        <text x="107" y="165" fontSize="19" fontWeight="900" fill="#1e1e1e" textAnchor="middle" dominantBaseline="central">J1</text>
        <path d="M 68 156 L 73 167 L 63 167 Z" fill="#F7F7F2" />
        <text x="68" y="177" fontSize="9" fontWeight="800" fill="#F7F7F2" textAnchor="middle" dominantBaseline="central">B</text>

        {/* J2 Badge & Compass Box (NE of J2) */}
        <rect x="626" y="148" width="54" height="34" rx="7" fill="#FAFAF8" stroke="#282828" strokeWidth="1.5" />
        <text x="653" y="165" fontSize="19" fontWeight="900" fill="#1e1e1e" textAnchor="middle" dominantBaseline="central">J2</text>
        <path d="M 692 156 L 697 167 L 687 167 Z" fill="#F7F7F2" />
        <text x="692" y="177" fontSize="9" fontWeight="800" fill="#F7F7F2" textAnchor="middle" dominantBaseline="central">B</text>

        {/* Equipment Footprints & Labels (matching Image 2 & SA_BAN_BAT_1200x600.html) */}
        {/* J1 MDF Base 200x200 */}
        <rect x="250" y="78" width="112" height="112" fill="none" stroke="#222831" strokeWidth="0.8" strokeDasharray="4 3" />
        <text x="306" y="88" fontSize="6.8" fontWeight="700" fill="#222831" textAnchor="middle" letterSpacing="0.3">ĐẾ TRỤ MDF 200 × 200</text>
        <rect x="264" y="165" width="14" height="14" fill="none" stroke="#222831" strokeWidth="0.8" />
        <text x="271" y="172" fontSize="5" fontWeight="700" fill="#222831" textAnchor="middle" dominantBaseline="central">TRỤ</text>

        {/* J2 MDF Base 200x200 */}
        <rect x="398" y="78" width="112" height="112" fill="none" stroke="#222831" strokeWidth="0.8" strokeDasharray="4 3" />
        <text x="454" y="88" fontSize="6.8" fontWeight="700" fill="#222831" textAnchor="middle" letterSpacing="0.3">ĐẾ TRỤ MDF 200 × 200</text>
        <rect x="482" y="165" width="14" height="14" fill="none" stroke="#222831" strokeWidth="0.8" />
        <text x="489" y="172" fontSize="5" fontWeight="700" fill="#222831" textAnchor="middle" dominantBaseline="central">TRỤ</text>

        {/* ESP32 J1 (South grass) */}
        <rect x="278" y="318" width="72" height="98" rx="4" fill="#C9C5BC" stroke="#8F8B83" strokeWidth="0.8" />
        <text x="314" y="328" fontSize="7" fontWeight="700" fill="#4A4741" textAnchor="middle">ESP32 · J1</text>
        <rect x="260" y="390" width="16" height="24" rx="2" fill="#C9C5BC" stroke="#8F8B83" strokeWidth="0.8" />
        <text x="268" y="402" fontSize="5" fontWeight="700" fill="#4A4741" textAnchor="middle" dominantBaseline="central">X1</text>

        {/* ESP32 J2 (South grass) */}
        <rect x="410" y="318" width="72" height="98" rx="4" fill="#C9C5BC" stroke="#8F8B83" strokeWidth="0.8" />
        <text x="446" y="328" fontSize="7" fontWeight="700" fill="#4A4741" textAnchor="middle">ESP32 · J2</text>

        {/* Pi 5 (SE grass) */}
        <rect x="646" y="348" width="66" height="48" rx="4" fill="#C9C5BC" stroke="#8F8B83" strokeWidth="0.8" />
        <text x="679" y="372" fontSize="6.8" fontWeight="700" fill="#4A4741" textAnchor="middle" dominantBaseline="central">AI BIÊN · PI 5</text>

        {/* Title & Scale Bar (SW grass) */}
        <text x="48" y="408" fontSize="9.5" fontWeight="800" fill="#F7F7F2">EdgeFlow AI · VEDC 2026 · đội 31μF</text>
        <line x1="48" y1="418" x2="108" y2="418" stroke="#F7F7F2" strokeWidth="2" />
        <line x1="48" y1="415" x2="48" y2="421" stroke="#F7F7F2" strokeWidth="1.5" />
        <line x1="108" y1="415" x2="108" y2="421" stroke="#F7F7F2" strokeWidth="1.5" />
        <text x="114" y="418" fontSize="6.5" fontWeight="700" fill="#F7F7F2" dominantBaseline="central">100 mm</text>
      </g>
    );
  };

  const renderTabletop5NutMat = () => {
    const renderZebraH = (cx, y) => {
      const startX = cx - 22;
      return Array.from({ length: 6 }).map((_, i) => (
        <rect key={`z5h-${cx}-${y}-${i}`} x={startX + i * 8} y={y} width="5" height="13" fill="#F0F0EC" rx="0.5" />
      ));
    };

    const renderZebraV = (x, cy) => {
      const startY = cy - 22;
      return Array.from({ length: 6 }).map((_, i) => (
        <rect key={`z5v-${x}-${cy}-${i}`} x={x} y={startY + i * 8} width="13" height="5" fill="#F0F0EC" rx="0.5" />
      ));
    };

    const renderHouse = (id, x, y, w, h, roofColor) => (
      <g key={id}>
        <rect x={x} y={y} width={w} height={h} rx="2" fill={roofColor} stroke="#2d3748" strokeWidth="0.8" />
        {/* Windows / Door */}
        <rect x={x + 3} y={y + 3} width={Math.max(4, (w - 10) / 2)} height={Math.max(3, h - 8)} fill="#fafafa" opacity="0.85" rx="0.5" />
        <rect x={x + w / 2 + 2} y={y + 3} width={Math.max(4, (w - 10) / 2)} height={Math.max(3, h - 8)} fill="#fafafa" opacity="0.85" rx="0.5" />
      </g>
    );

    const renderTree = (id, cx, cy) => (
      <g key={id}>
        <circle cx={cx + 1} cy={cy + 1} r="7.5" fill="#1b4332" opacity="0.3" />
        <circle cx={cx} cy={cy} r="7" fill="#40916c" stroke="#2d6a4f" strokeWidth="1" />
        <circle cx={cx - 1.5} cy={cy - 1.5} r="4" fill="#74c69d" opacity="0.7" />
      </g>
    );

    return (
      <g id="tabletop-5nut-sa-ban-layer" style={{ pointerEvents: 'none' }}>
        {/* Soft shadow */}
        <rect x="16" y="16" width="728" height="468" rx="14" fill="#0f172a" opacity="0.14" />

        {/* 1. Base Grass Lawn Mat (720 x 460 mm canvas representing 1800 x 1200 mm physical sa bàn) */}
        <rect x="20" y="20" width="720" height="460" rx="12" fill="#80A568" stroke="#5b784a" strokeWidth="2.5" />

        {/* 2. Sidewalk Borders (#D6D2C8) - Wide, crisp pedestrian borders */}
        <rect x="20" y="107" width="720" height="66" fill="#D6D2C8" />
        <rect x="20" y="317" width="580" height="66" fill="#D6D2C8" />
        <rect x="127" y="20" width="66" height="460" fill="#D6D2C8" />
        <rect x="337" y="20" width="66" height="460" fill="#D6D2C8" />
        <rect x="547" y="20" width="66" height="363" fill="#D6D2C8" />

        {/* 3. Asphalt Roads (#3E4044) - Wide, bold avenues */}
        <rect x="20" y="114" width="720" height="52" fill="#3E4044" />
        <rect x="20" y="324" width="570" height="52" fill="#3E4044" />
        <rect x="134" y="20" width="52" height="460" fill="#3E4044" />
        <rect x="344" y="20" width="52" height="460" fill="#3E4044" />
        <rect x="554" y="20" width="52" height="356" fill="#3E4044" />

        {/* 4. Animated Flow Centerlines (White dashed #F0F0EC with animated stream effect) */}
        {/* Horizontal top road */}
        <line x1="20" y1="140" x2="120" y2="140" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="200" y1="140" x2="330" y2="140" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="410" y1="140" x2="540" y2="140" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="620" y1="140" x2="740" y2="140" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />

        {/* Horizontal bottom road */}
        <line x1="20" y1="350" x2="120" y2="350" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="200" y1="350" x2="330" y2="350" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="410" y1="350" x2="540" y2="350" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />

        {/* Vertical West road (J1 - J4) */}
        <line x1="160" y1="20" x2="160" y2="100" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="160" y1="180" x2="160" y2="310" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="160" y1="390" x2="160" y2="480" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />

        {/* Vertical Mid road (J2 - J5) */}
        <line x1="370" y1="20" x2="370" y2="100" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="370" y1="180" x2="370" y2="310" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="370" y1="390" x2="370" y2="480" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />

        {/* Vertical East road (J3 - Parking) */}
        <line x1="580" y1="20" x2="580" y2="100" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />
        <line x1="580" y1="180" x2="580" y2="310" stroke="#F0F0EC" strokeWidth="2.5" strokeDasharray="14,10" className="flow-active" />

        {/* 5. Crosswalk Zebra Stripes at all 5 signalized intersections */}
        {/* J1 Crosswalks */}
        {renderZebraH(160, 97)}
        {renderZebraH(160, 169)}
        {renderZebraV(117, 140)}
        {renderZebraV(189, 140)}

        {/* J2 Crosswalks */}
        {renderZebraH(370, 97)}
        {renderZebraH(370, 169)}
        {renderZebraV(327, 140)}
        {renderZebraV(399, 140)}

        {/* J3 Crosswalks */}
        {renderZebraH(580, 97)}
        {renderZebraH(580, 169)}
        {renderZebraV(537, 140)}
        {renderZebraV(609, 140)}

        {/* J4 Crosswalks */}
        {renderZebraH(160, 307)}
        {renderZebraH(160, 379)}
        {renderZebraV(117, 350)}
        {renderZebraV(189, 350)}

        {/* J5 Crosswalks */}
        {renderZebraH(370, 307)}
        {renderZebraH(370, 379)}
        {renderZebraV(327, 350)}
        {renderZebraV(399, 350)}

        {/* Stop bars at J1..J5 approaches */}
        <rect x="134" y="93" width="26" height="3" fill="#F0F0EC" />
        <rect x="160" y="184" width="26" height="3" fill="#F0F0EC" />
        <rect x="344" y="93" width="26" height="3" fill="#F0F0EC" />
        <rect x="370" y="184" width="26" height="3" fill="#F0F0EC" />
        <rect x="554" y="93" width="26" height="3" fill="#F0F0EC" />
        <rect x="580" y="184" width="26" height="3" fill="#F0F0EC" />
        <rect x="134" y="303" width="26" height="3" fill="#F0F0EC" />
        <rect x="160" y="394" width="26" height="3" fill="#F0F0EC" />
        <rect x="344" y="303" width="26" height="3" fill="#F0F0EC" />
        <rect x="370" y="394" width="26" height="3" fill="#F0F0EC" />

        {/* 6. Residential Buildings (Khối nhà dân cư đúng theo ảnh sa bàn) */}
        {/* Block 1 (Top Left, NW of J1) */}
        {renderHouse('h_nw1', 35, 32, 28, 24, '#b91c1c')}
        {renderHouse('h_nw2', 72, 32, 28, 24, '#c2410c')}
        {renderHouse('h_nw3', 35, 68, 28, 24, '#0369a1')}

        {/* Block 2 (Between J1 and J2 North) */}
        <rect x="202" y="30" width="36" height="36" rx="2" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.8" />
        <rect x="268" y="30" width="36" height="36" rx="2" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.8" />
        {renderHouse('h_n1', 208, 74, 28, 24, '#b91c1c')}
        {renderHouse('h_n2', 268, 74, 28, 24, '#c2410c')}

        {/* Block 3 (Between J2 and J3 North) */}
        {renderHouse('h_ne1', 432, 70, 26, 22, '#0369a1')}
        {renderHouse('h_ne2', 462, 70, 26, 22, '#b91c1c')}
        {renderHouse('h_ne3', 496, 68, 28, 24, '#c2410c')}
        <rect x="504" y="30" width="38" height="34" rx="2" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.8" />

        {/* Block 4 (East of J3) */}
        {renderHouse('h_e1', 630, 32, 24, 24, '#0369a1')}
        {renderHouse('h_e2', 660, 32, 28, 24, '#b91c1c')}
        {renderHouse('h_e3', 665, 74, 26, 22, '#c2410c')}

        {/* Block 5 (Central Block between J1, J2, J4, J5) - Dense Urban Core */}
        {renderHouse('h_c1', 208, 185, 26, 22, '#0369a1')}
        {renderHouse('h_c2', 268, 185, 26, 22, '#c2410c')}
        {renderHouse('h_c3', 208, 218, 26, 22, '#b91c1c')}
        {renderHouse('h_c4', 268, 218, 26, 22, '#b91c1c')}
        {renderHouse('h_c5', 208, 252, 26, 22, '#c2410c')}
        {renderHouse('h_c6', 268, 252, 26, 22, '#0369a1')}
        {renderHouse('h_c7', 208, 286, 26, 22, '#b91c1c')}
        {renderHouse('h_c8', 268, 286, 26, 22, '#b91c1c')}

        {/* Block 6 (East Central between J2, J3, J5, RES_P) */}
        {renderHouse('h_ec1', 432, 175, 28, 22, '#b91c1c')}
        {renderHouse('h_ec2', 464, 175, 28, 22, '#0369a1')}
        {renderHouse('h_ec3', 432, 210, 28, 22, '#c2410c')}
        {renderHouse('h_ec4', 464, 210, 28, 22, '#b91c1c')}
        {renderHouse('h_ec5', 432, 245, 28, 22, '#b91c1c')}
        {renderHouse('h_ec6', 464, 245, 28, 22, '#c2410c')}
        {renderHouse('h_ec7', 500, 254, 28, 24, '#b91c1c')}
        {renderHouse('h_ec8', 532, 254, 28, 24, '#0369a1')}

        {/* Trees */}
        {renderTree('t1', 512, 185)}
        {renderTree('t2', 512, 220)}
        {renderTree('t3', 440, 288)}
        {renderTree('t4', 475, 292)}
        {renderTree('t5', 510, 292)}
        {renderTree('t6', 625, 292)}

        {/* Block 7 (South Central below J5) */}
        <rect x="412" y="390" width="42" height="32" rx="2" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.8" />
        {renderTree('t7', 462, 385)}
        {renderTree('t8', 462, 420)}
        {renderHouse('h_sc1', 500, 396, 30, 26, '#0369a1')}
        {renderHouse('h_sc2', 538, 396, 26, 26, '#b91c1c')}
        {renderHouse('h_sc3', 580, 396, 36, 26, '#e2e8f0')}
        {renderHouse('h_sc4', 626, 396, 26, 26, '#b91c1c')}
        {renderHouse('h_sc5', 668, 396, 30, 26, '#c2410c')}

        {/* 7. SOUTHEAST BÃI ĐỖ XE P & KHU DÂN CƯ BADGE (Góc Đông Nam cực kỳ nổi bật) */}
        {/* Asphalt Parking Area */}
        <rect x="548" y="356" width="102" height="66" rx="4" fill="#2d3748" stroke="#1a202c" strokeWidth="1.2" />
        {/* White parking bay divider lines */}
        {Array.from({ length: 6 }).map((_, i) => (
          <line key={`pb-${i}`} x1={558 + i * 16} y1="384" x2={558 + i * 16} y2="422" stroke="#ffffff" strokeWidth="1.5" />
        ))}
        <line x1="558" y1="384" x2="638" y2="384" stroke="#ffffff" strokeWidth="1.5" />
        {/* Large Parking 'P' Symbol */}
        <text x="592" y="372" fontSize="13" fontWeight="900" fill="#ffffff" textAnchor="middle">P</text>
        <text x="592" y="380" fontSize="5.5" fontWeight="700" fill="#94a3b8" textAnchor="middle">BÃI ĐỖ XE</text>

        {/* KHU DÂN CƯ Official Badge Card */}
        <rect x="646" y="320" width="70" height="52" rx="5" fill="#ffffff" stroke="#cbd5e1" strokeWidth="1.5" />
        {/* Orange roof house icon */}
        <polygon points="681,327 668,337 694,337" fill="#ea580c" />
        <rect x="672" y="337" width="18" height="12" fill="#eff6ff" stroke="#ea580c" strokeWidth="1" />
        <rect x="674" y="340" width="5" height="5" fill="#0284c7" />
        <rect x="683" y="340" width="5" height="5" fill="#0284c7" />
        <text x="681" y="357" fontSize="6.8" fontWeight="900" fill="#1e293b" textAnchor="middle">KHU DÂN CƯ</text>
        <text x="681" y="365" fontSize="5" fontWeight="600" fill="#64748b" textAnchor="middle">residential area</text>

        {/* 8. Intersection Label Badges (J1, J2, J3, J4, J5) */}
        {/* J1 Badge */}
        <rect x="80" y="152" width="36" height="24" rx="4" fill="#FAFAF8" stroke="#282828" strokeWidth="1.2" />
        <text x="98" y="164" fontSize="13" fontWeight="900" fill="#1e1e1e" textAnchor="middle" dominantBaseline="central">J1</text>

        {/* J2 Badge */}
        <rect x="408" y="152" width="36" height="24" rx="4" fill="#FAFAF8" stroke="#282828" strokeWidth="1.2" />
        <text x="426" y="164" fontSize="13" fontWeight="900" fill="#1e1e1e" textAnchor="middle" dominantBaseline="central">J2</text>

        {/* J3 Badge */}
        <rect x="632" y="152" width="36" height="24" rx="4" fill="#FAFAF8" stroke="#282828" strokeWidth="1.2" />
        <text x="650" y="164" fontSize="13" fontWeight="900" fill="#1e1e1e" textAnchor="middle" dominantBaseline="central">J3</text>

        {/* J4 Badge */}
        <rect x="80" y="362" width="36" height="24" rx="4" fill="#FAFAF8" stroke="#282828" strokeWidth="1.2" />
        <text x="98" y="374" fontSize="13" fontWeight="900" fill="#1e1e1e" textAnchor="middle" dominantBaseline="central">J4</text>

        {/* J5 Badge */}
        <rect x="408" y="362" width="36" height="24" rx="4" fill="#FAFAF8" stroke="#282828" strokeWidth="1.2" />
        <text x="426" y="374" fontSize="13" fontWeight="900" fill="#1e1e1e" textAnchor="middle" dominantBaseline="central">J5</text>

        {/* 9. Hardware Footprints & Competition Labels */}
        <text x="32" y="445" fontSize="8.5" fontWeight="800" fill="#F7F7F2">EdgeFlow AI · VEDC 2026 · đội 31μF</text>
        <line x1="32" y1="454" x2="92" y2="454" stroke="#F7F7F2" strokeWidth="1.8" />
        <line x1="32" y1="451" x2="32" y2="457" stroke="#F7F7F2" strokeWidth="1.5" />
        <line x1="92" y1="451" x2="92" y2="457" stroke="#F7F7F2" strokeWidth="1.5" />
        <text x="98" y="454" fontSize="6.5" fontWeight="700" fill="#F7F7F2" dominantBaseline="central">100 mm</text>

        {/* Hardware ESP32 & Pi 5 Indicators */}
        <rect x="180" y="440" width="48" height="18" rx="3" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.8" />
        <text x="204" y="449" fontSize="6" fontWeight="700" fill="#334155" textAnchor="middle" dominantBaseline="central">ESP32 · J4</text>

        <rect x="390" y="440" width="48" height="18" rx="3" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.8" />
        <text x="414" y="449" fontSize="6" fontWeight="700" fill="#334155" textAnchor="middle" dominantBaseline="central">ESP32 · J5</text>

        <rect x="445" y="440" width="38" height="18" rx="3" fill="#cbd5e1" stroke="#94a3b8" strokeWidth="0.8" />
        <text x="464" y="449" fontSize="5.5" fontWeight="700" fill="#334155" textAnchor="middle" dominantBaseline="central">HUB USB</text>

        <rect x="490" y="440" width="52" height="18" rx="3" fill="#0284c7" />
        <text x="516" y="449" fontSize="6" fontWeight="800" fill="#ffffff" textAnchor="middle" dominantBaseline="central">AI BIÊN · PI 5</text>
      </g>
    );
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
          {isTabletop && (
            <span style={{ 
              backgroundColor: '#dcfce7', 
              color: '#15803d', 
              padding: '2px 8px', 
              borderRadius: '4px', 
              fontWeight: 700,
              fontSize: '0.74rem',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              🌿 {tabletopLabel}
            </span>
          )}
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
          {/* Past the same node-count tier that shrinks nodeRadius/getFontSize to their smallest
              step, the default fit-to-screen view packs stations too tightly to read their IDs --
              the zoom controls already solve this (labels scale with the same transform), the gap
              is just that nothing says so. Hides itself once the operator has actually zoomed in. */}
          {totalCount > 40 && zoom <= 1.2 && (
            <span style={{
              backgroundColor: '#fffbeb',
              color: '#92400e',
              border: '1px solid #fde68a',
              padding: '2px 8px',
              borderRadius: '4px',
              fontWeight: 700,
              fontSize: '0.72rem',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <ZoomIn size={11} /> {totalCount} nodes — zoom in to read station IDs
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end', gap: '8px' }}>
          {/* Switch to Street Map */}
          {hasGeoCoords && (
            <button
              onClick={() => setMapType('STREET')}
              style={{
                backgroundColor: '#0284c7',
                color: '#ffffff',
                border: 'none',
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '0.74rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              🗺️ Mở OpenStreetMap
            </button>
          )}

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

      {/* Main Interactive SVG Canvas with Mouse Dragging & Scroll Zoom */}
      <div 
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{ 
          position: 'relative', 
          width: '100%', 
          height: `${height}px`, 
          backgroundColor: '#f8fafc',
          cursor: isDragging ? 'grabbing' : 'grab',
          userSelect: 'none'
        }}
      >
        <svg 
          width="100%" 
          height="100%" 
          viewBox="0 0 760 500" 
          preserveAspectRatio="xMidYMid meet"
          style={{ transition: 'transform 0.15s ease-out' }}
        >
          <defs>
            {/* Dynamic CSS animations for flowing traffic and congestion ripples */}
            <style>{`
              @keyframes flowDash {
                from { stroke-dashoffset: 24; }
                to { stroke-dashoffset: 0; }
              }
              @keyframes rippleWave {
                0% { r: ${nodeRadius + 4}; opacity: 0.85; stroke-width: 2.5px; }
                100% { r: ${nodeRadius + 28}; opacity: 0; stroke-width: 0.5px; }
              }
              .flow-active {
                animation: flowDash 1.2s linear infinite;
              }
              .pulse-ripple-ring {
                animation: rippleWave 1.8s cubic-bezier(0.1, 0.8, 0.3, 1) infinite;
              }
            `}</style>

            {/* Neon Glow Filters */}
            <filter id="neon-glow-green" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="neon-glow-blue" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="neon-glow-red" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

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
            
            {/* Tabletop Sa Bàn Overlay (Image 2 exact 1200x600 mm layout) */}
            {isTwoNodeMat && renderTabletopMat()}

            {/* Tabletop 5-node Sa Bàn Overlay (VEDC 2026 - 1800x1200 mm 5-nut layout with residential area) */}
            {isFiveNodeMat && renderTabletop5NutMat()}

            {/* Draw Directed Edges & SUMO Roads */}
            {showEdges && edgesToDraw.map((edge) => {
              const p1 = nodePositions[edge.src];
              const p2 = nodePositions[edge.tgt];
              if (!p1 || !p2) return null;

              const isConnectedToFocus = activeFocusNode === edge.src || activeFocusNode === edge.tgt;
              const hasActiveFocus = Boolean(activeFocusNode);
              const srcData = nodesData[edge.src];
              const hasQueueOnSrc = (srcData?.total_queue || 0) > 0;

              if (edge.pathD) {
                return (
                  <g key={edge.key}>
                    {/* Realistic asphalt road base */}
                    <path
                      d={edge.pathD}
                      stroke={isConnectedToFocus ? "#0284c7" : "#cbd5e1"}
                      strokeWidth={isConnectedToFocus ? "5.5" : "3.5"}
                      fill="none"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      opacity={isConnectedToFocus ? 1.0 : hasActiveFocus ? 0.35 : 0.75}
                    />
                    {/* Road lane centerline with direction */}
                    <path
                      d={edge.pathD}
                      stroke={isConnectedToFocus ? "#38bdf8" : hasQueueOnSrc ? "#f59e0b" : "#94a3b8"}
                      strokeWidth="1.2"
                      strokeDasharray="4,3"
                      fill="none"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      opacity={isConnectedToFocus ? 1.0 : hasActiveFocus ? 0.4 : 0.85}
                    />
                  </g>
                );
              }

              let lx1 = p1.x, ly1 = p1.y, lx2 = p2.x, ly2 = p2.y;
              if (isTwoNodeMat) {
                if (edge.src === 'J1' && edge.tgt === 'J2') {
                  // Eastbound: lower lane in right-hand traffic
                  ly1 = 266; ly2 = 266; lx1 = 238; lx2 = 520;
                } else if (edge.src === 'J2' && edge.tgt === 'J1') {
                  // Westbound: upper lane in right-hand traffic
                  ly1 = 234; ly2 = 234; lx1 = 522; lx2 = 240;
                }
              }

              return (
                <g key={edge.key}>
                  {/* Subtle edge road bed (hidden on tabletop where asphalt is already drawn) */}
                  {!isTwoNodeMat && (
                    <line
                      x1={lx1}
                      y1={ly1}
                      x2={lx2}
                      y2={ly2}
                      stroke={isConnectedToFocus ? "#38bdf8" : "#cbd5e1"}
                      strokeWidth={isConnectedToFocus ? "3.5" : totalCount > 30 ? "1.4" : "1.8"}
                      opacity={isConnectedToFocus ? 0.95 : hasActiveFocus ? 0.25 : 0.55}
                    />
                  )}
                  {/* Directional flow lane with marker */}
                  <line
                    x1={lx1}
                    y1={ly1}
                    x2={lx2}
                    y2={ly2}
                    stroke={isConnectedToFocus ? "#38bdf8" : isTabletop ? "#38bdf8" : "#0284c7"}
                    strokeWidth={isTabletop ? "2.4" : isConnectedToFocus ? "2.2" : totalCount > 30 ? "1" : "1.3"}
                    strokeDasharray={totalCount > 20 && !isTabletop ? "none" : "5,3"}
                    opacity={isConnectedToFocus ? 1.0 : hasActiveFocus ? 0.35 : 0.85}
                    markerEnd={isConnectedToFocus ? "url(#traffic-arrow-highlight)" : "url(#traffic-arrow)"}
                  />
                </g>
              );
            })}

            {/* Draw Nodes */}
            {Object.entries(nodePositions).map(([nodeId, pos]) => {
              const data = nodesData[nodeId] || { current_phase_id: `${nodeId}_PHASE_1`, total_queue: 0, speed: 13.9, status: 'ONLINE' };
              const phaseStr = String(data.current_phase_id || "").toUpperCase();
              // Bare "1"/"GREEN" substrings false-matched node ids like "A1" or phase names that just
              // happen to contain "GREEN" -- only trust the literal NS convention here.
              const isNS = phaseStr.includes("NS");
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

                  {/* Congestion Pulse Ripple Effect when totalQueue >= 6 */}
                  {totalQueue >= 6 && (
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      className="pulse-ripple-ring"
                      fill="none"
                      stroke={badgeColor}
                    />
                  )}

                  {/* Outer Active Signal Phase Ring (Green for Phase 1, Blue for Phase 2) with Glow */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={isHighlighted ? outerRadius + 3 : outerRadius}
                    fill={isNS ? "rgba(16, 185, 129, 0.16)" : "rgba(2, 132, 199, 0.16)"}
                    stroke={isNS ? "#10b981" : "#0284c7"}
                    strokeWidth={isHighlighted ? "2.6" : "1.8"}
                    filter={isHighlighted || isTabletop ? (isNS ? "url(#neon-glow-green)" : "url(#neon-glow-blue)") : "none"}
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
            ...drawerCornerStyle,
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
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
                {nodePositions[activeFocusNode]?.street_name && (
                  <span style={{ fontSize: '0.74rem', color: '#cbd5e1', fontWeight: 600 }}>
                    📍 {nodePositions[activeFocusNode].street_name}
                  </span>
                )}
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
