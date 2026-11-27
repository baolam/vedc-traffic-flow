from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    edgeflow_env: str = "dev"
    log_level: str = "INFO"
    mqtt_host: str = "mqtt"
    mqtt_port: int = 1883
    edgeflow_topology: str = "four_intersection_v1"
    edgeflow_controller: str = "max_pressure"
    rl_model_path: str = ""
    rl_models_dir: str = "/models/rl_demo"  # phase_dqn_baseline / edgeflow_rl policies per topology
    # API endpoint whose "active_controller" is followed live (dashboard "Apply Policy"); empty = off
    control_policy_url: str = ""
    # Dashboard phase override: seconds the forced phase stays green before the controller resumes; 0 = no hold
    manual_override_hold_s: float = 15.0
    # Fairness guard (fairness_guard.py): no road starves whatever the controller; false = controller alone
    fairness_guard: bool = True
    fairness_max_red_s: float = 60.0
    fairness_owed_after_s: float = 30.0
    fairness_stuck_after_s: float = 15.0

    # 5-Layer Noise Immunity & Resilience Configuration
    noise_shield_enabled: bool = True
    max_telemetry_age_ms: int = 5000
    neighbor_ttl_s: float = 8.0
    ema_alpha: float = 0.5
    max_queue_rise_per_s: float = 2.5
    max_queue_drop_per_s: float = 3.5
    max_single_step_jump: float = 4.0
    min_approach_confidence: float = 0.25
    fallback_demand_floor_veh: float = 1.0
    holdover_max_s: float = 10.0
    feedback_cooldown_s: float = 5.0
    debounce_ticks: int = 2
    clearance_lock_s: float = 5.0
    command_ttl_ms: int = 4000
    command_republish_s: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
