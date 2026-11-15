import React from 'react';
import { ShieldAlert, AlertTriangle, ArrowDown, Activity } from 'lucide-react';

/**
 * CtmIntersectionCanvas
 * Renders the 4-way Intersection J1 + Downstream Link to J3 with CTM Visualizations
 */
const CtmIntersectionCanvas = ({
  sim,
  title = "Nút Giao J1 (CTM Simulation)",
  subtitle = "Thuật toán FlowTheory",
  compact = false
}) => {
  if (!sim) return null;

  const { activePhase, phaseState, approaches, downstreamJ3, isGridlocked, lastDecisionBreakdown } = sim;
  const isNsGreen = activePhase === 'J1_PHASE_NS' && phaseState === 'GREEN';
  const isNsYellow = activePhase === 'J1_PHASE_NS' && phaseState === 'YELLOW';
  const isEwGreen = activePhase === 'J1_PHASE_EW' && phaseState === 'GREEN';
  const isEwYellow = activePhase === 'J1_PHASE_EW' && phaseState === 'YELLOW';

  const isJ3Blocked = downstreamJ3.occupancy >= 0.90;
  const isGated = lastDecisionBreakdown?.gatedPhases?.includes('J1_PHASE_NS');

  // Canvas dimensions
  const width = compact ? 380 : 520;
  const height = compact ? 420 : 560;
  const cx = width / 2;
  const cy = compact ? 190 : 250;
  const roadWidth = compact ? 90 : 120;
  const halfRoad = roadWidth / 2;

  // Render signal light head helper
  const renderSignalHead = (x, y, isGreen, isYellow) => {
    const isRed = !isGreen && !isYellow;
    return (
      <g transform={`translate(${x}, ${y})`}>
        <rect x="-8" y="-22" width="16" height="44" rx="4" fill="#1e293b" stroke="#475569" strokeWidth="1.5" />
        {/* Red light */}
        <circle cx="0" cy="-14" r="5" fill={isRed ? "#ef4444" : "#450a0a"} filter={isRed ? "drop-shadow(0 0 4px #ef4444)" : "none"} />
        {/* Yellow light */}
        <circle cx="0" cy="0" r="5" fill={isYellow ? "#eab308" : "#422006"} filter={isYellow ? "drop-shadow(0 0 4px #eab308)" : "none"} />
        {/* Green light */}
        <circle cx="0" cy="14" r="5" fill={isGreen ? "#22c55e" : "#052e16"} filter={isGreen ? "drop-shadow(0 0 4px #22c55e)" : "none"} />
      </g>
    );
  };

  return (
    <div style={{
      backgroundColor: '#ffffff',
      borderRadius: '12px',
      border: isGridlocked ? '2px solid #ef4444' : '1px solid #e2e8f0',
      padding: compact ? '12px' : '16px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      position: 'relative',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
    }}>
      {/* Title Header */}
      <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div>
          <h4 style={{ margin: 0, fontSize: compact ? '0.9rem' : '1.05rem', fontWeight: 800, color: '#0f172a' }}>
            {title}
          </h4>
          <span style={{ fontSize: '0.74rem', color: '#64748b' }}>{subtitle}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{
            fontSize: '0.72rem',
            fontWeight: 700,
            padding: '3px 8px',
            borderRadius: '6px',
            backgroundColor: phaseState === 'GREEN' ? '#dcfce7' : '#fef9c3',
            color: phaseState === 'GREEN' ? '#15803d' : '#a16207',
            border: `1px solid ${phaseState === 'GREEN' ? '#86efac' : '#fde047'}`
          }}>
            {phaseState === 'GREEN' ? '🟢 GREEN' : '🟡 YELLOW'} ({activePhase.replace('J1_PHASE_', '')})
          </span>
        </div>
      </div>

      {/* SVG Map Canvas */}
      <svg width={width} height={height} style={{ backgroundColor: '#f1f5f9', borderRadius: '8px', overflow: 'hidden' }}>
        {/* Grass / Background Pattern */}
        <rect x="0" y="0" width={width} height={height} fill="#e2e8f0" />

        {/* Roads */}
        {/* North-South Road */}
        <rect x={cx - halfRoad} y="0" width={roadWidth} height={cy + halfRoad + 90} fill="#334155" />
        {/* East-West Road */}
        <rect x="0" y={cy - halfRoad} width={width} height={roadWidth} fill="#334155" />

        {/* Downstream Connector to J3 (South Corridor) */}
        <rect x={cx - halfRoad + 10} y={cy + halfRoad + 30} width={roadWidth - 20} height={height - (cy + halfRoad + 30) - 20} fill="#1e293b" rx="6" />

        {/* Road Markings & Lane dividers */}
        {/* North Dash */}
        <line x1={cx} y1="0" x2={cx} y2={cy - halfRoad} stroke="#94a3b8" strokeWidth="2" strokeDasharray="8,6" />
        {/* South Dash */}
        <line x1={cx} y1={cy + halfRoad} x2={cx} y2={cy + halfRoad + 30} stroke="#94a3b8" strokeWidth="2" strokeDasharray="8,6" />
        {/* West Dash */}
        <line x1="0" y1={cy} x2={cx - halfRoad} y2={cy} stroke="#94a3b8" strokeWidth="2" strokeDasharray="8,6" />
        {/* East Dash */}
        <line x1={cx + halfRoad} y1={cy} x2={width} y2={cy} stroke="#94a3b8" strokeWidth="2" strokeDasharray="8,6" />

        {/* Stop Lines (White solid) */}
        <line x1={cx - halfRoad} y1={cy - halfRoad} x2={cx} y2={cy - halfRoad} stroke="#ffffff" strokeWidth="4" />
        <line x1={cx} y1={cy + halfRoad} x2={cx + halfRoad} y2={cy + halfRoad} stroke="#ffffff" strokeWidth="4" />
        <line x1={cx - halfRoad} y1={cy} x2={cx - halfRoad} y2={cy + halfRoad} stroke="#ffffff" strokeWidth="4" />
        <line x1={cx + halfRoad} y1={cy - halfRoad} x2={cx + halfRoad} y2={cy} stroke="#ffffff" strokeWidth="4" />

        {/* Intersection Box Yellow Grid (Indicates junction box) */}
        <rect x={cx - halfRoad} y={cy - halfRoad} width={roadWidth} height={roadWidth} fill="none" stroke="#eab308" strokeWidth="1.5" strokeDasharray="4,4" />

        {/* Traffic Signals Heads */}
        {/* North Signal (Faces southbound cars) */}
        {renderSignalHead(cx - halfRoad - 14, cy - halfRoad - 6, isNsGreen, isNsYellow)}
        {/* South Signal (Faces northbound cars) */}
        {renderSignalHead(cx + halfRoad + 14, cy + halfRoad + 6, isNsGreen, isNsYellow)}
        {/* West Signal (Faces eastbound cars) */}
        {renderSignalHead(cx - halfRoad - 6, cy + halfRoad + 14, isEwGreen, isEwYellow)}
        {/* East Signal (Faces westbound cars) */}
        {renderSignalHead(cx + halfRoad + 6, cy - halfRoad - 14, isEwGreen, isEwYellow)}

        {/* Render Animated Vehicles */}
        {sim.vehicles.map(veh => {
          let vx = 0, vy = 0;
          const dist = veh.distToStopLine;

          if (veh.approach === 'J1_N_IN') {
            vx = cx - halfRoad / 2;
            vy = (cy - halfRoad) - dist;
          } else if (veh.approach === 'J1_S_IN') {
            vx = cx + halfRoad / 2;
            vy = (cy + halfRoad) + dist;
          } else if (veh.approach === 'J1_W_IN') {
            vx = (cx - halfRoad) - dist;
            vy = cy + halfRoad / 2;
          } else if (veh.approach === 'J1_E_IN') {
            vx = (cx + halfRoad) + dist;
            vy = cy - halfRoad / 2;
          }

          const isBus = veh.type === 'bus';
          const vWidth = isBus ? 14 : 11;
          const vHeight = isBus ? 24 : 16;

          return (
            <g key={veh.id} transform={`translate(${vx}, ${vy})`}>
              <rect
                x={-vWidth / 2}
                y={-vHeight / 2}
                width={vWidth}
                height={vHeight}
                rx={isBus ? 3 : 2}
                fill={veh.color}
                stroke="#0f172a"
                strokeWidth="1"
              />
              {/* Headlights */}
              <circle cx={-vWidth / 4} cy={-vHeight / 2 + 1} r="1.5" fill="#fef08a" />
              <circle cx={vWidth / 4} cy={-vHeight / 2 + 1} r="1.5" fill="#fef08a" />
            </g>
          );
        })}

        {/* Approach Queues & Badges */}
        {/* North Approach Badge */}
        <g transform={`translate(${cx - halfRoad / 2}, 30)`}>
          <rect x="-42" y="-12" width="84" height="24" rx="5" fill="#0f172a" opacity="0.85" />
          <text x="0" y="4" fill="#ffffff" fontSize="10" fontWeight="bold" textAnchor="middle">
            N_IN: {approaches['J1_N_IN']?.queue || 0} xe
          </text>
        </g>

        {/* West Approach Badge */}
        <g transform={`translate(45, ${cy + halfRoad / 2})`}>
          <rect x="-40" y="-12" width="80" height="24" rx="5" fill="#0f172a" opacity="0.85" />
          <text x="0" y="4" fill="#ffffff" fontSize="10" fontWeight="bold" textAnchor="middle">
            W_IN: {approaches['J1_W_IN']?.queue || 0} xe
          </text>
        </g>

        {/* East Approach Badge */}
        <g transform={`translate(${width - 45}, ${cy - halfRoad / 2})`}>
          <rect x="-40" y="-12" width="80" height="24" rx="5" fill="#0f172a" opacity="0.85" />
          <text x="0" y="4" fill="#ffffff" fontSize="10" fontWeight="bold" textAnchor="middle">
            E_IN: {approaches['J1_E_IN']?.queue || 0} xe
          </text>
        </g>

        {/* Downstream J3 Visual Box */}
        <g transform={`translate(${cx}, ${height - 55})`}>
          <rect
            x="-110"
            y="-25"
            width="220"
            height="50"
            rx="8"
            fill={isJ3Blocked ? "#fef2f2" : "#f8fafc"}
            stroke={isJ3Blocked ? "#ef4444" : "#0284c7"}
            strokeWidth="2"
          />
          <text x="-95" y="-8" fill="#0f172a" fontSize="11" fontWeight="800">
            NÚT HẠ LƯU J3 (E_J1_J3_SB)
          </text>
          <text x="-95" y="10" fill="#64748b" fontSize="10">
            Độ chiếm dụng (Occ):
          </text>
          <text x="35" y="10" fill={isJ3Blocked ? "#dc2626" : "#0284c7"} fontSize="11" fontWeight="bold">
            {(downstreamJ3.occupancy * 100).toFixed(0)}% {isJ3Blocked ? '(BÃO HÒA!)' : '(Bình thường)'}
          </text>

          {/* Occupancy progress bar */}
          <rect x="-95" y="15" width="190" height="6" rx="3" fill="#e2e8f0" />
          <rect
            x="-95"
            y="15"
            width={Math.min(190, 190 * downstreamJ3.occupancy)}
            height="6"
            rx="3"
            fill={isJ3Blocked ? "#dc2626" : (downstreamJ3.occupancy > 0.6 ? "#f59e0b" : "#10b981")}
          />
        </g>

        {/* Status Overlays */}
        {/* Anti-Gridlock Gated Banner */}
        {isGated && (
          <g transform={`translate(${cx}, ${cy - halfRoad - 25})`}>
            <rect x="-105" y="-14" width="210" height="28" rx="6" fill="#fef3c7" stroke="#d97706" strokeWidth="1.5" />
            <text x="0" y="4" fill="#92400e" fontSize="11" fontWeight="800" textAnchor="middle">
              🛡️ CTM GATED: Cắt đèn xanh J1_N_IN
            </text>
          </g>
        )}

        {/* Gridlock Warning Banner (Fixed-Time Failure) */}
        {isGridlocked && (
          <g transform={`translate(${cx}, ${cy})`}>
            <rect x="-100" y="-22" width="200" height="44" rx="8" fill="#fee2e2" stroke="#ef4444" strokeWidth="2" />
            <text x="0" y="-4" fill="#991b1b" fontSize="12" fontWeight="900" textAnchor="middle">
              ⚠️ GRIDLOCK (KẸT CHỮ THẬP)
            </text>
            <text x="0" y="12" fill="#b91c1c" fontSize="10" fontWeight="600" textAnchor="middle">
              Xe chặn ngang nút giao!
            </text>
          </g>
        )}
      </svg>
    </div>
  );
};

export default CtmIntersectionCanvas;
