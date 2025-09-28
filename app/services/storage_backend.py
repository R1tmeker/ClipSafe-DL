from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    BotoCoreError = ClientError = Exception  # type: ignore[assignment]

from ..config import load_settings
from ..storage import Storage

logger = logging.getLogger(__name__)

METADATA_FILE = ".metadata.json"


@dataclass(slots=True)
class StoredResult:
    path: Path
    public_url: Optional[str]
    expires_at: datetime


class StorageBackend:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.settings = load_settings()
        self._s3_client = self._build_s3_client()
        self._s3_bucket = self.settings.s3_bucket

    def save_result(self, job_id: str, local_path: Path) -> StoredResult:
        ttl = timedelta(hours=self.settings.result_ttl_hours)
        expires_at = datetime.utcnow() + ttl

        target_dir = self.storage.job_dir(job_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / local_path.name
        if local_path.resolve() != target_path.resolve():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.replace(target_path)

        s3_key = self._upload_to_s3(job_id, target_path)
        public_url = self._build_public_url(job_id, target_path.name, s3_key)

        metadata = self._load_metadata(target_dir)
        metadata_results = metadata.setdefault("results", [])
        metadata_results = [
            entry
            for entry in metadata_results
            if entry.get("filename") != target_path.name
        ]
        metadata_results.append(
            {
                "filename": target_path.name,
                "expires_at": expires_at.isoformat(),
                "s3_key": s3_key,
            }
        )
        metadata["results"] = metadata_results
        self._write_metadata(target_dir, metadata)

        return StoredResult(path=target_path, public_url=public_url, expires_at=expires_at)

    def cleanup_expired(self) -> None:
        now = datetime.utcnow()
        for job_dir in self.storage.root.iterdir():
            if not job_dir.is_dir():
                continue

            metadata = self._load_metadata(job_dir)
            results = metadata.get("results", [])
            changed = False
            remaining = []

            for entry in results:
                expires_at_raw = entry.get("expires_at")
                try:
                    expires_at = datetime.fromisoformat(expires_at_raw)
                except (TypeError, ValueError):
                    expires_at = now

                if expires_at <= now:
                    filename = entry.get("filename")
                    if filename:
                        file_path = job_dir / filename
                        if file_path.exists():
                            try:
                                file_path.unlink()
                            except OSError:
                                logger.debug("Failed to delete %s", file_path, exc_info=True)
                    s3_key = entry.get("s3_key")
                    if s3_key:
                        self._delete_s3_object(s3_key)
                    changed = True
                else:
                    remaining.append(entry)

            if not changed:
                continue

            if remaining:
                metadata["results"] = remaining
                self._write_metadata(job_dir, metadata)
            else:
                meta_path = job_dir / METADATA_FILE
                if meta_path.exists():
                    try:
                        meta_path.unlink()
                    except OSError:
                        logger.debug("Failed to delete metadata %s", meta_path, exc_info=True)
                for residual in job_dir.iterdir():
                    if residual.is_file():
                        try:
                            residual.unlink()
                        except OSError:
                            logger.debug("Failed to delete %s", residual, exc_info=True)
                    else:
                        shutil.rmtree(residual, ignore_errors=True)
                try:
                    job_dir.rmdir()
                except OSError:
                    logger.debug("Failed to remove directory %s", job_dir, exc_info=True)

    def _build_public_url(self, job_id: str, filename: str, s3_key: Optional[str]) -> Optional[str]:
        if self.settings.public_base_url:
            base = self.settings.public_base_url.rstrip("/")
            return f"{base}/{job_id}/{filename}"
        if self.settings.s3_public_base and s3_key:
            base = self.settings.s3_public_base.rstrip("/")
            return f"{base}/{s3_key}"
        if s3_key and self._s3_bucket:
            endpoint = self.settings.s3_endpoint.rstrip("/") if self.settings.s3_endpoint else None
            if endpoint:
                return f"{endpoint}/{self._s3_bucket}/{s3_key}"
            return f"https://{self._s3_bucket}.s3.amazonaws.com/{s3_key}"
        return None

    def _build_s3_client(self):  # type: ignore[return-type]
        if not self.settings.s3_bucket or not boto3:
            return None
        if not (self.settings.s3_access_key and self.settings.s3_secret_key):
            logger.warning("S3 credentials are not fully configured; skipping S3 uploads")
            return None
        session = boto3.session.Session()
        return session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint,
            aws_access_key_id=self.settings.s3_access_key,
            aws_secret_access_key=self.settings.s3_secret_key,
            region_name=self.settings.s3_region,
        )

    def _upload_to_s3(self, job_id: str, path: Path) -> Optional[str]:
        if not self._s3_client or not self._s3_bucket:
            return None
        key = f"{job_id}/{path.name}"
        try:
            self._s3_client.upload_file(str(path), self._s3_bucket, key)
            logger.info("Uploaded %s to s3://%s/%s", path, self._s3_bucket, key)
            return key
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - network dependency
            logger.error("Failed to upload %s to S3: %s", path, exc)
            return None

    def _delete_s3_object(self, key: str) -> None:
        if not self._s3_client or not self._s3_bucket:
            return
        try:
            self._s3_client.delete_object(Bucket=self._s3_bucket, Key=key)
            logger.info("Deleted s3://%s/%s", self._s3_bucket, key)
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover
            logger.debug("Failed to delete S3 object %s: %s", key, exc)

    @staticmethod
    def _load_metadata(directory: Path) -> Dict[str, Any]:
        meta_path = directory / METADATA_FILE
        if not meta_path.exists():
            return {"results": []}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug("Failed to parse metadata %s", meta_path, exc_info=True)
            return {"results": []}

    @staticmethod
    def _write_metadata(directory: Path, metadata: Dict[str, Any]) -> None:
        meta_path = directory / METADATA_FILE
        try:
            meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        except OSError:
            logger.debug("Failed to write metadata %s", meta_path, exc_info=True)

