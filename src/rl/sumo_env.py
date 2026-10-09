"""Gymnasium joint environment with one observation/action per canonical node."""
import uuid
from pathlib import Path
import gymnasium as gym
import numpy as np

from contracts.research import FAIR_CYCLE_FEATURE_SPEC, FEATURE_SPEC
from contracts.contracts_sdk import load_topology
from src.control.research import action_mask, extract_fair_cycle_features, extract_features
from src.control.fair_cycle import FairCycleController
from src.simulation.runtime import SumoRuntime


class SumoNetworkEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, topology_path, network_path, output, demand_s=1800, drain_s=600,
                 trace=False, wait_penalty_lambda=0.):
        self.options = dict(topology_path=topology_path, network_path=network_path,
                            demand_s=demand_s, drain_s=drain_s, trace=trace,
                            wait_penalty_lambda=wait_penalty_lambda)
        self.output = Path(output)
        import json
        self.topology = json.loads(Path(topology_path).read_text())
        self.nodes = self.topology["nodes"]
        self.observation_space = gym.spaces.Dict({n["node_id"]: gym.spaces.Box(
            0, np.inf, shape=(len(FEATURE_SPEC["ordering"]),), dtype=np.float32) for n in self.nodes})
        self.action_space = gym.spaces.Dict({n["node_id"]: gym.spaces.Discrete(2) for n in self.nodes})
        self.runtime = None
        self.ended = True

    def _observe(self):
        state = self.runtime.telemetry
        obs = {n["node_id"]: extract_features(n, state[n["node_id"]], state) for n in self.nodes}
        info = {"action_masks": {n["node_id"]: action_mask(n, state[n["node_id"]]) for n in self.nodes},
                "time_s": self.runtime.time}
        return obs, info

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.close()
        options = options or {}
        scenario = options.get("scenario", "balanced")
        self.runtime = SumoRuntime(**self.options, output=self.output / uuid.uuid4().hex,
                                   scenario=scenario, seed=int(seed if seed is not None else self.np_random.integers(2**31)),
                                   intensity=options.get("intensity", 1.0))
        self.ended = False
        return self._observe()

    def step(self, actions):
        if self.ended:
            raise RuntimeError("Call reset before stepping an ended environment")
        try:
            _, reward, terminated, truncated = self.runtime.step(actions)
            obs, info = self._observe()
            self.ended = terminated or truncated
            if self.ended:
                info["metrics"] = self.runtime.finish()
            return obs, reward, terminated, truncated, info
        except BaseException as error:
            self.runtime.fail(error)
            self.ended = True
            raise

    def close(self):
        if self.runtime:
            self.runtime.close()
        self.runtime = None


class FairCycleSumoEnv(SumoNetworkEnv):
    """One joint transition per complete fair cycle with a bounded split action."""

    residuals = (-5, 0, 5)

    def __init__(self, *args, cycle_time_s=70, min_green_share=1/3, discount=.99, **kwargs):
        super().__init__(*args, **kwargs)
        self.cycle_time_s, self.min_green_share = cycle_time_s, min_green_share
        self.discount = discount
        self.controller = FairCycleController(cycle_time_s, min_green_share)
        self.action_space = gym.spaces.Dict({n["node_id"]: gym.spaces.Discrete(3) for n in self.nodes})
        self.observation_space = gym.spaces.Dict({n["node_id"]: gym.spaces.Box(
            -np.inf, np.inf, shape=(len(FAIR_CYCLE_FEATURE_SPEC["ordering"]),), dtype=np.float32)
            for n in self.nodes})

    def reset(self, *, seed=None, options=None):
        self.controller.reset()
        return super().reset(seed=seed, options=options)

    def _observe(self):
        state = self.runtime.telemetry
        obs, masks = {}, {}
        for node in self.nodes:
            nid = node["node_id"]
            if nid not in self.controller._state:
                self.controller.begin_cycle(nid, state[nid], self.topology, state, adjustment=0)
            at_cycle_boundary = (state[nid]["current_phase_id"] == node["phases"][0]["phase_id"]
                                 and state[nid]["signal_state"] == "GREEN"
                                 and state[nid]["elapsed_green_s"] == 0
                                 and self.controller._state[nid]["phase"] == node["phases"][1]["phase_id"])
            if at_cycle_boundary:
                base_split, previous_split = self.controller.preview_cycle(nid, state[nid], self.topology, state)
            else:
                base_split = self.controller.current_base_split(nid)
                previous_split = self.controller._state[nid]["previous_split"]
            obs[nid] = extract_fair_cycle_features(
                node, state[nid], state, base_split, previous_split,
                demand_s=self.runtime.demand_s, horizon_s=self.runtime.horizon)
            masks[nid] = np.asarray(self.controller.residual_mask_for(base_split[0]), dtype=bool)
        return obs, {"action_masks": masks, "time_s": self.runtime.time}

    def step(self, actions):
        if self.ended:
            raise RuntimeError("Call reset before stepping an ended environment")
        if set(actions) != {n["node_id"] for n in self.nodes}:
            raise ValueError("Actions must cover every canonical intersection")
        start = self.runtime.time
        state = self.runtime.telemetry
        for node in self.nodes:
            nid = node["node_id"]
            action = int(actions[nid])
            base_split, _ = self.controller.preview_cycle(nid, state[nid], self.topology, state)
            if action not in range(3) or not self.controller.residual_mask_for(base_split[0])[action]:
                raise ValueError("Illegal fair-cycle residual action")
            self.controller.begin_cycle(nid, state[nid], self.topology, state,
                                       adjustment=self.residuals[action])
        total_reward = 0.
        terminated = truncated = False
        max_steps = self.cycle_time_s // 5 + 1
        for index in range(max_steps):
            phase_actions = {}
            for node in self.nodes:
                nid = node["node_id"]
                command = self.controller.compute_command(
                    nid, self.runtime.telemetry[nid], self.topology,
                    network_state=self.runtime.telemetry, current_time_s=self.runtime.time)
                phase_actions[nid] = [p["phase_id"] for p in node["phases"]].index(command["target_phase_id"])
            _, reward, terminated, truncated = self.runtime.step(phase_actions)
            total_reward += (self.discount ** index) * reward
            if terminated or truncated:
                break
            if self.runtime.time > start and all(
                    self.runtime.telemetry[n["node_id"]]["current_phase_id"] == n["phases"][0]["phase_id"]
                    and self.runtime.telemetry[n["node_id"]]["signal_state"] == "GREEN"
                    and self.runtime.telemetry[n["node_id"]]["elapsed_green_s"] == 0
                    for n in self.nodes):
                break
        else:
            raise RuntimeError("Fair cycle failed to return to its NS boundary")
        self.ended = terminated or truncated
        obs, info = self._observe()
        info["elapsed_s"] = self.runtime.time - start
        if self.ended:
            info["metrics"] = self.runtime.finish()
        return obs, total_reward, terminated, truncated, info
