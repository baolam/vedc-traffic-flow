"""Reproducible batched Double DQN training on an explicit synthetic environment."""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from .policy import NumpyPolicy
from .traffic_env import TrafficSignalEnv


class ReplayBuffer:
    def __init__(self, capacity=5000, seed=0):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.rng = np.random.default_rng(seed)
        self.position = 0
        self.size = 0
        self.arrays = None

    def push(self, state, action, reward, next_state, done):
        state = np.asarray(state, dtype=np.float32)
        next_state = np.asarray(next_state, dtype=np.float32)
        if state.ndim != 1 or next_state.shape != state.shape:
            raise ValueError("Replay states must have matching vector shapes")
        if self.arrays is None:
            self.arrays = (np.empty((self.capacity, state.size), dtype=np.float32),
                           np.empty(self.capacity, dtype=np.int64),
                           np.empty(self.capacity, dtype=np.float32),
                           np.empty((self.capacity, state.size), dtype=np.float32),
                           np.empty(self.capacity, dtype=np.float32))
        if state.size != self.arrays[0].shape[1]:
            raise ValueError("Replay observation dimension changed")
        for array, value in zip(self.arrays, (state, action, reward, next_state, done)):
            array[self.position] = value
        self.position = (self.position + 1) % self.capacity
        self.size = min(self.capacity, self.size + 1)

    def sample(self, batch_size):
        if batch_size < 1 or not self.size:
            raise ValueError("Cannot sample an empty replay buffer or nonpositive batch")
        indices = self.rng.choice(self.size, min(self.size, batch_size), replace=False)
        return tuple(a[indices] for a in self.arrays)

    def __len__(self):
        return self.size


class DQNAgent:
    """Float32 MLP with batched gradients, Adam and a frozen target network."""

    def __init__(self, state_dim, action_dim, hidden_dim=32, lr=0.001, gamma=0.95,
                 epsilon=1.0, epsilon_decay=0.995, epsilon_min=0.05, seed=0,
                 target_update_interval=100, gradient_clip=10.0):
        if min(state_dim, action_dim, hidden_dim, target_update_interval) < 1:
            raise ValueError("Dimensions and target update interval must be positive")
        if not (0 <= gamma <= 1 and 0 <= epsilon_min <= epsilon <= 1
                and 0 < epsilon_decay <= 1 and lr > 0 and gradient_clip > 0):
            raise ValueError("Invalid learning hyperparameters")
        self.state_dim, self.action_dim, self.hidden_dim = state_dim, action_dim, hidden_dim
        self.lr, self.gamma = lr, gamma
        self.epsilon, self.epsilon_decay, self.epsilon_min = epsilon, epsilon_decay, epsilon_min
        self.target_update_interval, self.gradient_clip = target_update_interval, gradient_clip
        self.rng = np.random.default_rng(seed)
        self.w1 = (self.rng.standard_normal((hidden_dim, state_dim)) * np.sqrt(2 / state_dim)).astype(np.float32)
        self.b1 = np.zeros(hidden_dim, dtype=np.float32)
        self.w2 = (self.rng.standard_normal((action_dim, hidden_dim)) * np.sqrt(2 / hidden_dim)).astype(np.float32)
        self.b2 = np.zeros(action_dim, dtype=np.float32)
        self.updates = 0
        self._m = [np.zeros_like(p) for p in self.parameters]
        self._v = [np.zeros_like(p) for p in self.parameters]
        self.sync_target()

    @property
    def parameters(self):
        return self.w1, self.b1, self.w2, self.b2

    def sync_target(self):
        self.target = tuple(p.copy() for p in self.parameters)

    def forward(self, state):
        x = np.asarray(state, dtype=np.float32)
        hidden = np.maximum(x @ self.w1.T + self.b1, 0)
        return hidden, hidden @ self.w2.T + self.b2

    def act(self, state, explore=True):
        if explore and self.rng.random() < self.epsilon:
            return int(self.rng.integers(self.action_dim))
        return int(np.argmax(self.forward(state)[1]))

    def update(self, batch):
        if len(batch) == 0:
            return None
        if isinstance(batch, list):
            batch = tuple(np.asarray(v) for v in zip(*batch))
        states, actions, rewards, next_states, terminal = batch
        states, next_states = np.asarray(states, np.float32), np.asarray(next_states, np.float32)
        actions = np.asarray(actions, np.int64)
        rewards, terminal = np.asarray(rewards, np.float32), np.asarray(terminal, np.float32)
        n = len(states)
        if n == 0:
            return None
        if (states.shape != (n, self.state_dim) or next_states.shape != states.shape
                or any(a.shape != (n,) for a in (actions, rewards, terminal))
                or np.any(actions < 0) or np.any(actions >= self.action_dim)
                or np.any((terminal != 0) & (terminal != 1))
                or not all(np.isfinite(a).all() for a in (states, rewards, next_states))):
            raise ValueError("Invalid training batch")
        hidden, q = self.forward(states)
        # Select with online network, evaluate with frozen target (Double DQN).
        next_actions = np.argmax(self.forward(next_states)[1], axis=1)
        tw1, tb1, tw2, tb2 = self.target
        next_q = np.maximum(next_states @ tw1.T + tb1, 0) @ tw2.T + tb2
        targets = rewards + self.gamma * (1 - terminal) * next_q[np.arange(n), next_actions]
        error = q[np.arange(n), actions] - targets
        absolute = np.abs(error)
        loss = float(np.mean(np.where(absolute <= 1, 0.5 * error ** 2, absolute - 0.5)))
        dq = np.zeros_like(q)
        dq[np.arange(n), actions] = np.clip(error, -1, 1) / n
        # All gradients use the same pre-update parameters.
        dh = (dq @ self.w2) * (hidden > 0)
        gradients = (dh.T @ states, dh.sum(axis=0), dq.T @ hidden, dq.sum(axis=0))
        norm = float(np.sqrt(sum(float(np.sum(g.astype(np.float64) ** 2)) for g in gradients)))
        if not np.isfinite(loss) or not np.isfinite(norm):
            raise FloatingPointError("Non-finite training loss or gradient")
        scale = min(1.0, self.gradient_clip / max(norm, 1e-12))
        self.updates += 1
        for p, g, m, v in zip(self.parameters, gradients, self._m, self._v):
            g = g * scale
            m *= 0.9
            m += 0.1 * g
            v *= 0.999
            v += 0.001 * g * g
            p -= self.lr * (m / (1 - 0.9 ** self.updates)) / (np.sqrt(v / (1 - 0.999 ** self.updates)) + 1e-8)
        if self.updates % self.target_update_interval == 0:
            self.sync_target()
        return {"loss": loss, "gradient_norm": norm}

    def decay_exploration(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def export_weights(self):
        return {"state_dim": self.state_dim, "action_dim": self.action_dim, "hidden_dim": self.hidden_dim,
                **{k: v.tolist() for k, v in zip(("w1", "b1", "w2", "b2"), self.parameters)}}

    def save_weights(self, filepath, metadata=None):
        data = self.export_weights()
        data.update(metadata or {})
        NumpyPolicy(data)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")


def train_presslight(topology_id="four_intersection_v1", target_node="J1", episodes=200,
                     max_steps_per_episode=120, output_path="models/presslight_optimized.json",
                     seed=42, batch_size=64, hidden_dim=32, learning_rate=0.001):
    if episodes < 1 or batch_size < 1:
        raise ValueError("episodes and batch_size must be positive")
    env = TrafficSignalEnv(topology_id=topology_id, target_node=target_node, max_steps=max_steps_per_episode)
    agent = DQNAgent(env.observation_dim, env.action_space_n, hidden_dim=hidden_dim,
                     lr=learning_rate, seed=seed, epsilon_decay=0.98)
    buffer = ReplayBuffer(capacity=max(10000, batch_size), seed=seed + 1)
    episode_rewards, losses = [], []
    started = time.perf_counter()
    scenarios = ("balanced", "directional_surge", "downstream_congestion")
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode, scenario=scenarios[episode % len(scenarios)])
        total = 0.0
        for _ in range(max_steps_per_episode):
            action = agent.act(obs)
            next_obs, reward, terminated, truncated, _ = env.step(action)
            # A time limit truncates the rollout; it is not an absorbing terminal.
            buffer.push(obs, action, reward, next_obs, terminated)
            if len(buffer) >= max(batch_size, 128):
                metrics = agent.update(buffer.sample(batch_size))
                losses.append(metrics["loss"])
            obs = next_obs
            total += reward
            if terminated or truncated:
                break
        agent.decay_exploration()
        episode_rewards.append(total)
    elapsed = time.perf_counter() - started
    report = {"status": "SUCCESS", "source_mode": "synthetic_training", "valid_for_research": False,
              "seed": seed, "episodes_trained": episodes, "updates": agent.updates,
              "elapsed_s": elapsed, "updates_per_s": agent.updates / max(elapsed, 1e-9),
              "final_epsilon": agent.epsilon, "initial_reward": episode_rewards[0],
              "final_reward": episode_rewards[-1], "episode_rewards": episode_rewards,
              "mean_loss_last_100": float(np.mean(losses[-100:])) if losses else None,
              "weights_saved_to": str(output_path)}
    agent.save_weights(output_path, {"feature_spec": env.feature_spec, "training": {
        "algorithm": "double_dqn", "seed": seed, "episodes": episodes,
        "max_steps": max_steps_per_episode, "batch_size": batch_size, "learning_rate": learning_rate,
        "source_mode": "synthetic_training", "scenario_cycle": scenarios,
        "training_seeds": [seed, seed + episodes - 1]}})
    Path(output_path).with_suffix(".training.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=200)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--output", default="models/presslight_optimized.json")
    args = parser.parse_args()
    result = train_presslight(episodes=args.episodes, max_steps_per_episode=args.steps,
                             seed=args.seed, batch_size=args.batch_size, output_path=args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "episode_rewards"}, indent=2))
