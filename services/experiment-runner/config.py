import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field

    class Settings(BaseSettings):
        edgeflow_env: str = Field("dev")
        log_level: str = Field("INFO")
        mqtt_host: str = Field("localhost")
        mqtt_port: int = Field(1883)
        contracts_dir: str = Field("")
        artifacts_dir: str = Field("artifacts")

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )
except ImportError:
    try:
        from pydantic.v1 import BaseSettings, Field
    except ImportError:
        from pydantic import BaseSettings, Field

    class Settings(BaseSettings):
        edgeflow_env: str = Field("dev", env="EDGEFLOW_ENV")
        log_level: str = Field("INFO", env="LOG_LEVEL")
        mqtt_host: str = Field("localhost", env="MQTT_HOST")
        mqtt_port: int = Field(1883, env="MQTT_PORT")
        contracts_dir: str = Field("", env="CONTRACTS_DIR")
        artifacts_dir: str = Field("artifacts", env="ARTIFACTS_DIR")

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"

settings = Settings()
