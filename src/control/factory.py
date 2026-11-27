"""Controller construction shared by services and offline experiments."""
from functools import partial
from .controllers import (FixedTimeController, ActuatedController, MaxQueueController,
                          MaxPressureController, EdgeFlowController, PressLightRLController,
                          FlowTheoryController)
from .research import SharedDQNController, FairCycleRLController
from .graph_mappo import GraphMAPPOController
from .fair_cycle import FairCycleController
from .phase_dqn import PhaseDQNController
from .unified_dqn import UnifiedDQNController, GATES_OFF, EDGEFLOW_RL_GATES
from .cycle_dqn import FairCycleNativeController, FairCycleUnifiedController
from .mappo_unified import UnifiedMAPPOController

CONTROLLER_REGISTRY = {"fixed_time": FixedTimeController, "actuated": ActuatedController,
                       "max_queue": MaxQueueController, "max_pressure": MaxPressureController,
                       "edgeflow": EdgeFlowController, "presslight_rl": PressLightRLController,
                       "rl": PressLightRLController, "flow_theory": FlowTheoryController,
                       "shared_dqn": SharedDQNController, "fair_cycle": FairCycleController,
                       "fair_cycle_rl": FairCycleRLController, "phase_dqn": PhaseDQNController,
                       "graph_mappo": GraphMAPPOController, "local_mappo": GraphMAPPOController,
                       "phase_dqn_unified": UnifiedDQNController, "shared_dqn_unified": UnifiedDQNController,
                       "presslight_unified": UnifiedDQNController,
                       # Dashboard demo policies (models/rl_demo): gates fixed per instance, never from env
                       "phase_dqn_baseline": partial(UnifiedDQNController, gates=GATES_OFF),
                       "edgeflow_rl": partial(UnifiedDQNController, gates=EDGEFLOW_RL_GATES),
                       "fair_cycle_native": FairCycleNativeController,
                       "fair_cycle_unified": FairCycleUnifiedController,
                       "graph_mappo_unified": UnifiedMAPPOController,
                       "local_mappo_unified": UnifiedMAPPOController}


def create_controller(name, parameters=None, model_path=None):
    if name not in CONTROLLER_REGISTRY:
        raise ValueError(f"Unknown controller: {name}")
    params = dict(parameters or {})
    if name in ("shared_dqn", "fair_cycle_rl", "graph_mappo", "local_mappo",
                "presslight_rl", "rl", "phase_dqn", "phase_dqn_unified",
                "shared_dqn_unified", "presslight_unified", "fair_cycle_unified",
                "phase_dqn_baseline", "edgeflow_rl",
                "graph_mappo_unified", "local_mappo_unified"):
        params["model_path"] = model_path
    return CONTROLLER_REGISTRY[name](**params)
