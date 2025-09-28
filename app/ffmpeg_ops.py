from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence


@dataclass(slots=True)
class FfmpegResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


async def run_ffmpeg(args: Sequence[str], *, timeout: Optional[int] = None) -> FfmpegResult:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        raise
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    return FfmpegResult(returncode=process.returncode or 0, stdout=stdout, stderr=stderr)


def build_remux_command(input_path: Path, output_path: Path, *, mp4_faststart: bool = False) -> List[str]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0",
        "-c",
        "copy",
    ]
    if mp4_faststart:
        command += ["-movflags", "+faststart"]
    command.append(str(output_path))
    return command


def build_trim_command(
    input_path: Path,
    output_path: Path,
    *,
    start_seconds: Optional[float],
    end_seconds: Optional[float],
    smart: bool = False,
) -> List[str]:
    duration: Optional[float] = None
    if start_seconds is not None and end_seconds is not None and end_seconds > start_seconds:
        duration = end_seconds - start_seconds

    if smart:
        command: List[str] = ["ffmpeg", "-hide_banner", "-y", "-i", str(input_path)]
        if start_seconds is not None:
            command += ["-ss", f"{start_seconds:.3f}"]
        if duration is not None:
            command += ["-t", f"{duration:.3f}"]
        elif end_seconds is not None:
            command += ["-to", f"{end_seconds:.3f}"]
        command += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        return command

    command = ["ffmpeg", "-hide_banner", "-y"]
    if start_seconds is not None:
        command += ["-ss", f"{start_seconds:.3f}"]
    command += ["-i", str(input_path)]
    if duration is not None:
        command += ["-t", f"{duration:.3f}"]
    elif end_seconds is not None:
        command += ["-to", f"{end_seconds:.3f}"]
    command += ["-c", "copy", "-avoid_negative_ts", "make_zero", str(output_path)]
    return command


def build_audio_extract_command(input_path: Path, output_path: Path) -> List[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-c:a",
        "copy",
        str(output_path),
    ]


def build_thumbnail_command(
    input_path: Path,
    output_path: Path,
    *,
    timestamp_seconds: Optional[float] = None,
    frame_number: Optional[int] = None,
) -> List[str]:
    command = ["ffmpeg", "-hide_banner", "-y"]
    if timestamp_seconds is not None:
        command += ["-ss", f"{timestamp_seconds:.3f}"]
    command += ["-i", str(input_path)]
    if frame_number is not None:
        command += ["-vf", f"select='eq(n,{frame_number})'", "-vsync", "0"]
    command += ["-frames:v", "1", str(output_path)]
    return command
