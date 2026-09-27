"""
EdgeFlow AI - Reinforcement Learning Module (PressLight / Deep Q-Network)
"""

__all__ = ["TrafficSignalEnv", "DQNAgent", "train_presslight"]

def __getattr__(name):
    if name == "TrafficSignalEnv":
        from .traffic_env import TrafficSignalEnv
        return TrafficSignalEnv
    if name in ("DQNAgent", "train_presslight"):
        from . import train_dqn
        return getattr(train_dqn, name)
    raise AttributeError(name)
