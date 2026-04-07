from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Required — no defaults, crash if missing
    discord_bot_token: str
    discord_client_id: str
    discord_public_key: str  # Ed25519 key for verifying Discord interaction signatures
    llm_api_url: str  # Base URL of the LLM server (e.g. http://localhost:8000)
    redis_url: str

    # Optional with defaults
    log_level: str = "INFO"
    guild_id: int | None = None  # Set for dev guild-sync (instant), None for global sync
    llm_brat_level: int = Field(default=3, ge=1, le=3)  # Default brat attitude 1-3

    # Rate limiting
    rate_limit_user_seconds: int = 5
    rate_limit_channel_per_minute: int = 10

    # LLM request queue
    llm_queue_max_depth: int = 5
    llm_timeout_seconds: int = 30

    # Age verification — optional so processes that don't use the age gate (e.g. bonniebot)
    # can start without these being set; required in prod for the disclaimer links to work
    terms_url: str = ""  # Public URL for Terms of Service page
    privacy_url: str = ""  # Public URL for Privacy Policy page
