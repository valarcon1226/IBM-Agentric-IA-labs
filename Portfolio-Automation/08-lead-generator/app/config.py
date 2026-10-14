from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    API_KEY: str

    # Google Places Text Search — optional source (DECISIONES-08 L1). Only used when set; no
    # Google Maps scraping anywhere in this project.
    GOOGLE_PLACES_API_KEY: str | None = None

    # Polite scraping (DECISIONES-08 L1): identifiable User-Agent, 1 req/s per domain by default,
    # tenacity backoff on 429/5xx (see app/fetching.py).
    SCRAPER_USER_AGENT: str = "LeadGeneratorBot/1.0 (+https://example.com/leadbot)"
    SCRAPER_RATE_LIMIT_PER_SECOND: float = 1.0

    # demo-directory service base URL (compose network name; the container itself is wired in
    # batch B — this default lets the CLI/API point at it once it exists).
    DEMO_DIRECTORY_BASE_URL: str = "http://demo-directory"

    FUZZY_MATCH_THRESHOLD: int = 85
    EMAIL_MX_TIMEOUT_SECONDS: float = 3.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
