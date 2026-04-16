from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiMessage(BaseModel):
    detail: str


class ElderVoiceInputRequest(BaseModel):
    elder_id: str
    transcript: str = Field(min_length=1)
    now_ts: str | None = None


class ElderVoiceInputResponse(BaseModel):
    elder_id: str
    transcript: str
    reply_text: str
    subtitle: str
    should_speak: bool
    mood: str
    risk_level: str
    delivered_notice_ids: list[str] = Field(default_factory=list)
    reminder_plan_ids: list[str] = Field(default_factory=list)


class ElderSessionResponse(BaseModel):
    elder_id: str
    profile: dict[str, Any]
    daily_status: dict[str, Any]
    recent_conversations: list[dict[str, Any]]


class TodayRemindersResponse(BaseModel):
    elder_id: str
    notices: list[dict[str, Any]]
    medications: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    cognition: list[dict[str, Any]] = Field(default_factory=list)


class FamilyNoticeRequest(BaseModel):
    elder_id: str
    text: str = Field(min_length=1)


class ManualNoticeResponse(BaseModel):
    id: str
    elder_id: str
    raw_text: str
    summarized_notice: str
    urgency: Literal['low', 'medium', 'high', 'critical']
    delivery_strategy: Literal['now', 'next_free_slot', 'before_meal', 'after_nap', 'evening', 'manual_review']
    suitable_window: str | None = None
    rationale: str
    status: str
    planned_for: str | None = None
    delivered_at: str | None = None
    created_at: str


class ManualNoticeCreateRequest(BaseModel):
    elder_id: str
    summarized_notice: str = Field(min_length=1)
    urgency: Literal['low', 'medium', 'high', 'critical'] = 'medium'
    delivery_strategy: Literal['now', 'next_free_slot', 'before_meal', 'after_nap', 'evening', 'manual_review'] = 'next_free_slot'
    rationale: str = '家属手动编辑'


class ManualNoticeUpdateRequest(BaseModel):
    summarized_notice: str | None = Field(default=None, min_length=1)
    urgency: Literal['low', 'medium', 'high', 'critical'] | None = None
    delivery_strategy: Literal['now', 'next_free_slot', 'before_meal', 'after_nap', 'evening', 'manual_review'] | None = None
    rationale: str | None = None


class FamilyInstructionResponse(BaseModel):
    elder_id: str
    kind: Literal['notice', 'query', 'message', 'other']
    summary: str
    urgency: Literal['low', 'medium', 'high', 'critical']
    delivery_strategy: str | None = None
    suitable_window: str | None = None
    rationale: str
    stored_notice: dict[str, Any] | None = None
    relay_message: dict[str, Any] | None = None
    query: dict[str, Any] | None = None
    review: dict[str, Any] | None = None


class UploadPrescriptionResponse(BaseModel):
    prescription_id: str
    parse_status: str
    extraction: dict[str, Any]
    created_plans: list[dict[str, Any]]
    review_item: dict[str, Any] | None = None


class MedicationPlanResponse(BaseModel):
    id: str
    elder_id: str
    prescription_id: str | None = None
    medication_name: str
    dose: str
    frequency: str
    meal_timing: str
    time_slots: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    confidence: float
    needs_confirmation: bool
    status: str
    created_at: str


class MedicationPlansResponse(BaseModel):
    elder_id: str
    items: list[MedicationPlanResponse]


class MedicationPlanCreateRequest(BaseModel):
    elder_id: str
    medication_name: str = Field(min_length=1)
    dose: str = ''
    frequency: str = ''
    meal_timing: str = ''
    time_slots: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    needs_confirmation: bool = False


class MedicationPlanUpdateRequest(BaseModel):
    medication_name: str | None = Field(default=None, min_length=1)
    dose: str | None = None
    frequency: str | None = None
    meal_timing: str | None = None
    time_slots: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    needs_confirmation: bool | None = None
    status: Literal['active', 'review'] | None = None


class FamilyMessageCreateRequest(BaseModel):
    elder_id: str
    text: str = Field(min_length=1)


class DailyReportResponse(BaseModel):
    elder_id: str
    date: str
    report: dict[str, Any]


class ProfileItem(BaseModel):
    key: str
    label: str
    value: str


class EffectiveRoutineItem(ProfileItem):
    source: Literal['today', 'long_term']


class LongTermProfileSummary(BaseModel):
    routine: list[ProfileItem] = Field(default_factory=list)
    preferences: list[ProfileItem] = Field(default_factory=list)
    health: list[ProfileItem] = Field(default_factory=list)
    risk: list[ProfileItem] = Field(default_factory=list)


class TodayProfileSummary(BaseModel):
    fallback_note: str = ''
    effective_routine: list[EffectiveRoutineItem] = Field(default_factory=list)
    observed_updates: list[ProfileItem] = Field(default_factory=list)
    status: list[ProfileItem] = Field(default_factory=list)


class ProfileSummaryResponse(BaseModel):
    long_term_profile: LongTermProfileSummary
    today_profile: TodayProfileSummary


class DashboardResponse(BaseModel):
    elder_id: str
    elder_name: str
    cards: list[dict[str, Any]]
    today_mood_summary: dict[str, Any]
    medication_summary: dict[str, Any]
    notices: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    cognition_summary: dict[str, Any]
    risk_alerts: list[dict[str, Any]]
    profile_summary: ProfileSummaryResponse | None = None
    daily_report: dict[str, Any]


class FamilyMessagesResponse(BaseModel):
    elder_id: str
    items: list[dict[str, Any]]


class SchedulerRunResponse(BaseModel):
    ok: bool = True
    processed: int
    details: list[dict[str, Any]] = Field(default_factory=list)


class DemoResetResponse(BaseModel):
    ok: bool = True
    detail: str
    elder_id: str
    cleared_uploads: int = 0


class UserContext(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    role: str
    elder_id: str | None = None
    family_member_id: str | None = None
    email: str | None = None
    display_name: str | None = None
