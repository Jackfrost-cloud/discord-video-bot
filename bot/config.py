"""Configuration centralisée du bot, chargée depuis les variables d'environnement."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"La variable d'environnement {name} doit être un entier, reçu: {raw!r}")


@dataclass(frozen=True)
class Config:
    discord_token: str
    max_concurrent_downloads: int
    max_queue_size: int
    max_active_downloads_per_user: int
    download_cooldown: int
    download_timeout: int
    temp_directory: Path
    downloads_directory: Path
    storage_provider: str
    file_retention_minutes: int
    discord_max_file_size: int
    log_level: str
    public_base_url: str
    fallback_server_host: str
    fallback_server_port: int
    ffmpeg_location: str | None
    cookies_file: str | None

    @classmethod
    def load(cls) -> "Config":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "DISCORD_TOKEN manquant. Renseigne-le dans le fichier .env "
                "(voir .env.example)."
            )

        temp_dir = Path(os.getenv("TEMP_DIRECTORY", "./tmp")).resolve()
        downloads_dir = Path(os.getenv("DOWNLOADS_DIRECTORY", "./downloads")).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        downloads_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            discord_token=token,
            max_concurrent_downloads=_get_int("MAX_CONCURRENT_DOWNLOADS", 2),
            max_queue_size=_get_int("MAX_QUEUE_SIZE", 20),
            max_active_downloads_per_user=_get_int("MAX_ACTIVE_DOWNLOADS_PER_USER", 1),
            download_cooldown=_get_int("DOWNLOAD_COOLDOWN", 15),
            download_timeout=_get_int("DOWNLOAD_TIMEOUT", 600),
            temp_directory=temp_dir,
            downloads_directory=downloads_dir,
            storage_provider=os.getenv("STORAGE_PROVIDER", "local").strip().lower(),
            file_retention_minutes=_get_int("FILE_RETENTION_MINUTES", 30),
            discord_max_file_size=_get_int("DISCORD_MAX_FILE_SIZE", 25 * 1024 * 1024),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/"),
            fallback_server_host=os.getenv("FALLBACK_SERVER_HOST", "0.0.0.0"),
            fallback_server_port=_get_int("FALLBACK_SERVER_PORT", 8080),
            ffmpeg_location=os.getenv("FFMPEG_LOCATION") or None,
            cookies_file=os.getenv("COOKIES_FILE") or None,
        )


config = Config.load()
