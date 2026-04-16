from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from eldercare_api.config import get_settings
from eldercare_api.database import get_db
from eldercare_api.models import Elder, FamilyMember, User
from eldercare_api.schemas import UserContext


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith('bearer '):
        return authorization.split(' ', 1)[1].strip()
    return authorization.strip()


def _user_context_from_user(db: Session, user: User) -> UserContext:
    elder = db.scalar(select(Elder).where(Elder.user_id == user.id))
    family_member = db.scalar(select(FamilyMember).where(FamilyMember.user_id == user.id))
    return UserContext(
        user_id=user.id,
        role=user.role,
        elder_id=elder.id if elder else (family_member.elder_id if family_member else None),
        family_member_id=family_member.id if family_member else None,
        email=user.email,
        display_name=user.display_name,
    )


def get_current_user(required_role: str | None = None):
    def dependency(
        authorization: str | None = Header(default=None),
        x_demo_role: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ) -> UserContext:
        settings = get_settings()
        token = _parse_bearer(authorization)
        user = None
        if token:
            user = db.scalar(select(User).where(User.access_token == token))
        elif settings.eldercare_auth_optional:
            fallback_role = required_role or x_demo_role or 'family'
            user = db.scalar(select(User).where(User.role == fallback_role).order_by(User.created_at.asc()))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
        context = _user_context_from_user(db, user)
        if required_role and context.role != required_role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
        return context
    return dependency


require_elder_user = get_current_user('elder')
require_family_user = get_current_user('family')
