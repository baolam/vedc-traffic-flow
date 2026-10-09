"""Masked Double DQN learner and portable NumPy export."""
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn

from contracts.research import FAIR_CYCLE_FEATURE_SPEC, FEATURE_SPEC, TIMING, TOPOLOGY_ID


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(1)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


class Replay:
    def __init__(self, capacity, dim, action_dim=2):
        self.states = np.empty((capacity, dim), np.float32)
        self.next_states = np.empty_like(self.states)
        self.actions = np.empty(capacity, np.int64)
        self.rewards = np.empty(capacity, np.float32)
        self.terminal = np.empty(capacity, np.float32)
        self.masks = np.empty((capacity, action_dim), bool)
        self.discounts = np.full(capacity, -1., np.float32)
        self.size = self.position = 0

    def add(self, state, action, reward, next_state, terminal, mask, discount=None):
        i = self.position
        for array, value in ((self.states, state), (self.actions, action), (self.rewards, reward),
                             (self.next_states, next_state), (self.terminal, terminal), (self.masks, mask)):
            array[i] = value
        self.discounts[i] = -1. if discount is None else discount
        self.position = (i + 1) % len(self.states)
        self.size = min(self.size + 1, len(self.states))

    def batch(self, count, device):
        indices = np.random.randint(self.size, size=count)
        return [torch.as_tensor(a[indices], device=device) for a in (
            self.states, self.actions, self.rewards, self.next_states, self.terminal, self.masks,
            self.discounts)]


class Learner:
    def __init__(self, config, seed):
        seed_everything(seed)
        self.config, self.seed = config, seed
        self.algorithm = config.get("algorithm", "shared_dqn")
        self.feature_spec = FAIR_CYCLE_FEATURE_SPEC if self.algorithm == "fair_cycle_dqn" else FEATURE_SPEC
        self.action_dim = 3 if self.algorithm == "fair_cycle_dqn" else 2
        self.state_dim = len(self.feature_spec["ordering"])
        self.device = torch.device(config.get("device", "cuda"))
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA training requested but unavailable")
        self.online = nn.Sequential(nn.Linear(self.state_dim, 64), nn.ReLU(), nn.Linear(64, self.action_dim)).to(self.device)
        self.target = nn.Sequential(nn.Linear(self.state_dim, 64), nn.ReLU(), nn.Linear(64, self.action_dim)).to(self.device)
        self.target.load_state_dict(self.online.state_dict())
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=config.get("learning_rate", 3e-4))
        self.replay = Replay(config.get("replay_capacity", 200000), self.state_dim, self.action_dim)
        self.decisions = self.episodes = self.updates = 0
        self.elapsed_s = 0.
        self.validation = []
        self.action_counts = [0] * self.action_dim
        self.last_update_diagnostics = {}

    def actions(self, obs, masks):
        epsilon = 1. - .95 * min(1., self.decisions / self.config.get("epsilon_decisions", 25000))
        keys = list(obs)
        with torch.no_grad():
            q = self.online(torch.as_tensor(np.stack([obs[k] for k in keys]), device=self.device)).cpu().numpy()
        actions = {key: int(np.random.choice(np.flatnonzero(masks[key]))) if np.random.random() < epsilon
                   else int(np.argmax(np.where(masks[key], q[i], -np.inf))) for i, key in enumerate(keys)}
        for action in actions.values():
            self.action_counts[action] += 1
        return actions

    def update(self):
        size = self.config.get("batch_size", 256)
        s, a, r, ns, terminal, masks, discounts = self.replay.batch(size, self.device)
        with torch.no_grad():
            # Online network selects among legal next actions; target network evaluates.
            next_action = self.online(ns).masked_fill(~masks, -torch.inf).argmax(1)
            future = self.target(ns).gather(1, next_action[:, None]).squeeze(1)
            gamma = torch.where(discounts >= 0, discounts,
                                torch.full_like(discounts, self.config.get("discount", .99)))
            target = r + gamma * (1-terminal) * future
        value = self.online(s).gather(1, a[:, None]).squeeze(1)
        td_error = value.detach() - target
        loss = nn.functional.smooth_l1_loss(value, target)
        if not torch.isfinite(loss):
            raise RuntimeError("Non-finite training loss")
        self.optimizer.zero_grad()
        loss.backward()
        gradient_norm = float(nn.utils.clip_grad_norm_(self.online.parameters(), 10.))
        self.optimizer.step()
        self.last_update_diagnostics = {"loss": float(loss.detach()),
                                       "mean_abs_td_error": float(td_error.abs().mean()),
                                       "gradient_norm": gradient_norm,
                                       "gradient_clipped": gradient_norm > 10.,
                                       "mean_q": float(value.detach().mean())}
        self.updates += 1
        if self.updates % self.config.get("target_sync_updates", 1000) == 0:
            self.target.load_state_dict(self.online.state_dict())
        return float(loss.detach())

    def export(self, path, provenance):
        weights = {name: tensor.detach().cpu().numpy().tolist() for name, tensor in (
            ("w1", self.online[0].weight), ("b1", self.online[0].bias),
            ("w2", self.online[2].weight), ("b2", self.online[2].bias))}
        config_hash = hashlib.sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest()
        algorithm = self.algorithm
        timing = ({**TIMING, "cycle_time_s": self.config.get("cycle_time_s", 70),
                   "min_green_share": self.config.get("min_green_share", 1/3)}
                  if algorithm == "fair_cycle_dqn" else TIMING)
        artifact = {"algorithm": algorithm, "artifact_version": 1, "weights": weights,
                    "feature_spec": self.feature_spec, "topology_id": TOPOLOGY_ID, "timing": timing,
                    "training_seeds": [self.seed], "provenance": {**provenance,
                        "joint_decisions": self.decisions, "episodes": self.episodes,
                        "training_config_sha256": config_hash}}
        Path(path).write_text(json.dumps(artifact, indent=2))
        return artifact

    def save(self, path):
        # Episode boundaries only: workers have no live SUMO state to reconstruct.
        state = {"version": 1, "config": self.config, "seed": self.seed,
                 "online": self.online.state_dict(), "target": self.target.state_dict(),
                 "optimizer": self.optimizer.state_dict(), "replay": self.replay,
                 "decisions": self.decisions, "episodes": self.episodes, "updates": self.updates,
                 "elapsed_s": self.elapsed_s, "validation": self.validation,
                 "action_counts": self.action_counts,
                 "last_update_diagnostics": self.last_update_diagnostics,
                 "python_rng": random.getstate(), "numpy_rng": np.random.get_state(),
                 "torch_rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state_all()}
        temporary = Path(str(path) + ".tmp")
        torch.save(state, temporary)
        temporary.replace(path)

    def load(self, path):
        # Only locally produced checkpoints are supported; torch checkpoints use pickle.
        state = torch.load(path, map_location=self.device, weights_only=False)
        if state["version"] != 1 or state["config"] != self.config or state["seed"] != self.seed:
            raise ValueError("Checkpoint configuration/seed mismatch")
        self.online.load_state_dict(state["online"])
        self.target.load_state_dict(state["target"])
        self.optimizer.load_state_dict(state["optimizer"])
        loaded_replay = state["replay"]
        if not hasattr(loaded_replay, "discounts"):
            loaded_replay.discounts = np.full(len(loaded_replay.states), -1., np.float32)
        for name in ("replay", "decisions", "episodes", "updates", "elapsed_s", "validation",
                     "action_counts", "last_update_diagnostics"):
            if name in state:
                setattr(self, name, state[name])
        random.setstate(state["python_rng"])
        np.random.set_state(state["numpy_rng"])
        torch.set_rng_state(state["torch_rng"].cpu())
        if state["cuda_rng"]:
            torch.cuda.set_rng_state_all([s.cpu() for s in state["cuda_rng"]])
