import os
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

try:
    import yaml
except ImportError:
    yaml = None

class ScenarioConfig(BaseModel):
    name: str = "directional_surge"
    duration_s: int = 900
    random_seed: int = 42

class ControllerConfig(BaseModel):
    type: str = "max_pressure"  # 'max_pressure' or 'fixed_time'
    decision_interval_s: float = 1.0

class ExperimentManifest(BaseModel):
    experiment_id: str
    topology: str = "four_intersection_v1"
    scenario: ScenarioConfig = Field(default_factory=ScenarioConfig)
    controller: ControllerConfig = Field(default_factory=ControllerConfig)
    metrics: List[str] = [
        "average_waiting_time",
        "average_queue",
        "maximum_queue",
        "throughput",
        "stopped_vehicles",
        "controller_latency_ms"
    ]

    def _dump_dict(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()

    def to_yaml(self) -> str:
        data = self._dump_dict()
        if yaml is not None:
            return yaml.dump(data, sort_keys=False)
        return json.dumps(data, indent=2)

    def save_yaml(self, file_path: str) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.to_yaml())

    @classmethod
    def from_yaml(cls, file_path: str) -> "ExperimentManifest":
        with open(file_path, "r", encoding="utf-8") as f:
            if yaml is not None:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        return cls(**data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentManifest":
        return cls(**data)
