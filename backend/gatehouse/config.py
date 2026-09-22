from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Semantic-check adapter. "groq" is a second, independent implementation of
    # the same three-question contract (via Groq's fast open-weight-model API),
    # used to test whether the pattern holds regardless of which model answers
    # it — not a production option.
    jev_adapter: Literal["mock", "real", "groq"] = "mock"
    typesafe_api_key: str | None = None
    jev_model: str = "jev-latest"
    jev_timeout_seconds: float = 8.0

    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = 15.0

    # Decision policy thresholds (tuned on the benchmark dev split)
    clarify_confidence: float = 0.6
    block_confidence: float = 0.75

    # Approval / execution
    approval_ttl_minutes: int = 15

    # Evaluations per session per minute — closes the unbounded-cost vector on
    # a public demo when JEV_ADAPTER is a real, billed model.
    rate_limit_per_minute: int = 20

    # Sandbox: every visitor session plays this fixed customer persona
    acting_customer_id: str = "cust_001"

    # Infra
    database_url: str = "sqlite:///./gatehouse.db"
    session_cookie_name: str = "gatehouse_session"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
