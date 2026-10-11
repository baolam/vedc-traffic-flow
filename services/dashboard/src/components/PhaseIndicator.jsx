import React from 'react';

/**
 * PhaseIndicator
 * 
 * Accurately displays traffic signal states without creating false alarm styling.
 * Distinguishes normal cyclic RED (conflicting approach waiting) from system alerts.
 */
const PhaseIndicator = ({ activePhase = "J1_PHASE_NS", state = "GREEN", compact = false }) => {
  const phaseUpper = String(activePhase || "").toUpperCase();
  const isNS = phaseUpper.includes("NS") || phaseUpper.includes("PHASE_1") || phaseUpper.endsWith("_1");
  const isEW = phaseUpper.includes("EW") || phaseUpper.includes("PHASE_2") || phaseUpper.endsWith("_2");

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

  // Multi-phase general display if neither NS nor EW explicitly
  if (!isNS && !isEW) {
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
          color: '#065f46'
        }}
      >
        <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#10b981' }} />
        <span>{activePhase || 'ACTIVE GREEN'}</span>
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
