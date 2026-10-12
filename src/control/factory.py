"""Controller construction shared by services and offline experiments."""
from .controllers import (FixedTimeController, ActuatedController, MaxQueueController,
                          MaxPressureController, EdgeFlowController, PressLightRLController,
                          FlowTheoryController)
from .research import SharedDQNController, FairCycleRLController
from .graph_mappo import GraphMAPPOController
from .fair_cycle import FairCycleController

CONTROLLER_REGISTRY = {"fixed_time": FixedTimeController, "actuated": ActuatedController,
                       "max_queue": MaxQueueController, "max_pressure": MaxPressureController,
                       "edgeflow": EdgeFlowController, "presslight_rl": PressLightRLController,
                       "rl": PressLightRLController, "flow_theory": FlowTheoryController,
                       "shared_dqn": SharedDQNController, "fair_cycle": FairCycleController,
                       "fair_cycle_rl": FairCycleRLController,
                       "graph_mappo": GraphMAPPOController, "local_mappo": GraphMAPPOController}


def create_controller(name, parameters=None, model_path=None):
    if name not in CONTROLLER_REGISTRY:
        raise ValueError(f"Unknown controller: {name}")
    params = dict(parameters or {})
    if name in ("shared_dqn", "fair_cycle_rl", "graph_mappo", "local_mappo",
                "presslight_rl", "rl"):
        params["model_path"] = model_path
    return CONTROLLER_REGISTRY[name](**params)
