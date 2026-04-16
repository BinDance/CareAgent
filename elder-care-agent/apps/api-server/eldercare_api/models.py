from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eldercare_api.database import Base, utcnow


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = 'users'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)


class Elder(TimestampMixin, Base):
    __tablename__ = 'elders'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Shanghai', nullable=False)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    voice_locale: Mapped[str] = mapped_column(String(32), default='zh-CN', nullable=False)

    user = relationship('User')


class FamilyMember(TimestampMixin, Base):
    __tablename__ = 'family_members'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    relationship_label: Mapped[str] = mapped_column(String(64), nullable=False)
    preferred_name: Mapped[str] = mapped_column(String(120), nullable=False)

    user = relationship('User')
    elder = relationship('Elder')


class ElderProfile(TimestampMixin, Base):
    __tablename__ = 'elder_profiles'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, unique=True, index=True)
    stable_profile_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    risk_profile_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    profile_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyStatus(TimestampMixin, Base):
    __tablename__ = 'daily_status'
    __table_args__ = (UniqueConstraint('elder_id', 'status_date', name='uq_daily_status_elder_date'),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    status_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    family_report_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class FamilyNotice(TimestampMixin, Base):
    __tablename__ = 'family_notices'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    family_member_id: Mapped[str | None] = mapped_column(ForeignKey('family_members.id'), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    summarized_notice: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    delivery_strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    suitable_window: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='pending', nullable=False, index=True)
    planned_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Prescription(TimestampMixin, Base):
    __tablename__ = 'prescriptions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(24), default='uploaded', nullable=False, index=True)
    extracted_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    uncertainty_notes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MedicationPlan(TimestampMixin, Base):
    __tablename__ = 'medication_plans'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    prescription_id: Mapped[str | None] = mapped_column(ForeignKey('prescriptions.id'), nullable=True, index=True)
    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dose: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    frequency: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    meal_timing: Mapped[str] = mapped_column(String(64), nullable=False, default='')
    time_slots: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default='active', nullable=False, index=True)
    instructions_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MedicationLog(TimestampMixin, Base):
    __tablename__ = 'medication_logs'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey('medication_plans.id'), nullable=False, index=True)
    log_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Conversation(TimestampMixin, Base):
    __tablename__ = 'conversations'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    speaker: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class FamilyMessage(TimestampMixin, Base):
    __tablename__ = 'family_messages'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='pending', nullable=False, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CognitionSession(TimestampMixin, Base):
    __tablename__ = 'cognition_sessions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    theme: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default='generated', nullable=False, index=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class Alert(TimestampMixin, Base):
    __tablename__ = 'alerts'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str] = mapped_column(ForeignKey('elders.id'), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReviewQueue(TimestampMixin, Base):
    __tablename__ = 'review_queue'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    elder_id: Mapped[str | None] = mapped_column(ForeignKey('elders.id'), nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default='pending', nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(16), default='medium', nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


Index('ix_conversations_elder_created', Conversation.elder_id, Conversation.created_at)
Index('ix_medication_logs_plan_created', MedicationLog.plan_id, MedicationLog.created_at)
Index('ix_family_messages_elder_created', FamilyMessage.elder_id, FamilyMessage.created_at)
