"""Versioned research protocol shared by simulation, training and inference."""

TOPOLOGY_ID = "four_intersection_rl_v1"
TIMING = {"step_s": 1, "decision_s": 5, "min_green_s": 10,
          "max_green_s": 60, "yellow_s": 3, "all_red_s": 2}
SIGNAL_STATES = ("GREEN", "YELLOW", "ALL_RED")
FEATURE_SPEC = {
    "version": "shared_dqn_v1", "queue_scale": 20.0, "time_scale_s": 60.0,
    "ordering": [*[f"local_{d}_{x}" for d in "NSEW" for x in ("queue", "occupancy")],
                 *[f"downstream_{d}_{x}" for d in "NSEW" for x in ("queue", "occupancy")],
                 "phase_ns", "phase_ew", "green", "yellow", "all_red",
                 "elapsed_green", "age_ns", "age_ew",
                 *[f"valid_{d}" for d in "NSEW"]],
    "normalization": "queues / 20, seconds / 60; no clipping; occupancy and validity in [0,1]",
}
FAIR_CYCLE_FEATURE_SPEC = {
    "version": "fair_cycle_dqn_v1",
    "base_feature_version": FEATURE_SPEC["version"],
    "ordering": [*FEATURE_SPEC["ordering"],
                 *[f"{d}_{name}" for d in "NSEW" for name in (
                     "stopped_wait_sum", "oldest_stopped_wait", "external_due_count",
                     "external_wait_sum", "oldest_external_wait")],
                 "remaining_demand_fraction", "remaining_episode_fraction",
                 "base_ns_share", "previous_ns_share"],
    "normalization": "base shared_dqn_v1 plus wait sums / 2400, oldest waits / 1200, external counts / 20, time and green shares in [0,1]",
}
SEED_SPLITS = {"train": tuple(range(20000, 21000)),
               "validation": tuple(range(30001, 30006)),
               # 40001-40010 was opened during the first DQN evaluation; it is
               # retained for regression only and is no longer a pristine holdout.
               "holdout": tuple(range(50001, 50011))}
RESEARCH_SCENARIOS = {
    "balanced": {"profile": "balanced"},
    "directional_surge": {"profile": "directional_surge"},
    "downstream_bottleneck": {"profile": "downstream_bottleneck",
                              "edge": "J3_S_OUT", "begin_s": 600,
                              "end_s": 1200, "speed_mps": 2.0},
}
RESEARCH_ROBUSTNESS_SCENARIOS = {
    "directional_surge_ew": {"profile": "directional_surge_ew"},
}
ALL_RESEARCH_SCENARIOS = {**RESEARCH_SCENARIOS, **RESEARCH_ROBUSTNESS_SCENARIOS}


def validate_research_topology(topology):
    """Reject model inputs whose canonical node/feature/action order has drifted."""
    node_ids = [f"J{i}" for i in range(1, 5)]
    if topology.get("topology_id") != TOPOLOGY_ID:
        raise ValueError("Shared DQN requires four_intersection_rl_v1")
    nodes = topology.get("nodes", [])
    if [node.get("node_id") for node in nodes] != node_ids:
        raise ValueError("Shared DQN node order does not match its feature contract")
    node_ids_set = set(node_ids)
    for node in nodes:
        nid = node["node_id"]
        expected_approaches = [f"{nid}_{direction}_IN" for direction in "NSEW"]
        phases = node.get("phases", [])
        if node.get("approaches") != expected_approaches or [p.get("phase_id") for p in phases] != [f"{nid}_PHASE_NS", f"{nid}_PHASE_EW"]:
            raise ValueError(f"Shared DQN phase/approach order drift at {nid}")
        movements = [m for phase in phases for m in phase.get("movements", [])]
        if {m.get("from_approach") for m in movements} != set(expected_approaches) or len(movements) != 4:
            raise ValueError(f"Shared DQN movement order/mapping is incomplete at {nid}")
        for movement in movements:
            to_node, to_approach = movement.get("to_node"), movement.get("to_approach")
            if to_node is None:
                if to_approach is not None:
                    raise ValueError(f"Boundary movement has an internal target at {nid}")
            elif to_node not in node_ids_set or to_approach not in next(n["approaches"] for n in nodes if n["node_id"] == to_node):
                raise ValueError(f"Invalid mapped downstream approach at {nid}")
    return topology
