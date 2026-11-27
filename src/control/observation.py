"""Map-independent raw-telemetry observation (raw_two_hop_v1) with an enforced hop radius."""
import numpy as np
from contracts.benchmark import OBSERVATION_SPEC as SPEC

Q = SPEC["normalization"]["queue_vehicles"]


def flow_index(topology):
    """down[(node, approach)] -> receiving (node, approach) pairs; up[...] the reverse."""
    down, up = {}, {}
    for node in topology["nodes"]:
        for phase in node["phases"]:
            for m in phase.get("movements", []):
                if m.get("to_node") is not None:
                    src, dst = (node["node_id"], m["from_approach"]), (m["to_node"], m["to_approach"])
                    down.setdefault(src, set()).add(dst)
                    up.setdefault(dst, set()).add(src)
    return dict(down=down, up=up)


def _step(index, frontier):
    return {t for key in frontier for t in index.get(key, ())}


def _aggregate(telemetry, keys, confidence):
    rows = []
    for node, approach in sorted(keys):
        if node not in telemetry:
            raise ValueError(f"Telemetry for {node} is required within the observation radius")
        rows.append(next(a for a in telemetry[node]["approaches"] if a["approach_id"] == approach))
    confidence.extend(r["confidence"] for r in rows)
    return (sum(r["queue_vehicles"] for r in rows) / Q, max((r["occupancy_ratio"] for r in rows), default=0.0))


def observe_node(node, telemetry, index, radius=SPEC["radius_hops"]):
    """Rows per native phase. Only nodes within `radius` hops are read; radius 0 is local-only."""
    own = telemetry[node["node_id"]]
    local = {a["approach_id"]: a for a in own["approaches"]}
    rows = []
    for phase in node["phases"]:
        served_ids = sorted(set(phase["approaches"]))
        served = [local[a] for a in served_ids]
        confidence = [a["confidence"] for a in served]
        groups = [(sum(a["queue_vehicles"] for a in served) / Q, float(np.mean([a["occupancy_ratio"] for a in served])))]
        for direction in ("down", "up"):
            frontier = {(node["node_id"], a) for a in served_ids}
            for hop in (1, 2):
                frontier = _step(index[direction], frontier) if hop <= radius else set()
                groups.append(_aggregate(telemetry, frontier, confidence))
        # groups order: served, down1, down2, up1, up2 -> matches SPEC feature order
        state = own["signal_state"]
        rows.append([
            *[v for g in groups for v in g],
            sum(a["queue_vehicles"] for k, a in local.items() if k not in served_ids) / Q,
            own["phase_service_age_s"][phase["phase_id"]] / SPEC["normalization"]["service_age_s"],
            own["elapsed_green_s"] / SPEC["normalization"]["elapsed_green_s"],
            float(phase["phase_id"] == own["current_phase_id"]),
            *[float(state == s) for s in ("GREEN", "YELLOW", "ALL_RED")],
            min(confidence),
        ])
    result = np.asarray(rows, dtype=np.float32)
    if (result.shape != (len(node["phases"]), len(SPEC["features"]))
            or not np.isfinite(result).all() or (result[:, -1] <= 0).any()):
        raise ValueError("Required phase observations unavailable")
    return result
