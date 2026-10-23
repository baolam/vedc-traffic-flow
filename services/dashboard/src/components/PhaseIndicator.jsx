import React from 'react';

/**
 * PhaseIndicator
 * 
 * Accurately displays traffic signal states without creating false alarm styling.
 * Distinguishes normal cyclic RED (conflicting approach waiting) from system alerts.
 */
const PhaseIndicator = ({ activePhase = "J1_PHASE_NS", state = "GREEN", compact = false, safeStop = false }) => {
  const phaseUpper = String(activePhase || "").toUpperCase();
  // Only the literal NS/EW convention (four_intersection_v1, hcm_realworld_v1) is trustworthy here.
  // Topologies with many phases per node (grid4x4, cologne8: PHASE_1..PHASE_10) fall through to the
  // generic badge below instead of being mislabeled N-S/E-W off a "_1"/"_2" suffix match.
  const isNS = phaseUpper.includes("NS");
  const isEW = phaseUpper.includes("EW");

  // Emergency Safe-Stop button held on the board: firmware freezes its clearance state machine and
  // flashes BOTH heads yellow (writeHeads('Y'/'-', 'Y'/'-')) instead of showing any normal phase, so
  // `state`/`clearance` from health (frozen at whatever it was before the press) would be misleading
  // here. Must be checked before YELLOW/ALL_RED/NS/EW so it always wins.
  if (safeStop) {
    return (
      <div
        className="safe-stop-flash"
        title="Nút dừng khẩn cấp (Safe-Stop) đang được nhấn: cả hai hướng nhấp nháy vàng, mọi lệnh bị từ chối"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          padding: '3px 8px',
          borderRadius: '6px',
          backgroundColor: '#fef3c7',
          border: '2px solid #f59e0b',
          fontSize: '0.72rem',
          fontWeight: 800,
          color: '#92400e'
        }}
      >
        <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#f59e0b' }} />
        <span>🛑 SAFE-STOP (nhấp nháy vàng)</span>
      </div>
    );
  }

  // If in transitional clearance state (YELLOW or ALL_RED)
  if (state === 'YELLOW') {
    return (
      <div 
        title="Signal Transition: Yellow clearance interval in progress"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          padding: '3px 8px',
          borderRadius: '6px',
          backgroundColor: '#fefce8',
          border: '1px solid #fef08a',
          fontSize: '0.72rem',
          fontWeight: 600,
          color: '#a16207'
        }}
      >
        <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#eab308' }} />
        <span>CLEARANCE (YELLOW)</span>
      </div>
    );
  }

  if (state === 'ALL_RED') {
    return (
      <div 
        title="Actuator Safety Invariant: All-Red clearance ensures intersection is empty before next green"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          padding: '3px 8px',
          borderRadius: '6px',
          backgroundColor: '#fef2f2',
          border: '1px solid #fecaca',
          fontSize: '0.72rem',
          fontWeight: 600,
          color: '#991b1b'
        }}
      >
        <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#ef4444' }} />
        <span>ALL-RED CLEARANCE</span>
      </div>
    );
  }

  // Multi-phase general display if neither NS nor EW explicitly. In compact contexts (station
  // list rows) this used to dump the whole raw phase_id -- for OSM-derived node IDs that's a
  // 40+ character string (e.g. "cluster_2938641203_366431367_5750600582_PHASE_2") that blew out
  // the row layout. Compact mode now shows just the phase number, full id still on hover.
  if (!isNS && !isEW) {
    const shortLabel = phaseUpper.includes('_PHASE_')
      ? `PHASE ${activePhase.split(/_PHASE_/i).pop()}`
      : 'ACTIVE';
    return (
      <div
        title={`Active Signal Phase: ${activePhase}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          padding: '3px 8px',
          borderRadius: '6px',
          backgroundColor: '#ecfdf5',
          border: '1px solid #a7f3d0',
          fontSize: '0.72rem',
          fontWeight: 600,
          color: '#065f46',
          maxWidth: compact ? '110px' : 'none',
          overflow: 'hidden'
        }}
      >
        <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#10b981', flexShrink: 0 }} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {compact ? shortLabel : (activePhase || 'ACTIVE GREEN')}
        </span>
      </div>
    );
  }

  if (compact) {
    return (
      <div 
        title={isNS ? "Phase 1: North-South Green" : "Phase 2: East-West Green"}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          padding: '3px 8px',
          borderRadius: '6px',
          backgroundColor: '#ecfdf5',
          border: '1px solid #a7f3d0',
          fontSize: '0.72rem',
          fontWeight: 700,
          color: '#065f46'
        }}
      >
        <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#10b981' }} />
        <span>{isNS ? 'N-S GREEN' : 'E-W GREEN'}</span>
      </div>
    );
  }

  return (
    <div 
      title="Normal Traffic Signal Cycle: Green approach has right of way; red approach safely held"
      style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}
    >
      {/* North-South Phase Pill */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 7px',
        borderRadius: '5px',
        backgroundColor: isNS ? '#ecfdf5' : '#f8fafc',
        border: `1px solid ${isNS ? '#a7f3d0' : '#e2e8f0'}`,
        fontSize: '0.72rem',
        fontWeight: isNS ? 700 : 500,
        color: isNS ? '#065f46' : '#64748b'
      }}>
        <span style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: isNS ? '#10b981' : '#94a3b8'
        }} />
        <span>N-S {isNS ? 'GREEN' : 'RED'}</span>
      </div>

      {/* East-West Phase Pill */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 7px',
        borderRadius: '5px',
        backgroundColor: isEW ? '#ecfdf5' : '#f8fafc',
        border: `1px solid ${isEW ? '#a7f3d0' : '#e2e8f0'}`,
        fontSize: '0.72rem',
        fontWeight: isEW ? 700 : 500,
        color: isEW ? '#065f46' : '#64748b'
      }}>
        <span style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: isEW ? '#10b981' : '#94a3b8'
        }} />
        <span>E-W {isEW ? 'GREEN' : 'RED'}</span>
      </div>
    </div>
  );
};

export default PhaseIndicator;
