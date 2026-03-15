from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Required — no defaults, crash if missing
    discord_bot_token: str
    discord_client_id: str
    anthropic_api_key: str
    database_url: str
    redis_url: str

    # Optional with defaults
    log_level: str = "INFO"
    guild_id: int | None = None  # Set for dev guild-sync (instant), None for global sync

    # Rate limiting
    rate_limit_user_seconds: int = 5
    rate_limit_channel_per_minute: int = 10

    # LLM request queue
    llm_queue_max_depth: int = 5
    llm_timeout_seconds: int = 30
