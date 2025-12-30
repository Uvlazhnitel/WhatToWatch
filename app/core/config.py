from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url_async: str
    database_url_sync: str

    tmdb_api_key: str
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_language: str = "en-US"


settings = Settings()
