from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class JobType(str, Enum):
    ORIGINAL = "original"
    REMUX = "remux"
    TRIM = "trim"
    AUDIO = "audio"
    PREVIEW = "preview"


class JobStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceKind(str, Enum):
    FILE = "file"
    URL = "url"
    YT = "yt"
    TT = "tt"


@dataclass(slots=True)
class Job:
    user_id: int
    type: JobType = JobType.ORIGINAL
    status: JobStatus = JobStatus.DRAFT
    source_kind: SourceKind = SourceKind.FILE
    id: str = field(default_factory=lambda: uuid4().hex)
    source_url: Optional[str] = None
    source_file_id: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    result_path: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type.value,
            "status": self.status.value,
            "source_kind": self.source_kind.value,
            "source_url": self.source_url,
            "source_file_id": self.source_file_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "params": self.params,
            "result_path": self.result_path,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Job":
        payload = payload.copy()
        payload["type"] = JobType(payload["type"])
        payload["status"] = JobStatus(payload["status"])
        payload["source_kind"] = SourceKind(payload["source_kind"])
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        payload["updated_at"] = datetime.fromisoformat(payload["updated_at"])
        return cls(**payload)

    @classmethod
    def from_file(
        cls,
        user_id: int,
        file_id: str,
        file_name: Optional[str],
        file_size: Optional[int],
        mime_type: Optional[str],
    ) -> "Job":
        return cls(
            user_id=user_id,
            source_kind=SourceKind.FILE,
            source_file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
        )

    @classmethod
    def from_url(
        cls,
        user_id: int,
        url: str,
        media_info: Optional[Dict[str, Any]] = None,
    ) -> "Job":
        params: Dict[str, Any] = {}
        if media_info:
            params["media_info"] = media_info
        return cls(
            user_id=user_id,
            source_kind=SourceKind.URL,
            source_url=url,
            params=params,
        )

    def touch(self, *, status: Optional[JobStatus] = None, error: Optional[str] = None) -> None:
        if status:
            self.status = status
        if error is not None:
            self.error = error
        self.updated_at = datetime.utcnow()


