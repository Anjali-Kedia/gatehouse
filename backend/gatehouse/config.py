from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Jev adapter
    jev_adapter: Literal["mock", "real"] = "mock"
    typesafe_api_key: str | None = None
    jev_model: str = "jev-latest"
    jev_timeout_seconds: float = 8.0

    # Decision policy thresholds (tuned on the benchmark dev split)
    clarify_confidence: float = 0.6
    block_confidence: float = 0.75

    # Approval / execution
    approval_ttl_minutes: int = 15

    # Sandbox: every visitor session plays this fixed customer persona
    acting_customer_id: str = "cust_001"

    # Infra
    database_url: str = "sqlite:///./gatehouse.db"
    session_cookie_name: str = "gatehouse_session"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
