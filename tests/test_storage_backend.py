from __future__ import annotations

from pathlib import Path

from app.services.storage_backend import StorageBackend
from app.storage import Storage


def test_cleanup_expired_removes_files(monkeypatch, tmp_path):
    storage_root = tmp_path / "data"
    temp_root = tmp_path / "temp"
    monkeypatch.setenv("CLIPSAFE_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("CLIPSAFE_TEMP_ROOT", str(temp_root))
    monkeypatch.setenv("CLIPSAFE_RESULT_TTL_H", "0")

    storage = Storage(storage_root, temp_root)
    backend = StorageBackend(storage)

    job_id = "job123"
    temp_file = storage.allocate_temp(job_id, "result.mkv")
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file.write_bytes(b"data")

    stored = backend.save_result(job_id, temp_file)
    assert stored.path.exists()

    backend.cleanup_expired()

    assert not stored.path.exists()
    assert not (storage_root / job_id).exists()
