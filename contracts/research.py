"""Versioned research protocol shared by simulation, training and inference."""

import math

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

# Graph-MAPPO is a separate protocol; archived DQN contracts remain unchanged.
GRAPH_MAPPO_NODE_ORDER = ("J1", "J2", "J3", "J4")
GRAPH_MAPPO_FEATURE_SPEC = {**FAIR_CYCLE_FEATURE_SPEC,
                            "version": "fair_cycle_residual_mappo_v1"}
GRAPH_MAPPO_TIMING = {**TIMING, "cycle_time_s": 90, "min_green_share": 0.25}
GRAPH_MAPPO_HORIZON = {"demand_s": 1800, "drain_s": 600, "horizon_s": 2400}
GRAPH_MAPPO_ACTIONS = (-5, 0, 5)
GRAPH_MAPPO_RELATION_FEATURE_SPEC = {
    "version": "movement_relation_v1",
    "ordering": [*[f"source_approach_{d}" for d in "NSEW"],
                 *[f"destination_approach_{d}" for d in "NSEW"],
                 "controlling_phase_ns", "controlling_phase_ew", "turn_ratio",
                 "capacity_over_20", "follows_movement", "reverses_movement", "self_relation"],
    "normalization": "approach and phase indicators in [0,1]; capacity / 20; turn ratio unchanged",
}
GRAPH_MAPPO_MODEL_SPEC = {
    "version": "graph_mappo_actor_v1",
    "node_order": list(GRAPH_MAPPO_NODE_ORDER),
    "feature_spec": GRAPH_MAPPO_FEATURE_SPEC,
    "relation_feature_spec": GRAPH_MAPPO_RELATION_FEATURE_SPEC,
    "actor": {"node_encoder": [len(FAIR_CYCLE_FEATURE_SPEC["ordering"]), 64],
              "attention_layers": 2, "heads": 4, "head_dim": 16,
              "attention": "additive_receiver_sender_relation_softmax_by_receiver",
              "residual": True, "activation": "relu", "dropout": 0.0},
    "action_meanings_s": list(GRAPH_MAPPO_ACTIONS),
    "critic": {"node_encoder": [len(FAIR_CYCLE_FEATURE_SPEC["ordering"]), 64],
               "value_head": [128, 64, 1], "training_only": True},
}
GRAPH_MAPPO_PROTOCOL = {
    "version": "graph_mappo_four_intersection_v1",
    "training_seeds": list(range(20000, 21000)),
    "validation_seeds": list(range(31001, 31006)),
    "holdout_seeds": list(range(60001, 60011)),
    "learner_seeds": [17, 29, 43],
    "pilot_seed": 11,
}
GRAPH_MAPPO_SEED_SPLITS = {
    "train": tuple(GRAPH_MAPPO_PROTOCOL["training_seeds"]),
    "validation": tuple(GRAPH_MAPPO_PROTOCOL["validation_seeds"]),
    "holdout": tuple(GRAPH_MAPPO_PROTOCOL["holdout_seeds"]),
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


def build_research_graph(topology, node_order=GRAPH_MAPPO_NODE_ORDER):
    """Build deterministic directed movement relations, retaining every movement."""
    validate_research_topology(topology)
    node_order = tuple(node_order)
    if node_order != GRAPH_MAPPO_NODE_ORDER:
        raise ValueError("Graph-MAPPO requires the canonical J1-J4 node order")
    nodes = {node["node_id"]: node for node in topology["nodes"]}
    positions = {node_id: index for index, node_id in enumerate(node_order)}
    senders, receivers, features, relation_ids, self_relations = [], [], [], [], []

    def direction(approach, owner):
        prefix = f"{owner}_"
        if not approach.startswith(prefix):
            raise ValueError(f"Approach {approach!r} does not belong to {owner}")
        cardinal = approach[len(prefix):len(prefix) + 1]
        if cardinal not in "NSEW" or not approach.endswith("_IN"):
            raise ValueError(f"Invalid canonical approach {approach!r}")
        return "NSEW".index(cardinal)

    def relation_feature(from_app=None, from_node=None, to_app=None, to_node=None,
                         phase_index=None, turn_ratio=0., capacity=0., forward=False,
                         reverse=False, self_relation=False):
        row = [0.] * len(GRAPH_MAPPO_RELATION_FEATURE_SPEC["ordering"])
        if self_relation:
            row[-1] = 1.
            return row
        row[direction(from_app, from_node)] = 1.
        row[4 + direction(to_app, to_node)] = 1.
        row[8 + phase_index] = 1.
        row[10] = turn_ratio
        row[11] = capacity / 20.
        row[12] = float(forward)
        row[13] = float(reverse)
        return row

    for node_id in node_order:
        for phase_index, phase in enumerate(nodes[node_id]["phases"]):
            for movement_index, movement in enumerate(phase["movements"]):
                target = movement.get("to_node")
                target_approach = movement.get("to_approach")
                if target is None:
                    if target_approach is not None:
                        raise ValueError("Boundary movement cannot have an intersection approach")
                    continue
                if target not in positions or target_approach not in nodes[target]["approaches"]:
                    raise ValueError("Movement points outside the canonical graph")
                source_approach = movement["from_approach"]
                turn_ratio = float(movement["turn_ratio"])
                capacity = float(movement["capacity_vehicles"])
                if not math.isfinite(turn_ratio) or turn_ratio < 0 or not math.isfinite(capacity) or capacity <= 0:
                    raise ValueError("Invalid movement relation attributes")
                identity = (f"{node_id}:{phase['phase_id']}:{source_approach}->"
                            f"{target}:{target_approach}:{movement.get('to_edge', movement_index)}")
                senders.extend((positions[node_id], positions[target]))
                receivers.extend((positions[target], positions[node_id]))
                features.append(relation_feature(source_approach, node_id, target_approach, target,
                                                 phase_index, turn_ratio, capacity, forward=True))
                features.append(relation_feature(source_approach, node_id, target_approach, target,
                                                 phase_index, turn_ratio, capacity, reverse=True))
                relation_ids.extend((f"{identity}:forward", f"{identity}:reverse"))
                self_relations.extend((False, False))
    for node_id in node_order:
        senders.append(positions[node_id])
        receivers.append(positions[node_id])
        features.append(relation_feature(self_relation=True))
        relation_ids.append(f"self:{node_id}")
        self_relations.append(True)
    return {"node_order": list(node_order), "senders": senders, "receivers": receivers,
            "relation_features": features, "relation_ids": relation_ids,
            "self_relations": self_relations}
