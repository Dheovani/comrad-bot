"""Typed application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    discord_token: SecretStr
    discord_guild_id: int | None = None
    discord_sync_global_commands: bool = False
    discord_respond_to_mentions: bool = True
    discord_message_content_intent: bool = False

    database_url: str = "sqlite+aiosqlite:///./data/comradbot.db"
    alembic_config_file: Path = Path("./alembic.ini")
    alembic_directory: Path = Path("./alembic")

    ai_provider: Literal["auto", "openai", "groq"] = "auto"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "coral"
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_transcription_model: Literal["whisper-large-v3", "whisper-large-v3-turbo"] = (
        "whisper-large-v3-turbo"
    )
    custom_comradbot_persona: str | None = Field(default=None, max_length=20000)

    data_directory: Path = Path("./data")
    sounds_directory: Path = Path("./data/sounds")
    healthcheck_heartbeat_file: Path = Path("./data/.heartbeat")

    default_volume: float = Field(default=0.5, ge=0.0, le=1.0)
    max_queue_size: int = Field(default=100, ge=1, le=1000)
    max_playlists_per_guild: int = Field(default=25, ge=1, le=100)
    max_playlist_tracks: int = Field(default=100, ge=1, le=500)
    max_sound_file_size_mb: int = Field(default=10, ge=1, le=100)
    max_sound_duration_seconds: int = Field(default=30, ge=1, le=600)
    max_sounds_per_guild: int = Field(default=100, ge=1, le=10000)
    max_sound_storage_mb_per_guild: int = Field(default=500, ge=1, le=100000)
    max_ai_context_messages: int = Field(default=30, ge=1, le=100)
    max_ai_response_characters: int = Field(default=1800, ge=200, le=2000)
    max_transcription_file_size_mb: int = Field(default=20, ge=1, le=25)
    max_transcription_duration_seconds: int = Field(default=300, ge=1, le=3600)
    max_transcription_characters: int = Field(default=12000, ge=200, le=50000)
    audio_idle_timeout_seconds: int = Field(default=300, ge=30, le=3600)

    ai_user_requests_per_minute: int = Field(default=3, ge=1, le=60)
    ai_guild_requests_per_minute: int = Field(default=15, ge=1, le=300)
    ai_cooldown_seconds: float = Field(default=5.0, ge=0.0, le=300.0)
    ai_max_prompt_characters: int = Field(default=4000, ge=100, le=20000)
    ai_timeout_seconds: float = Field(default=45.0, ge=1.0, le=180.0)
    music_resolve_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    heartbeat_interval_seconds: float = Field(default=15.0, ge=1.0, le=300.0)
    healthcheck_max_age_seconds: float = Field(default=45.0, ge=5.0, le=900.0)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("discord_token")
    @classmethod
    def token_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("DISCORD_TOKEN não pode estar vazio")
        return value

    @field_validator("custom_comradbot_persona")
    @classmethod
    def normalize_custom_persona(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @property
    def ai_enabled(self) -> bool:
        return self.configured_ai_provider is not None

    @property
    def configured_ai_provider(self) -> Literal["openai", "groq"] | None:
        openai_configured = bool(
            self.openai_api_key and self.openai_api_key.get_secret_value().strip()
        )
        groq_configured = bool(self.groq_api_key and self.groq_api_key.get_secret_value().strip())
        if self.ai_provider == "openai":
            return "openai" if openai_configured else None
        if self.ai_provider == "groq":
            return "groq" if groq_configured else None
        if openai_configured:
            return "openai"
        return "groq" if groq_configured else None

    def prepare_directories(self) -> None:
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.sounds_directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache process configuration."""
    return Settings()
