from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eldercare_api.models import Alert, ReviewQueue


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_alert(self, **kwargs) -> Alert:
        alert = Alert(**kwargs)
        self.db.add(alert)
        self.db.flush()
        return alert

    def create_review(self, **kwargs) -> ReviewQueue:
        item = ReviewQueue(**kwargs)
        self.db.add(item)
        self.db.flush()
        return item

    def unresolved_for_elder(self, elder_id: str) -> list[Alert]:
        stmt = select(Alert).where(Alert.elder_id == elder_id, Alert.resolved.is_(False)).order_by(Alert.created_at.desc())
        return list(self.db.scalars(stmt))
