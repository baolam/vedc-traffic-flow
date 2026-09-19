from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    edgeflow_env: str = "dev"
    log_level: str = "INFO"
    mqtt_host: str = "mqtt"
    mqtt_port: int = 1883

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
