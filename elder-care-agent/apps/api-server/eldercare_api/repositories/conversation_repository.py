from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eldercare_api.models import Conversation


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> Conversation:
        conversation = Conversation(**kwargs)
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def recent_for_elder(self, elder_id: str, limit: int = 10) -> list[Conversation]:
        stmt = select(Conversation).where(Conversation.elder_id == elder_id).order_by(Conversation.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))
