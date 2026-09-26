"""Représentation d'une demande de téléchargement."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class JobStatus(Enum):
    PENDING = auto()
    DOWNLOADING = auto()
    PROCESSING = auto()
    UPLOADING = auto()
    DONE = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class DownloadJob:
    job_id: str
    user_id: int
    channel_id: int
    url: str
    format_selector: str
    quality_label: str
    created_at: float = field(default_factory=time.time)
    status: JobStatus = JobStatus.PENDING
    output_path: Path | None = None
    title: str | None = None
    error_message: str | None = None

    @classmethod
    def create(
        cls, user_id: int, channel_id: int, url: str, format_selector: str, quality_label: str
    ) -> "DownloadJob":
        return cls(
            job_id=secrets.token_hex(8),
            user_id=user_id,
            channel_id=channel_id,
            url=url,
            format_selector=format_selector,
            quality_label=quality_label,
        )
