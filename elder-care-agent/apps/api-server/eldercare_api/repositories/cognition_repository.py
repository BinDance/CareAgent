from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eldercare_api.models import CognitionSession


class CognitionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> CognitionSession:
        session = CognitionSession(**kwargs)
        self.db.add(session)
        self.db.flush()
        return session

    def history(self, elder_id: str, limit: int = 20) -> list[CognitionSession]:
        stmt = select(CognitionSession).where(CognitionSession.elder_id == elder_id).order_by(CognitionSession.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))
