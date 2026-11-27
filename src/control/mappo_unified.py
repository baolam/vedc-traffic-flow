"""Unified MAPPO deployment: graph, node features, framework-free actor and the cycle-residual controller.

Node features are local telemetry only (observation radius 0); two attention layers give each node exactly
two hops of communication over the movement graph. Local MAPPO keeps self-edges only, so communication is
the single difference between the two variants.
"""
import json
from collections import Counter

import numpy as np

from contracts.benchmark import CYCLE_DQN as D, CYCLE_RULE as R, OBSERVATION_SPEC as OBS, TIMING, UNIFIED_MAPPO as M
from contracts.contracts_sdk import validate_payload
from .cycle_dqn import GRID, FairCycleNativeController, candidate_mask
from .cycle_plan import cycle_length
from .observation import flow_index, observe_node
from .unified_dqn import MAX_PHASES, pad_rows

NODE_DIM, REL_DIM, HEADS, HIDDEN = M["node_dim"], M["relation_dim"], M["heads"], M["hidden"]
MAPPO_ALGORITHMS = ("graph_mappo_unified", "local_mappo_unified")


class Graph:
    """Directed message edges (sender -> receiver) with a padded incoming-edge table per receiver."""

    def __init__(self, topology, local_only=False):
        nodes = topology["nodes"]
        self.node_ids = [n["node_id"] for n in nodes]
        index = {nid: i for i, nid in enumerate(self.node_ids)}
        links = Counter()
        for n in nodes:
            for phase in n["phases"]:
                for m in phase.get("movements", []):
                    if m.get("to_node") is not None:
                        links[(index[n["node_id"]], index[m["to_node"]])] += 1
        peak = max(links.values(), default=1)
        edges = [(i, i, [1., 0., 0., 0.]) for i in range(len(nodes))]  # self relation
        if not local_only:
            for (u, v), count in sorted(links.items()):
                edges.append((u, v, [0., 1., 0., count / peak]))  # upstream -> downstream
                edges.append((v, u, [0., 0., 1., count / peak]))  # downstream -> upstream
        self.senders = np.array([e[0] for e in edges], np.int64)
        self.receivers = np.array([e[1] for e in edges], np.int64)
        self.relation = np.array([e[2] for e in edges], np.float32)
        incoming = [np.flatnonzero(self.receivers == i) for i in range(len(nodes))]
        width = max(len(i) for i in incoming)
        self.incoming = np.zeros((len(nodes), width), np.int64)
        self.incoming_mask = np.zeros((len(nodes), width), bool)
        for i, edge_ids in enumerate(incoming):
            self.incoming[i, : len(edge_ids)] = edge_ids
            self.incoming_mask[i, : len(edge_ids)] = True


def snapshot_features(nodes, view, plans, flow, acting=None):
    """(N, NODE_DIM): padded local phase rows, current plan greens, phase count, cycle length.

    `plans` maps node id -> greens of its running cycle; `acting` = (node id, base greens) overrides the node
    that is deciding now. Nodes with no plan yet contribute zero greens.
    """
    x = np.zeros((len(nodes), NODE_DIM), np.float32)
    for i, node in enumerate(nodes):
        nid, phases = node["node_id"], len(node["phases"])
        greens = acting[1] if acting and acting[0] == nid else plans.get(nid)
        padded = np.zeros(MAX_PHASES, np.float32)
        if greens is not None:
            padded[:phases] = greens
        rows = pad_rows(observe_node(node, view, flow, 0)).reshape(-1)  # radius 0: own telemetry only
        x[i] = np.concatenate([rows, padded / R["max_green_s"], [phases / MAX_PHASES, cycle_length(phases) / 200]])
    return x


def _linear(layer, values):
    return values @ np.asarray(layer["weight"], np.float32).T + np.asarray(layer["bias"], np.float32)


def with_noop_prior(logits, legal):
    """Add log(legal transfers) to the no-op logit, so the learned no-op bias is a phase-count-free prior."""
    logits = np.array(logits, np.float64)
    logits[..., GRID - 1] += np.log(np.maximum(1, np.asarray(legal)[..., :GRID - 1].sum(-1)))
    return logits


def actor_logits(weights, x, graph):
    """Framework-free forward pass; mirrors the torch actor exactly. x (N, NODE_DIM) -> (N, GRID)."""
    hidden = np.maximum(_linear(weights["encoder"], x), 0)
    for layer in weights["attention"]:
        projected = _linear(layer["node"], hidden).reshape(-1, HEADS, HIDDEN // HEADS)
        relation = _linear(layer["relation"], graph.relation).reshape(-1, HEADS, HIDDEN // HEADS)
        receiver, sender, rel = (np.asarray(layer[k], np.float32) for k in
                                 ("attention_receiver", "attention_sender", "attention_relation"))
        scores = ((projected[graph.receivers] * receiver).sum(-1) + (projected[graph.senders] * sender).sum(-1)
                  + (relation * rel).sum(-1))
        scores = np.where(scores > 0, scores, 0.2 * scores)
        messages = projected[graph.senders] + relation
        grouped = np.where(graph.incoming_mask[..., None], scores[graph.incoming], -np.inf)  # (N, D, heads)
        grouped = np.exp(grouped - grouped.max(axis=1, keepdims=True))
        attention = grouped / grouped.sum(axis=1, keepdims=True)
        aggregated = (attention[..., None] * messages[graph.incoming]).sum(axis=1)
        hidden = np.maximum(hidden + aggregated.reshape(len(x), HIDDEN), 0)
    return _linear(weights["head"], hidden)


class UnifiedMAPPOController(FairCycleNativeController):
    """Deployed unified MAPPO actor: greedy masked transfer at each node's cycle start."""

    def __init__(self, model_path, inference_device="cpu"):
        if not model_path:
            raise ValueError("MAPPO controllers require an explicit model_path")
        with open(model_path, encoding="utf-8") as handle:
            self.artifact = a = json.load(handle)
        validate_payload(a, "unified_mappo_model")
        if (a["observation"] != OBS or a["timing"] != TIMING or a["cycle_rule"] != R
                or a.get("candidate_extras") != D["extras"] or a.get("node_dim") != NODE_DIM):
            raise ValueError("Incompatible MAPPO model specification")
        if inference_device != "cpu":
            raise ValueError("Unified MAPPO inference is CPU/NumPy")
        if len(a["weights"]["head"]["bias"]) != GRID or len(a["weights"]["attention"]) != M["layers"]:
            raise ValueError("MAPPO weights do not match the candidate grid or layer count")
        self.controller_name = a["algorithm"]
        self.local_only = a["algorithm"] == "local_mappo_unified"
        self.weights = a["weights"]
        self._maps = {}
        super().__init__(selector=self._select)

    def compute_command(self, node_id, telemetry, topology, network_state=None, current_time_s=None):
        if topology["topology_id"] != self.artifact["topology_id"]:
            raise ValueError("Model was trained for another map")
        if topology["topology_id"] not in self._maps:
            self._maps[topology["topology_id"]] = (Graph(topology, self.local_only), flow_index(topology), topology["nodes"])
        self._graph, self._flow, self._nodes = self._maps[topology["topology_id"]]
        if set(network_state or {}) | {node_id} != set(self._graph.node_ids):
            raise ValueError("MAPPO requires a complete network snapshot")
        return super().compute_command(node_id, telemetry, topology, network_state, current_time_s)

    def _select(self, node, view, base):
        nid, phases = node["node_id"], len(base)
        x = snapshot_features(self._nodes, view, self.plans(), self._flow, acting=(nid, base))
        logits = actor_logits(self.weights, x, self._graph)[self._graph.node_ids.index(nid)]
        greens = np.zeros(MAX_PHASES, np.float32)
        greens[:phases] = base
        legal = candidate_mask(greens, phases)
        return int(np.argmax(np.where(legal, with_noop_prior(logits, legal), -np.inf)))
