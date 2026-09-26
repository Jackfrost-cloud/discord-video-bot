"""Extraction des métadonnées et des formats disponibles via yt-dlp."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import yt_dlp

from bot.config import config
from bot.utils.logging import get_logger

logger = get_logger(__name__)

# Paliers de qualité proposés à l'utilisateur s'il existe un format correspondant.
QUALITY_LADDER = [360, 480, 720, 1080]


class VideoUnavailableError(Exception):
    """Le contenu n'existe pas, n'est pas téléchargeable, ou n'est pas une vidéo unique."""


class AuthenticationRequiredError(Exception):
    """Le contenu nécessite une authentification/cookies non configurés sur le bot."""


@dataclass
class QualityOption:
    label: str
    format_selector: str
    height: int | None  # None pour "Meilleure qualité"


@dataclass
class VideoInfo:
    title: str
    duration: float | None
    platform: str
    thumbnail: str | None
    qualities: list[QualityOption]


def _base_ydl_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    if config.cookies_file:
        opts["cookiefile"] = config.cookies_file
    if config.ffmpeg_location:
        opts["ffmpeg_location"] = config.ffmpeg_location
    return opts


def _extract_sync(url: str) -> dict:
    with yt_dlp.YoutubeDL(_base_ydl_opts()) as ydl:
        return ydl.extract_info(url, download=False)


async def fetch_video_info(url: str) -> VideoInfo:
    """Récupère les métadonnées d'une vidéo et calcule les qualités réellement disponibles.

    Lève VideoUnavailableError si l'URL ne pointe pas vers une vidéo unique téléchargeable
    (playlist, chaîne, page sans vidéo, contenu retiré...) et AuthenticationRequiredError
    si le contenu nécessite une connexion/des cookies non configurés.
    """
    try:
        info = await asyncio.to_thread(_extract_sync, url)
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc).lower()
        if any(kw in message for kw in ("login", "cookies", "sign in", "private video")):
            raise AuthenticationRequiredError(str(exc)) from exc
        raise VideoUnavailableError(str(exc)) from exc

    if info is None:
        raise VideoUnavailableError("Aucune information retournée pour cette URL.")

    # yt-dlp renvoie "_type": "playlist" pour les playlists, chaînes et pages de résultats.
    if info.get("_type") in ("playlist", "multi_video"):
        entries = info.get("entries") or []
        if len(entries) == 1:
            info = entries[0]
        else:
            raise VideoUnavailableError(
                "Cette URL correspond à une playlist ou une chaîne, pas à une vidéo unique."
            )

    formats = info.get("formats") or []
    if not formats and not info.get("url"):
        raise VideoUnavailableError("Aucun format téléchargeable trouvé pour cette URL.")

    available_heights = sorted(
        {
            f.get("height")
            for f in formats
            if f.get("height") and f.get("vcodec") not in (None, "none")
        }
    )

    qualities: list[QualityOption] = []
    for target in QUALITY_LADDER:
        # On ne propose ce palier que s'il existe réellement un format proche de cette hauteur ;
        # jamais une qualité qui n'existe pas.
        if target in available_heights or any(abs(h - target) <= 40 for h in available_heights):
            selector = f"bestvideo[height<={target}]+bestaudio/best[height<={target}]"
            qualities.append(QualityOption(label=f"{target}p", format_selector=selector, height=target))

    if not qualities and available_heights:
        top = max(available_heights)
        qualities.append(
            QualityOption(
                label=f"{top}p",
                format_selector=f"bestvideo[height<={top}]+bestaudio/best[height<={top}]",
                height=top,
            )
        )

    qualities.append(
        QualityOption(label="⭐ Meilleure qualité", format_selector="bestvideo+bestaudio/best", height=None)
    )

    return VideoInfo(
        title=info.get("title") or "Vidéo sans titre",
        duration=info.get("duration"),
        platform=(info.get("extractor_key") or info.get("extractor") or "Inconnue"),
        thumbnail=info.get("thumbnail"),
        qualities=qualities,
    )
