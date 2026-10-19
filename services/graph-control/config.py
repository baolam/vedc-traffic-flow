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
    # API endpoint whose "active_controller" is followed live (dashboard "Apply Policy"); empty = off
    control_policy_url: str = ""
    # Dashboard phase override: seconds the forced phase stays green before the controller resumes; 0 = no hold
    manual_override_hold_s: float = 15.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
