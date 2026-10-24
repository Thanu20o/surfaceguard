from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Surfaceguard"
    database_url: str = "sqlite:///./surfaceguard.db"
    allowed_origins: str = "http://localhost:5173"
    request_timeout_seconds: float = 4.0
    request_interval_seconds: float = 0.2
    ct_min_interval_seconds: float = 10.0
    max_response_bytes: int = 65536
    max_hosts_per_scan: int = 20
    allow_private_targets: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()