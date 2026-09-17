import React from 'react';

const PhaseIndicator = ({ activePhase = "J1_PHASE_NS", state = "GREEN" }) => {
  const isNS = activePhase.includes("NS");
  const isEW = activePhase.includes("EW");

  return (
    <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
      {/* North-South Light */}
      <div style={{
        backgroundColor: '#0f172a',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '8px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8' }}>N-S:</span>
        <div style={{
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          backgroundColor: isNS ? (state === 'GREEN' ? '#22c55e' : state === 'YELLOW' ? '#eab308' : '#ef4444') : '#ef4444',
          boxShadow: isNS ? `0 0 8px ${state === 'GREEN' ? '#22c55e' : state === 'YELLOW' ? '#eab308' : '#ef4444'}` : 'none'
        }} />
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isNS ? '#22c55e' : '#ef4444' }}>
          {isNS ? state : 'RED'}
        </span>
      </div>

      {/* East-West Light */}
      <div style={{
        backgroundColor: '#0f172a',
        border: '1px solid #334155',
        borderRadius: '8px',
        padding: '8px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8' }}>E-W:</span>
        <div style={{
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          backgroundColor: isEW ? (state === 'GREEN' ? '#22c55e' : state === 'YELLOW' ? '#eab308' : '#ef4444') : '#ef4444',
          boxShadow: isEW ? `0 0 8px ${state === 'GREEN' ? '#22c55e' : state === 'YELLOW' ? '#eab308' : '#ef4444'}` : 'none'
        }} />
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isEW ? '#22c55e' : '#ef4444' }}>
          {isEW ? state : 'RED'}
        </span>
      </div>
    </div>
  );
};

export default PhaseIndicator;
