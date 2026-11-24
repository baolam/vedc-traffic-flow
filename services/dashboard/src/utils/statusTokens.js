// Canonical semantic status palette shared by every status-bearing badge/dot in the dashboard.
// Resolves the many raw status strings the API/graph-control/actuator emit (ONLINE,
// WAITING_FOR_TELEMETRY, SIGNAL_LOST, SAFE_STOP, HEALTHY, DISCONNECTED, ...) down to exactly
// four visual tiers, so "healthy" and "no data yet" can never both render as the same color,
// and a real fault is never mistaken for a transient "waiting" state.
//
//   success  - operating normally (green)
//   warning  - degraded but not unsafe, or a transient in-progress state (amber)
//   critical - a real fault, loss of control, or disconnect an operator must act on (red)
//   neutral  - no data yet / not applicable (slate gray -- never red)

export const STATUS_TIERS = {
  success: {
    bg: '#dcfce7',
    color: '#15803d',
    border: '#bbf7d0',
    dot: '#16a34a'
  },
  warning: {
    bg: '#fef9c3',
    color: '#a16207',
    border: '#fef08a',
    dot: '#ca8a04'
  },
  critical: {
    bg: '#fee2e2',
    color: '#b91c1c',
    border: '#fecaca',
    dot: '#dc2626'
  },
  neutral: {
    bg: '#f1f5f9',
    color: '#475569',
    border: '#e2e8f0',
    dot: '#94a3b8'
  }
};

// Order matters: first match wins. Keep more specific statuses above generic ones.
const TIER_RULES = [
  ['neutral', [
    'WAITING_FOR_TELEMETRY', 'WAITING', 'UNKNOWN', 'NO_DATA', 'IDLE', 'N/A'
  ]],
  ['critical', [
    'CRITICAL', 'DISCONNECTED', 'OFFLINE', 'SIGNAL_LOST', 'CAMERA_FAULT', 'ACTUATOR_FAULT', 'HARDWARE_FAULT',
    'HEARTBEAT_LOST', 'UNHEALTHY', 'FAILED', 'REJECTED', 'NOT_APPLIED', 'EXPIRED', 'INTERLOCK',
    'CONGESTED', 'HEAVY'
  ]],
  ['warning', [
    'ATTENTION', 'DEGRADED', 'MODERATE', 'WARNING', 'FALLBACK', 'CLEARING', 'SENT', 'ACCEPTED',
    'SAFE_STOP', 'ZERO_CONFIDENCE', 'PENDING', 'EMERGENCY_FLASH'
  ]],
  ['success', [
    'HEALTHY', 'ONLINE', 'OPTIMAL', 'ACTIVE', 'APPLIED', 'NORMAL', 'GREEN', 'SUCCESS', 'LOW'
  ]]
];

/**
 * Resolve a raw backend status string to its semantic tier key.
 * Unrecognized strings resolve to "neutral" rather than a default color, since treating an
 * unknown status as an alarm (or as healthy) is worse than treating it as "no information yet".
 */
export function getStatusTier(rawStatus) {
  if (!rawStatus) return 'neutral';
  const s = String(rawStatus).toUpperCase();
  for (const [tier, keywords] of TIER_RULES) {
    if (keywords.some((kw) => s === kw || s.includes(kw))) {
      return tier;
    }
  }
  return 'neutral';
}

/** Resolve a raw status string straight to its {bg, color, border, dot} token. */
export function getStatusToken(rawStatus) {
  return STATUS_TIERS[getStatusTier(rawStatus)];
}
