# Dashboard UI Review — 2026-11-16

Full-page screenshots of all 7 routes in `services/dashboard`, captured with Playwright
(Chromium, 1600px wide, full content height) against the API running locally with no
MQTT broker, simulator, or vision service attached. All live metrics therefore read
0 / WAITING_FOR_TELEMETRY — that is an artifact of the capture environment, not a
dashboard bug.

Images are numbered in the order a user would navigate the sidebar.

## Cross-cutting findings

1. **"HEALTHY" status pill rendered in danger (red) color.** Visible top-right on
   every page, next to a red shield icon. A "healthy" label styled as an alarm is
   exactly the kind of mismatch that gets misread during a quick glance at an ops
   console. Likely the status→color mapping falls through to a red default when
   `overall_status` is `WAITING_FOR_TELEMETRY` instead of treating "no data yet" as
   neutral/gray. See `Header.jsx`.
2. **Inconsistent language per page.** Overview, Experiments, and Cameras are almost
   entirely English; Station Detail, Benchmark, and the Raspberry Pi page are mostly
   Vietnamese with scattered English labels (`VIDEO`, `ROI`, `BBOX`, `APPLIED`). Looks
   organic rather than a deliberate i18n decision — worth standardizing on one
   language or adding a real toggle.

## Page-by-page

### 01 — Network Overview (`/`)
Good density: KPI cards, live topology graph with a queue-severity legend, per-station
monitoring list, collapsible event log. Minor: the small "0" count badges on the node
circles crowd right up against the ring border. All 4 stations show WAITING + ATTENTION
pills simultaneously — expected with no telemetry feed, but the two pills sitting
side-by-side in the same color family reads as redundant/cluttered.

### 02 — Station Details (`/intersections/J1`)
Thorough per-node diagnostics; consistent red-left-border cards per approach. The
"Edge Vision Perception Canvas" box stacks three separate warning tags top-left
("Chưa có health của vision", a captioned-video note, "Chưa chạy demo...") plus a
fourth, overlapping empty-state message centered in the box — four messages for one
empty state. Worth consolidating into a single centered empty-state card.

### 03 — Benchmark Campaign (`/benchmark`)
Strong, credible report (SHA-256 hash, frozen-demand chip, 300/300 runs, zero-fallback
badges). On first load the bar chart rendered as a blank gray box even though the data
table above it had numbers; it only appeared after scrolling/resizing the window. This
smells like a Recharts `ResponsiveContainer` sizing race against the app's internal
scroll container (the page body doesn't scroll — `.main-content` does — so the
container's measured width/height can be 0 on first paint). Worth checking in a real
browser: hard-refresh `/benchmark` and see if the bar chart appears without touching the
scrollbar. Also, in the detail table at the bottom, "Baseline" text in the last column
gets visually clipped against the row divider on a couple of rows.

### 04 — Control & Experiments (`/experiments`)
Clean two-column layout. The Min/Max Green sliders have draggable-looking handles but
are captioned "not adjustable here yet" — they should probably be visually disabled
(dimmed, `cursor: not-allowed`) rather than look interactive.

### 05 — HCM Camera Network (`/cameras`)
The real HCMC map with 793 cameras / 5487 edges is genuinely impressive. The floating
info card (bottom-left) sits directly on top of the densest, most-congested part of
the map (central HCMC), covering exactly the area an operator would most want to see.
Consider making it collapsible or anchoring it somewhere less data-dense.

### 06 — Raspberry Pi Demo (`/raspberry-pi-demo`, node J3)
Correctly shows the "signal lost" modal (no MQTT/video) — functionally right for this
environment. But the page's actual content is only ~470px tall while the scrollable
container is sized to ~2300px, leaving roughly 1500px of dead gray space below the
fold. This is a real layout bug specific to this page — looks like a stale height left
on the page's root container.

### 07 — FlowTheory CTM Demo (`/flowtheory-demo`)
The best-looking page: live intersection animation, step/speed controls, and a
"whiteboard" showing the actual demand/supply math with live numbers. One
inconsistency: the decision box concludes "Đông-Tây ưu tiên" (East-West should win,
F(EW) > F(NS)) while the live sim badge right above still shows "GREEN (NS)" — reads
as the demo contradicting itself unless you realize it's showing the *next* decision,
not the current one. Labeling it "Next Decision" would remove the ambiguity. Also the
two bottom history charts show only 1-2 isolated dots rather than a trend line, simply
because the capture happened seconds after page load.
