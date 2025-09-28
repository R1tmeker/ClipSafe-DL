from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional


class Storage:
    def __init__(self, root: Path, temp_root: Optional[Path] = None) -> None:
        self.root = Path(root)
        self.temp_root = Path(temp_root) if temp_root else self.root / "tmp"
        self.root.mkdir(parents=True, exist_ok=True)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        path = self.root / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def temp_dir(self, job_id: str) -> Path:
        path = self.temp_root / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def allocate_result(self, job_id: str, filename: str) -> Path:
        return self.job_dir(job_id) / filename

    def allocate_temp(self, job_id: str, filename: str) -> Path:
        return self.temp_dir(job_id) / filename

    def cleanup(self, job_id: str) -> None:
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)
        shutil.rmtree(self.temp_dir(job_id), ignore_errors=True)

