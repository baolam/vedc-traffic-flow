"""Fail-closed, NumPy-only inference for graph and self-only MAPPO actors."""

import hashlib
import json
import math
import uuid
from copy import deepcopy

from contracts.contracts_sdk import CONTRACTS_DIR, load_topology, validate_payload
from contracts.research import (GRAPH_MAPPO_FEATURE_SPEC, GRAPH_MAPPO_ACTIONS,
                                GRAPH_MAPPO_HORIZON, GRAPH_MAPPO_MODEL_SPEC,
                                GRAPH_MAPPO_NODE_ORDER, GRAPH_MAPPO_PROTOCOL,
                                GRAPH_MAPPO_RELATION_FEATURE_SPEC, GRAPH_MAPPO_TIMING,
                                TOPOLOGY_ID, build_research_graph,
                                validate_research_topology)
from .fair_cycle import FairCycleController
from .graph_mappo_numpy import NumpyGraphActor
from .research import extract_fair_cycle_features


class GraphMAPPOController(FairCycleController):
    """Shared four-node policy that installs one masked joint residual decision per cycle."""

    def __init__(self, model_path, cycle_time_s=None, min_green_share=None,
                 demand_s=None, drain_s=None):
        if not model_path:
            raise ValueError("graph_mappo requires an explicit model_path")
        with open(model_path, encoding="utf-8") as handle:
            self.artifact = json.load(handle)
        validate_payload(self.artifact, "graph_mappo_model")
        actor_digest = hashlib.sha256(json.dumps(
            self.artifact["weights"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if actor_digest != self.artifact["provenance"]["actor_sha256"]:
            raise ValueError("Graph-MAPPO actor weights failed their provenance hash")
        if self.artifact["architecture"] != {
                "graph_mappo": "graph_attention", "local_mappo": "self_only"}[self.artifact["algorithm"]]:
            raise ValueError("Algorithm and actor communication architecture disagree")
        canonical_topology_path = CONTRACTS_DIR / "topology" / f"{TOPOLOGY_ID}.json"
        canonical_topology_hash = hashlib.sha256(canonical_topology_path.read_bytes()).hexdigest()
        if self.artifact["provenance"]["topology_sha256"] != canonical_topology_hash:
            raise ValueError("Graph-MAPPO actor was trained against a different topology contract")
        if self.artifact["model_spec"] != GRAPH_MAPPO_MODEL_SPEC:
            raise ValueError("Incompatible graph-MAPPO architecture contract")
        if (self.artifact["feature_spec"] != GRAPH_MAPPO_FEATURE_SPEC
                or self.artifact["relation_feature_spec"] != GRAPH_MAPPO_RELATION_FEATURE_SPEC
                or self.artifact["node_order"] != list(GRAPH_MAPPO_NODE_ORDER)
                or self.artifact["topology_id"] != TOPOLOGY_ID
                or self.artifact["timing"] != GRAPH_MAPPO_TIMING
                or self.artifact["horizon"] != GRAPH_MAPPO_HORIZON
                or self.artifact["protocol"] != GRAPH_MAPPO_PROTOCOL):
            raise ValueError("Incompatible graph-MAPPO feature, graph, timing or protocol contract")
        if cycle_time_s is not None and cycle_time_s != GRAPH_MAPPO_TIMING["cycle_time_s"]:
            raise ValueError("Model cycle timing does not match requested timing")
        if min_green_share is not None and min_green_share != GRAPH_MAPPO_TIMING["min_green_share"]:
            raise ValueError("Model minimum green share does not match requested timing")
        if demand_s is not None and demand_s != GRAPH_MAPPO_HORIZON["demand_s"]:
            raise ValueError("Model demand horizon does not match requested horizon")
        if drain_s is not None and drain_s != GRAPH_MAPPO_HORIZON["drain_s"]:
            raise ValueError("Model drain horizon does not match requested horizon")
        super().__init__(GRAPH_MAPPO_TIMING["cycle_time_s"], GRAPH_MAPPO_TIMING["min_green_share"])
        self.controller_name = self.artifact["algorithm"]
        self.local_only = self.artifact["architecture"] == "self_only"
        self.demand_s = GRAPH_MAPPO_HORIZON["demand_s"]
        self.horizon_s = GRAPH_MAPPO_HORIZON["horizon_s"]
        self._graph = build_research_graph(load_topology(TOPOLOGY_ID))
        self._actor = NumpyGraphActor(self.artifact["weights"], self._graph,
                                      local_only=self.local_only)
        self._decision_signature = None

    def reset(self):
        super().reset()
        self._decision_signature = None

    @staticmethod
    def _finite_time(value, node_id):
        time_s = float(value)
        if not math.isfinite(time_s) or time_s < 0:
            raise ValueError(f"Invalid simulation time for {node_id}")
        return time_s

    def _snapshot(self, node_id, telemetry, network_state, current_time_s):
        if telemetry.get("node_id") not in (None, node_id):
            raise ValueError("Telemetry node ID does not match controller call")
        snapshot = deepcopy(network_state or {})
        snapshot[node_id] = telemetry
        if set(snapshot) != set(GRAPH_MAPPO_NODE_ORDER):
            raise ValueError("Graph-MAPPO requires a complete four-intersection snapshot")
        times = {key: self._finite_time(value["simulation_time_s"], key)
                 for key, value in snapshot.items()}
        now = self._finite_time(current_time_s if current_time_s is not None
                                else telemetry["simulation_time_s"], node_id)
        if any(abs(value - now) > GRAPH_MAPPO_TIMING["decision_s"] for value in times.values()):
            raise ValueError("Graph-MAPPO requires a complete fresh network snapshot")
        return snapshot, now

    def _install_joint_decision(self, topology, snapshot, now):
        nodes = {node["node_id"]: node for node in topology["nodes"]}
        features, masks = [], []
        for node_id in GRAPH_MAPPO_NODE_ORDER:
            node, state = nodes[node_id], snapshot[node_id]
            base_split, previous_split = self.preview_cycle(node_id, state, topology, snapshot)
            features.append(extract_fair_cycle_features(
                node, state, snapshot, base_split, previous_split,
                demand_s=self.demand_s, horizon_s=self.horizon_s))
            mask = self.residual_mask_for(base_split[0])
            if len(mask) != len(GRAPH_MAPPO_ACTIONS) or not any(mask):
                raise ValueError("Graph-MAPPO received an empty residual action mask")
            masks.append(mask)
        actions = self._actor.deterministic_actions(features, masks)
        for index, node_id in enumerate(GRAPH_MAPPO_NODE_ORDER):
            if not masks[index][int(actions[index])]:
                raise RuntimeError("Graph-MAPPO selected an illegal residual action")
            self.begin_cycle(node_id, snapshot[node_id], topology, snapshot,
                             adjustment=GRAPH_MAPPO_ACTIONS[int(actions[index])])
        self._decision_signature = (now, tuple(int(action) for action in actions))

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        if node_id not in GRAPH_MAPPO_NODE_ORDER:
            raise ValueError(f"Unsupported graph-MAPPO node: {node_id}")
        validate_research_topology(topology)
        if topology["topology_id"] != self.artifact["topology_id"]:
            raise ValueError("Model/topology mismatch")
        if build_research_graph(topology) != self._graph:
            raise ValueError("Runtime movement graph does not match the frozen actor graph")
        snapshot, now = self._snapshot(node_id, telemetry, network_state, current_time_s)
        nodes = {node["node_id"]: node for node in topology["nodes"]}
        at_boundary = all(
            snapshot[key]["current_phase_id"] == nodes[key]["phases"][0]["phase_id"]
            and snapshot[key]["signal_state"] == "GREEN"
            and float(snapshot[key]["elapsed_green_s"]) == 0.
            for key in GRAPH_MAPPO_NODE_ORDER)
        if at_boundary and (self._decision_signature is None
                            or self._decision_signature[0] != now):
            self._install_joint_decision(topology, snapshot, now)
        if any(key not in self._state for key in GRAPH_MAPPO_NODE_ORDER):
            raise RuntimeError("Graph-MAPPO has no complete joint cycle decision")
        if at_boundary and self._decision_signature[0] == now and not self._state:
            raise RuntimeError("Graph-MAPPO could not install a joint cycle decision")
        node = nodes[node_id]
        return super().compute_command(node_id, telemetry, topology, snapshot, current_time_s)


LocalMAPPOController = GraphMAPPOController
