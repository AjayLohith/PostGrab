"""Application configuration via environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


MAX_VIDEO_SIZE_MB: int = 150
MAX_VIDEO_SIZE_BYTES: int = MAX_VIDEO_SIZE_MB * 1024 * 1024


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    port: int = 8000
    debug: bool = False

    # Temporary storage
    temp_dir: str = "./tmp"

    # Job management
    job_ttl_seconds: int = 1800  # 30 minutes

    # Rate limiting
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60

    # Download limits (hard limit: 150 MB maximum)
    max_download_size_mb: int = MAX_VIDEO_SIZE_MB

    # CORS
    cors_origins: str = "*"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def temp_path(self) -> Path:
        """Get the temp directory as a Path object."""
        path = Path(self.temp_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_download_size_bytes(self) -> int:
        """Max download size in bytes."""
        return self.max_download_size_mb * 1024 * 1024


settings = Settings()
