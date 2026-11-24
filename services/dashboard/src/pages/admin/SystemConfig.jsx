import React, { useState, useEffect } from 'react';
import { Sliders, Gauge, CheckCircle2, Save, AlertCircle, Shield } from 'lucide-react';
import { useActiveScenario } from '../../hooks/useActiveScenario';
import { useLanguage } from '../../hooks/useLanguage';

const CONTROLLERS = [
  { value: 'max_pressure', labelEn: 'Max-Pressure (Queue Differential Balancing)', labelVi: 'Max-Pressure (Cân bằng áp lực chênh lệch)' },
  { value: 'max_queue', labelEn: 'Max-Queue (Greedy Longest Queue Flush)', labelVi: 'Max-Queue (Xả hàng chờ dài nhất)' },
  { value: 'fixed_time', labelEn: 'Fixed-Time (Pre-timed Baseline Cycle)', labelVi: 'Fixed-Time (Chu kỳ cố định truyền thống)' },
  { value: 'flow_theory', labelEn: 'FlowTheory CTM (Macroscopic Shockwave Cell)', labelVi: 'FlowTheory CTM (Mô hình sóng xung kích CTM)' },
  { value: 'actuated', labelEn: 'Actuated (Vehicle Detector Gap-Out)', labelVi: 'Actuated (Cảm biến kích hoạt khoảng cách Gap-Out)' }
];

const MODES = [
  { value: 'NORMAL', descEn: 'Normal automated adaptive control', descVi: 'Vận hành thích ứng tự động bình thường' },
  { value: 'FLASHING_YELLOW', descEn: 'Flashing yellow caution for off-peak', descVi: 'Vàng nhấp nháy cảnh báo ban đêm' },
  { value: 'ALL_RED', descEn: 'Emergency all-red network lockdown', descVi: 'Đỏ toàn bộ khẩn cấp phong tỏa mạng' }
];

const COPY = {
  en: {
    loading: 'Loading current controller policy and actuator timing...',
    policyCard: {
      title: 'Adaptive Controller Policy',
      subtitle: (scenario) => `Select active policy deployed to Graph-Control for topology ${scenario}`,
      desc: 'Controller determines how green time is allocated across competing traffic streams. Commands are published via MQTT to edgeflow/v1/control/<node_id>/command.',
      applyBtn: 'Apply Controller Policy'
    },
    timingCard: {
      title: 'Actuator Safety & Timing Constraints',
      subtitle: 'Hardware clearance interlocks enforced on ESP32 & Virtual Actuator',
      desc: 'Enforces non-negotiable safety invariant: conflicting phases are physically locked until Yellow + All-Red intervals expire (0% hazard).',
      yellow: 'Yellow Clearance (s)',
      allRed: 'All-Red Clearance (s)',
      minGreen: 'Minimum Green (s)',
      maxGreen: 'Maximum Green (s)',
      safetyMode: 'Operational Safety Mode',
      applyBtn: 'Save Safety Constraints'
    },
    successPolicy: (ctrl) => `Controller policy applied: ${ctrl}`,
    successTiming: 'Actuator timing constraints updated. Actuators will enforce new bounds on next cycle.',
    errorApi: 'API unreachable: settings could not be saved.'
  },
  vi: {
    loading: 'Đang tải cấu hình bộ điều khiển và thông số chấp hành...',
    policyCard: {
      title: 'Chính Sách Thuật Toán Điều Khiển',
      subtitle: (scenario) => `Chọn thuật toán đang điều phối cho cấu trúc mạng ${scenario}`,
      desc: 'Bộ điều khiển quyết định cách phân bổ quyền ưu tiên xanh cho các luồng giao thông. Lệnh được phát qua MQTT tới topic edgeflow/v1/control/<node_id>/command.',
      applyBtn: 'Áp Dụng Bộ Điều Khiển'
    },
    timingCard: {
      title: 'Quy Chuẩn An Toàn & Thời Gian Actuator',
      subtitle: 'Khóa cứng giải phóng an toàn thực thi trên ESP32 và Virtual Actuator',
      desc: 'Đảm bảo bất biến an toàn: các hướng xung đột bị khóa cứng phần cứng trong suốt thời gian Vàng + Đỏ toàn bộ (đảm bảo 0% va chạm chéo).',
      yellow: 'Thời Gian Vàng (giây)',
      allRed: 'Thời Gian Đỏ Toàn Bộ (giây)',
      minGreen: 'Xanh Tối Thiểu (giây)',
      maxGreen: 'Xanh Tối Đa (giây)',
      safetyMode: 'Chế Độ An Toàn Vận Hành',
      applyBtn: 'Lưu Thông Số An Toàn'
    },
    successPolicy: (ctrl) => `Đã kích hoạt chính sách điều khiển: ${ctrl}`,
    successTiming: 'Đã cập nhật thông số an toàn của thiết bị chấp hành. Chu kỳ kế tiếp sẽ áp dụng ràng buộc mới.',
    errorApi: 'Không thể kết nối API: không lưu được cấu hình.'
  }
};

const SystemConfig = () => {
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.en;
  const isVi = lang === 'vi';

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const [activeScenarioId] = useActiveScenario();
  const [controller, setController] = useState('max_pressure');
  const [actuatorCfg, setActuatorCfg] = useState({
    yellow_duration_s: 3.0,
    all_red_duration_s: 2.0,
    min_green_s: 10.0,
    max_green_s: 60.0,
    mode: 'NORMAL'
  });
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch(`${apiBase}/api/v1/control/policy`).then((r) => r.json()).catch(() => null),
      fetch(`${apiBase}/api/v1/actuator/config`).then((r) => r.json()).catch(() => null)
    ]).then(([policy, cfg]) => {
      if (policy?.active_controller) setController(policy.active_controller);
      if (cfg) setActuatorCfg((prev) => ({ ...prev, ...cfg }));
      setLoading(false);
    });
  }, [apiBase]);

  const flash = (message) => {
    setStatus(message);
    setTimeout(() => setStatus(null), 5000);
  };

  const savePolicy = () => {
    fetch(`${apiBase}/api/v1/control/policy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ controller, topology_id: activeScenarioId })
    })
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => flash(ok ? t.successPolicy(data.active_controller) : `Rejected: ${data.detail || 'unknown error'}`))
      .catch(() => flash(t.errorApi));
  };

  const saveActuatorConfig = () => {
    fetch(`${apiBase}/api/v1/actuator/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(actuatorCfg)
    })
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => flash(ok ? t.successTiming : `Rejected: ${data.detail || 'unknown error'}`))
      .catch(() => flash(t.errorApi));
  };

  if (loading) return <div className="card" style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>{t.loading}</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {status && (
        <div style={{
          backgroundColor: '#f0fdf4', border: '1px solid #16a34a', borderRadius: '8px',
          padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px', color: '#15803d', fontWeight: 600
        }}>
          <CheckCircle2 size={18} /> <span>{status}</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* 1. Controller Policy Card */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '20px', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
            <div style={{ backgroundColor: '#f0f9ff', padding: '8px', borderRadius: '8px' }}>
              <Sliders color="#0284c7" size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                {t.policyCard.title}
              </h3>
              <p style={{ margin: 0, fontSize: '0.74rem', color: '#64748b' }}>
                {t.policyCard.subtitle(activeScenarioId)}
              </p>
            </div>
          </div>

          <p style={{ fontSize: '0.78rem', color: '#475569', lineHeight: '1.5', margin: 0 }}>
            {t.policyCard.desc}
          </p>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', color: '#334155', marginBottom: '8px', fontWeight: 700 }}>
              {isVi ? 'Chọn Thuật Toán Điều Phối Pha:' : 'Select Control Algorithm:'}
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {CONTROLLERS.map((c) => (
                <label 
                  key={c.value} 
                  style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '10px 12px', borderRadius: '8px',
                    border: controller === c.value ? '1.5px solid #0284c7' : '1px solid #e2e8f0',
                    backgroundColor: controller === c.value ? '#f0f9ff' : '#ffffff',
                    cursor: 'pointer'
                  }}
                >
                  <input
                    type="radio"
                    name="controller"
                    value={c.value}
                    checked={controller === c.value}
                    onChange={(e) => setController(e.target.value)}
                    style={{ accentColor: '#0284c7' }}
                  />
                  <div>
                    <div style={{ fontSize: '0.84rem', fontWeight: 700, color: controller === c.value ? '#0284c7' : '#0f172a' }}>
                      {isVi ? c.labelVi : c.labelEn}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <button 
            className="btn btn-primary" 
            onClick={savePolicy} 
            style={{ alignSelf: 'flex-start', padding: '10px 18px', display: 'flex', alignItems: 'center', gap: '8px', marginTop: 'auto' }}
          >
            <Save size={16} /> {t.policyCard.applyBtn}
          </button>
        </div>

        {/* 2. Actuator Timing Constraints Card */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '20px', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
            <div style={{ backgroundColor: '#f0fdf4', padding: '8px', borderRadius: '8px' }}>
              <Gauge color="#16a34a" size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
                {t.timingCard.title}
              </h3>
              <p style={{ margin: 0, fontSize: '0.74rem', color: '#64748b' }}>
                {t.timingCard.subtitle}
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', padding: '8px 12px', borderRadius: '6px', fontSize: '0.74rem', color: '#166534' }}>
            <Shield size={14} style={{ flexShrink: 0 }} />
            <span>{t.timingCard.desc}</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            {[
              ['yellow_duration_s', t.timingCard.yellow, 2, 6, 0.5, '#ca8a04'],
              ['all_red_duration_s', t.timingCard.allRed, 1, 5, 0.5, '#dc2626'],
              ['min_green_s', t.timingCard.minGreen, 5, 30, 1, '#16a34a'],
              ['max_green_s', t.timingCard.maxGreen, 20, 90, 1, '#0284c7']
            ].map(([key, label, min, max, step, color]) => (
              <div key={key} style={{ backgroundColor: '#f8fafc', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.76rem', color: '#475569', fontWeight: 600 }}>{label}</span>
                  <span style={{ fontSize: '0.88rem', fontWeight: 800, color, fontFamily: 'JetBrains Mono, monospace' }}>
                    {actuatorCfg[key]}s
                  </span>
                </div>
                <input
                  type="range"
                  min={min}
                  max={max}
                  step={step}
                  value={actuatorCfg[key]}
                  onChange={(e) => setActuatorCfg((prev) => ({ ...prev, [key]: parseFloat(e.target.value) }))}
                  style={{ width: '100%', accentColor: color }}
                />
              </div>
            ))}
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', color: '#334155', marginBottom: '6px', fontWeight: 700 }}>
              {t.timingCard.safetyMode}
            </label>
            <select
              value={actuatorCfg.mode}
              onChange={(e) => setActuatorCfg((prev) => ({ ...prev, mode: e.target.value }))}
              style={{ width: '100%', border: '1px solid #cbd5e1', padding: '10px 12px', borderRadius: '7px', fontSize: '0.85rem', color: '#0f172a', backgroundColor: '#ffffff', outline: 'none' }}
            >
              {MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.value} — {isVi ? m.descVi : m.descEn}
                </option>
              ))}
            </select>
          </div>

          <button 
            className="btn btn-primary" 
            onClick={saveActuatorConfig} 
            style={{ alignSelf: 'flex-start', padding: '10px 18px', display: 'flex', alignItems: 'center', gap: '8px', marginTop: 'auto' }}
          >
            <Save size={16} /> {t.timingCard.applyBtn}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SystemConfig;
