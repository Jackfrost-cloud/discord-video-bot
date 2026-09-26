"""Vérification et finalisation du fichier téléchargé."""
from __future__ import annotations

import shutil
from pathlib import Path

from bot.utils.formatting import sanitize_filename
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class InvalidMediaFileError(Exception):
    pass


def finalize_output(raw_path: Path, title: str, job_id: str) -> Path:
    """Vérifie le fichier téléchargé et le renomme avec un nom lisible et sûr.

    yt-dlp + FFmpeg ont déjà fusionné audio/vidéo si nécessaire (merge_output_format=mp4).
    Ce module vérifie l'intégrité basique du résultat et nettoie le nom final, sans jamais
    faire confiance à un chemin ou un nom provenant directement de la plateforme distante.
    """
    if not raw_path.exists():
        raise InvalidMediaFileError("Le fichier attendu n'existe pas.")

    size = raw_path.stat().st_size
    if size == 0:
        raise InvalidMediaFileError("Le fichier téléchargé est vide.")

    if raw_path.suffix.lower() in {".part", ".tmp", ".ytdl"}:
        raise InvalidMediaFileError("Le fichier est un fichier temporaire non finalisé.")

    safe_name = sanitize_filename(title, fallback=job_id)
    final_path = raw_path.with_name(f"{safe_name}{raw_path.suffix}")

    if final_path != raw_path:
        try:
            raw_path.rename(final_path)
        except OSError:
            shutil.move(str(raw_path), str(final_path))

    return final_path


def get_file_size(path: Path) -> int:
    return path.stat().st_size
