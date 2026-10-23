// Topology contracts converted from raw SUMO .net.xml (hcm_corridor, cologne8, grid4x4...) name
// phases after the SUMO traffic-light state string, e.g. "Phase 2 (GGggrrrrGGggrrrr)". That
// string is meaningless to an operator, and — having no spaces — can't line-wrap, so it forces
// its container wider than its grid/flex track and breaks the page layout around it.
// Strip it and fall back to a short, readable label.
const SUMO_STATE_SUFFIX_RE = /\s*\([GgYyRrOoUusS]{3,}\)\s*$/;

export function cleanPhaseName(name, fallback) {
  if (!name) return fallback || '';
  const cleaned = name.replace(SUMO_STATE_SUFFIX_RE, '').trim();
  return cleaned || fallback || name;
}
