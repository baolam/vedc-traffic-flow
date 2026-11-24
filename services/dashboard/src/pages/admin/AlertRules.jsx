import React, { useState, useEffect } from 'react';
import { Info, BellRing, ShieldAlert, CheckCircle, Save } from 'lucide-react';
import StatusBadge from '../../components/StatusBadge';
import { useLanguage } from '../../hooks/useLanguage';

const DEFAULT_RULES = [
  { id: 'congestion-warning', labelEn: 'Congestion Threshold — Warning', labelVi: 'Ngưỡng Ùn Tắc — Cảnh Báo Vừa', metric: 'queue_vehicles', operator: '>', threshold: 12, severity: 'WARNING' },
  { id: 'congestion-critical', labelEn: 'Congestion Threshold — Critical', labelVi: 'Ngưỡng Ùn Tắc — Nghiêm Trọng', metric: 'queue_vehicles', operator: '>', threshold: 18, severity: 'CRITICAL' },
  { id: 'device-health', labelEn: 'Device Heartbeat & Health Trigger', labelVi: 'Kích Hoạt Mất Nhịp Tim Thiết Bị', metric: 'status', operator: '!=', threshold: 'ONLINE', severity: 'WARNING' }
];

const COPY = {
  en: {
    activeAlertsTitle: 'Active System Alerts & Safety Triggers',
    loading: 'Loading active alerts from system reports...',
    noAlerts: 'No active alarms. Network telemetry is nominal and safe.',
    columns: {
      node: 'Junction Node',
      type: 'Fault Type',
      severity: 'Severity',
      message: 'Alert Details & Diagnostic Message'
    },
    ruleCardTitle: 'Congestion & Safety Alert Thresholds',
    ruleInfo: 'Alert thresholds configure the background telemetry monitoring engine. Rules trigger alarms across the top notification bell and overview map markers.',
    saveBtn: 'Save Rule Thresholds',
    savedNotice: 'Thresholds updated in local session.'
  },
  vi: {
    activeAlertsTitle: 'Cảnh Báo Đang Hoạt Động & Sự Cố An Toàn',
    loading: 'Đang tải cảnh báo từ báo cáo tổng hợp hệ thống...',
    noAlerts: 'Không có cảnh báo nào đang kích hoạt. Mạng lưới giao thông vận hành bình thường và an toàn.',
    columns: {
      node: 'Nút Giao',
      type: 'Phân Loại',
      severity: 'Mức Độ',
      message: 'Chi Tiết & Thông Điệp Chẩn Đoán'
    },
    ruleCardTitle: 'Ngưỡng Kích Hoạt Cảnh Báo & Ùn Tắc',
    ruleInfo: 'Các ngưỡng cảnh báo cấu hình cho bộ giám sát telemetry chạy ngầm. Khi vượt ngưỡng, hệ thống sẽ kích hoạt chuông thông báo và đánh dấu đỏ trên bản đồ.',
    saveBtn: 'Lưu Ngưỡng Cảnh Báo',
    savedNotice: 'Đã cập nhật ngưỡng cảnh báo cho phiên làm việc hiện tại.'
  }
};

const AlertRules = () => {
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.en;
  const isVi = lang === 'vi';

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [rules, setRules] = useState(DEFAULT_RULES);
  const [savedNote, setSavedNote] = useState(null);

  useEffect(() => {
    fetch(`${apiBase}/api/v1/system/reports`)
      .then((res) => res.json())
      .then((data) => {
        setAlerts(Array.isArray(data?.active_alerts) ? data.active_alerts : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [apiBase]);

  const updateThreshold = (id, value) => {
    setRules((prev) => prev.map((r) => (r.id === id ? { ...r, threshold: value } : r)));
  };

  const handleSave = () => {
    setSavedNote(t.savedNotice);
    setTimeout(() => setSavedNote(null), 5000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Active Alerts Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <BellRing size={18} color="#dc2626" />
          <h3 style={{ fontSize: '0.96rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
            {t.activeAlertsTitle} ({alerts.length})
          </h3>
        </div>

        {loading && <div style={{ padding: '24px', color: '#64748b', fontSize: '0.84rem', textAlign: 'center' }}>{t.loading}</div>}
        {!loading && alerts.length === 0 && (
          <div style={{ padding: '24px', color: '#16a34a', fontSize: '0.84rem', display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
            <CheckCircle size={16} /> {t.noAlerts}
          </div>
        )}
        {!loading && alerts.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', backgroundColor: '#f8fafc', color: '#475569', borderBottom: '1px solid #e2e8f0' }}>
                  <th style={{ padding: '9px 16px', fontWeight: 700 }}>{t.columns.node}</th>
                  <th style={{ padding: '9px 16px', fontWeight: 700 }}>{t.columns.type}</th>
                  <th style={{ padding: '9px 16px', fontWeight: 700 }}>{t.columns.severity}</th>
                  <th style={{ padding: '9px 16px', fontWeight: 700 }}>{t.columns.message}</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a, idx) => (
                  <tr key={`${a.node_id}-${idx}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '9px 16px', fontFamily: 'JetBrains Mono, monospace', fontWeight: 800, color: '#0284c7' }}>{a.node_id}</td>
                    <td style={{ padding: '9px 16px', color: '#475569' }}>{a.type}</td>
                    <td style={{ padding: '9px 16px' }}><StatusBadge status={a.severity} size="sm" /></td>
                    <td style={{ padding: '9px 16px', color: '#0f172a', fontWeight: 600 }}>{a.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 2. Alert Rules Configuration */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '20px', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
          <ShieldAlert color="#0284c7" size={18} />
          <h3 style={{ fontSize: '0.96rem', margin: 0, fontWeight: 800, color: '#0f172a' }}>
            {t.ruleCardTitle}
          </h3>
        </div>

        <div style={{
          display: 'flex', gap: '10px', alignItems: 'flex-start', backgroundColor: '#f0f9ff',
          border: '1px solid #bae6fd', borderRadius: '8px', padding: '10px 14px', fontSize: '0.78rem', color: '#0369a1'
        }}>
          <Info size={16} style={{ flexShrink: 0, marginTop: '1px' }} />
          <span>{t.ruleInfo}</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {rules.map((rule) => (
            <div key={rule.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#0f172a' }}>
                  {isVi ? rule.labelVi : rule.labelEn}
                </span>
                <StatusBadge status={rule.severity} size="sm" />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.78rem', color: '#64748b', fontFamily: 'JetBrains Mono, monospace' }}>
                  {rule.metric} {rule.operator}
                </span>
                <input
                  value={rule.threshold}
                  onChange={(e) => updateThreshold(rule.id, e.target.value)}
                  style={{ width: '80px', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '5px 8px', fontSize: '0.82rem', textAlign: 'center', fontWeight: 700, outline: 'none' }}
                />
              </div>
            </div>
          ))}
        </div>

        <button className="btn btn-primary" onClick={handleSave} style={{ alignSelf: 'flex-start', padding: '9px 18px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Save size={15} /> {t.saveBtn}
        </button>
        {savedNote && <div style={{ fontSize: '0.78rem', color: '#16a34a', fontWeight: 600 }}>✓ {savedNote}</div>}
      </div>
    </div>
  );
};

export default AlertRules;
