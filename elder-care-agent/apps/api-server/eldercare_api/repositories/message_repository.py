from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from eldercare_api.models import FamilyMessage


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> FamilyMessage:
        message = FamilyMessage(**kwargs)
        self.db.add(message)
        self.db.flush()
        return message

    def list_for_elder(self, elder_id: str) -> list[FamilyMessage]:
        stmt = select(FamilyMessage).where(FamilyMessage.elder_id == elder_id).order_by(FamilyMessage.created_at.desc())
        return list(self.db.scalars(stmt))

    def get(self, message_id: str) -> FamilyMessage | None:
        return self.db.get(FamilyMessage, message_id)

    def mark_delivered(self, message_id: str, delivered_at: datetime) -> FamilyMessage | None:
        message = self.get(message_id)
        if message:
            message.status = 'delivered'
            message.delivered_at = delivered_at
        return message
