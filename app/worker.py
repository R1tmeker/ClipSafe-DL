from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from aiogram import Bot

from .analytics import AnalyticsClient, AnalyticsEvent
from .antispam import AntiSpam, RateLimitExceeded
from .config import load_settings
from .jobs import JobQueue
from .logs import setup_logging
from .metrics import track_end, track_start
from .models import Job, JobStatus, JobType
from .prometheus_exporter import PrometheusExporter
from .services import (
    Downloader,
    DownloadError,
    FfmpegProcessingError,
    StorageBackend,
    StoredResult,
    download_with_retry,
    run_job,
)
from .storage import Storage

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL = timedelta(minutes=30)


@dataclass(slots=True)
class JobContext:
    job: Job
    started_at: datetime
    source_path: Path


async def process_job(
    job: Job,
    storage: Storage,
    downloader: Downloader,
    backend: StorageBackend,
    analytics: AnalyticsClient,
) -> StoredResult:
    started = datetime.utcnow()
    ctx = JobContext(job=job, started_at=started, source_path=Path())
    track_start(job.type.value)

    try:
        source_path = await download_with_retry(downloader, job)
        ctx.source_path = source_path
        output_dir = storage.job_dir(job.id)
        result_path = await run_job(job, source_path, output_dir)
        stored = backend.save_result(job.id, result_path)

        job.params.setdefault("metadata", {})
        job.params["result_path"] = str(stored.path)
        if stored.public_url:
            job.params["public_url"] = stored.public_url

        analytics.track(
            AnalyticsEvent(
                name="job_completed",
                payload={
                    "job_id": job.id,
                    "type": job.type.value,
                    "status": "completed",
                },
            )
        )
        duration = (datetime.utcnow() - started).total_seconds()
        track_end(job.type.value, "completed", duration)
        return stored
    except (DownloadError, FfmpegProcessingError) as exc:
        duration = (datetime.utcnow() - started).total_seconds()
        track_end(job.type.value, "failed", duration)
        logger.error("job %s failed: %s", job.id, exc)
        raise
    finally:
        try:
            if ctx.source_path.exists():
                ctx.source_path.unlink()
        except OSError:
            logger.debug("Failed to cleanup source file", exc_info=True)


async def worker_loop() -> None:
    settings = load_settings()
    queue = JobQueue(settings.redis_url)
    storage = Storage(settings.storage_root, settings.temp_root)
    backend = StorageBackend(storage)
    antispam = AntiSpam()
    analytics = AnalyticsClient()
    prometheus = PrometheusExporter(settings.prometheus_port)
    prometheus.ensure_started()

    bot: Optional[Bot] = None
    if settings.bot_token:
        bot = Bot(token=settings.bot_token)

    downloader = Downloader(storage, bot)
    next_cleanup_at = datetime.utcnow()

    try:
        while True:
            if datetime.utcnow() >= next_cleanup_at:
                try:
                    backend.cleanup_expired()
                except Exception:  # pragma: no cover - defensive cleanup
                    logger.debug("Cleanup failed", exc_info=True)
                next_cleanup_at = datetime.utcnow() + CLEANUP_INTERVAL

            job = await queue.dequeue(timeout=5)
            if not job:
                await asyncio.sleep(1)
                continue

            try:
                antispam.register_job(job.user_id)
            except RateLimitExceeded as exc:
                logger.info("Skipping job %s: %s", job.id, exc)
                await queue.set_status(job.id, JobStatus.FAILED, error=str(exc))
                continue

            await queue.set_status(job.id, JobStatus.PROCESSING)
            try:
                stored = await process_job(job, storage, downloader, backend, analytics)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Job %s failed: %s", job.id, exc)
                await queue.set_status(job.id, JobStatus.FAILED, error=str(exc))
                continue

            await queue.update_job(job)
            await queue.set_status(
                job.id,
                JobStatus.COMPLETED,
                result_path=str(stored.path) if stored.path else None,
            )
    finally:
        await queue.close()
        if bot:
            await bot.session.close()


async def main_async() -> None:
    setup_logging()
    await worker_loop()


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Worker interrupted")


if __name__ == "__main__":
    main()
