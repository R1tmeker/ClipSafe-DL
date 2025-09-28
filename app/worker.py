from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import Optional

from .config import load_settings
from .jobs import JobQueue
from .models import Job, JobStatus
from .storage import Storage

logger = logging.getLogger(__name__)


async def process_job(job: Job, storage: Storage) -> Optional[Path]:
    logger.info("Processing job %s (%s)", job.id, job.type.value)
    # TODO: реализовать скачивание исходника, ремукс и другие операции через ffmpeg_ops.
    raise NotImplementedError("FFmpeg processing is not implemented yet")


async def worker_loop() -> None:
    settings = load_settings()
    queue = JobQueue(settings.redis_url)
    storage = Storage(settings.storage_root, settings.temp_root)

    try:
        while True:
            job = await queue.dequeue(timeout=5)
            if not job:
                await asyncio.sleep(1)
                continue

            await queue.set_status(job.id, JobStatus.PROCESSING)
            try:
                result_path = await process_job(job, storage)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Job %s failed: %s", job.id, exc)
                await queue.set_status(job.id, JobStatus.FAILED, error=str(exc))
                continue

            await queue.set_status(
                job.id,
                JobStatus.COMPLETED,
                result_path=str(result_path) if result_path else None,
            )
    finally:
        await queue.close()


async def main_async() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    await worker_loop()


def main() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(main_async())


if __name__ == "__main__":
    main()
