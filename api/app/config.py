from pydantic_settings import BaseSettings, SettingsConfigDict

from app.watchlists import DEFAULT_WATCHLIST


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    hf_token: str = ""
    hf_model: str = "meta-llama/Llama-3.2-1B-Instruct"
    hf_sentiment_model: str = "ProsusAI/finbert"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    watchlist_symbols: str = ""
    market: str = "IN"

    @property
    def watchlist(self) -> list[str]:
        from app.symbols import normalize_symbol

        if self.watchlist_symbols.strip():
            return [normalize_symbol(s) for s in self.watchlist_symbols.split(",") if s.strip()]
        return DEFAULT_WATCHLIST


settings = Settings()
