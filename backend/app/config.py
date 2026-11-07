"""Application settings. Values come from the environment or .env, never from code.

Demo values match the README's configuration table.
"""

from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Secrets and machine-specific values (see .env.example)
    DATABASE_URL: str
    JWT_SECRET: str
    TESSERACT_CMD: str = "tesseract"
    DEFAULT_LAT: float = 0.0
    DEFAULT_LNG: float = 0.0
    DEMO_PASSWORD: str = ""
    SEED_PASSWORD: str = "Parola123!"  # the seeded test users; development only

    # Business rules
    MARGIN: Decimal = Decimal("0.05")
    MAX_MODIFIER: Decimal = Decimal("1.25")
    POINTS_PER_LEI: int = 10
    POINTS_PER_UNLISTED_PRODUCT: int = 5
    MIN_SPLIT_SAVING_LEI: Decimal = Decimal("10")
    TRASH_RETENTION_DAYS: int = 14
    VOUCHER_VALID_DAYS: int = 30

    # Scanning and uploads
    OCR_ENGINE: str = "rapidocr"  # or "tesseract"; RapidOCR read real receipt photos far better
    OCR_RAPID_LANG: str = "ro"
    OCR_LANG: str = "ron+eng"  # Tesseract only
    OCR_PSM: int = 4
    OCR_MIN_MATCH_SCORE: int = 70
    MAX_UPLOAD_MB: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
