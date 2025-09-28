from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import load_settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    is_premium = Column(Integer)
    created_at = Column(DateTime)


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    user_id = Column(Integer)
    type = Column(String)
    status = Column(String)
    src_kind = Column(String)
    src_url = Column(String)
    src_file_id = Column(String)
    params = Column(String)
    result_path = Column(String)
    error = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class FileModel(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String)
    path = Column(String)
    size = Column(Integer)
    mime = Column(String)
    hash = Column(String)
    created_at = Column(DateTime)


class DatabaseSession:
    def __init__(self, url: Optional[str] = None) -> None:
        settings = load_settings()
        engine_url = url or settings.database_url or "sqlite:///clipsafe.db"
        self.engine = create_engine(engine_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self):
        return self.Session()

