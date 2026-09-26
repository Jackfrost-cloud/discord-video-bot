"""Tâches de nettoyage : fichiers temporaires orphelins et liens de téléchargement expirés."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from bot.config import config
from bot.services.storage import StorageProvider
from bot.utils.logging import get_logger

logger = get_logger(__name__)

_ORPHAN_MAX_AGE_SECONDS = 3600  # fichiers temporaires oubliés depuis plus d'une heure


def cleanup_job_files(job_id: str) -> None:
    """Supprime tous les fichiers restants d'un job : succès, échec, timeout ou annulation."""
    for path in config.temp_directory.glob(f"{job_id}*"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Impossible de supprimer %s lors du nettoyage", path)


def _sweep_orphans(directory: Path) -> None:
    now = time.time()
    for path in directory.glob("*"):
        if not path.is_file():
            continue
        try:
            if now - path.stat().st_mtime > _ORPHAN_MAX_AGE_SECONDS:
                path.unlink(missing_ok=True)
                logger.info("Fichier temporaire orphelin supprimé : %s", path.name)
        except OSError:
            continue


async def run_periodic_cleanup(storage: StorageProvider, interval_seconds: int = 300) -> None:
    """Boucle de fond : purge les liens expirés et les fichiers temporaires oubliés."""
    while True:
        try:
            await storage.purge_expired()
            await asyncio.to_thread(_sweep_orphans, config.temp_directory)
        except Exception:
            logger.exception("Erreur pendant le nettoyage périodique")
        await asyncio.sleep(interval_seconds)
