import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import TopologyMap from '../components/TopologyMap';
import PhaseIndicator from '../components/PhaseIndicator';
import MqttPacketInspector from '../components/MqttPacketInspector';
import { useWebSocket } from '../hooks/useWebSocket';
import { useActiveScenario, MAP_ONLY_SCENARIOS } from '../hooks/useActiveScenario';
import { useLanguage } from '../hooks/useLanguage';
import { 
  Activity, Car, Gauge, Radio, Search, ChevronRight, ShieldCheck, 
  Terminal, FileText, CheckCircle, AlertTriangle, ChevronDown, ChevronUp,
  Pause, Play, Filter, Layers, Cpu, Server, ExternalLink, HelpCircle
} from 'lucide-react';

// Queue above 12 vehicles or any status other than ONLINE (camera fault, heartbeat lost, fallback, ...)
const ATTENTION_QUEUE_VEH = 12;
const needsAttention = (d) => (d.total_queue || 0) > ATTENTION_QUEUE_VEH || Boolean(d.status && d.status !== 'ONLINE');

// OSM-derived node IDs (e.g. "cluster_2938641203_366431367_5750600582") blow out the station
// row layout at full length; show a short form and keep the full ID in a title tooltip.
const shortNodeId = (id) => (id && id.length > 16 ? `${id.slice(0, 10)}…${id.slice(-4)}` : id);

const SCENARIO_PRETTY_NAMES = {
  en: {
    four_intersection_v1: 'Four Intersection V1 (4 Stations - SUMO Standard)',
    tabletop_5nut_v1: 'Tabletop 5-Nut V1 (5 Stations - Lab Tabletop)',
    cologne8: 'Cologne 8-Junction (8 Stations - Urban Grid)',
    cologne: 'Cologne Urban Grid (Cologne City Network)',
    grid4x4: 'Grid 4x4 Corridor (16 Stations - Grid Corridor)',
    grid16: 'Grid 16-Junction (16 Stations - Grid Network)',
    hcm_realworld_v1: 'HCM Realworld V1 (793 Cameras HCMC)',
    three_way_junction_v1: 'Three Way Junction V1 (3 Stations - Y-Junction)',
    multi_phase_v1: 'Multi Phase V1 (5 Stations - Complex Multi-Phase)',
    four_intersection_rl_v1: 'Four Intersection RL (4 Stations - RL Training)'
  },
  vi: {
    four_intersection_v1: 'Four Intersection V1 (4 Nút - Chuẩn SUMO)',
    tabletop_5nut_v1: 'Tabletop 5-Nut V1 (5 Nút - Sa Bàn Lab)',
    cologne8: 'Cologne 8-Junction (8 Nút - Đô Thị)',
    cologne: 'Cologne Urban Grid (Mạng Cologne Đô Thị)',
    grid4x4: 'Grid 4x4 Corridor (16 Nút - Hành Lang Lưới)',
    grid16: 'Grid 16-Junction (16 Nút - Lưới Hành Lang)',
    hcm_realworld_v1: 'HCM Realworld V1 (793 Camera TP.HCM)',
    three_way_junction_v1: 'Three Way Junction V1 (3 Nút - Ngã Ba Chữ Y)',
    multi_phase_v1: 'Multi Phase V1 (5 Nút - Đa Pha Phức Hợp)',
    four_intersection_rl_v1: 'Four Intersection RL (4 Nút - Huấn Luyện RL)'
  }
};

const COPY = {
  en: {
    liveControl: 'LIVE CONTROL',
    title: 'Traffic Operations Center Overview',
    subtitle: 'Real-time topology surveillance, queue pressure analysis, and certified safety compliance.',
    opsCenter: 'Operations Center',
    engDiag: 'Engineering Diagnostics',
    backToOps: '← Back to Operations Center',
    wsLive: 'WebSocket Live (<50ms)',
    pollingFallback: 'Polling Fallback',
    mapLabel: 'Map:',
    stationsLabel: 'stations',
    totalQueue: 'Total Network Queue',
    acrossApproaches: 'Across all approaches',
    meanDelay: 'Mean Network Delay',
    actuatorClearance: 'Actuator clearance: 5s',
    syncing: 'SYNCING',
    throughput: 'Network Throughput',
    noReports: 'No system reports data yet',
    activeAlerts: 'Active Alerts & Safety',
    allNormal: 'All Nominal',
    attentionNeeded: 'Attention Needed',
    hardwareInterlock: 'Hardware Interlock',
    displayMode: 'Display Mode:',
    splitLayout: 'Split (Map + Stations)',
    mapOnlyLayout: '🗺️ Fullscreen SUMO Map',
    listOnlyLayout: '📋 Station List',
    coordMatch: '1:1 Coordinate match with SUMO-GUI (10.882°N, 106.822°E - HCMC)',
    mapTitle: (count) => `SUMO Traffic Network Map (${count} Junctions)`,
    mapSubtitle: 'Coordinates and edges extracted directly from SUMO C++ Engine; click any station for diagnostics',
    syncingGraph: 'Syncing graph...',
    junctionMonitoring: 'Junction Monitoring',
    stationsCount: (filtered, total) => `${filtered} of ${total} stations`,
    allFilter: (count) => `All (${count})`,
    attentionFilter: (count) => `Attention (${count})`,
    normalFilter: (count) => `Normal (${count})`,
    filterPlaceholder: 'Filter by junction ID (e.g. J1, A0)...',
    viewDiagnostics: 'View Detailed Diagnostics',
    systemLogsTitle: 'System Event & Execution Stream',
    eventsCount: (count) => `${count} Events · Click to expand logs`,
    eventsCountExpanded: (count) => `${count} Events · Click to collapse`,
    filterAll: 'All',
    filterControl: 'Control',
    filterActuator: 'Actuator',
    filterWarn: 'Warnings',
    highlightBtn: (nodeId) => `Highlight ${nodeId}`,
    noLogsMatch: 'No logs match this filter'
  },
  vi: {
    liveControl: 'ĐIỀU KHIỂN TRỰC TIẾP',
    title: 'Tổng Quan Trung Tâm Điều Hành Giao Thông',
    subtitle: 'Giám sát cấu trúc liên kết thời gian thực, phân tích áp lực hàng chờ và tuân thủ an toàn chuẩn hóa.',
    opsCenter: 'Trung Tâm Vận Hành',
    engDiag: 'Chẩn Đoán Kỹ Thuật',
    backToOps: '← Quay Lại Trung Tâm Điều Hành',
    wsLive: 'WebSocket Trực Tiếp (<50ms)',
    pollingFallback: 'Dự phòng Polling',
    mapLabel: 'Bản đồ:',
    stationsLabel: 'trạm',
    totalQueue: 'Tổng Hàng Chờ Mạng Lưới',
    acrossApproaches: 'Trên tất cả các luồng nhánh',
    meanDelay: 'Độ Trễ Trung Bình Mạng',
    actuatorClearance: 'Thời gian giải phóng: 5s',
    syncing: 'ĐANG ĐỒNG BỘ',
    throughput: 'Thông Lượng Mạng Lưới',
    noReports: 'Chưa có dữ liệu system reports',
    activeAlerts: 'Cảnh Báo & An Toàn',
    allNormal: 'Tất cả bình thường',
    attentionNeeded: 'Cần chú ý',
    hardwareInterlock: 'Interlock Phần Cứng',
    displayMode: 'Chế độ hiển thị:',
    splitLayout: 'Chia đôi (Bản đồ + Trạm)',
    mapOnlyLayout: '🗺️ Bản đồ SUMO toàn màn hình',
    listOnlyLayout: '📋 Danh sách trạm',
    coordMatch: 'Khớp tọa độ 1:1 với SUMO-GUI (10.882°N, 106.822°E - TP.HCM)',
    mapTitle: (count) => `Bản đồ Mạng lưới Giao thông SUMO (${count} Nút Giao)`,
    mapSubtitle: 'Tọa độ và cung đường trích xuất trực tiếp từ SUMO C++ Engine; nhấp vào trạm để xem chi tiết',
    syncingGraph: 'Đang đồng bộ đồ thị...',
    junctionMonitoring: 'Danh Sách Giám Sát Nút Giao',
    stationsCount: (filtered, total) => `${filtered} / ${total} trạm`,
    allFilter: (count) => `Tất cả (${count})`,
    attentionFilter: (count) => `Cần chú ý (${count})`,
    normalFilter: (count) => `Bình thường (${count})`,
    filterPlaceholder: 'Lọc nhanh ID nút (vd: J1, A0)...',
    viewDiagnostics: 'Xem Chi Tiết Chẩn Đoán',
    systemLogsTitle: 'Dòng Sự Kiện & Lệnh Thực Thi Hệ Thống',
    eventsCount: (count) => `${count} Sự kiện · Nhấp để mở rộng nhật ký`,
    eventsCountExpanded: (count) => `${count} Sự kiện · Nhấp để thu gọn`,
    filterAll: 'Tất cả',
    filterControl: 'Lệnh điều khiển',
    filterActuator: 'Phần cứng',
    filterWarn: 'Cảnh báo',
    highlightBtn: (nodeId) => `Định vị ${nodeId}`,
    noLogsMatch: 'Không có nhật ký nào khớp bộ lọc'
  }
};

// System Log timestamps: the API formats "timestamp" with the SERVER/container's own local clock
// (often UTC in Docker, unrelated to the operator's timezone), so it can look hours off on screen.
// timestamp_ms is an unambiguous UTC epoch; format it with the browser's own timezone instead.
// "timestamp" is only a fallback for the rare log entry that predates this field.
const formatLogTime = (log) => (
  log.timestamp_ms
    ? new Date(log.timestamp_ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : (log.timestamp || '--:--:--')
);

const NetworkOverview = () => {
  const navigate = useNavigate();
  const [lang] = useLanguage();
  const isVi = lang === 'vi';
  const t = COPY[lang] || COPY.en;
  const prettyNames = SCENARIO_PRETTY_NAMES[lang] || SCENARIO_PRETTY_NAMES.en;

  const [scenarios, setScenarios] = useState([
    { scenario_id: 'four_intersection_v1', name: 'Four Intersection V1', has_sumo_config: true, total_nodes: 4 },
    { scenario_id: 'cologne8', name: 'Cologne 8-Junction SUMO', has_sumo_config: true, total_nodes: 8 },
    { scenario_id: 'grid4x4', name: 'Grid 4x4 Corridor SUMO', has_sumo_config: true, total_nodes: 16 },
    { scenario_id: 'three_way_junction_v1', name: 'Three Way Junction V1', has_sumo_config: false, total_nodes: 3 },
    { scenario_id: 'multi_phase_v1', name: 'Multi Phase V1', has_sumo_config: false, total_nodes: 5 }
  ]);

  const [activeScenarioId, setActiveScenarioId] = useActiveScenario();

  const [topology, setTopology] = useState(null);
  const [nodes, setNodes] = useState({});
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [stationFilter, setStationFilter] = useState('ALL'); // 'ALL', 'ATTENTION', 'NORMAL'
  const [loading, setLoading] = useState(false);
  const [activeController, setActiveController] = useState('max_pressure');
  const [sourceMode, setSourceMode] = useState('system');
  
  // Dashboard View Mode: 'OPERATIONS' (Traffic Operations Center) or 'DIAGNOSTICS' (Engineering)
  const [viewMode, setViewMode] = useState('OPERATIONS');
  // Layout mode: 'SPLIT' (Map + List), 'MAP_ONLY' (Fullscreen Map), 'LIST_ONLY' (Fullscreen List)
  const [viewLayout, setViewLayout] = useState('SPLIT');

  // Collapsible Log Drawer State
  const [isLogExpanded, setIsLogExpanded] = useState(false);
  const [streamViewMode, setStreamViewMode] = useState('LOGS'); // 'LOGS' | 'MQTT'
  const [logFilter, setLogFilter] = useState('ALL'); // 'ALL', 'WARN', 'CONTROL', 'ACTUATOR'
  const [logSearch, setLogSearch] = useState('');
  const [isStreamPaused, setIsStreamPaused] = useState(false);

  // null until the first successful /api/v1/system/reports fetch: the KPI cards show '—' rather than
  // inventing numbers that would look as authoritative as real telemetry.
  const [systemReports, setSystemReports] = useState(null);

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // Fallback REST fetch function
  const fetchLiveStateREST = async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/network/state`);
      const data = await res.json();
      return data;
    } catch {
      return null;
    }
  };

  // WebSocket connection for real-time updates
  const { data: wsData, isConnected: wsConnected } = useWebSocket(
    `${apiBase}/ws/telemetry`,
    fetchLiveStateREST,
    1000
  );

  const formatControllerName = (ctrl) => {
    if (!ctrl) return 'Max-Pressure';
    const mapping = {
      'fixed_time': 'Fixed-Time',
      'max_pressure': 'Max-Pressure',
      'max_queue': 'Max-Queue',
      'edgeflow': 'EdgeFlow AI',
      'presslight_rl': 'PressLight RL',
      'rl': 'RL Agent'
    };
    return mapping[ctrl.toLowerCase()] || ctrl.replace('_', ' ').toUpperCase();
  };

  // 0. Open on the topology the running system uses (API EDGEFLOW_TOPOLOGY), not a stale browser default
  useEffect(() => {
    fetch(`${apiBase}/health`)
      .then(res => res.json())
      .then(data => {
        if (data && data.active_topology) {
          setActiveScenarioId(data.active_topology);
        }
      })
      .catch(() => {});
  }, [apiBase]);

  // 1. Fetch available scenarios
  useEffect(() => {
    fetch(`${apiBase}/api/v1/scenarios`)
      .then(res => res.json())
      .then(data => {
        if (data && data.scenarios && data.scenarios.length > 0) {
          const mapScenarios = data.scenarios.filter(s => !MAP_ONLY_SCENARIOS.includes(s.scenario_id));
          if (mapScenarios.length > 0) setScenarios(mapScenarios);
        }
      })
      .catch(() => {});
  }, [apiBase]);

  // 2. Fetch active topology contract
  useEffect(() => {
    setLoading(true);
    fetch(`${apiBase}/api/v1/topologies/${activeScenarioId}`)
      .then(res => res.json())
      .then(data => {
        setTopology(data);
        if (data && data.nodes) {
          const initialNodes = {};
          data.nodes.forEach(n => {
            const nodeId = n.node_id;
            const phases = n.phases || [];
            const firstPhaseId = phases.length ? phases[0].phase_id : `${nodeId}_PHASE_1`;
            // Placeholder until live state arrives: nothing observed yet, so no speed and no confidence
            initialNodes[nodeId] = {
              node_id: nodeId,
              name: n.name || nodeId,
              street_name: n.street_name || '',
              x: n.x,
              y: n.y,
              current_phase_id: firstPhaseId,
              total_queue: 0,
              speed: 0,
              flow: 0.0,
              occupancy: 0.0,
              confidence: 0,
              source_type: 'system',
              status: 'WAITING_FOR_TELEMETRY',
              approaches: (n.approaches || []).map(appId => ({
                approach_id: appId,
                queue_vehicles: 0,
                flow_veh_per_s: 0,
                mean_speed_mps: 0,
                occupancy_ratio: 0.0,
                confidence: 0.0
              }))
            };
          });
          setNodes(prev => {
            const merged = { ...initialNodes };
            if (prev && Object.keys(prev).length > 0) {
              Object.keys(merged).forEach(k => {
                if (prev[k] && prev[k].status !== 'WAITING_FOR_TELEMETRY') {
                  merged[k] = { ...merged[k], ...prev[k] };
                }
              });
            }
            return merged;
          });
          if (data.nodes.length > 0 && !selectedNodeId) {
            setSelectedNodeId(data.nodes[0].node_id);
          }
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [activeScenarioId, apiBase]);

  // 3. Fetch aggregated system reports
  useEffect(() => {
    const fetchReports = () => {
      if (isStreamPaused) return;
      fetch(`${apiBase}/api/v1/system/reports`)
        .then(res => res.json())
        .then(data => {
          if (data) setSystemReports(data);
        })
        .catch(() => {});
    };
    fetchReports();
    const interval = setInterval(fetchReports, 2500);
    return () => clearInterval(interval);
  }, [apiBase, isStreamPaused]);

  // Handle incoming live telemetry state
  useEffect(() => {
    if (wsData && !isStreamPaused) {
      if (wsData.controller) setActiveController(wsData.controller);
      if (wsData.source_mode) setSourceMode(wsData.source_mode);
      if (wsData.topology_id && wsData.topology_id !== activeScenarioId) {
        setActiveScenarioId(wsData.topology_id);
      }
      if (wsData.nodes && wsData.nodes.length > 0) {
        const updated = {};
        wsData.nodes.forEach(n => {
          const approaches = n.approaches || [];
          const totalQ = approaches.reduce((acc, a) => acc + (a.queue_vehicles || 0), 0);
          const totalF = approaches.reduce((acc, a) => acc + (a.flow_veh_per_s || 0), 0);
          const avgSpd = approaches.length 
            ? (approaches.reduce((acc, a) => acc + (a.mean_speed_mps || 0), 0) / approaches.length)
            : 13.89;
          const avgOcc = approaches.length
            ? (approaches.reduce((acc, a) => acc + (a.occupancy_ratio || 0), 0) / approaches.length) * 100
            : 0.0;
          const avgConf = approaches.length
            ? (approaches.reduce((acc, a) => acc + (a.confidence != null ? a.confidence : 1.0), 0) / approaches.length) * 100
            : 100;

          updated[n.node_id] = {
            node_id: n.node_id,
            name: n.name || n.node_id,
            street_name: n.street_name || '',
            x: n.x,
            y: n.y,
            current_phase_id: n.current_phase_id || `${n.node_id}_PHASE_1`,
            total_queue: Math.round(totalQ * 10) / 10,
            speed: Math.round(avgSpd * 10) / 10,
            flow: Math.round(totalF * 100) / 100,
            occupancy: Math.round(avgOcc * 10) / 10,
            confidence: Math.round(avgConf),
            source_type: n.source_type || 'system',
            status: n.status || 'ONLINE',
            // overall_status collapses SAFE_STOP and HEARTBEAT_LOST into the same "ACTUATOR_FAULT"
            // (intentional, see services/api/main.py); device_health.actuator.status keeps them apart
            // so the overview badge can tell "someone pressed the emergency button" from "device down".
            device_health: n.device_health || null,
            approaches: approaches
          };
        });
        setNodes(updated);
      }
    }
  }, [wsData, isStreamPaused]);

  const handleScenarioChange = (e) => {
    const newId = e.target.value;
    setActiveScenarioId(newId);
    setSelectedNodeId(null);
  };

  const nodeEntries = Object.entries(nodes);
  const totalNodesCount = topology?.nodes?.length || nodeEntries.length;

  // Calculate live aggregate metrics
  const totalQueue = nodeEntries.reduce((acc, [_, d]) => acc + (d.total_queue || 0), 0);
  const avgSpeed = nodeEntries.length 
    ? (nodeEntries.reduce((acc, [_, d]) => acc + (d.speed || 0), 0) / nodeEntries.length).toFixed(1)
    : '13.9';

  // Nodes requiring attention: one rule for the KPI, the tabs, the sort order and the cards. A speed rule
  // (< 5 m/s) was dropped: it was set for real roads, and the tabletop video speeds are always below it.
  const attentionNodes = useMemo(() => nodeEntries.filter(([_, d]) => needsAttention(d)), [nodeEntries]);

  // Priority Sorting: Nodes requiring attention appear FIRST, followed by normal junctions
  const sortedNodes = useMemo(() => {
    return [...nodeEntries].sort((a, b) => {
      const aQueue = a[1].total_queue || 0;
      const bQueue = b[1].total_queue || 0;
      const aAttn = needsAttention(a[1]);
      const bAttn = needsAttention(b[1]);

      if (aAttn && !bAttn) return -1;
      if (!aAttn && bAttn) return 1;
      return bQueue - aQueue; // Highest queue first within same category
    });
  }, [nodeEntries]);

  // Filtered nodes by search and tab
  const filteredNodes = useMemo(() => {
    return sortedNodes.filter(([id, data]) => {
      const matchSearch = id.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          (data.name && data.name.toLowerCase().includes(searchQuery.toLowerCase()));
      if (!matchSearch) return false;

      const isAttn = needsAttention(data);
      if (stationFilter === 'ATTENTION') return isAttn;
      if (stationFilter === 'NORMAL') return !isAttn;
      return true;
    });
  }, [sortedNodes, searchQuery, stationFilter]);

  // Filtered log events
  const filteredLogs = useMemo(() => {
    const rawLogs = systemReports?.recent_system_logs || [];
    return rawLogs.filter(log => {
      const lvl = (log.level || 'INFO').toUpperCase();
      const svc = (log.service || '').toUpperCase();
      const msg = (log.message || '').toLowerCase();

      if (logFilter === 'WARN' && !(lvl.includes('WARN') || lvl.includes('ERR') || lvl.includes('CRIT'))) {
        return false;
      }
      if (logFilter === 'CONTROL' && !svc.includes('CONTROL')) {
        return false;
      }
      if (logFilter === 'ACTUATOR' && !svc.includes('ACTUATOR')) {
        return false;
      }

      if (logSearch) {
        const query = logSearch.toLowerCase();
        return msg.includes(query) || svc.toLowerCase().includes(query) || (log.timestamp || '').includes(query);
      }
      return true;
    });
  }, [systemReports?.recent_system_logs, logFilter, logSearch]);

  const activeAlertsCount = attentionNodes.length;

  return (
    <div className="page-container">
      {/* 1. Command Center Sub-Header Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px',
        flexWrap: 'wrap',
        gap: '16px',
        paddingBottom: '16px',
        borderBottom: '1px solid #e2e8f0'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <h2 style={{ fontSize: '1.45rem', fontWeight: 800, margin: 0, color: '#0f172a' }}>
              {t.title}
            </h2>
            <span style={{
              backgroundColor: '#ecfdf5',
              color: '#065f46',
              border: '1px solid #a7f3d0',
              padding: '2px 8px',
              borderRadius: '9999px',
              fontSize: '0.72rem',
              fontWeight: 700
            }}>
              {t.liveControl}
            </span>
          </div>
          <p style={{ color: '#64748b', margin: 0, fontSize: '0.85rem' }}>
            {t.subtitle}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* View Mode Toggle: Operations vs Diagnostics */}
          <div style={{
            display: 'flex',
            backgroundColor: '#f1f5f9',
            padding: '3px',
            borderRadius: '8px',
            border: '1px solid #e2e8f0'
          }}>
            <button
              onClick={() => setViewMode('OPERATIONS')}
              style={{
                border: 'none',
                padding: '5px 12px',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
                backgroundColor: viewMode === 'OPERATIONS' ? '#ffffff' : 'transparent',
                color: viewMode === 'OPERATIONS' ? '#0284c7' : '#64748b',
                boxShadow: viewMode === 'OPERATIONS' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none'
              }}
            >
              {t.opsCenter}
            </button>
            <button
              onClick={() => setViewMode('DIAGNOSTICS')}
              style={{
                border: 'none',
                padding: '5px 12px',
                borderRadius: '6px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
                backgroundColor: viewMode === 'DIAGNOSTICS' ? '#ffffff' : 'transparent',
                color: viewMode === 'DIAGNOSTICS' ? '#0284c7' : '#64748b',
                boxShadow: viewMode === 'DIAGNOSTICS' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none'
              }}
            >
              {t.engDiag}
            </button>
          </div>

          {/* Connection Status Pill */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: wsConnected ? '#f0fdf4' : '#fffbeb',
            border: `1px solid ${wsConnected ? '#86efac' : '#fde68a'}`,
            padding: '6px 12px',
            borderRadius: '20px',
            fontSize: '0.76rem',
            fontWeight: 700,
            color: wsConnected ? '#15803d' : '#b45309'
          }}>
            <span 
              className={wsConnected ? 'pulse-indicator' : ''}
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: wsConnected ? '#22c55e' : '#f59e0b',
                display: 'inline-block'
              }}
            />
            {wsConnected ? t.wsLive : t.pollingFallback}
          </div>

          {/* Scenario Selector Dropdown */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#ffffff',
            border: '1px solid #cbd5e1',
            borderRadius: '8px',
            padding: '5px 12px',
            boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
          }}>
            <Layers size={14} color="#0284c7" />
            <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600 }}>{t.mapLabel}</span>
            <select
              value={activeScenarioId}
              onChange={handleScenarioChange}
              style={{
                border: 'none',
                backgroundColor: 'transparent',
                fontSize: '0.86rem',
                fontWeight: 700,
                color: '#0f172a',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {scenarios.map((sc) => (
                <option key={sc.scenario_id} value={sc.scenario_id}>
                  {prettyNames[sc.scenario_id] || `${sc.name || sc.scenario_id} (${sc.total_nodes || '?'} ${t.stationsLabel})`}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 2. Top Metric Cards Row (Clean, High Context, Standardized Units) */}
      <div className="grid-cols-4" style={{ marginBottom: '20px' }}>
        {/* Card 1: Total Network Queue */}
        <div className="card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>
              {t.totalQueue}
            </span>
            <div style={{ backgroundColor: 'rgba(2, 132, 199, 0.1)', padding: '8px', borderRadius: '8px' }}>
              <Car size={18} color="#0284c7" />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', marginBottom: '4px' }}>
            {Math.round(totalQueue * 10) / 10} <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#64748b' }}>{isVi ? 'xe' : 'veh'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem' }}>
            <span style={{
              padding: '2px 6px',
              borderRadius: '4px',
              fontWeight: 700,
              backgroundColor: totalQueue > 40 ? '#fee2e2' : totalQueue > 20 ? '#fef9c3' : '#dcfce7',
              color: totalQueue > 40 ? '#b91c1c' : totalQueue > 20 ? '#a16207' : '#15803d'
            }}>
              {totalQueue > 40 ? (isVi ? 'ÙN Ứ' : 'CONGESTED') : totalQueue > 20 ? (isVi ? 'TRUNG BÌNH' : 'MODERATE') : (isVi ? 'TỐI ƯU' : 'OPTIMAL')}
            </span>
            <span style={{ color: '#64748b' }}>{t.acrossApproaches}</span>
          </div>
        </div>

        {/* Card 2: Mean Network Delay */}
        <div className="card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>
              {t.meanDelay}
            </span>
            <div style={{ backgroundColor: 'rgba(22, 163, 74, 0.1)', padding: '8px', borderRadius: '8px' }}>
              <Gauge size={18} color="#16a34a" />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', marginBottom: '4px' }}>
            {systemReports ? systemReports.mean_network_wait_time_s : '—'} <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#64748b' }}>{isVi ? 'giây' : 'sec'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem' }}>
            <span style={{
              padding: '2px 6px',
              borderRadius: '4px',
              fontWeight: 700,
              backgroundColor: !systemReports ? '#f1f5f9' : systemReports.mean_network_wait_time_s > 15 ? '#fef9c3' : '#dcfce7',
              color: !systemReports ? '#64748b' : systemReports.mean_network_wait_time_s > 15 ? '#a16207' : '#15803d'
            }}>
              {!systemReports ? t.syncing : systemReports.mean_network_wait_time_s > 15 ? (isVi ? 'HƠI CAO' : 'ELEVATED') : (isVi ? 'MỤC TIÊU <15s' : 'TARGET <15s')}
            </span>
            <span style={{ color: '#64748b' }}>{t.actuatorClearance}</span>
          </div>
        </div>

        {/* Card 3: Network Throughput (Vehicles Per Minute) */}
        <div className="card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>
              {t.throughput}
            </span>
            <div style={{ backgroundColor: 'rgba(202, 138, 4, 0.1)', padding: '8px', borderRadius: '8px' }}>
              <Activity size={18} color="#ca8a04" />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', marginBottom: '4px' }}>
            {systemReports ? systemReports.total_throughput_veh_per_min : '—'} <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#ca8a04' }}>{isVi ? 'xe/phút' : 'veh/min'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', color: '#64748b' }}>
            <span title="Calculated as sum of all lane flow rates × 60s" style={{ textDecoration: 'underline dotted', cursor: 'help' }}>
              {systemReports ? `~${Math.round(systemReports.total_throughput_veh_per_min * 60)} ${isVi ? 'xe/h tương đương' : 'veh/h equivalent'}` : t.noReports}
            </span>
          </div>
        </div>

        {/* Card 4: Active Alerts & Safety Assurance */}
        <div className="card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>
              {t.activeAlerts}
            </span>
            <div style={{ backgroundColor: 'rgba(147, 51, 234, 0.1)', padding: '8px', borderRadius: '8px' }}>
              <ShieldCheck size={18} color="#9333ea" />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '4px' }}>
            <div style={{ 
              fontSize: '1.6rem', 
              fontWeight: 800, 
              color: activeAlertsCount > 0 ? '#dc2626' : '#16a34a' 
            }}>
              {activeAlertsCount}
            </div>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: activeAlertsCount > 0 ? '#b91c1c' : '#15803d' }}>
              {activeAlertsCount === 0 ? t.allNormal : t.attentionNeeded}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem' }}>
            <span style={{
              padding: '2px 6px',
              borderRadius: '4px',
              fontWeight: 700,
              backgroundColor: '#ecfdf5',
              color: '#065f46',
              border: '1px solid #a7f3d0'
            }}>
              {t.hardwareInterlock}
            </span>
            <span title="Switches green only after yellow 3 s + all-red 2 s clearance" style={{ color: '#64748b', cursor: 'help' }}>
              (Y 3s + all-red 2s)
            </span>
          </div>
        </div>
      </div>

      {/* 3. Main Operational View vs Engineering Diagnostics Toggle */}
      {viewMode === 'OPERATIONS' ? (
        <>
          {/* Main Operational View Controls: Layout Switcher & Status */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155' }}>{t.displayMode}</span>
          <div style={{ display: 'flex', backgroundColor: '#e2e8f0', padding: '2px', borderRadius: '7px' }}>
            <button
              onClick={() => setViewLayout('SPLIT')}
              style={{
                border: 'none',
                padding: '5px 12px',
                borderRadius: '5px',
                fontSize: '0.76rem',
                fontWeight: 700,
                cursor: 'pointer',
                backgroundColor: viewLayout === 'SPLIT' ? '#ffffff' : 'transparent',
                color: viewLayout === 'SPLIT' ? '#0284c7' : '#64748b',
                boxShadow: viewLayout === 'SPLIT' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
              }}
            >
              {t.splitLayout}
            </button>
            <button
              onClick={() => setViewLayout('MAP_ONLY')}
              style={{
                border: 'none',
                padding: '5px 12px',
                borderRadius: '5px',
                fontSize: '0.76rem',
                fontWeight: 700,
                cursor: 'pointer',
                backgroundColor: viewLayout === 'MAP_ONLY' ? '#ffffff' : 'transparent',
                color: viewLayout === 'MAP_ONLY' ? '#0284c7' : '#64748b',
                boxShadow: viewLayout === 'MAP_ONLY' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
              }}
            >
              {t.mapOnlyLayout}
            </button>
            <button
              onClick={() => setViewLayout('LIST_ONLY')}
              style={{
                border: 'none',
                padding: '5px 12px',
                borderRadius: '5px',
                fontSize: '0.76rem',
                fontWeight: 700,
                cursor: 'pointer',
                backgroundColor: viewLayout === 'LIST_ONLY' ? '#ffffff' : 'transparent',
                color: viewLayout === 'LIST_ONLY' ? '#0284c7' : '#64748b',
                boxShadow: viewLayout === 'LIST_ONLY' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none'
              }}
            >
              {t.listOnlyLayout}
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            fontSize: '0.72rem',
            padding: '3px 8px',
            borderRadius: '5px',
            backgroundColor: '#f0fdf4',
            color: '#16a34a',
            fontWeight: 700,
            border: '1px solid #bbf7d0',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px'
          }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#22c55e' }}></span>
            {t.coordMatch}
          </span>
        </div>
      </div>

      {/* Main Operational View: Dynamic Layout based on viewLayout */}
      <div 
        className="overview-main-grid"
        style={{
          gridTemplateColumns: viewLayout === 'MAP_ONLY' ? '1fr' : viewLayout === 'LIST_ONLY' ? '1fr' : '1.62fr 1fr'
        }}
      >
        {/* Column 1: Enhanced Topology Map */}
        {(viewLayout === 'SPLIT' || viewLayout === 'MAP_ONLY') && (
          <div className="card" style={{ padding: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', margin: '0 0 2px 0', fontWeight: 800, color: '#0f172a' }}>
                  {t.mapTitle(totalNodesCount)}
                </h3>
                <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                  {t.mapSubtitle}
                </span>
              </div>
              {loading && <span style={{ fontSize: '0.8rem', color: '#0284c7', fontWeight: 600 }}>{t.syncingGraph}</span>}
            </div>

            <TopologyMap
              nodesData={nodes}
              topology={topology}
              selectedNodeId={selectedNodeId}
              onSelectNode={(nodeId) => setSelectedNodeId(nodeId)}
              onNavigateDetail={(nodeId) => navigate(`/intersections/${nodeId}`)}
              height={viewLayout === 'MAP_ONLY' ? 680 : 540}
            />
          </div>
        )}

        {/* Column 2: Prioritized Intersection Attention List */}
        {(viewLayout === 'SPLIT' || viewLayout === 'LIST_ONLY') && (
          <div className="card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', height: viewLayout === 'LIST_ONLY' ? 'auto' : '620px' }}>
            {/* Station List Header & Search */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                  {t.junctionMonitoring}
                </h3>
                <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>
                {t.stationsCount(filteredNodes.length, totalNodesCount)}
              </span>
            </div>

            {/* Filter Pills & Search Bar */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  onClick={() => setStationFilter('ALL')}
                  style={{
                    border: 'none',
                    padding: '3px 8px',
                    borderRadius: '5px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    backgroundColor: stationFilter === 'ALL' ? '#0284c7' : '#f1f5f9',
                    color: stationFilter === 'ALL' ? '#ffffff' : '#64748b'
                  }}
                >
                  {t.allFilter(nodeEntries.length)}
                </button>
                <button
                  onClick={() => setStationFilter('ATTENTION')}
                  style={{
                    border: 'none',
                    padding: '3px 8px',
                    borderRadius: '5px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    backgroundColor: stationFilter === 'ATTENTION' ? '#dc2626' : '#fef2f2',
                    color: stationFilter === 'ATTENTION' ? '#ffffff' : '#b91c1c'
                  }}
                >
                  {t.attentionFilter(attentionNodes.length)}
                </button>
                <button
                  onClick={() => setStationFilter('NORMAL')}
                  style={{
                    border: 'none',
                    padding: '3px 8px',
                    borderRadius: '5px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    backgroundColor: stationFilter === 'NORMAL' ? '#16a34a' : '#f0fdf4',
                    color: stationFilter === 'NORMAL' ? '#ffffff' : '#15803d'
                  }}
                >
                  {t.normalFilter(nodeEntries.length - attentionNodes.length)}
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '6px 10px' }}>
                <Search size={14} color="#94a3b8" />
                <input
                  type="text"
                  placeholder={t.filterPlaceholder}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ border: 'none', backgroundColor: 'transparent', fontSize: '0.78rem', width: '100%', outline: 'none' }}
                />
              </div>
            </div>
          </div>

          {/* Scrollable Prioritized Station Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', flex: 1, paddingRight: '4px' }}>
            {filteredNodes.length === 0 && (
              <div style={{ textAlign: 'center', padding: '30px 10px', color: '#94a3b8', fontSize: '0.82rem' }}>
                No junctions match the current filter.
              </div>
            )}

            {filteredNodes.map(([nodeId, data]) => {
              const isSelected = selectedNodeId === nodeId;
              const isAttn = needsAttention(data);

              return (
                <div
                  key={nodeId}
                  onClick={() => setSelectedNodeId(nodeId)}
                  style={{
                    backgroundColor: isSelected ? '#f0f9ff' : '#ffffff',
                    border: `1.5px solid ${isSelected ? '#0284c7' : isAttn ? '#fca5a5' : '#e2e8f0'}`,
                    borderRadius: '8px',
                    padding: '10px 12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? '0 2px 6px rgba(2, 132, 199, 0.15)' : '0 1px 2px rgba(0,0,0,0.02)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span title={nodeId} style={{ fontWeight: 800, fontSize: '0.88rem', color: isSelected ? '#0284c7' : '#0f172a', fontFamily: 'JetBrains Mono, monospace' }}>
                          {isVi ? 'Trạm' : 'Station'} {shortNodeId(nodeId)}
                        </span>
                        
                        {/* Health Status */}
                        {data.status === 'WAITING_FOR_TELEMETRY' ? (
                          <span className="badge badge-yellow" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>WAITING</span>
                        ) : data.status === 'SIGNAL_LOST' ? (
                          <span className="badge badge-red" style={{ fontSize: '0.65rem', padding: '1px 6px', backgroundColor: '#fee2e2', color: '#b91c1c' }}>SIGNAL LOST</span>
                        ) : data.status === 'CAMERA_FAULT' ? (
                          <span className="badge badge-red" style={{ fontSize: '0.65rem', padding: '1px 6px', backgroundColor: '#fee2e2', color: '#b91c1c' }}>CAM FAULT</span>
                        ) : data.device_health?.actuator?.status === 'SAFE_STOP' ? (
                          // Deliberate operator action on the board, not a device malfunction --
                          // must look different from ACTUATOR ERR (heartbeat lost) below.
                          <span title="Nút dừng khẩn cấp trên board đang được nhấn" className="badge" style={{ fontSize: '0.65rem', padding: '1px 6px', backgroundColor: '#fef3c7', color: '#92400e', fontWeight: 800 }}>🛑 SAFE-STOP</span>
                        ) : data.status === 'ACTUATOR_FAULT' ? (
                          <span className="badge badge-red" style={{ fontSize: '0.65rem', padding: '1px 6px', backgroundColor: '#fee2e2', color: '#b91c1c' }}>ACTUATOR ERR</span>
                        ) : data.status === 'FALLBACK' ? (
                          <span className="badge badge-yellow" title="Device has had no command for > 5 s: fixed 15 s/phase cycle" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>FALLBACK 15s</span>
                        ) : (
                          <span className="badge badge-green" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>ONLINE</span>
                        )}

                        {/* Congestion Advisory Badge */}
                        {isAttn && (
                          <span style={{
                            backgroundColor: '#fee2e2',
                            color: '#b91c1c',
                            fontSize: '0.65rem',
                            fontWeight: 800,
                            padding: '1px 6px',
                            borderRadius: '4px'
                          }}>
                            ATTENTION
                          </span>
                        )}
                      </div>

                      {/* Real Street Name mapping from OpenStreetMap */}
                      {data.street_name && (
                        <span style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600 }}>
                          📍 {data.street_name}
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <PhaseIndicator
                        activePhase={data.current_phase_id}
                        state="GREEN"
                        compact
                        safeStop={data.device_health?.actuator?.status === 'SAFE_STOP'}
                      />
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/intersections/${nodeId}`);
                        }}
                        title={t.viewDiagnostics}
                        style={{
                          backgroundColor: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          padding: '2px',
                          color: '#94a3b8'
                        }}
                      >
                        <ChevronRight size={16} />
                      </button>
                    </div>
                  </div>

                  {/* Operational Telemetry Metrics */}
                  <div style={{ display: 'flex', gap: '12px', fontSize: '0.74rem', color: '#475569' }}>
                    <span>
                      {isVi ? 'Hàng chờ: ' : 'Queue: '}<strong style={{ color: (data.total_queue || 0) > 12 ? '#dc2626' : '#0f172a' }}>
                        {data.total_queue || 0}
                      </strong> {isVi ? 'xe' : 'veh'}
                    </span>
                    <span>
                      {isVi ? 'Tốc độ: ' : 'Speed: '}<strong>{data.speed != null ? data.speed : 13.9}</strong> m/s
                    </span>
                    <span>
                      {isVi ? 'Lưu lượng: ' : 'Flow: '}<strong>{data.flow || 0.0}</strong> veh/s
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      </div>

      {/* 4. Collapsible Event & Execution Stream Panel */}
      <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
        {/* Panel Header & Toggle */}
        <div 
          onClick={() => setIsLogExpanded(!isLogExpanded)}
          style={{
            padding: '12px 18px',
            backgroundColor: '#ffffff',
            borderBottom: isLogExpanded ? '1px solid #e2e8f0' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            userSelect: 'none',
            flexWrap: 'wrap',
            gap: '10px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {streamViewMode === 'MQTT' ? (
                <Radio size={18} color="#0284c7" />
              ) : (
                <Terminal size={18} color="#0284c7" />
              )}
              <h3 style={{ fontSize: '0.95rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>
                {streamViewMode === 'MQTT'
                  ? (isVi ? 'Gói Tin Trạng Thái MQTT (Trực Tiếp)' : 'Live MQTT Status Packets')
                  : t.systemLogsTitle}
              </h3>
            </div>

            {/* Mode Switcher Tabs */}
            <div 
              onClick={(e) => e.stopPropagation()} 
              style={{ display: 'flex', gap: '4px', backgroundColor: '#f1f5f9', padding: '3px', borderRadius: '6px' }}
            >
              <button
                onClick={() => {
                  setStreamViewMode('LOGS');
                  setIsLogExpanded(true);
                }}
                style={{
                  border: 'none',
                  padding: '3px 10px',
                  borderRadius: '4px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: streamViewMode === 'LOGS' ? '#ffffff' : 'transparent',
                  color: streamViewMode === 'LOGS' ? '#0284c7' : '#64748b',
                  boxShadow: streamViewMode === 'LOGS' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'
                }}
              >
                📋 {isVi ? 'Nhật Ký Thực Thi' : 'System Logs'} ({filteredLogs.length})
              </button>
              <button
                onClick={() => {
                  setStreamViewMode('MQTT');
                  setIsLogExpanded(true);
                }}
                style={{
                  border: 'none',
                  padding: '3px 10px',
                  borderRadius: '4px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: streamViewMode === 'MQTT' ? '#0284c7' : 'transparent',
                  color: streamViewMode === 'MQTT' ? '#ffffff' : '#64748b',
                  boxShadow: streamViewMode === 'MQTT' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'
                }}
              >
                📡 {isVi ? 'Gói Tin MQTT (Live)' : 'MQTT Packets (Live)'}
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              {isLogExpanded ? (isVi ? 'Nhấp để thu gọn' : 'Click to collapse drawer') : (isVi ? 'Nhấp để mở rộng' : 'Click to expand drawer')}
            </span>
            <button
              style={{
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                color: '#64748b'
              }}
            >
              {isLogExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
          </div>
        </div>

        {/* Collapsible Content */}
        {isLogExpanded && (
          <div style={{ padding: streamViewMode === 'MQTT' ? '0' : '14px 18px', backgroundColor: '#ffffff' }}>
            {streamViewMode === 'MQTT' ? (
              <MqttPacketInspector showHeader={true} maxHeight="320px" pollIntervalMs={1500} />
            ) : (
              <>
                {/* Filter Toolbar */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    {['ALL', 'WARN', 'CONTROL', 'ACTUATOR'].map((f) => (
                      <button
                        key={f}
                        onClick={() => setLogFilter(f)}
                        style={{
                          border: 'none',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                          backgroundColor: logFilter === f ? '#0284c7' : '#f1f5f9',
                          color: logFilter === f ? '#ffffff' : '#64748b'
                        }}
                      >
                        {f}
                      </button>
                    ))}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input
                      type="text"
                      placeholder="Filter logs by keyword..."
                      value={logSearch}
                      onChange={(e) => setLogSearch(e.target.value)}
                      style={{
                        border: '1px solid #cbd5e1',
                        borderRadius: '5px',
                        padding: '3px 8px',
                        fontSize: '0.75rem',
                        outline: 'none',
                        width: '160px'
                      }}
                    />
                    <button
                      onClick={() => setIsStreamPaused(!isStreamPaused)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        backgroundColor: isStreamPaused ? '#fef9c3' : '#f1f5f9',
                        color: isStreamPaused ? '#a16207' : '#64748b',
                        border: '1px solid #cbd5e1',
                        borderRadius: '5px',
                        padding: '3px 8px',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                    >
                      {isStreamPaused ? <Play size={12} /> : <Pause size={12} />}
                      {isStreamPaused ? 'Resume' : 'Pause'}
                    </button>
                  </div>
                </div>

                {/* Dark Terminal Output Stream */}
                <div style={{
                  backgroundColor: '#0f172a',
                  borderRadius: '8px',
                  padding: '14px',
                  color: '#38bdf8',
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: '0.78rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  maxHeight: '220px',
                  overflowY: 'auto'
                }}>
                  {filteredLogs.map((log, idx) => {
                    const lvl = (log.level || 'INFO').toUpperCase();
                    const isWarn = lvl.includes('WARN') || lvl.includes('ERR');
                    const isCtrl = (log.service || '').toUpperCase().includes('CONTROL');

                    // Extract node mention if present to enable map link
                    const nodeMatch = (log.message || '').match(/\b(J[1-8]|A[0-3]|B[0-3]|C[0-3]|D[0-3])\b/);
                    const mentionedNode = nodeMatch ? nodeMatch[1] : null;

                    return (
                      <div key={idx} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                        <span style={{ color: '#64748b', flexShrink: 0 }}>[{formatLogTime(log)}]</span>
                        <span style={{
                          color: isWarn ? '#f87171' : isCtrl ? '#38bdf8' : '#a7f3d0',
                          fontWeight: 700,
                          flexShrink: 0
                        }}>
                          [{log.service ? log.service.toUpperCase() : 'SYSTEM'}]
                        </span>
                        <span style={{ color: isWarn ? '#fca5a5' : '#e2e8f0', flex: 1 }}>
                          {log.message}
                        </span>
                        {mentionedNode && (
                          <button
                            onClick={() => setSelectedNodeId(mentionedNode)}
                            style={{
                              backgroundColor: '#1e293b',
                              color: '#38bdf8',
                              border: '1px solid #334155',
                              borderRadius: '4px',
                              padding: '1px 5px',
                              fontSize: '0.68rem',
                              cursor: 'pointer',
                              flexShrink: 0
                            }}
                          >
                            {t.highlightBtn(mentionedNode)}
                          </button>
                        )}
                      </div>
                    );
                  })}

                  {filteredLogs.length === 0 && (
                    <div style={{ color: '#64748b' }}>{t.noLogsMatch}</div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
      </>
      ) : (
        /* 5. Engineering Diagnostics Mode (When toggled) */
        <div className="card" style={{ border: '2px solid #0284c7', boxShadow: '0 4px 16px rgba(2, 132, 199, 0.12)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Cpu size={22} color="#0284c7" />
              <div>
                <h3 style={{ fontSize: '1.2rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                  {isVi ? 'Chẩn Đoán Kỹ Thuật & Luồng Thông Điệp Microservice' : 'Engineering Diagnostics & Inter-Service Message Pipeline'}
                </h3>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  {isVi ? 'Giám sát luồng thông điệp kiến trúc Microservice EdgeFlow (Vision → Graph-Control → Actuator)' : 'Microservice architecture message stream (Vision → Graph-Control → Actuator)'}
                </span>
              </div>
            </div>
            <button
              onClick={() => setViewMode('OPERATIONS')}
              className="btn btn-primary"
              style={{ padding: '6px 14px', fontSize: '0.8rem', fontWeight: 700 }}
            >
              {t.backToOps}
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '20px' }}>
            <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: 800, fontSize: '0.9rem', color: '#0f172a', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#16a34a' }} />
                Perception Stream (Edge Vision)
              </div>
              <div style={{ fontSize: '0.78rem', color: '#475569', lineHeight: '1.6' }}>
                {isVi ? 'Nguồn:' : 'Source:'} <strong style={{ color: '#0284c7' }}>{sourceMode.toUpperCase()}</strong><br />
                {isVi ? 'Phát sóng:' : 'Broadcasting:'} <strong>{totalNodesCount}</strong> {isVi ? 'nút giao qua MQTT' : 'junctions via MQTT'}<br />
                Topic: <code>edgeflow/v1/telemetry/&lt;node_id&gt;</code><br />
                {isVi ? 'Tần số:' : 'Rate:'} <strong>{isVi ? '1.5s chu kỳ gửi' : '1.5s telemetry interval'}</strong>
              </div>
            </div>

            <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: 800, fontSize: '0.9rem', color: '#0f172a', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#0284c7' }} />
                Graph Controller Decision
              </div>
              <div style={{ fontSize: '0.78rem', color: '#475569', lineHeight: '1.6' }}>
                {isVi ? 'Thuật toán:' : 'Algorithm:'} <strong style={{ color: '#0284c7' }}>{formatControllerName(activeController)}</strong><br />
                {isVi ? 'Chu kỳ tính:' : 'Cycle:'} <strong>5.0s decision epoch</strong><br />
                Command Topic: <code>edgeflow/v1/control/&lt;node_id&gt;/command</code><br />
                Fairness Guard: <strong>{isVi ? 'Bảo vệ chống đói tín hiệu' : 'Starvation prevention guard'}</strong>
              </div>
            </div>

            <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: 800, fontSize: '0.9rem', color: '#0f172a', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#16a34a' }} />
                Actuator Safety Invariants
              </div>
              <div style={{ fontSize: '0.78rem', color: '#475569', lineHeight: '1.6' }}>
                {isVi ? 'Chu trình:' : 'Cycle:'} <strong>{isVi ? 'Xanh → Vàng (3s) → Đỏ (2s) → Xanh' : 'Green → Yellow (3s) → All-Red (2s) → Green'}</strong><br />
                {isVi ? 'Xanh tối thiểu:' : 'Min Green:'} <strong>10.0s</strong> | {isVi ? 'Tối đa:' : 'Max:'} <strong>60.0s</strong><br />
                {isVi ? 'Xung đột pha:' : 'Phase Conflict:'} <strong style={{ color: '#16a34a' }}>{isVi ? '0% (Khóa cứng phần cứng)' : '0% (Hardware locked)'}</strong><br />
                ACK Topic: <code>edgeflow/v1/actuator/&lt;node_id&gt;/ack</code>
              </div>
            </div>
          </div>

          {/* Full Audit Log View in Diagnostics */}
          <div style={{ padding: '16px', backgroundColor: '#0f172a', borderRadius: '10px', color: '#f8fafc', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', borderBottom: '1px solid #334155', paddingBottom: '10px' }}>
              <span style={{ fontWeight: 800, color: '#38bdf8' }}>LIVE AUDIT LOG STREAM ({filteredLogs.length} events)</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                {['ALL', 'WARN', 'CONTROL', 'ACTUATOR'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setLogFilter(f)}
                    style={{
                      backgroundColor: logFilter === f ? '#0284c7' : '#1e293b',
                      color: logFilter === f ? '#ffffff' : '#94a3b8',
                      border: 'none',
                      padding: '3px 10px',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ maxHeight: '350px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {filteredLogs.map((log, index) => (
                <div key={log.id || index} style={{ display: 'flex', gap: '10px', padding: '3px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <span style={{ color: '#64748b' }}>[ {formatLogTime(log)} ]</span>
                  <span style={{ color: log.level === 'WARN' ? '#f59e0b' : log.level === 'ERROR' ? '#ef4444' : '#38bdf8', fontWeight: 700 }}>
                    [ {log.source?.toUpperCase() || 'SYSTEM'} ]
                  </span>
                  <span style={{ flex: 1, color: '#e2e8f0' }}>{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NetworkOverview;
