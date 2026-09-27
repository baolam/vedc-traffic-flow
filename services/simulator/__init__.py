"""
EdgeFlow AI - Simulator Service Package.
Provides digital twin traffic simulation using Eclipse SUMO and internal TrafficEngine.
"""

from .traffic_engine import TrafficEngine

try:
    from .sumo_engine import SumoTrafficEngine
except ImportError:
    SumoTrafficEngine = None

__all__ = ["TrafficEngine", "SumoTrafficEngine"]
