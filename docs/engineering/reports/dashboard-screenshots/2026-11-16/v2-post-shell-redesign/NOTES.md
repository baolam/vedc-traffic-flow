# Dashboard screenshots — post global-shell redesign (2026-11-16)

Second capture of all 7 routes, taken after the Phase 1 global-shell redesign (Sidebar grouping,
Header status-color fix + alert bell + EN|VI toggle, StatusBadge/statusTokens, StationContextBar).
Same capture conditions as the first set in the parent folder: API running locally, no MQTT/
simulator/vision service attached, so live metrics still read 0/WAITING_FOR_TELEMETRY.

Visible changes vs. the first capture:
- Sidebar is grouped into Live Operations / Simulation & Benchmarks / System & Hardware.
- Header's system-health pill now renders green for "HEALTHY" (previously red — see
  DASHBOARD_UI_REVIEW_20261116.md finding #1) and has an alert bell + EN|VI toggle.
- Station Details (02) and Raspberry Pi Demo (06) now have a sticky "STATIONS" quick-switcher bar
  with live status dots, replacing the old sidebar chip list.
- Raspberry Pi Demo (06) no longer has dead gray space below the fault modal — the stray
  `minHeight: 100vh` on that page's container was removed.

Not yet addressed (tracked as Phase 2, page-by-page layout work):
- Overview's above-the-fold KPI/map grid, Station Details' 2-column split + consolidated empty
  state, Camera Map's floating card placement, FlowTheory's "Next Phase Decision" labeling, and
  the Benchmark chart's first-paint sizing race (03 rendered fine this time, but the race is
  timing-dependent, not fixed).
- Full page-content i18n (every page besides the shell chrome still has hardcoded EN/VI copy).
