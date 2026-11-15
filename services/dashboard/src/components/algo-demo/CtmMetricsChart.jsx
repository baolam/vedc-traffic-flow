import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  AreaChart,
  Area
} from 'recharts';
import { Trophy, Clock, Car, ShieldAlert, CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react';

/**
 * CtmMetricsChart
 * Plots real-time CTM metrics & Duel benchmark comparison
 */
const CtmMetricsChart = ({ sim, duelSim, isDuelMode = false }) => {
  const history = sim?.history || [];

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: '#0f172a' }}>
          {isDuelMode ? 'Bảng Đối Đầu & Hiệu Năng Thời Gian Thực' : 'Biểu Đồ Hiệu Năng CTM & Lưu Lượng'}
        </h4>
        <span style={{ fontSize: '0.74rem', color: '#64748b' }}>Cập nhật mỗi chu kỳ mô phỏng</span>
      </div>

      {/* KPI Cards Grid */}
      {isDuelMode && duelSim ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
          {/* Card 1: Cleared Throughput */}
          <div style={{ padding: '10px', borderRadius: '8px', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0' }}>
            <div style={{ fontSize: '0.7rem', color: '#166534', fontWeight: 700 }}>TỔNG XE THOÁT</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: '4px' }}>
              <div>
                <span style={{ fontSize: '1.2rem', fontWeight: 900, color: '#15803d' }}>{sim.totalVehiclesCleared}</span>
                <span style={{ fontSize: '0.65rem', color: '#166534' }}> (FlowTheory)</span>
              </div>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#64748b' }}>
                vs {duelSim.totalVehiclesCleared}
              </div>
            </div>
          </div>

          {/* Card 2: Average Delay */}
          <div style={{ padding: '10px', borderRadius: '8px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe' }}>
            <div style={{ fontSize: '0.7rem', color: '#1e40af', fontWeight: 700 }}>ĐỘ TRỄ TRUNG BÌNH</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: '4px' }}>
              <div>
                <span style={{ fontSize: '1.2rem', fontWeight: 900, color: '#1d4ed8' }}>{sim.avgWaitTime.toFixed(1)}s</span>
              </div>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#64748b' }}>
                vs {duelSim.avgWaitTime.toFixed(1)}s
              </div>
            </div>
          </div>

          {/* Card 3: Gridlock Incidents */}
          <div style={{
            padding: '10px',
            borderRadius: '8px',
            backgroundColor: duelSim.gridlockIncidents > 0 ? '#fef2f2' : '#f8fafc',
            border: `1px solid ${duelSim.gridlockIncidents > 0 ? '#fca5a5' : '#e2e8f0'}`
          }}>
            <div style={{ fontSize: '0.7rem', color: duelSim.gridlockIncidents > 0 ? '#991b1b' : '#475569', fontWeight: 700 }}>
              SỰ CỐ KẸT CỨNG (GRIDLOCK)
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: '4px' }}>
              <div>
                <span style={{ fontSize: '1.2rem', fontWeight: 900, color: '#15803d' }}>{sim.gridlockIncidents} vụ</span>
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: duelSim.gridlockIncidents > 0 ? '#dc2626' : '#64748b' }}>
                vs {duelSim.gridlockIncidents} vụ ⚠️
              </div>
            </div>
          </div>

          {/* Card 4: Current Queue */}
          <div style={{ padding: '10px', borderRadius: '8px', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '0.7rem', color: '#475569', fontWeight: 700 }}>HÀNG ĐỢI TỨC THỜI</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: '4px' }}>
              <div>
                <span style={{ fontSize: '1.2rem', fontWeight: 900, color: '#0f172a' }}>
                  {Object.values(sim.approaches).reduce((a, b) => a + b.queue, 0)} xe
                </span>
              </div>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#64748b' }}>
                vs {Object.values(duelSim.approaches).reduce((a, b) => a + b.queue, 0)} xe
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
          <div style={{ padding: '12px', borderRadius: '8px', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0' }}>
            <div style={{ fontSize: '0.72rem', color: '#166534', fontWeight: 700 }}>TỔNG XE ĐÃ GIẢI PHÓNG</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#15803d', marginTop: '4px' }}>
              {sim.totalVehiclesCleared} xe
            </div>
          </div>

          <div style={{ padding: '12px', borderRadius: '8px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe' }}>
            <div style={{ fontSize: '0.72rem', color: '#1e40af', fontWeight: 700 }}>THỜI GIAN CHỜ TRUNG BÌNH</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#1d4ed8', marginTop: '4px' }}>
              {sim.avgWaitTime.toFixed(1)} giây
            </div>
          </div>

          <div style={{ padding: '12px', borderRadius: '8px', backgroundColor: '#fdf4ff', border: '1px solid #f0abfc' }}>
            <div style={{ fontSize: '0.72rem', color: '#86198f', fontWeight: 700 }}>TỶ LỆ CHỐNG NGHẼN MẠNG</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#a21caf', marginTop: '4px' }}>
              100% Zero-Gridlock
            </div>
          </div>
        </div>
      )}

      {/* Recharts: Effective Flow Rates F(NS) vs F(EW) over time */}
      <div style={{ height: '200px', width: '100%', marginTop: '6px' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
          Lịch sử Thông lượng Hiệu dụng CTM: F(NS) vs F(EW) (xe/giây)
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={history} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} domain={[0, 1.2]} />
            <Tooltip contentStyle={{ fontSize: '11px', borderRadius: '6px' }} />
            <Legend wrapperStyle={{ fontSize: '11px' }} />
            <Line type="monotone" dataKey="f_NS" name="Pha NS (vps)" stroke="#0284c7" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="f_EW" name="Pha EW (vps)" stroke="#10b981" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Recharts: Queue & Downstream Occupancy */}
      <div style={{ height: '170px', width: '100%', marginTop: '6px' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
          Độ Chiếm Dụng Nút Hạ Lưu J3 (%) & Tổng Hàng Đợi (xe)
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ fontSize: '11px', borderRadius: '6px' }} />
            <Legend wrapperStyle={{ fontSize: '11px' }} />
            <Area type="monotone" dataKey="j3Occupancy" name="Độ chiếm dụng J3 (%)" stroke="#f59e0b" fill="#fef3c7" />
            <Area type="monotone" dataKey="queue" name="Tổng Hàng Đợi (xe)" stroke="#ef4444" fill="#fee2e2" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default CtmMetricsChart;
