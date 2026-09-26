"""Téléchargement effectif d'une vidéo via yt-dlp (fusion audio/vidéo par FFmpeg incluse)."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Awaitable, Callable

import yt_dlp

from bot.config import config
from bot.utils.logging import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[dict], Awaitable[None]]


class DownloadFailedError(Exception):
    pass


class DownloadTimeoutError(Exception):
    pass


def _build_ydl_opts(job_id: str, format_selector: str, dest_dir: Path, progress_hook) -> dict:
    outtmpl = str(dest_dir / f"{job_id}.%(ext)s")
    opts = {
        "format": format_selector,
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # yt-dlp appelle FFmpeg automatiquement pour fusionner vidéo+audio séparés.
        "merge_output_format": "mp4",
        "restrictfilenames": True,
        "progress_hooks": [progress_hook],
        "retries": 3,
        "fragment_retries": 3,
    }
    if config.cookies_file:
        opts["cookiefile"] = config.cookies_file
    if config.ffmpeg_location:
        opts["ffmpeg_location"] = config.ffmpeg_location
    return opts


def _download_sync(url: str, opts: dict) -> str:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


async def download_video(
    job_id: str,
    url: str,
    format_selector: str,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Télécharge la vidéo dans le répertoire temporaire et retourne le chemin du fichier final.

    L'opération tourne dans un thread séparé (asyncio.to_thread) afin de ne jamais bloquer
    la boucle événementielle du bot Discord pendant un téléchargement long.
    """
    dest_dir = config.temp_directory
    loop = asyncio.get_running_loop()
    last_emit = 0.0

    def progress_hook(data: dict) -> None:
        nonlocal last_emit
        if on_progress is None:
            return
        now = time.monotonic()
        # Limite la fréquence des mises à jour pour ne pas spammer l'API Discord (rate limit).
        if data.get("status") == "finished" or now - last_emit >= 3:
            last_emit = now
            asyncio.run_coroutine_threadsafe(on_progress(data), loop)

    opts = _build_ydl_opts(job_id, format_selector, dest_dir, progress_hook)

    try:
        raw_path = await asyncio.wait_for(
            asyncio.to_thread(_download_sync, url, opts),
            timeout=config.download_timeout,
        )
    except asyncio.TimeoutError as exc:
        _cleanup_partials(dest_dir, job_id)
        raise DownloadTimeoutError("Le téléchargement a dépassé le délai autorisé.") from exc
    except yt_dlp.utils.DownloadError as exc:
        _cleanup_partials(dest_dir, job_id)
        raise DownloadFailedError(str(exc)) from exc

    final_path = Path(raw_path)
    if not final_path.exists() or final_path.stat().st_size == 0:
        _cleanup_partials(dest_dir, job_id)
        raise DownloadFailedError("Le fichier téléchargé est introuvable ou vide.")

    return final_path


def _cleanup_partials(dest_dir: Path, job_id: str) -> None:
    """Supprime les fichiers .part/.tmp restants après un échec ou un timeout."""
    for path in dest_dir.glob(f"{job_id}.*"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Impossible de supprimer le fichier partiel %s", path)
