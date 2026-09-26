import asyncio

import pytest

from bot.models.download_job import DownloadJob
from bot.services.queue import DownloadQueue, TooManyActiveDownloadsError


@pytest.mark.asyncio
async def test_enqueue_and_process():
    processed = []

    async def runner(job: DownloadJob) -> None:
        processed.append(job.job_id)

    queue = DownloadQueue(runner=runner)
    queue.start_workers()
    try:
        job = DownloadJob.create(1, 1, "https://x", "best", "best")
        await queue.enqueue(job)
        await asyncio.sleep(0.1)
        assert processed == [job.job_id]
    finally:
        await queue.stop()


@pytest.mark.asyncio
async def test_per_user_limit_enforced():
    async def slow_runner(job: DownloadJob) -> None:
        await asyncio.sleep(0.3)

    queue = DownloadQueue(runner=slow_runner)
    queue.start_workers()
    try:
        job1 = DownloadJob.create(42, 1, "https://x", "best", "best")
        await queue.enqueue(job1)
        with pytest.raises(TooManyActiveDownloadsError):
            queue.check_can_enqueue(42)
    finally:
        await queue.stop()
