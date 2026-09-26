"""Fonctions utilitaires de mise en forme (tailles, durées, noms de fichiers)."""
from __future__ import annotations

import re
import unicodedata

_INVALID_FS_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_MAX_FILENAME_LENGTH = 150


def format_size(num_bytes: float | None) -> str:
    if not num_bytes or num_bytes <= 0:
        return "inconnue"
    units = ["o", "Ko", "Mo", "Go"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} Go"


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "inconnue"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def sanitize_filename(name: str, fallback: str = "video") -> str:
    """Nettoie un titre distant pour en faire un nom de fichier sûr.

    Ne renvoie jamais un chemin (pas de '/', '\\', '..', caractères de contrôle) :
    un titre distant ne doit jamais pouvoir être interprété comme un chemin système.
    """
    if not name:
        name = fallback
    name = unicodedata.normalize("NFKC", name)
    name = _INVALID_FS_CHARS.sub("_", name)
    name = name.replace("..", "_")
    name = name.strip(" .")
    if not name:
        name = fallback
    return name[:_MAX_FILENAME_LENGTH]
