import React from 'react';

const PhaseIndicator = ({ activePhase = "J1_PHASE_NS", state = "GREEN" }) => {
  const phaseUpper = String(activePhase || "").toUpperCase();
  const isNS = phaseUpper.includes("NS") || phaseUpper.includes("1");
  const isEW = phaseUpper.includes("EW") || phaseUpper.includes("2");

  return (
    <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
      {/* North-South Indicator Pill */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: '3px 8px',
        borderRadius: '6px',
        backgroundColor: isNS ? (state === 'GREEN' ? '#f0fdf4' : '#fefce8') : '#fef2f2',
        border: `1px solid ${isNS ? (state === 'GREEN' ? '#bbf7d0' : '#fef08a') : '#fee2e2'}`,
        fontSize: '0.75rem',
        fontWeight: 600
      }}>
        <span style={{ color: '#64748b', fontSize: '0.7rem' }}>N-S</span>
        <span style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: isNS ? (state === 'GREEN' ? '#22c55e' : '#eab308') : '#ef4444',
          boxShadow: isNS && state === 'GREEN' ? '0 0 6px rgba(34, 197, 94, 0.6)' : 'none'
        }} />
        <span style={{ color: isNS ? (state === 'GREEN' ? '#15803d' : '#a16207') : '#991b1b', fontSize: '0.7rem', fontWeight: 700 }}>
          {isNS ? state : 'RED'}
        </span>
      </div>

      {/* East-West Indicator Pill */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: '3px 8px',
        borderRadius: '6px',
        backgroundColor: isEW ? (state === 'GREEN' ? '#f0fdf4' : '#fefce8') : '#fef2f2',
        border: `1px solid ${isEW ? (state === 'GREEN' ? '#bbf7d0' : '#fef08a') : '#fee2e2'}`,
        fontSize: '0.75rem',
        fontWeight: 600
      }}>
        <span style={{ color: '#64748b', fontSize: '0.7rem' }}>E-W</span>
        <span style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: isEW ? (state === 'GREEN' ? '#22c55e' : '#eab308') : '#ef4444',
          boxShadow: isEW && state === 'GREEN' ? '0 0 6px rgba(34, 197, 94, 0.6)' : 'none'
        }} />
        <span style={{ color: isEW ? (state === 'GREEN' ? '#15803d' : '#a16207') : '#991b1b', fontSize: '0.7rem', fontWeight: 700 }}>
          {isEW ? state : 'RED'}
        </span>
      </div>
    </div>
  );
};

export default PhaseIndicator;
