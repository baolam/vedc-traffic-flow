from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    edgeflow_env: str = "dev"
    log_level: str = "INFO"
    mqtt_host: str = "mqtt"
    mqtt_port: int = 1883
    yellow_duration_s: float = 3.0
    all_red_duration_s: float = 2.0
    min_green_s: float = 10.0
    max_green_s: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
