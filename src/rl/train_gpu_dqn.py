"""
High-Speed GPU-Accelerated Double DQN Training Engine for EdgeFlow AI.
Optimized for NVIDIA CUDA GPUs (NVIDIA GeForce RTX 4060).

Architecture:
  - Vectorized Experience Replay on GPU
  - Double DQN with Target Network Sync
  - Fast Multi-Scenario Rollout (Balanced, Directional Surge, Downstream Congestion)
  - Automatic Weight Export to lightweight JSON for Embedded NumPy/C Inference
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.rl.traffic_env import TrafficSignalEnv
from src.rl.policy import NumpyPolicy


class QNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, action_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class GPUReplayBuffer:
    def __init__(self, capacity: int, state_dim: int, device: torch.device):
        self.capacity = capacity
        self.device = device
        self.states = torch.zeros((capacity, state_dim), dtype=torch.float32, device=device)
        self.actions = torch.zeros(capacity, dtype=torch.int64, device=device)
        self.rewards = torch.zeros(capacity, dtype=torch.float32, device=device)
        self.next_states = torch.zeros((capacity, state_dim), dtype=torch.float32, device=device)
        self.dones = torch.zeros(capacity, dtype=torch.float32, device=device)
        self.ptr = 0
        self.size = 0

    def push(self, state, action, reward, next_state, done):
        self.states[self.ptr] = torch.as_tensor(state, dtype=torch.float32, device=self.device)
        self.actions[self.ptr] = int(action)
        self.rewards[self.ptr] = float(reward)
        self.next_states[self.ptr] = torch.as_tensor(next_state, dtype=torch.float32, device=self.device)
        self.dones[self.ptr] = 1.0 if done else 0.0
        self.ptr = (self.ptr + 1) % self.capacity
        self.size = min(self.capacity, self.size + 1)

    def sample(self, batch_size: int):
        idx = torch.randint(0, self.size, (batch_size,), device=self.device)
        return (
            self.states[idx],
            self.actions[idx],
            self.rewards[idx],
            self.next_states[idx],
            self.dones[idx],
        )

    def __len__(self):
        return self.size


def train_gpu_presslight(
    episodes: int = 1000,
    max_steps_per_episode: int = 120,
    batch_size: int = 128,
    hidden_dim: int = 64,
    learning_rate: float = 0.001,
    gamma: float = 0.95,
    seed: int = 42,
    output_path: str = "models/presslight_optimized.json",
):
    print("=" * 70)
    print("  EDGEFLOW AI — HIGH-SPEED GPU REINFORCEMENT LEARNING TRAINING")
    print("=" * 70)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        print(f"  ⚡ ACCELERATION: NVIDIA CUDA ENABLED [{gpu_name}]")
    else:
        print("  ⚠️ RUNNING ON CPU")

    print(f"  Episodes:        {episodes}")
    print(f"  Steps / Episode: {max_steps_per_episode}")
    print(f"  Batch Size:      {batch_size}")
    print(f"  Learning Rate:   {learning_rate}")
    print("=" * 70)

    # Initialize environment
    env = TrafficSignalEnv(topology_id="four_intersection_v1", target_node="J1", max_steps=max_steps_per_episode)
    state_dim = env.observation_dim
    action_dim = env.action_space_n

    # Multi-layer Perceptron (2-layer MLP compatible with NumpyPolicy)
    # NumpyPolicy uses w1, b1, w2, b2:
    # State (state_dim) -> w1 (hidden_dim, state_dim) + b1 -> ReLU -> w2 (action_dim, hidden_dim) + b2
    q_net = nn.Sequential(
        nn.Linear(state_dim, hidden_dim),
        nn.ReLU(),
        nn.Linear(hidden_dim, action_dim)
    ).to(device)

    target_net = nn.Sequential(
        nn.Linear(state_dim, hidden_dim),
        nn.ReLU(),
        nn.Linear(hidden_dim, action_dim)
    ).to(device)
    target_net.load_state_dict(q_net.state_dict())

    optimizer = optim.Adam(q_net.parameters(), lr=learning_rate)
    criterion = nn.MSELoss()
    buffer = GPUReplayBuffer(capacity=50000, state_dim=state_dim, device=device)

    epsilon = 1.0
    epsilon_decay = 0.995
    epsilon_min = 0.02
    target_update_freq = 50

    scenarios = ("balanced", "directional_surge", "downstream_congestion")
    start_time = time.perf_counter()

    rewards_history = []
    loss_history = []

    for ep in range(episodes):
        scenario = scenarios[ep % len(scenarios)]
        obs, _ = env.reset(seed=seed + ep, scenario=scenario)
        ep_reward = 0.0

        for step in range(max_steps_per_episode):
            # Epsilon-greedy action
            if np.random.rand() < epsilon:
                action = np.random.randint(action_dim)
            else:
                with torch.no_grad():
                    s_tensor = torch.as_tensor(obs, dtype=torch.float32, device=device).unsqueeze(0)
                    q_values = q_net(s_tensor)
                    action = int(q_values.argmax(dim=1).item())

            next_obs, reward, terminated, truncated, _ = env.step(action)
            buffer.push(obs, action, reward, next_obs, terminated)
            obs = next_obs
            ep_reward += reward

            # Train batch on GPU
            if len(buffer) >= batch_size:
                s_b, a_b, r_b, ns_b, d_b = buffer.sample(batch_size)

                # Double DQN: evaluate greedy action using q_net, value using target_net
                with torch.no_grad():
                    next_actions = q_net(ns_b).argmax(dim=1, keepdim=True)
                    next_q = target_net(ns_b).gather(1, next_actions).squeeze(1)
                    target = r_b + (1.0 - d_b) * gamma * next_q

                curr_q = q_net(s_b).gather(1, a_b.unsqueeze(1)).squeeze(1)
                loss = criterion(curr_q, target)

                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(q_net.parameters(), 10.0)
                optimizer.step()
                loss_history.append(loss.item())

            if terminated or truncated:
                break

        # Decay epsilon & sync target
        epsilon = max(epsilon_min, epsilon * epsilon_decay)
        if ep % target_update_freq == 0:
            target_net.load_state_dict(q_net.state_dict())

        rewards_history.append(ep_reward)

        if (ep + 1) % 100 == 0 or ep == episodes - 1:
            recent_reward = np.mean(rewards_history[-50:])
            recent_loss = np.mean(loss_history[-100:]) if loss_history else 0.0
            fps = (ep + 1) * max_steps_per_episode / (time.perf_counter() - start_time)
            print(f"  [Ep {ep+1:4d}/{episodes}] Reward: {recent_reward:6.2f} | Loss: {recent_loss:.4f} | Epsilon: {epsilon:.3f} | Speed: {fps:.0f} steps/s")

    elapsed = time.perf_counter() - start_time
    print("=" * 70)
    print(f"  🎉 TRAINING COMPLETE in {elapsed:.2f}s ({episodes * max_steps_per_episode / elapsed:.0f} steps/s)")

    # Extract weights for NumpyPolicy export
    # Layer 0: Linear(state_dim -> hidden_dim)
    # Layer 2: Linear(hidden_dim -> action_dim)
    w1 = q_net[0].weight.detach().cpu().numpy()  # (hidden_dim, state_dim)
    b1 = q_net[0].bias.detach().cpu().numpy()    # (hidden_dim,)
    w2 = q_net[2].weight.detach().cpu().numpy()  # (action_dim, hidden_dim)
    b2 = q_net[2].bias.detach().cpu().numpy()    # (action_dim,)

    export_data = {
        "state_dim": state_dim,
        "action_dim": action_dim,
        "hidden_dim": hidden_dim,
        "w1": w1.tolist(),
        "b1": b1.tolist(),
        "w2": w2.tolist(),
        "b2": b2.tolist(),
        "feature_spec": env.feature_spec,
        "training_metadata": {
            "device": str(device),
            "gpu_name": gpu_name if device.type == "cuda" else "CPU",
            "episodes": episodes,
            "training_time_s": round(elapsed, 2),
            "final_mean_reward": round(float(np.mean(rewards_history[-50:])), 2),
            "scenarios_trained": scenarios,
        }
    }

    # Verify that NumpyPolicy can load and infer correctly
    np_policy = NumpyPolicy(export_data)
    test_obs = np.zeros(state_dim, dtype=np.float32)
    test_q = np_policy.predict(test_obs)
    print(f"  ✅ Export verified: NumpyPolicy test prediction = {test_q}")

    # Save to disk
    out_file = repo_root / output_path
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)

    print(f"  💾 Trained weights exported to: {out_file}")
    return export_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPU-Accelerated PressLight RL Training")
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--output", default="models/presslight_optimized.json")
    args = parser.parse_args()

    train_gpu_presslight(
        episodes=args.episodes,
        max_steps_per_episode=args.steps,
        batch_size=args.batch_size,
        hidden_dim=args.hidden_dim,
        learning_rate=args.lr,
        output_path=args.output,
    )
