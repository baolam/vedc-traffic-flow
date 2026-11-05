"""
EdgeFlow AI — Canonical Domain Models & Dataclasses for Contracts.

Provides strongly-typed dataclasses for Topology Graphs, Nodes, Phases, Movements,
and Schemas while preserving dictionary serializability.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class MovementSpec:
    """Represents a specific lane movement inside a traffic light phase."""
    from_approach: str
    to_edge: Optional[str] = None
    to_node: Optional[str] = None
    turn_ratio: float = 1.0
    capacity_vehicles: int = 100
    to_approach: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MovementSpec":
        return cls(
            from_approach=data.get("from_approach", ""),
            to_edge=data.get("to_edge"),
            to_node=data.get("to_node"),
            turn_ratio=float(data.get("turn_ratio", 1.0)),
            capacity_vehicles=int(data.get("capacity_vehicles", 100)),
            to_approach=data.get("to_approach"),
        )

    def to_dict(self) -> Dict[str, Any]:
        res = {"from_approach": self.from_approach}
        if self.to_edge is not None:
            res["to_edge"] = self.to_edge
        if self.to_node is not None:
            res["to_node"] = self.to_node
        res["turn_ratio"] = self.turn_ratio
        res["capacity_vehicles"] = self.capacity_vehicles
        if self.to_approach is not None:
            res["to_approach"] = self.to_approach
        return res


@dataclass
class PhaseSpec:
    """Represents a traffic signal green phase for a node."""
    phase_id: str
    name: str = ""
    approaches: List[str] = field(default_factory=list)
    movements: List[MovementSpec] = field(default_factory=list)
    sumo_phase_index: Optional[int] = None
    sumo_state: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseSpec":
        movements = [MovementSpec.from_dict(m) for m in data.get("movements", [])]
        return cls(
            phase_id=data.get("phase_id", ""),
            name=data.get("name", ""),
            approaches=list(data.get("approaches", []) or []),
            movements=movements,
            sumo_phase_index=data.get("sumo_phase_index"),
            sumo_state=data.get("sumo_state"),
        )

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "phase_id": self.phase_id,
            "name": self.name,
            "approaches": list(self.approaches),
            "movements": [m.to_dict() for m in self.movements],
        }
        if self.sumo_phase_index is not None:
            res["sumo_phase_index"] = self.sumo_phase_index
        if self.sumo_state is not None:
            res["sumo_state"] = self.sumo_state
        return res


@dataclass
class NodeSpec:
    """Represents an intersection node in the network topology graph."""
    node_id: str
    name: str = ""
    approaches: List[str] = field(default_factory=list)
    phases: List[PhaseSpec] = field(default_factory=list)
    sumo_links: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeSpec":
        phases = [PhaseSpec.from_dict(p) for p in data.get("phases", [])]
        return cls(
            node_id=data.get("node_id", ""),
            name=data.get("name", ""),
            approaches=list(data.get("approaches", []) or []),
            phases=phases,
            sumo_links=data.get("sumo_links"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "node_id": self.node_id,
            "name": self.name,
            "approaches": list(self.approaches),
            "phases": [p.to_dict() for p in self.phases],
        }
        if self.sumo_links is not None:
            result["sumo_links"] = self.sumo_links
        return result

    def get_phase(self, phase_id: str) -> Optional[PhaseSpec]:
        for p in self.phases:
            if p.phase_id == phase_id:
                return p
        return None


@dataclass
class EdgeSpec:
    """Represents a connecting road segment (edge) between nodes."""
    edge_id: str
    from_node: Optional[str] = None
    to_node: Optional[str] = None
    length_m: float = 100.0
    lanes_count: int = 1
    speed_limit_mps: float = 13.89

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EdgeSpec":
        from_n = data.get("from_node") or data.get("source")
        to_n = data.get("to_node") or data.get("target")
        return cls(
            edge_id=data.get("edge_id", ""),
            from_node=from_n,
            to_node=to_n,
            length_m=float(data.get("length_m", 100.0)),
            lanes_count=int(data.get("lanes_count", 1)),
            speed_limit_mps=float(data.get("speed_limit_mps", 13.89)),
        )

    def to_dict(self) -> Dict[str, Any]:
        res = {"edge_id": self.edge_id}
        if self.from_node is not None:
            res["from_node"] = self.from_node
        if self.to_node is not None:
            res["to_node"] = self.to_node
        res["length_m"] = self.length_m
        res["lanes_count"] = self.lanes_count
        res["speed_limit_mps"] = self.speed_limit_mps
        return res


@dataclass
class TopologyContract:
    """Canonical Network Topology Contract ($G_t = (V, E)$)."""
    topology_id: str
    version: str = "1.0"
    nodes: List[NodeSpec] = field(default_factory=list)
    edges: List[EdgeSpec] = field(default_factory=list)
    routes: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopologyContract":
        nodes = [NodeSpec.from_dict(n) for n in data.get("nodes", [])]
        edges = [EdgeSpec.from_dict(e) for e in data.get("edges", [])]
        return cls(
            topology_id=data.get("topology_id", ""),
            version=data.get("version", "1.0"),
            nodes=nodes,
            edges=edges,
            routes=data.get("routes"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "topology_id": self.topology_id,
            "version": self.version,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }
        if self.routes is not None:
            result["routes"] = self.routes
        return result

    def get_node(self, node_id: str) -> Optional[NodeSpec]:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def summary(self) -> Dict[str, Any]:
        total_phases = sum(len(n.phases) for n in self.nodes)
        return {
            "id": self.topology_id,
            "topology_id": self.topology_id,
            "version": self.version,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "total_phases": total_phases,
        }

@dataclass
class SignalFaultEvent:
    """Canonical Signal Fault & Disconnection Event Model."""
    event_id: str
    node_id: str
    category: str
    fault_code: str
    severity: str
    timestamp_ms: int
    current_phase: Optional[str] = None
    target_phase: Optional[str] = None
    clearance_state: Optional[str] = None
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalFaultEvent":
        return cls(
            event_id=data.get("event_id", ""),
            node_id=data.get("node_id", ""),
            category=data.get("category", "disconnect"),
            fault_code=data.get("fault_code", "ERR_COORDINATOR_TIMEOUT"),
            severity=data.get("severity", "WARNING"),
            timestamp_ms=int(data.get("timestamp_ms", 0)),
            current_phase=data.get("current_phase"),
            target_phase=data.get("target_phase"),
            clearance_state=data.get("clearance_state"),
            reason=data.get("reason"),
            details=dict(data.get("details", {}) or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "event_id": self.event_id,
            "node_id": self.node_id,
            "category": self.category,
            "fault_code": self.fault_code,
            "severity": self.severity,
            "timestamp_ms": self.timestamp_ms,
        }
        if self.current_phase is not None:
            res["current_phase"] = self.current_phase
        if self.target_phase is not None:
            res["target_phase"] = self.target_phase
        if self.clearance_state is not None:
            res["clearance_state"] = self.clearance_state
        if self.reason is not None:
            res["reason"] = self.reason
        if self.details:
            res["details"] = self.details
        return res
