from bot.models.download_job import DownloadJob, JobStatus


def test_create_generates_unique_ids():
    job1 = DownloadJob.create(1, 2, "https://x", "best", "Meilleure qualité")
    job2 = DownloadJob.create(1, 2, "https://x", "best", "Meilleure qualité")
    assert job1.job_id != job2.job_id


def test_create_default_status_is_pending():
    job = DownloadJob.create(1, 2, "https://x", "best", "720p")
    assert job.status == JobStatus.PENDING
    assert job.output_path is None
