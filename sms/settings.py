from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Twilio credentials — optional; SMS is disabled if not set
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None

    # Required — service URLs
    llm_api_url: str = "http://localhost:8000"
    redis_url: str = "redis://redis:6379/0"

    # Optional — behavior
    llm_brat_level: int = Field(default=3, ge=1, le=3)
    llm_timeout_seconds: float = 30.0
    rate_limit_user_seconds: int = 5
    log_level: str = "INFO"

    # Dev/testing only — skip Twilio signature validation
    twilio_skip_validation: bool = False


settings = Settings()
