import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Layers, RotateCcw, ZoomIn, ZoomOut, Navigation, Eye, EyeOff, Radio } from 'lucide-react';

const TILE_PROVIDERS = {
  STREET: {
    name: 'OpenStreetMap',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  },
  VOYAGER: {
    name: 'CartoDB Voyager',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 20
  },
  DARK: {
    name: 'Bản đồ Đêm (Dark)',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 20
  }
};

export default function LeafletStreetMap({
  nodesData = {},
  topology = null,
  selectedNodeId = null,
  onSelectNode,
  onNavigateDetail,
  height = 540
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef({});
  const polylinesRef = useRef([]);
  const tileLayerRef = useRef(null);

  const [activeTile, setActiveTile] = useState('VOYAGER');
  const [showQueueBadges, setShowQueueBadges] = useState(true);
  const [showRoadLines, setShowRoadLines] = useState(true);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Extract nodes with valid GPS lat/lng
  const geoNodes = useMemo(() => {
    if (!topology?.nodes?.length) return [];
    return topology.nodes
      .filter(n => n.lat != null && n.lng != null)
      .map(n => ({
        node_id: n.node_id,
        name: n.name || n.node_id,
        street_name: n.street_name || '',
        lat: Number(n.lat),
        lng: Number(n.lng)
      }));
  }, [topology]);

  // Extract edges
  const geoEdges = useMemo(() => {
    if (!topology?.edges?.length) return [];
    return topology.edges;
  }, [topology]);

  // Corridor Center & Bounds
  const { center, bounds } = useMemo(() => {
    if (!geoNodes.length) {
      return { center: [10.88317, 106.82169], bounds: null };
    }
    const lats = geoNodes.map(n => n.lat);
    const lngs = geoNodes.map(n => n.lng);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
    return {
      center: [(minLat + maxLat) / 2, (minLng + maxLng) / 2],
      bounds: [[minLat, minLng], [maxLat, maxLng]]
    };
  }, [geoNodes]);

  // 1. Initialize Leaflet Map
  useEffect(() => {
    const L = window.L;
    if (!L || !mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: center,
        zoom: 17,
        zoomControl: false,
        attributionControl: false
      });

      // Add Tile Layer
      const provider = TILE_PROVIDERS[activeTile];
      const tileLayer = L.tileLayer(provider.url, {
        maxZoom: provider.maxZoom,
        attribution: provider.attribution
      }).addTo(map);

      tileLayerRef.current = tileLayer;
      mapInstanceRef.current = map;

      if (bounds) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 18 });
      }

      setMapLoaded(true);
    }

    return () => {
      // Keep map instance mounted across prop re-renders
    };
  }, [center, bounds]);

  // 2. Handle Tile Layer Switch
  useEffect(() => {
    const L = window.L;
    const map = mapInstanceRef.current;
    if (!L || !map) return;

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }

    const provider = TILE_PROVIDERS[activeTile];
    const newTile = L.tileLayer(provider.url, {
      maxZoom: provider.maxZoom,
      attribution: provider.attribution
    }).addTo(map);

    tileLayerRef.current = newTile;
  }, [activeTile]);

  // 3. Draw Road Lines between connected junctions
  useEffect(() => {
    const L = window.L;
    const map = mapInstanceRef.current;
    if (!L || !map || !mapLoaded) return;

    // Clear existing polylines
    polylinesRef.current.forEach(line => map.removeLayer(line));
    polylinesRef.current = [];

    if (!showRoadLines) return;

    const nodePosMap = {};
    geoNodes.forEach(n => {
      nodePosMap[n.node_id] = [n.lat, n.lng];
    });

    geoEdges.forEach(e => {
      const src = e.source || e.from;
      const tgt = e.target || e.to;
      const p1 = nodePosMap[src];
      const p2 = nodePosMap[tgt];
      if (p1 && p2) {
        const srcData = nodesData[src];
        const queueVeh = srcData?.total_queue || 0;
        const color = queueVeh >= 10 ? '#ef4444' : queueVeh >= 4 ? '#f59e0b' : '#0ea5e9';
        const weight = queueVeh >= 4 ? 4.5 : 3.0;

        // Base road casing
        const roadCasing = L.polyline([p1, p2], {
          color: '#334155',
          weight: weight + 2,
          opacity: 0.7,
          lineCap: 'round'
        }).addTo(map);

        // Traffic flow line
        const flowLine = L.polyline([p1, p2], {
          color: color,
          weight: weight,
          opacity: 0.9,
          lineCap: 'round',
          dashArray: queueVeh > 0 ? undefined : '5, 5'
        }).addTo(map);

        polylinesRef.current.push(roadCasing, flowLine);
      }
    });
  }, [geoEdges, geoNodes, showRoadLines, mapLoaded, nodesData]);

  // 4. Draw & Update Real-time Junction Markers
  useEffect(() => {
    const L = window.L;
    const map = mapInstanceRef.current;
    if (!L || !map || !mapLoaded) return;

    geoNodes.forEach(node => {
      const nid = node.node_id;
      const live = nodesData[nid] || {};
      const queue = live.total_queue || 0;
      const phase = String(live.current_phase_id || 'PHASE_1');
      const isSelected = selectedNodeId === nid;

      // Color scheme based on queue & signal state
      const isGreen = phase.includes('GREEN') || phase.includes('NS') || phase.includes('1');
      const signalColor = isGreen ? '#22c55e' : '#0284c7';
      const queueBadgeColor = queue >= 10 ? '#ef4444' : queue >= 4 ? '#f59e0b' : '#10b981';

      const shortId = nid.length > 8 ? nid.slice(-4) : nid;

      // HTML template for custom interactive map pin
      const html = `
        <div class="traffic-marker-container" style="
          position: relative;
          cursor: pointer;
          transform: translate(-50%, -50%);
          display: flex;
          align-items: center;
          justify-content: center;
        ">
          <!-- Selection Glow Pulse -->
          ${isSelected ? `
            <div style="
              position: absolute;
              width: 44px;
              height: 44px;
              border-radius: 50%;
              background: rgba(2, 132, 199, 0.35);
              border: 2px solid #0284c7;
              animation: marker-pulse 1.6s infinite ease-out;
            "></div>
          ` : ''}

          <!-- Junction Pin Body -->
          <div style="
            width: ${isSelected ? '26px' : '22px'};
            height: ${isSelected ? '26px' : '22px'};
            border-radius: 50%;
            background-color: ${isSelected ? '#0284c7' : '#ffffff'};
            border: 2.5px solid ${signalColor};
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            font-weight: 800;
            color: ${isSelected ? '#ffffff' : '#0f172a'};
            font-family: 'JetBrains Mono', monospace;
            transition: all 0.2s ease;
          ">
            ${shortId}
          </div>

          <!-- Real-time Queue Badge -->
          ${showQueueBadges ? `
            <div style="
              position: absolute;
              top: -6px;
              right: -8px;
              background-color: ${queueBadgeColor};
              color: #ffffff;
              font-size: 8px;
              font-weight: 800;
              padding: 1px 4px;
              border-radius: 8px;
              border: 1.5px solid #ffffff;
              box-shadow: 0 1px 4px rgba(0,0,0,0.25);
              min-width: 12px;
              text-align: center;
            ">
              ${queue}
            </div>
          ` : ''}
        </div>
      `;

      const icon = L.divIcon({
        className: 'custom-traffic-pin',
        html: html,
        iconSize: [26, 26],
        iconAnchor: [13, 13]
      });

      if (!markersRef.current[nid]) {
        const marker = L.marker([node.lat, node.lng], { icon: icon }).addTo(map);

        marker.on('click', () => {
          if (onSelectNode) onSelectNode(nid);
        });

        markersRef.current[nid] = marker;
      } else {
        markersRef.current[nid].setIcon(icon);
      }

      // Bind rich popup content
      const popupHtml = `
        <div style="font-family: 'Inter', sans-serif; font-size: 12px; line-height: 1.4; min-width: 200px;">
          <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px;">
            <strong style="color: #0284c7; font-size: 13px;">Station ${nid}</strong>
            <span style="font-size: 10px; background: #f0fdf4; color: #16a34a; font-weight: 700; padding: 1px 5px; border-radius: 4px;">
              ${live.status || 'ONLINE'}
            </span>
          </div>
          ${node.street_name ? `<div style="color: #475569; font-weight: 600; margin-bottom: 4px;">📍 ${node.street_name}</div>` : ''}
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-bottom: 6px; font-size: 11px;">
            <div>Hàng đợi: <strong style="color: ${queue > 8 ? '#dc2626' : '#0f172a'}">${queue} xe</strong></div>
            <div>Lưu lượng: <strong>${live.flow || 0} xe/s</strong></div>
            <div>Tốc độ: <strong>${live.speed != null ? live.speed : 13.9} m/s</strong></div>
            <div>Pha đèn: <strong style="color: #16a34a;">${phase}</strong></div>
          </div>
          <div style="font-size: 10px; color: #64748b; font-style: italic;">Khớp tọa độ GPS thực địa OpenStreetMap</div>
        </div>
      `;
      markersRef.current[nid].bindPopup(popupHtml, { closeButton: false });
    });
  }, [geoNodes, nodesData, selectedNodeId, showQueueBadges, mapLoaded]);

  // 5. Smooth Fly-to when user selects a station
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !selectedNodeId) return;

    const node = geoNodes.find(n => n.node_id === selectedNodeId);
    if (node) {
      map.flyTo([node.lat, node.lng], 18, {
        animate: true,
        duration: 0.7
      });
      if (markersRef.current[selectedNodeId]) {
        markersRef.current[selectedNodeId].openPopup();
      }
    }
  }, [selectedNodeId, geoNodes]);

  // Handlers
  const handleZoomIn = () => mapInstanceRef.current?.zoomIn();
  const handleZoomOut = () => mapInstanceRef.current?.zoomOut();
  const handleResetCorridor = () => {
    if (mapInstanceRef.current && bounds) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 18, animate: true });
    }
  };

  return (
    <div style={{
      position: 'relative',
      width: '100%',
      borderRadius: '12px',
      overflow: 'hidden',
      border: '1px solid #cbd5e1',
      boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
      backgroundColor: '#f8fafc'
    }}>
      {/* Top Map Control Toolbar */}
      <div style={{
        position: 'absolute',
        top: '12px',
        left: '12px',
        right: '12px',
        zIndex: 1000,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '8px',
        pointerEvents: 'none'
      }}>
        {/* Left Toolbar: Corridor Indicator */}
        <div style={{
          pointerEvents: 'auto',
          backgroundColor: 'rgba(255, 255, 255, 0.94)',
          backdropFilter: 'blur(6px)',
          borderRadius: '8px',
          padding: '6px 12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
          border: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.8rem',
          fontWeight: 700,
          color: '#0f172a'
        }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e' }}></span>
          <span>Hành lang TP.HCM (OpenStreetMap Live)</span>
          <span style={{ color: '#64748b', fontWeight: 500, fontSize: '0.74rem' }}>
            ({geoNodes.length} trạm)
          </span>
        </div>

        {/* Right Toolbar: Map Controls */}
        <div style={{
          pointerEvents: 'auto',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          backgroundColor: 'rgba(255, 255, 255, 0.94)',
          backdropFilter: 'blur(6px)',
          borderRadius: '8px',
          padding: '4px 6px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
          border: '1px solid #e2e8f0'
        }}>
          {/* Tile Layer Selector */}
          <select
            value={activeTile}
            onChange={(e) => setActiveTile(e.target.value)}
            style={{
              border: '1px solid #cbd5e1',
              borderRadius: '6px',
              padding: '3px 8px',
              fontSize: '0.74rem',
              fontWeight: 600,
              backgroundColor: '#ffffff',
              color: '#334155',
              cursor: 'pointer'
            }}
          >
            <option value="VOYAGER">Bản đồ Đường phố (Voyager)</option>
            <option value="STREET">OpenStreetMap Chuẩn</option>
            <option value="DARK">Bản đồ Đêm (Dark Mode)</option>
          </select>

          {/* Toggle Road Lines */}
          <button
            onClick={() => setShowRoadLines(!showRoadLines)}
            title="Bật/Tắt đường nối giao thông"
            style={{
              border: '1px solid #cbd5e1',
              backgroundColor: showRoadLines ? '#e0f2fe' : '#ffffff',
              color: showRoadLines ? '#0284c7' : '#64748b',
              padding: '4px 8px',
              borderRadius: '6px',
              fontSize: '0.72rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            {showRoadLines ? 'Tuyến đường ON' : 'Tuyến đường OFF'}
          </button>

          {/* Toggle Queue Badges */}
          <button
            onClick={() => setShowQueueBadges(!showQueueBadges)}
            title="Bật/Tắt số lượng xe chờ trên trạm"
            style={{
              border: '1px solid #cbd5e1',
              backgroundColor: showQueueBadges ? '#f0fdf4' : '#ffffff',
              color: showQueueBadges ? '#16a34a' : '#64748b',
              padding: '4px 8px',
              borderRadius: '6px',
              fontSize: '0.72rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            {showQueueBadges ? 'Hàng đợi ON' : 'Hàng đợi OFF'}
          </button>

          {/* Zoom & Reset Buttons */}
          <button
            onClick={handleZoomIn}
            title="Phóng to"
            style={{
              border: '1px solid #cbd5e1',
              backgroundColor: '#ffffff',
              padding: '4px 6px',
              borderRadius: '5px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <ZoomIn size={14} color="#334155" />
          </button>
          <button
            onClick={handleZoomOut}
            title="Thu nhỏ"
            style={{
              border: '1px solid #cbd5e1',
              backgroundColor: '#ffffff',
              padding: '4px 6px',
              borderRadius: '5px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <ZoomOut size={14} color="#334155" />
          </button>
          <button
            onClick={handleResetCorridor}
            title="Định vị toàn cảnh hành lang"
            style={{
              border: '1px solid #cbd5e1',
              backgroundColor: '#f8fafc',
              padding: '4px 8px',
              borderRadius: '5px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.72rem',
              fontWeight: 700,
              color: '#0284c7'
            }}
          >
            <RotateCcw size={12} />
            Toàn cảnh
          </button>
        </div>
      </div>

      {/* Main Map Canvas with Mouse Dragging & Scroll Zoom */}
      <div 
        ref={mapContainerRef} 
        style={{ 
          width: '100%', 
          height: `${height}px`,
          backgroundColor: '#e2e8f0',
          cursor: 'grab'
        }} 
      />

      {/* Map Legend Footer */}
      <div style={{
        padding: '8px 16px',
        backgroundColor: '#ffffff',
        borderTop: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.74rem',
        color: '#64748b',
        flexWrap: 'wrap',
        gap: '10px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontWeight: 700, color: '#334155' }}>Hướng dẫn thao tác:</span>
          <span>🖱️ <strong>Cuộn chuột</strong> để phóng to / thu nhỏ</span>
          <span>🖐️ <strong>Giữ & Kéo chuột</strong> để di chuyển bản đồ</span>
          <span>📍 <strong>Nhấp vào trạm</strong> để xem chi tiết lưu lượng</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e' }}></span>
            Pha Xanh (Green)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444' }}></span>
            Ùn tắc (&gt;10 xe)
          </span>
        </div>
      </div>

      {/* Marker Pulse CSS Animation Keyframes */}
      <style>{`
        @keyframes marker-pulse {
          0% {
            transform: scale(0.9);
            opacity: 0.9;
          }
          70% {
            transform: scale(1.6);
            opacity: 0;
          }
          100% {
            transform: scale(1.6);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}
