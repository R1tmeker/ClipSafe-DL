from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx
from aiogram import Bot

from ..storage import Storage
from ..models import Job, SourceKind

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1 << 20  # 1 MiB


class DownloadError(Exception):
    """Raised when media could not be downloaded."""


class Downloader:
    def __init__(self, storage: Storage, bot: Optional[Bot] = None) -> None:
        self.storage = storage
        self.bot = bot

    async def fetch_job_source(self, job: Job) -> Path:
        if job.source_kind == SourceKind.FILE:
            return await self._download_telegram_file(job)
        if job.source_kind == SourceKind.URL:
            return await self._download_http(job)
        raise DownloadError(f"Unsupported source kind: {job.source_kind}")

    async def _download_http(self, job: Job) -> Path:
        if not job.source_url:
            raise DownloadError("Job does not contain source_url")

        target_dir = self.storage.temp_dir(job.id)
        filename = job.file_name or Path(job.source_url).name or f"{job.id}.bin"
        target_path = target_dir / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)

        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                async with client.stream("GET", job.source_url) as response:
                    response.raise_for_status()
                    with target_path.open("wb") as fp:
                        async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE):
                            fp.write(chunk)
            except httpx.HTTPError as exc:
                logger.warning("Failed to download %s: %s", job.source_url, exc)
                raise DownloadError("Не удалось скачать файл по ссылке") from exc

        return target_path

    async def _download_telegram_file(self, job: Job) -> Path:
        if not self.bot:
            raise DownloadError("Telegram bot instance is not available")
        if not job.source_file_id:
            raise DownloadError("Job does not contain source_file_id")

        target_dir = self.storage.temp_dir(job.id)
        filename = job.file_name or f"{job.id}.bin"
        target_path = target_dir / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)

        file = await self.bot.get_file(job.source_file_id)
        await self.bot.download_file(file.file_path, destination=target_path)
        return target_path


async def download_with_retry(downloader: Downloader, job: Job, retries: int = 3) -> Path:
    attempt = 0
    while True:
        try:
            return await downloader.fetch_job_source(job)
        except DownloadError:
            attempt += 1
            if attempt >= retries:
                raise
            await asyncio.sleep(2 ** attempt)

