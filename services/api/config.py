from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    edgeflow_env: str = "dev"
    log_level: str = "INFO"
    contracts_dir: str = ""
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
