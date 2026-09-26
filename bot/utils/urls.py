"""Détection et validation des URLs présentes dans les messages Discord."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def extract_first_url(text: str) -> str | None:
    """Retourne la première URL trouvée dans un texte, ou None si aucune."""
    if not text:
        return None
    match = _URL_RE.search(text)
    return match.group(0) if match else None


def is_well_formed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)
