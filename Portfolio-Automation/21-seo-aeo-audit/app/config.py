"""Configuration constants for SEO and AEO audit."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditConfig:
    """Audit settings and thresholds."""

    user_agent: str = (
        "Mozilla/5.0 (compatible; PortfolioAuditBot/1.0; "
        "+https://github.com/valarcon1226/IBM-Agentric-IA-labs; SEO-AEO-Auditor)"
    )
    request_timeout: float = 12.0
    crawl_delay_seconds: float = 0.05
    default_max_pages: int = 10
    max_crawl_pages_limit: int = 50

    # Image threshold: images heavier than 200 KB trigger a warning
    heavy_image_bytes_threshold: int = 200 * 1024

    # SEO Title character guidelines
    title_min_length: int = 30
    title_max_length: int = 60

    # SEO Meta Description character guidelines
    description_min_length: int = 70
    description_max_length: int = 160

    # AEO concise answer length (characters)
    aeo_concise_answer_max_chars: int = 300


DEFAULT_CONFIG = AuditConfig()
