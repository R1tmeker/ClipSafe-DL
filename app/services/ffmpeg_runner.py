from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Iterable, Optional

from ..ffmpeg_ops import (
    build_audio_extract_command,
    build_remux_command,
    build_thumbnail_command,
    build_trim_command,
    run_ffmpeg,
)
from ..models import Job, JobType

logger = logging.getLogger(__name__)


class FfmpegProcessingError(Exception):
    """Raised when FFmpeg finishes with a non-zero code."""


async def execute_ffmpeg(command: Iterable[str], job: Job, description: str) -> Path:
    command = list(command)
    logger.info("job=%s executing %s: %s", job.id, description, " ".join(command))
    result = await run_ffmpeg(command, timeout=600)
    if not result.ok:
        logger.error("job=%s ffmpeg failed (%s): %s", job.id, description, result.stderr)
        raise FfmpegProcessingError(result.stderr)
    return Path(command[-1])


async def process_remux(job: Job, source_path: Path, output_path: Path, *, mp4: bool) -> Path:
    command = build_remux_command(source_path, output_path, mp4_faststart=mp4)
    return await execute_ffmpeg(command, job, "remux")


async def process_audio(job: Job, source_path: Path, output_path: Path) -> Path:
    command = build_audio_extract_command(source_path, output_path)
    return await execute_ffmpeg(command, job, "audio-extract")


async def process_thumbnail(
    job: Job,
    source_path: Path,
    output_path: Path,
    *,
    timestamp_seconds: Optional[float] = None,
    frame_number: Optional[int] = None,
) -> Path:
    command = build_thumbnail_command(
        source_path,
        output_path,
        timestamp_seconds=timestamp_seconds,
        frame_number=frame_number,
    )
    return await execute_ffmpeg(command, job, "thumbnail")


async def process_trim(
    job: Job,
    source_path: Path,
    output_path: Path,
    *,
    start_seconds: Optional[float],
    end_seconds: Optional[float],
    smart: bool,
) -> Path:
    command = build_trim_command(
        source_path,
        output_path,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        smart=smart,
    )
    description = "trim-smart" if smart else "trim"
    return await execute_ffmpeg(command, job, description)


async def run_job(job: Job, source_path: Path, output_dir: Path) -> Path:
    params = job.params or {}
    suffix_map = {
        JobType.ORIGINAL: source_path.suffix or ".bin",
        JobType.REMUX: ".mp4" if params.get("target_container") == "mp4" else ".mkv",
        JobType.AUDIO: ".m4a",
        JobType.PREVIEW: ".jpg",
        JobType.TRIM: "_cut" + (source_path.suffix or ".mkv"),
    }
    suffix = suffix_map.get(job.type, ".bin")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job.id}{suffix}"

    if job.type == JobType.ORIGINAL:
        # Return the original file without encoding.
        await asyncio.to_thread(_copy_file, source_path, output_path)
        return output_path
    if job.type == JobType.REMUX:
        mp4 = params.get("target_container") == "mp4"
        return await process_remux(job, source_path, output_path, mp4=mp4)
    if job.type == JobType.AUDIO:
        return await process_audio(job, source_path, output_path)
    if job.type == JobType.PREVIEW:
        ts = params.get("time_seconds")
        frame = params.get("frame_number")
        return await process_thumbnail(job, source_path, output_path, timestamp_seconds=ts, frame_number=frame)
    if job.type == JobType.TRIM:
        start = params.get("start_seconds")
        end = params.get("end_seconds")
        smart = params.get("smart", False)
        return await process_trim(job, source_path, output_path, start_seconds=start, end_seconds=end, smart=smart)

    raise FfmpegProcessingError(f"Unsupported job type: {job.type}")


def _copy_file(source: Path, target: Path) -> None:
    shutil.copy2(source, target)
