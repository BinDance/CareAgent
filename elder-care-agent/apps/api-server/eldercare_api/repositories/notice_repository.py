from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from eldercare_api.models import FamilyNotice


class NoticeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> FamilyNotice:
        notice = FamilyNotice(**kwargs)
        self.db.add(notice)
        self.db.flush()
        return notice

    def list_pending(self, elder_id: str) -> list[FamilyNotice]:
        stmt = select(FamilyNotice).where(FamilyNotice.elder_id == elder_id, FamilyNotice.status.in_(['pending', 'ready'])).order_by(FamilyNotice.created_at.asc())
        return list(self.db.scalars(stmt))

    def list_all_pending(self) -> list[FamilyNotice]:
        stmt = select(FamilyNotice).where(FamilyNotice.status.in_(['pending', 'ready'])).order_by(FamilyNotice.created_at.asc())
        return list(self.db.scalars(stmt))

    def get(self, notice_id: str) -> FamilyNotice | None:
        return self.db.get(FamilyNotice, notice_id)

    def mark_delivered(self, notice_id: str, delivered_at: datetime) -> FamilyNotice | None:
        notice = self.get(notice_id)
        if notice:
            notice.status = 'delivered'
            notice.delivered_at = delivered_at
        return notice

    def reschedule(self, notice_id: str, new_slot: datetime) -> FamilyNotice | None:
        notice = self.get(notice_id)
        if notice:
            notice.status = 'pending'
            notice.planned_for = new_slot
        return notice
