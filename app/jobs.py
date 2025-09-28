from __future__ import annotations

import json
import logging
from typing import List, Optional

import redis.asyncio as redis

from .models import Job, JobStatus, JobType

logger = logging.getLogger(__name__)

QUEUE_KEY = "clipsafe:queue"
JOB_KEY_PREFIX = "clipsafe:job:"
USER_DRAFT_KEY = "clipsafe:user:{user_id}:drafts"
USER_HISTORY_KEY = "clipsafe:user:{user_id}:history"
MAX_HISTORY = 20


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


class JobQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis: redis.Redis = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def close(self) -> None:
        await self._redis.close()

    async def enqueue(self, job: Job) -> Job:
        job.touch(status=JobStatus.DRAFT)
        await self._save_job(job)
        draft_key = USER_DRAFT_KEY.format(user_id=job.user_id)
        await self._redis.rpush(draft_key, job.id)
        await self._redis.ltrim(draft_key, -5, -1)
        logger.info("Stored draft job %s for user %s", job.id, job.user_id)
        return job

    async def assign_latest_job(self, user_id: int, job_type: JobType) -> Optional[Job]:
        draft_key = USER_DRAFT_KEY.format(user_id=user_id)
        job_id = await self._redis.rpop(draft_key)
        if not job_id:
            return None

        job = await self.get_job(job_id)
        if not job:
            logger.warning("Draft job %s not found in storage", job_id)
            return None

        if not job.params.get("rights_confirmed"):
            await self._redis.rpush(draft_key, job.id)
            logger.info("Job %s awaiting rights confirmation", job.id)
            return None

        job.type = job_type
        job.touch(status=JobStatus.QUEUED)
        await self._save_job(job)
        await self._redis.rpush(QUEUE_KEY, job.id)
        history_key = USER_HISTORY_KEY.format(user_id=user_id)
        await self._redis.lpush(history_key, job.id)
        await self._redis.ltrim(history_key, 0, MAX_HISTORY - 1)
        logger.info("Queued job %s (%s) for user %s", job.id, job_type.value, user_id)
        return job

    async def cancel_latest_job(self, user_id: int) -> Optional[Job]:
        draft_key = USER_DRAFT_KEY.format(user_id=user_id)
        job_id = await self._redis.rpop(draft_key)
        if not job_id:
            return None
        job = await self.get_job(job_id)
        if not job:
            return None
        job.touch(status=JobStatus.CANCELLED)
        await self._save_job(job)
        return job

    async def delete_job(self, job_id: str) -> None:
        job = await self.get_job(job_id)
        if not job:
            return
        draft_key = USER_DRAFT_KEY.format(user_id=job.user_id)
        await self._redis.lrem(draft_key, 0, job_id)
        await self._redis.delete(_job_key(job_id))
        logger.info("Deleted draft job %s for user %s", job_id, job.user_id)

    async def update_job(self, job: Job) -> None:
        job.touch()
        await self._save_job(job)

    async def list_user_jobs(self, user_id: int, limit: int = 5) -> List[Job]:
        history_key = USER_HISTORY_KEY.format(user_id=user_id)
        ids = await self._redis.lrange(history_key, 0, limit - 1)
        jobs: List[Job] = []
        for job_id in ids:
            job = await self.get_job(job_id)
            if job:
                jobs.append(job)
        return jobs

    async def dequeue(self, timeout: int = 5) -> Optional[Job]:
        item = await self._redis.blpop(QUEUE_KEY, timeout=timeout)
        if not item:
            return None
        _, job_id = item
        job = await self.get_job(job_id)
        if not job:
            logger.warning("Lost job %s referenced in queue", job_id)
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        payload = await self._redis.get(_job_key(job_id))
        if not payload:
            return None
        data = json.loads(payload)
        return Job.from_dict(data)

    async def set_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error: Optional[str] = None,
        result_path: Optional[str] = None,
    ) -> Optional[Job]:
        job = await self.get_job(job_id)
        if not job:
            return None
        job.touch(status=status, error=error)
        if result_path:
            job.result_path = result_path
        await self._save_job(job)
        return job

    async def _save_job(self, job: Job) -> None:
        await self._redis.set(_job_key(job.id), json.dumps(job.to_dict()))



