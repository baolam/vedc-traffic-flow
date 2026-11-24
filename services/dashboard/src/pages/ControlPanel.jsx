import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { 
  Sliders, AlertTriangle, Play, RefreshCw, Cpu, Layers, CheckCircle2, 
  Camera, ShieldAlert, Info, ArrowRight, Zap, Clock, Activity, Lock
} from 'lucide-react';
import { describeOverride, overrideRequestError, OVERRIDE_IN_PROGRESS } from '../utils/manualOverride';
import { useActiveScenario, MAP_ONLY_SCENARIOS } from '../hooks/useActiveScenario';
import { useLanguage } from '../hooks/useLanguage';

const OVERRIDE_FOLLOW_MAX_POLLS = 60; // 1 s each: covers the 25 s wait + 15 s hold

const CONTROLLER_DESCRIPTIONS = {
  en: {
    flow_theory: {
      name: 'FlowTheory (CTM & Anti-Gridlock Gating)',
      tag: 'Recommended · Optimal',
      tagColor: '#16a34a',
      summary: 'Cell Transmission Model (Daganzo) coupled with upstream perimeter gating.',
      howItWorks: 'Predicts downstream spillback via occupancy (Occ > 80%). When downstream links congest, it meters upstream green to prevent gridlock propagation, preserving full network throughput (Zero-Gridlock).'
    },
    max_pressure: {
      name: 'Max-Pressure Controller',
      tag: 'Network Balanced',
      tagColor: '#0284c7',
      summary: 'Distributed network control algorithm minimizing queue differentials.',
      howItWorks: 'Computes pressure W = Queue(in) − Queue(out) for each phase. The phase with maximal net pressure is awarded green, automatically equalizing network-wide queue buildup.'
    },
    max_queue: {
      name: 'Max-Queue Controller (Greedy)',
      tag: 'Local Greedy',
      tagColor: '#d97706',
      summary: 'Greedy heuristic prioritizing the approach with the single longest queue.',
      howItWorks: 'Counts stopped vehicles on each approach and selects the phase with the highest count. Fast response to local surges, but does not consider downstream link capacity.'
    },
    actuated: {
      name: 'Actuated Gap-Out Controller',
      tag: 'Vehicle-Actuated',
      tagColor: '#6366f1',
      summary: 'Dynamic green extension based on real-time vehicle arrival gap-out.',
      howItWorks: 'Extends green as long as vehicles arrive within gap thresholds. If headway exceeds 3s or max green expires, it terminates the phase to eliminate wasted green.'
    },
    fixed_time: {
      name: 'Fixed-Time Controller',
      tag: 'Fixed Baseline',
      tagColor: '#64748b',
      summary: 'Traditional fixed-time cyclic scheduling (control benchmark baseline).',
      howItWorks: 'Cycles through phases on rigid pre-timed intervals (e.g. 30s per phase) regardless of instantaneous real-time traffic conditions.'
    }
  },
  vi: {
    flow_theory: {
      name: 'FlowTheory (CTM & Anti-Gridlock Gating)',
      tag: 'Khuyên Dùng · Tối Ưu Nhất',
      tagColor: '#16a34a',
      summary: 'Mô hình Cell Transmission Model (Daganzo) kết hợp cơ chế kiểm soát cửa vào (gating).',
      howItWorks: 'Dự báo nguy cơ kẹt xe hạ lưu qua độ chiếm dụng (Occ > 80%). Khi hạ lưu quá tải, thuật toán chủ động hãm nhịp xanh phía trước để ngăn chặn tắc nghẽn lan truyền, bảo toàn thông lượng toàn mạng (Zero-Gridlock).'
    },
    max_pressure: {
      name: 'Max-Pressure Controller',
      tag: 'Cân Bằng Đa Hướng',
      tagColor: '#0284c7',
      summary: 'Thuật toán điều khiển mạng lưới phân tán dựa trên chênh lệch áp lực dòng xe.',
      howItWorks: 'Tính áp lực W = Queue(vào) − Queue(ra) cho từng pha đèn. Pha có áp lực ròng lớn nhất được ưu tiên cấp đèn xanh, tự động phân phối đều tải giao thông toàn mạng.'
    },
    max_queue: {
      name: 'Max-Queue Controller (Greedy)',
      tag: 'Tham Lam Cục Bộ',
      tagColor: '#d97706',
      summary: 'Ưu tiên nhánh đường có hàng chờ dài nhất tại nút giao.',
      howItWorks: 'Đếm tổng số xe đang dừng chờ của mỗi pha đèn và chọn pha có số xe lớn nhất. Phản ứng nhanh khi có đột biến cục bộ nhưng không tính đến sức chứa của tuyến đường phía sau.'
    },
    actuated: {
      name: 'Actuated Gap-Out Controller',
      tag: 'Cảm Biến Co Giãn',
      tagColor: '#6366f1',
      summary: 'Điều khiển co giãn thời gian xanh thích ứng theo khoảng cách xe (gap-out).',
      howItWorks: 'Duy trì đèn xanh khi xe liên tục đi qua cảm biến. Khi khoảng trống giữa 2 xe vượt quá 3s (gap-out) hoặc hết thời gian xanh tối đa, đèn chuyển pha để tránh lãng phí thời gian xanh.'
    },
    fixed_time: {
      name: 'Fixed-Time Controller',
      tag: 'Chu Kỳ Cố Định',
      tagColor: '#64748b',
      summary: 'Chu kỳ đèn tín hiệu cố định truyền thống (Baseline đối chứng).',
      howItWorks: 'Luân chuyển các pha đèn theo khoảng thời gian đặt sẵn (ví dụ 30s xanh mỗi hướng), hoàn toàn không phụ thuộc vào mật độ phương tiện thực tế.'
    }
  }
};

const ControlPanel = () => {
  const [lang] = useLanguage();
  const isVi = lang === 'vi';

  const [scenarios, setScenarios] = useState([
    { scenario_id: 'four_intersection_v1', name: 'Four Intersection V1 (4 Nút - SUMO Tiêu Chuẩn)', has_sumo_config: true },
    { scenario_id: 'tabletop_5nut_v1', name: 'Tabletop 5-Nut V1 (5 Nút - Sa Bàn Phòng Lab)', has_sumo_config: true },
    { scenario_id: 'cologne8', name: 'Cologne 8-Junction (8 Nút - Đô Thị Đức)', has_sumo_config: true },
    { scenario_id: 'grid4x4', name: 'Grid 4x4 Corridor (16 Nút - Hành Lang Lưới)', has_sumo_config: true },
    { scenario_id: 'hcm_realworld_v1', name: 'HCM Realworld V1 (793 Camera TP.HCM)', has_sumo_config: false },
    { scenario_id: 'three_way_junction_v1', name: 'Three Way Junction V1 (Ngã Ba Chữ Y)', has_sumo_config: false },
    { scenario_id: 'multi_phase_v1', name: 'Multi Phase V1 (Nút Giao Đa Pha)', has_sumo_config: false }
  ]);

  const [activeScenarioId, setActiveScenarioId] = useActiveScenario();
  const [simEngine] = useState('live_mqtt');
  const [controllerMode, setControllerMode] = useState('max_pressure');
  const [appliedController, setAppliedController] = useState('max_pressure');
  const [overrideViews, setOverrideViews] = useState({}); // nodeId -> banner
  const overrideTimers = useRef({});
  const [configSuccess, setConfigSuccess] = useState(null);

  const [topologyNodes, setTopologyNodes] = useState(['J1', 'J2', 'J3', 'J4']);
  const [nodeDefaultPhase, setNodeDefaultPhase] = useState({});
  const [nodeCurrentPhases, setNodeCurrentPhases] = useState({});
  const [searchQuery, setSearchQuery] = useState('');

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // Load currently running controller policy from API
  useEffect(() => {
    fetch(`${apiBase}/health`)
      .then(res => res.json())
      .then(data => {
        const running = data && (data.applied_controller || data.active_controller);
        if (running && running !== 'edgeflow') {
          setControllerMode(running);
          setAppliedController(running);
        } else {
          setControllerMode('max_pressure');
          setAppliedController('max_pressure');
        }
      })
      .catch(() => {});
  }, [apiBase]);

  // Load scenarios list
  useEffect(() => {
    fetch(`${apiBase}/api/v1/scenarios`)
      .then(res => res.json())
      .then(data => {
        if (data && data.scenarios) {
          setScenarios(data.scenarios);
        }
      })
      .catch(() => {});
  }, [apiBase]);

  // Load topology nodes and phases
  useEffect(() => {
    fetch(`${apiBase}/api/v1/topologies/${activeScenarioId}`)
      .then(res => res.json())
      .then(data => {
        if (data && data.nodes) {
          setTopologyNodes(data.nodes.map(n => n.node_id));
          const defaultPhases = {};
          data.nodes.forEach(n => {
            if (n.phases && n.phases.length > 0) defaultPhases[n.node_id] = n.phases[0].phase_id;
          });
          setNodeDefaultPhase(defaultPhases);
        }
      })
      .catch(() => {
        setTopologyNodes(['J1', 'J2', 'J3', 'J4']);
        setNodeDefaultPhase({});
      });
  }, [activeScenarioId, apiBase]);

  // Poll real-time node current active phases
  useEffect(() => {
    let cancelled = false;
    const fetchPhases = () => {
      fetch(`${apiBase}/api/v1/network/state`)
        .then(res => res.json())
        .then(data => {
          if (cancelled || !data?.nodes) return;
          const phases = {};
          data.nodes.forEach(n => {
            phases[n.node_id] = n.telemetry?.current_phase_id || n.current_phase_id || 'Đang xác định';
          });
          setNodeCurrentPhases(phases);
        })
        .catch(() => {});
    };
    fetchPhases();
    const interval = setInterval(fetchPhases, 2000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [apiBase]);

  const handleScenarioChange = (e) => {
    const newId = e.target.value;
    setActiveScenarioId(newId);
    setConfigSuccess(isVi ? `Đã chuyển kịch bản hoạt động sang ${newId}` : `Active scenario switched to ${newId}`);
    setTimeout(() => setConfigSuccess(null), 4000);
  };

  const isMapOnlyScenario = MAP_ONLY_SCENARIOS.includes(activeScenarioId);

  const handleSaveConfig = () => {
    fetch(`${apiBase}/api/v1/control/policy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        controller: controllerMode,
        topology_id: activeScenarioId
      })
    })
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (ok) {
          setAppliedController(controllerMode);
          setConfigSuccess(isVi 
            ? `Chính sách đã cập nhật: ${CONTROLLER_DESCRIPTIONS[controllerMode]?.name || controllerMode}. Graph-control đồng bộ sau ~2s.` 
            : `Policy requested: ${data.active_controller}. Graph-control switches within ~2s.`);
        } else {
          setConfigSuccess(isVi ? `Bị từ chối: ${data.detail || 'Lỗi không xác định'}` : `Rejected: ${data.detail || 'unknown error'}`);
        }
        setTimeout(() => setConfigSuccess(null), 6000);
      })
      .catch(() => {
        setConfigSuccess(isVi ? `Không kết nối được API: Chính sách chưa thay đổi (${controllerMode})` : `API unreachable: policy not changed (${controllerMode})`);
        setTimeout(() => setConfigSuccess(null), 6000);
      });
  };

  useEffect(() => () => Object.values(overrideTimers.current).forEach(clearInterval), []);

  const showOverride = (nodeId, view) => setOverrideViews(prev => ({ ...prev, [nodeId]: view }));

  const followOverride = (nodeId) => {
    clearInterval(overrideTimers.current[nodeId]);
    let polls = 0;
    overrideTimers.current[nodeId] = setInterval(() => {
      polls += 1;
      fetch(`${apiBase}/api/v1/network/state/${nodeId}`)
        .then(res => res.json())
        .then(data => {
          const override = data && data.manual_override;
          showOverride(nodeId, describeOverride(override));
          const settled = !override || !(OVERRIDE_IN_PROGRESS.includes(override.status) || override.status === 'APPLIED');
          if (settled || polls >= OVERRIDE_FOLLOW_MAX_POLLS) clearInterval(overrideTimers.current[nodeId]);
        })
        .catch(() => {
          if (polls >= OVERRIDE_FOLLOW_MAX_POLLS) clearInterval(overrideTimers.current[nodeId]);
        });
    }, 1000);
  };

  const handleEmergencyOverride = (nodeId) => {
    const targetPhaseId = nodeDefaultPhase[nodeId] || `${nodeId}_PHASE_NS`;
    showOverride(nodeId, null);
    fetch(`${apiBase}/api/v1/control/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId, target_phase_id: targetPhaseId })
    })
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          showOverride(nodeId, overrideRequestError(isVi ? `API từ chối: ${data.detail || 'Lỗi không rõ'}` : `API rejected: ${data.detail || 'Unknown error'}`));
          return;
        }
        showOverride(nodeId, describeOverride({ status: 'SENT', target_phase_id: data.target_phase_id }));
        followOverride(nodeId);
      })
      .catch(() => showOverride(nodeId, overrideRequestError(isVi ? 'Không gọi được API: Lệnh chưa tới thiết bị.' : 'API unreachable.')));
  };

  const filteredNodes = topologyNodes.filter(id => id.toLowerCase().includes(searchQuery.toLowerCase()));
  const descDict = CONTROLLER_DESCRIPTIONS[lang] || CONTROLLER_DESCRIPTIONS.en;
  const activeDesc = descDict[controllerMode] || descDict.max_pressure;

  return (
    <div className="page-container">
      {/* Page Title & Context Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 800, margin: '0 0 6px 0', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Sliders color="#0284c7" size={26} />
              {isVi ? 'Trung Tâm Điều Khiển & Cơ Chế Phân Bổ Tín Hiệu' : 'Signal Control & Traffic Policy Management'}
            </h2>
            <p style={{ color: '#64748b', margin: 0, fontSize: '0.92rem', maxWidth: '850px' }}>
              {isVi 
                ? 'Quản lý chính sách thuật toán điều khiển (FlowTheory CTM, Max-Pressure), quy chuẩn an toàn phần cứng và đè lệnh chuyển pha khẩn cấp.'
                : 'Configure traffic control algorithms (FlowTheory CTM, Max-Pressure), monitor hardware safety bounds, and execute emergency phase overrides.'}
            </p>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 600 }}>
              {isVi ? 'Thuật toán đang chạy:' : 'Active Controller:'}
            </span>
            <span className="badge badge-green" style={{ fontSize: '0.85rem', padding: '6px 14px', gap: '6px' }}>
              <Activity size={14} className="pulse-indicator" />
              {descDict[appliedController]?.name || appliedController}
            </span>
          </div>
        </div>
      </div>

      {configSuccess && (
        <div style={{
          backgroundColor: '#f0fdf4',
          border: '1px solid #16a34a',
          borderRadius: '10px',
          padding: '12px 18px',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#15803d',
          fontWeight: 600,
          boxShadow: '0 2px 6px rgba(22, 163, 74, 0.1)'
        }}>
          <CheckCircle2 size={22} style={{ flexShrink: 0 }} />
          <span>{configSuccess}</span>
        </div>
      )}

      {/* Main Grid: Policy Configuration & Emergency Overrides */}
      <div className="grid-cols-2" style={{ marginBottom: '24px' }}>
        
        {/* PANEL 1: Controller Policy & Algorithm Selector */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap color="#0284c7" size={20} />
              <h3 style={{ fontSize: '1.15rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>
                {isVi ? 'Chính Sách Thuật Toán Điều Khiển' : 'Traffic Controller Policy'}
              </h3>
            </div>
            <span className="badge badge-blue">
              {scenarios.find(s => s.scenario_id === activeScenarioId)?.has_sumo_config ? 'SUMO Engine' : 'Topology Contract'}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Scenario Selector */}
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#475569', marginBottom: '6px', fontWeight: 700 }}>
                <Layers size={16} color="#0284c7" /> {isVi ? 'Kịch Bản Giao Thông / Sơ Đồ Nút Mạng' : 'Active Network Scenario'}
              </label>
              <select
                value={activeScenarioId}
                onChange={handleScenarioChange}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                {scenarios.map((sc) => (
                  <option key={sc.scenario_id} value={sc.scenario_id}>
                    {sc.name || sc.scenario_id}
                  </option>
                ))}
              </select>
            </div>

            {/* Controller Algorithm Policy */}
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#475569', marginBottom: '6px', fontWeight: 700 }}>
                <Cpu size={16} color="#0284c7" /> {isVi ? 'Lựa Chọn Thuật Toán Điều Khiển Đèn' : 'Traffic Signal Controller Algorithm'}
              </label>
              <select
                value={controllerMode}
                onChange={(e) => setControllerMode(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <option value="flow_theory">
                  {isVi ? 'FlowTheory (CTM & Anti-Gridlock Gating) — [Khuyên Dùng / Khóa Kẹt Mạng]' : 'FlowTheory (CTM & Anti-Gridlock Gating) — [Recommended / Zero-Gridlock]'}
                </option>
                <option value="max_pressure">
                  {isVi ? 'Max-Pressure Controller — [Cân Bằng Áp Lực Đa Tuyến]' : 'Max-Pressure Controller — [Multi-Direction Pressure Balance]'}
                </option>
                <option value="max_queue">
                  {isVi ? 'Max-Queue Controller — [Tham Lam Giải Phóng Hàng Đợi]' : 'Max-Queue Controller — [Greedy Longest Queue Clearance]'}
                </option>
                <option value="actuated">
                  {isVi ? 'Actuated Controller — [Cảm Biến Xe Co Giãn Thời Gian Xanh]' : 'Actuated Controller — [Dynamic Gap-Out Green Extension]'}
                </option>
                <option value="fixed_time">
                  {isVi ? 'Fixed-Time Controller — [Chu Kỳ Cố Định Baseline]' : 'Fixed-Time Controller — [Fixed-Time Benchmark Baseline]'}
                </option>
              </select>
            </div>

            {/* Active Controller Interactive Explainer Card */}
            <div className="algo-card algo-card-active" style={{ marginTop: '2px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontWeight: 800, color: '#0369a1', fontSize: '0.95rem' }}>
                  {activeDesc.name}
                </span>
                <span style={{ 
                  backgroundColor: activeDesc.tagColor + '20', 
                  color: activeDesc.tagColor, 
                  border: `1px solid ${activeDesc.tagColor}50`,
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '6px'
                }}>
                  {activeDesc.tag}
                </span>
              </div>
              <div style={{ fontSize: '0.83rem', color: '#334155', lineHeight: 1.45, marginBottom: '8px' }}>
                {activeDesc.summary}
              </div>
              <div style={{ 
                fontSize: '0.78rem', 
                color: '#475569', 
                backgroundColor: '#ffffff', 
                padding: '8px 10px', 
                borderRadius: '6px', 
                border: '1px solid #e2e8f0',
                lineHeight: 1.4
              }}>
                <strong style={{ color: '#0284c7' }}>{isVi ? '💡 Cơ chế vận hành: ' : '💡 How it works: '}</strong>
                {activeDesc.howItWorks}
              </div>
            </div>

            {/* Apply Button */}
            <button 
              className="btn btn-primary" 
              onClick={handleSaveConfig} 
              style={{ 
                padding: '12px 18px', 
                borderRadius: '8px', 
                fontWeight: 700, 
                fontSize: '0.92rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                marginTop: '4px'
              }}
            >
              <RefreshCw size={18} /> {isVi ? 'Áp Dụng Thuật Toán Điều Khiển' : 'Apply Controller Policy'}
            </button>
          </div>
        </div>

        {/* PANEL 2: Hardware Safety Constraints & Certified Rules */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Lock color="#16a34a" size={20} />
              <h3 style={{ fontSize: '1.15rem', margin: 0, fontWeight: 700, color: '#0f172a' }}>
                {isVi ? 'Quy Chuẩn An Toàn Phần Cứng (Hardware Interlock)' : 'Hardware Safety & Timing Specs'}
              </h3>
            </div>
            <span className="badge badge-green" style={{ gap: '4px' }}>
              <ShieldAlert size={12} /> EN-17038 / ISO-26262
            </span>
          </div>

          <p style={{ color: '#64748b', fontSize: '0.85rem', margin: 0, lineHeight: 1.5 }}>
            {isVi 
              ? 'Tất cả lệnh tín hiệu từ thuật toán AI/Graph-Control đều phải tuân thủ nghiêm ngặt các giới hạn an toàn được khóa cứng tại thiết bị chấp hành (Actuator/ESP32), đảm bảo 0% nguy cơ xảy ra xung đột pha đèn.'
              : 'All commands from AI/Graph-Control algorithms are rigorously verified by actuator hardware interlocks (ESP32) to prevent conflicting phase rights.'}
          </p>

          {/* Clean Specification Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <Clock size={16} color="#0284c7" />
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569' }}>
                  {isVi ? 'Xanh Tối Thiểu (Min Green)' : 'Minimum Green Time'}
                </span>
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#0284c7' }}>10s</div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '4px' }}>
                {isVi ? 'Đủ thời gian cho xe đã dừng lăn bánh an toàn qua nút.' : 'Ensures initial vehicles clear intersection safely.'}
              </div>
            </div>

            <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <Clock size={16} color="#0284c7" />
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569' }}>
                  {isVi ? 'Xanh Tối Đa (Max Green)' : 'Maximum Green Time'}
                </span>
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#0284c7' }}>60s</div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '4px' }}>
                {isVi ? 'Chống bỏ đói luồng đối diện khi đường quá đông.' : 'Anti-starvation cap for cross-direction flow.'}
              </div>
            </div>

            <div style={{ backgroundColor: '#fffbeb', border: '1px solid #fde68a', borderRadius: '10px', padding: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#d97706' }} />
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#92400e' }}>
                  {isVi ? 'Đèn Vàng Chuyển Tiếp' : 'Yellow Clearance'}
                </span>
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#d97706' }}>3s</div>
              <div style={{ fontSize: '0.72rem', color: '#78350f', marginTop: '4px' }}>
                {isVi ? 'Cảnh báo giảm tốc theo quy chuẩn giao thông.' : 'Safe transition deceleration warning.'}
              </div>
            </div>

            <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '10px', padding: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#dc2626' }} />
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#991b1b' }}>
                  {isVi ? 'Đỏ Toàn Bộ (All-Red)' : 'All-Red Clearance'}
                </span>
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#dc2626' }}>2s</div>
              <div style={{ fontSize: '0.72rem', color: '#7f1d1d', marginTop: '4px' }}>
                {isVi ? 'Khóa cứng giải phóng hoàn toàn tâm ngã tư.' : 'Zero-collision clearing before opposite green.'}
              </div>
            </div>
          </div>

          <div style={{ 
            backgroundColor: '#f8fafc', 
            borderRadius: '8px', 
            padding: '10px 14px', 
            border: '1px solid #e2e8f0', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            fontSize: '0.82rem',
            color: '#475569'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Info size={16} color="#0284c7" />
              <span>{isVi ? 'Cần tinh chỉnh các thông số này trên firmware?' : 'Need to adjust hardware constraint thresholds?'}</span>
            </div>
            <Link to="/admin" style={{ color: '#0284c7', fontWeight: 700, textDecoration: 'underline' }}>
              {isVi ? 'Quản Lý Tại Admin' : 'Open Admin Console'}
            </Link>
          </div>
        </div>
      </div>

      {/* PANEL 3: Emergency Manual Phase Override */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertTriangle color="#ef4444" size={24} />
            <div>
              <h3 style={{ fontSize: '1.15rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                {isVi ? 'Cơ Chế Đè Lệnh Chuyển Pha Khẩn Cấp (1-Click Emergency Override)' : 'Emergency Manual Phase Override'}
              </h3>
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#64748b' }}>
                {isVi 
                  ? 'Ưu tiên đặc biệt cho xe cứu thương, đoàn xe ưu tiên hoặc xử lý ùn tắc đột xuất.' 
                  : 'For emergency vehicles, priority convoys, or acute localized congestion clearance.'}
              </p>
            </div>
          </div>
          <span className="badge badge-slate" style={{ fontSize: '0.85rem' }}>
            {topologyNodes.length} {isVi ? 'Nút Giao Sẵn Sàng' : 'Nodes Registered'}
          </span>
        </div>

        {/* Override Visual Stepper Lifecycle */}
        <div style={{ backgroundColor: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: '10px', padding: '14px 16px' }}>
          <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0369a1', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.04em' }}>
            {isVi ? 'Chu Trình Chuyển Pha An Toàn Của Thiết Bị Chấp Hành (Actuator Lifecycle)' : 'Actuator Clearance & Safety Lifecycle'}
          </div>
          <div className="control-stepper">
            <div className="control-step-item control-step-active">
              1. {isVi ? 'Nhận Lệnh Tay' : 'Operator Trigger'}
            </div>
            <ArrowRight size={14} color="#0284c7" />
            <div className="control-step-item control-step-active">
              2. {isVi ? 'Xanh Hiện Tại Đủ 5s' : 'Min 5s Active Green'}
            </div>
            <ArrowRight size={14} color="#0284c7" />
            <div className="control-step-item" style={{ backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fde68a' }}>
              3. {isVi ? 'Vàng 3s' : 'Yellow (3s)'}
            </div>
            <ArrowRight size={14} color="#0284c7" />
            <div className="control-step-item" style={{ backgroundColor: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca' }}>
              4. {isVi ? 'Đỏ Toàn Bộ 2s' : 'All-Red (2s)'}
            </div>
            <ArrowRight size={14} color="#0284c7" />
            <div className="control-step-item" style={{ backgroundColor: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0' }}>
              5. {isVi ? 'Giữ Xanh Ưu Tiên 15s' : 'Hold Priority Green 15s'}
            </div>
            <ArrowRight size={14} color="#0284c7" />
            <div className="control-step-item control-step-idle">
              6. {isVi ? 'Trả Về AI Tự Động' : 'Resume Auto Policy'}
            </div>
          </div>
        </div>

        {isMapOnlyScenario ? (
          <div style={{
            backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px',
            padding: '14px 16px', display: 'flex', alignItems: 'center', gap: '12px'
          }}>
            <Camera size={22} color="#0284c7" />
            <div style={{ fontSize: '0.85rem', color: '#1e3a8a' }}>
              <strong>{activeScenarioId}</strong> {isVi ? `là mạng lưới camera địa lý (${topologyNodes.length} trạm), không phải kịch bản mô phỏng trực tiếp.` : `is a geographic camera network (${topologyNodes.length} stations), not an interactive simulation scenario.`}{' '}
              <Link to="/cameras" style={{ color: '#0284c7', fontWeight: 700, textDecoration: 'underline' }}>
                {isVi ? 'Xem Bản đồ Camera HCM' : 'Open HCM Camera Map'}
              </Link>
            </div>
          </div>
        ) : (
          <>
            {topologyNodes.length > 4 && (
              <input
                type="text"
                placeholder={isVi ? "Tìm kiếm nút giao theo Node ID (VD: J1, J2)..." : "Filter intersection node ID..."}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.88rem',
                  maxWidth: '360px',
                  outline: 'none'
                }}
              />
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '12px' }}>
              {filteredNodes.map((nodeId) => {
                const targetPhase = nodeDefaultPhase[nodeId] || `${nodeId}_PHASE_NS`;
                const currentPhase = nodeCurrentPhases[nodeId] || '—';
                const isTargetActive = currentPhase.includes('NS') || currentPhase === targetPhase;
                const view = overrideViews[nodeId];
                const isBusy = Boolean(view && ['info', 'warn'].includes(view.tone));

                return (
                  <div 
                    key={nodeId}
                    style={{
                      backgroundColor: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: '10px',
                      padding: '14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 800, color: '#0f172a', fontSize: '1.05rem' }}>
                          {isVi ? 'Trạm' : 'Station'} {nodeId}
                        </span>
                        <Link 
                          to={`/intersections/${nodeId}`}
                          style={{ fontSize: '0.74rem', color: '#0284c7', fontWeight: 600, textDecoration: 'underline' }}
                        >
                          {isVi ? 'Chi tiết' : 'Details'}
                        </Link>
                      </div>
                      <span className={`badge ${isTargetActive ? 'badge-green' : 'badge-yellow'}`} style={{ fontSize: '0.72rem' }}>
                        {isVi ? 'Pha: ' : 'Phase: '}{currentPhase}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                      {isVi ? 'Pha ưu tiên khẩn cấp:' : 'Default Priority Phase:'} <strong style={{ color: '#0f172a' }}>{targetPhase}</strong>
                    </div>

                    <button
                      className="btn btn-danger"
                      style={{ 
                        padding: '9px 14px', 
                        fontSize: '0.82rem', 
                        fontWeight: 700, 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        gap: '6px',
                        cursor: isBusy ? 'not-allowed' : 'pointer'
                      }}
                      onClick={() => handleEmergencyOverride(nodeId)}
                      disabled={isBusy}
                    >
                      <Play size={14} />
                      {isVi ? `Ép Xanh Pha Ưu Tiên (${targetPhase})` : `Force Priority Phase (${targetPhase})`}
                    </button>

                    {view && (
                      <div style={{
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: `1px solid ${view.colors.border}`,
                        backgroundColor: view.colors.background,
                        color: view.colors.color,
                        fontSize: '0.78rem'
                      }}>
                        <div style={{ fontWeight: 700 }}>{view.title}</div>
                        <div>{view.detail}</div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ControlPanel;
