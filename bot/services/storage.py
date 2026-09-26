"""Abstraction de stockage pour le fallback des fichiers trop volumineux pour Discord."""
from __future__ import annotations

import asyncio
import secrets
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from bot.config import config
from bot.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StoredFile:
    token: str
    path: Path
    filename: str
    expires_at: float


class StorageProvider(ABC):
    @abstractmethod
    async def store(self, source_path: Path, filename: str) -> StoredFile:
        """Déplace le fichier vers le stockage et retourne un accès temporaire (token)."""

    @abstractmethod
    async def get_url(self, stored: StoredFile) -> str:
        """Retourne l'URL publique et temporaire à communiquer à l'utilisateur."""

    @abstractmethod
    async def resolve(self, token: str) -> StoredFile | None:
        """Retrouve un fichier stocké à partir de son token, si valide et non expiré."""

    @abstractmethod
    async def purge_expired(self) -> None:
        """Supprime les fichiers dont la durée de rétention est dépassée."""


class LocalStorage(StorageProvider):
    """Stockage local, servi par le petit serveur HTTP interne (bot/services/fileserver.py).

    Les fichiers ne sont jamais exposés par leur chemin système : seul un token aléatoire
    (secrets.token_urlsafe) donne accès à un fichier, et le lien expire automatiquement.
    """

    def __init__(self) -> None:
        self._files: dict[str, StoredFile] = {}
        self._lock = asyncio.Lock()
        config.downloads_directory.mkdir(parents=True, exist_ok=True)

    async def store(self, source_path: Path, filename: str) -> StoredFile:
        token = secrets.token_urlsafe(24)
        dest_path = config.downloads_directory / f"{token}{source_path.suffix}"
        await asyncio.to_thread(shutil.move, str(source_path), str(dest_path))

        stored = StoredFile(
            token=token,
            path=dest_path,
            filename=filename,
            expires_at=time.time() + config.file_retention_minutes * 60,
        )
        async with self._lock:
            self._files[token] = stored
        logger.info("Fichier stocké temporairement (expire dans %s min)", config.file_retention_minutes)
        return stored

    async def get_url(self, stored: StoredFile) -> str:
        return f"{config.public_base_url}/files/{stored.token}"

    async def resolve(self, token: str) -> StoredFile | None:
        async with self._lock:
            stored = self._files.get(token)
        if stored is None:
            return None
        if stored.expires_at < time.time() or not stored.path.exists():
            await self._remove(token)
            return None
        return stored

    async def purge_expired(self) -> None:
        now = time.time()
        async with self._lock:
            expired = [t for t, f in self._files.items() if f.expires_at < now]
        for token in expired:
            await self._remove(token)

    async def _remove(self, token: str) -> None:
        async with self._lock:
            stored = self._files.pop(token, None)
        if stored and stored.path.exists():
            try:
                await asyncio.to_thread(stored.path.unlink)
                logger.info("Fichier temporaire expiré supprimé")
            except OSError:
                logger.warning("Impossible de supprimer le fichier expiré %s", stored.path)


def build_storage_provider() -> StorageProvider:
    """Point d'extension : ajouter un autre provider (ex. S3Storage) en le branchant ici."""
    if config.storage_provider == "local":
        return LocalStorage()
    raise NotImplementedError(
        f"Fournisseur de stockage '{config.storage_provider}' non implémenté. "
        "Utilise STORAGE_PROVIDER=local ou ajoute ton propre StorageProvider dans storage.py."
    )
