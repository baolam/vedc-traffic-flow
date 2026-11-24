import React from 'react';
import { getStatusToken } from '../utils/statusTokens';

const SIZES = {
  sm: { fontSize: '0.65rem', padding: '1px 6px', gap: '3px', iconSize: 10 },
  md: { fontSize: '0.72rem', padding: '3px 8px', gap: '4px', iconSize: 12 },
  lg: { fontSize: '0.8rem', padding: '4px 10px', gap: '5px', iconSize: 14 }
};

/**
 * Semantic status badge. Always resolves `status` through statusTokens so the same raw string
 * (e.g. "HEALTHY", "WAITING_FOR_TELEMETRY") renders with the same color everywhere in the app --
 * no page should hand-roll its own red/green/yellow badge styling for a status string anymore.
 */
const StatusBadge = ({ status, label, size = 'md', icon: Icon, title, dot = false }) => {
  const token = getStatusToken(status);
  const dims = SIZES[size] || SIZES.md;

  return (
    <span
      title={title}
      className="badge"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: dims.gap,
        fontSize: dims.fontSize,
        padding: dims.padding,
        backgroundColor: token.bg,
        color: token.color,
        border: `1px solid ${token.border}`
      }}
    >
      {dot && (
        <span style={{
          width: 6, height: 6, borderRadius: '50%', backgroundColor: token.dot, flexShrink: 0
        }} />
      )}
      {Icon && <Icon size={dims.iconSize} />}
      {label ?? status}
    </span>
  );
};

export default StatusBadge;
