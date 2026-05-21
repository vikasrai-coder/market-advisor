from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    hf_token: str = ""
    hf_model: str = "HuggingFaceH4/zephyr-7b-beta"
    hf_sentiment_model: str = "ProsusAI/finbert"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    watchlist_symbols: str = ""

    @property
    def watchlist(self) -> list[str]:
        if self.watchlist_symbols.strip():
            return [s.strip().upper() for s in self.watchlist_symbols.split(",") if s.strip()]
        return DEFAULT_WATCHLIST


DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
    "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "CVX", "LLY", "ABBV",
    "AVGO", "PEP", "KO", "COST", "MRK", "AMD", "ADBE", "CRM", "NFLX", "DIS",
    "INTC", "BAC", "ORCL", "CSCO", "TMO", "ACN", "LIN", "ABT", "DHR", "TXN",
]


settings = Settings()
