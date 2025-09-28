from __future__ import annotations

import logging
from typing import Optional

from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)

JOB_STARTED = Counter("clipsafe_job_started", "Jobs started", ["type"])
JOB_COMPLETED = Counter("clipsafe_job_completed", "Jobs completed", ["type", "status"])
JOB_DURATION = Gauge("clipsafe_job_duration_seconds", "Job processing duration", ["type"])
ACTIVE_JOBS = Gauge("clipsafe_active_jobs", "Jobs currently processed")


def track_start(job_type: str) -> None:
    logger.debug("prometheus track_start %s", job_type)
    ACTIVE_JOBS.inc()
    JOB_STARTED.labels(job_type).inc()


def track_end(job_type: str, status: str, duration: Optional[float] = None) -> None:
    logger.debug("prometheus track_end %s status=%s duration=%s", job_type, status, duration)
    ACTIVE_JOBS.dec()
    JOB_COMPLETED.labels(job_type, status).inc()
    if duration is not None:
        JOB_DURATION.labels(job_type).set(duration)

