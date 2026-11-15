import React from 'react';
import { ShieldCheck, ShieldAlert, Zap, Layers, AlertCircle, ArrowRight, Gauge, Cpu } from 'lucide-react';

/**
 * FlowTheoryInspector
 * Explains internal CTM (Cell Transmission Model) calculations in real-time
 */
const FlowTheoryInspector = ({ sim }) => {
  if (!sim || !sim.lastDecisionBreakdown) {
    return (
      <div style={{ padding: '20px', backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
        <p style={{ color: '#64748b' }}>Đang khởi tạo bộ giải trình FlowTheory...</p>
      </div>
    );
  }

  const breakdown = sim.lastDecisionBreakdown;
  const { flows, details, bestPhase, gatedPhases, qMax, j3EffectiveOcc, antiGridlockActive } = breakdown;

  const f_NS = flows['J1_PHASE_NS'] || 0;
  const f_EW = flows['J1_PHASE_EW'] || 0;
  const nDetails = details['J1_N_IN'] || { Sa: 0, Rd: 0, Feff: 0, isGated: false };
  const wDetails = details['J1_W_IN'] || { Sa: 0, Rd: 0, Feff: 0, isGated: false };

  return (
    <div style={{
      backgroundColor: '#ffffff',
      borderRadius: '12px',
      border: '1px solid #e2e8f0',
      padding: '18px',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f1f5f9', paddingBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu color="#0284c7" size={20} />
          <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#0f172a' }}>
            Bảng Giải Trình Toán Học CTM (Whiteboard)
          </h3>
        </div>
        <span style={{
          fontSize: '0.74rem',
          fontWeight: 800,
          padding: '4px 8px',
          borderRadius: '6px',
          backgroundColor: antiGridlockActive ? '#fef2f2' : '#f0fdf4',
          color: antiGridlockActive ? '#dc2626' : '#16a34a',
          border: `1px solid ${antiGridlockActive ? '#fca5a5' : '#bbf7d0'}`,
          display: 'flex',
          alignItems: 'center',
          gap: '5px'
        }}>
          {antiGridlockActive ? <ShieldAlert size={14} /> : <ShieldCheck size={14} />}
          {antiGridlockActive ? 'ANTI-GRIDLOCK GATING KÍCH HOẠT' : 'HỆ THỐNG AN TOÀN BÌNH THƯỜNG'}
        </span>
      </div>

      {/* CTM Formula Overview Card */}
      <div style={{ backgroundColor: '#f8fafc', borderRadius: '8px', padding: '12px', border: '1px solid #e2e8f0' }}>
        <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: '#64748b', fontWeight: 800, marginBottom: '6px' }}>
          Công thức Cốt Lõi (Cell Transmission Model - CTM)
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.8rem', color: '#1e293b' }}>
          <div style={{ background: '#ffffff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <span style={{ color: '#0284c7', fontWeight: 700 }}>1. Cầu Gửi (Demand):</span>
            <div style={{ fontFamily: 'monospace', fontSize: '0.84rem', marginTop: '2px', fontWeight: 600 }}>
              S_a = min(Q_max, Queue / 10 + Flow_in)
            </div>
          </div>
          <div style={{ background: '#ffffff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <span style={{ color: '#d97706', fontWeight: 700 }}>2. Cung Nhận (Supply):</span>
            <div style={{ fontFamily: 'monospace', fontSize: '0.84rem', marginTop: '2px', fontWeight: 600 }}>
              R_d = Q_max * max(0, 1 - (Occ / 0.90)²)
            </div>
          </div>
        </div>
        <div style={{ marginTop: '8px', fontSize: '0.76rem', color: '#475569', fontStyle: 'italic' }}>
          * Thông lượng hiệu dụng: <strong style={{ color: '#0f172a' }}>F(p) = ∑ min(S_a, R_d)</strong> — Luôn bị giới hạn bởi khâu yếu nhất giữa Cung và Cầu.
        </div>
      </div>

      {/* Movement Real-time Breakdown */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#334155' }}>
          Phân Tích Cung - Cầu Trực Quan Theo Tiếp Cận:
        </div>

        {/* Approach J1_N_IN */}
        <div style={{
          padding: '12px',
          borderRadius: '8px',
          border: nDetails.isGated ? '2px solid #ef4444' : '1px solid #cbd5e1',
          backgroundColor: nDetails.isGated ? '#fff5f5' : '#ffffff'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontWeight: 800, fontSize: '0.85rem', color: '#0f172a' }}>Nhánh Bắc (J1_N_IN) → Hạ Lưu J3</span>
              {nDetails.isGated && (
                <span style={{ backgroundColor: '#dc2626', color: '#ffffff', fontSize: '0.68rem', fontWeight: 800, padding: '2px 6px', borderRadius: '4px' }}>
                  GATED (CHẶN ĐÈN)
                </span>
              )}
            </div>
            <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0284c7' }}>
              F_eff = {nDetails.Feff.toFixed(2)} vps
            </span>
          </div>

          {/* S_a vs R_d comparison bars */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.75rem' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#0284c7', fontWeight: 600 }}>
                <span>Cầu Gửi S_a: {nDetails.Sa.toFixed(2)} vps</span>
                <span>(Queue: {sim.approaches['J1_N_IN'].queue} xe)</span>
              </div>
              <div style={{ height: '6px', backgroundColor: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${(nDetails.Sa / qMax) * 100}%`, height: '100%', backgroundColor: '#0284c7' }} />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#d97706', fontWeight: 600 }}>
                <span>Cung Nhận Hạ Lưu R_d: {nDetails.Rd.toFixed(2)} vps</span>
                <span>(Occ J3: {(j3EffectiveOcc * 100).toFixed(0)}%)</span>
              </div>
              <div style={{ height: '6px', backgroundColor: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${(nDetails.Rd / qMax) * 100}%`, height: '100%', backgroundColor: '#f59e0b' }} />
              </div>
            </div>
          </div>

          {nDetails.isGated && (
            <div style={{ marginTop: '8px', fontSize: '0.74rem', color: '#b91c1c', fontWeight: 600 }}>
              ⚠️ Khả năng nhận R_d = 0 do hạ lưu J3 vượt ngưỡng 90%. FlowTheory cắt lưu lượng nhánh này để ngăn kẹt ngã tư!
            </div>
          )}
        </div>

        {/* Approach J1_W_IN */}
        <div style={{ padding: '12px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontWeight: 800, fontSize: '0.85rem', color: '#0f172a' }}>Nhánh Tây (J1_W_IN) → Hạ Lưu J2</span>
            <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0284c7' }}>
              F_eff = {wDetails.Feff.toFixed(2)} vps
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.75rem' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#0284c7', fontWeight: 600 }}>
                <span>Cầu Gửi S_a: {wDetails.Sa.toFixed(2)} vps</span>
                <span>(Queue: {sim.approaches['J1_W_IN'].queue} xe)</span>
              </div>
              <div style={{ height: '6px', backgroundColor: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${(wDetails.Sa / qMax) * 100}%`, height: '100%', backgroundColor: '#0284c7' }} />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#d97706', fontWeight: 600 }}>
                <span>Cung Nhận Hạ Lưu R_d: {wDetails.Rd.toFixed(2)} vps</span>
                <span>(Occ J2: {(wDetails.downstreamOcc * 100).toFixed(0)}%)</span>
              </div>
              <div style={{ height: '6px', backgroundColor: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${(wDetails.Rd / qMax) * 100}%`, height: '100%', backgroundColor: '#f59e0b' }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Decision Summary Banner */}
      <div style={{ backgroundColor: '#0f172a', color: '#ffffff', borderRadius: '8px', padding: '14px' }}>
        <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: '#94a3b8', fontWeight: 800, marginBottom: '6px' }}>
          So Sánh Quyết Định Pha (Phase Selection):
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', marginBottom: '10px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.76rem', color: '#94a3b8' }}>Pha Bắc - Nam (NS)</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 900, color: f_NS >= f_EW ? '#22c55e' : '#f87171' }}>
              F(NS) = {f_NS.toFixed(2)} vps
            </div>
          </div>
          <div style={{ fontSize: '1.1rem', color: '#64748b' }}>vs</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.76rem', color: '#94a3b8' }}>Pha Đông - Tây (EW)</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 900, color: f_EW >= f_NS ? '#22c55e' : '#f87171' }}>
              F(EW) = {f_EW.toFixed(2)} vps
            </div>
          </div>
        </div>

        <div style={{
          backgroundColor: '#1e293b',
          borderRadius: '6px',
          padding: '8px 12px',
          fontSize: '0.78rem',
          lineHeight: '1.4',
          borderLeft: '3px solid #0284c7'
        }}>
          💡 <strong>Kết luận điều khiển:</strong> {
            bestPhase === 'J1_PHASE_NS'
              ? 'Pha Bắc - Nam đạt thông lượng hiệu dụng tối ưu hơn mà không gây tắc nghẽn hạ lưu. Duy trì/chuyển pha NS.'
              : 'Pha Đông - Tây được ưu tiên do thông lượng cao hơn (hoặc do nhánh Bắc bị Gated bởi kẹt hạ lưu J3).'
          }
        </div>
      </div>
    </div>
  );
};

export default FlowTheoryInspector;
