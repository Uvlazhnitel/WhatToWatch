from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url_async: str
    database_url_sync: str

    tmdb_api_key: str
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_language: str = "en-US"

    telegram_bot_token: str

    openai_api_key: str
    openai_embed_model: str = "text-embedding-3-small"
    openai_embed_dimensions: int = 1536
    openai_timeout_secs: int = 30

    openai_text_model: str = "gpt-4o-mini"
    openai_text_temperature: float = 0.35
    openai_text_max_output_tokens: int = 350

    @model_validator(mode="after")
    def validate_api_keys(self) -> "Settings":
        """Validate that API keys are set and not placeholder values."""
        if self.tmdb_api_key in ("your_tmdb_api_key_here", "PUT_YOUR_TMDB_KEY_HERE", "test_key"):
            raise ValueError(
                "TMDB_API_KEY is not properly configured. "
                "Get your API key from https://www.themoviedb.org/settings/api"
            )
        if self.telegram_bot_token in ("your_bot_token_here", "test_token"):
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is not properly configured. "
                "Create a bot with @BotFather on Telegram"
            )
        if self.openai_api_key in ("your_openai_api_key_here", "test_key"):
            raise ValueError(
                "OPENAI_API_KEY is not properly configured. "
                "Get your API key from https://platform.openai.com/api-keys"
            )
        return self


settings = Settings()
