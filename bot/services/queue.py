"""File d'attente des téléchargements : limite la concurrence et le nombre par utilisateur."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from bot.config import config
from bot.models.download_job import DownloadJob
from bot.utils.logging import get_logger

logger = get_logger(__name__)

JobRunner = Callable[[DownloadJob], Awaitable[None]]


class QueueFullError(Exception):
    pass


class TooManyActiveDownloadsError(Exception):
    pass


class CooldownActiveError(Exception):
    def __init__(self, remaining_seconds: float):
        self.remaining_seconds = remaining_seconds
        super().__init__(f"Cooldown actif encore {remaining_seconds:.0f}s")


@dataclass
class DownloadQueue:
    runner: JobRunner
    _semaphore: asyncio.Semaphore = field(init=False)
    _queue: "asyncio.Queue[DownloadJob]" = field(init=False)
    _active_per_user: dict[int, int] = field(default_factory=dict, init=False)
    _last_request_at: dict[int, float] = field(default_factory=dict, init=False)
    _worker_tasks: list[asyncio.Task] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(config.max_concurrent_downloads)
        self._queue = asyncio.Queue(maxsize=config.max_queue_size)

    def start_workers(self) -> None:
        for i in range(config.max_concurrent_downloads):
            task = asyncio.create_task(self._worker(i))
            self._worker_tasks.append(task)

    async def stop(self) -> None:
        for task in self._worker_tasks:
            task.cancel()

    def check_can_enqueue(self, user_id: int) -> None:
        """Vérifie les limites avant d'accepter une nouvelle demande (lève une exception sinon)."""
        now = time.monotonic()
        last = self._last_request_at.get(user_id)
        if last is not None:
            elapsed = now - last
            if elapsed < config.download_cooldown:
                raise CooldownActiveError(config.download_cooldown - elapsed)

        active = self._active_per_user.get(user_id, 0)
        if active >= config.max_active_downloads_per_user:
            raise TooManyActiveDownloadsError(
                f"Tu as déjà {active} téléchargement(s) actif(s) "
                f"(maximum {config.max_active_downloads_per_user})."
            )

        if self._queue.full():
            raise QueueFullError("La file d'attente est pleine, réessaie dans quelques instants.")

    async def enqueue(self, job: DownloadJob) -> None:
        self.check_can_enqueue(job.user_id)
        self._last_request_at[job.user_id] = time.monotonic()
        self._active_per_user[job.user_id] = self._active_per_user.get(job.user_id, 0) + 1
        await self._queue.put(job)
        logger.info("Job %s mis en file (utilisateur %s)", job.job_id, job.user_id)

    async def _worker(self, worker_index: int) -> None:
        while True:
            job = await self._queue.get()
            async with self._semaphore:
                try:
                    await self.runner(job)
                except Exception:
                    logger.exception("Erreur non gérée pendant le traitement du job %s", job.job_id)
                finally:
                    self._active_per_user[job.user_id] = max(
                        0, self._active_per_user.get(job.user_id, 1) - 1
                    )
                    self._queue.task_done()
