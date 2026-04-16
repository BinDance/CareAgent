from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field


class MoodSignal(BaseModel):
    label: str = Field(description='Mood label such as calm, positive, low, anxious')
    confidence: float = Field(ge=0, le=1)
    summary: str


class RiskSignal(BaseModel):
    level: Literal['none', 'low', 'medium', 'high', 'critical'] = 'none'
    indicators: list[str] = Field(default_factory=list)
    rationale: str = ''
    requires_alert: bool = False


class IntentClassification(BaseModel):
    primary_intent: Literal[
        'chat',
        'family_relay',
        'medication_confirmation',
        'ask_notice',
        'schedule_update',
        'distress_signal',
        'cognition_response',
        'other'
    ] = 'chat'
    needs_tool_call: bool = False
    family_message: str | None = None
    medication_taken: bool | None = None
    mentioned_family_member: str | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)
    rationale: str = ''


class ProfileCandidateSet(BaseModel):
    stable_updates: dict[str, Any] = Field(default_factory=dict)
    daily_updates: dict[str, Any] = Field(default_factory=dict)
    risk_updates: dict[str, Any] = Field(default_factory=dict)
    review_items: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ''


class ElderResponsePlan(BaseModel):
    reply_text: str
    subtitle: str
    should_speak: bool = True
    deliver_notice_ids: list[str] = Field(default_factory=list)
    deliver_message_ids: list[str] = Field(default_factory=list)
    reminder_plan_ids: list[str] = Field(default_factory=list)
    cognition_prompt: str | None = None
    family_message_sent: bool = False
    tone: Literal['gentle', 'neutral', 'firm'] = 'gentle'


class FamilyInstructionResult(BaseModel):
    kind: Literal['notice', 'query', 'message', 'other'] = 'notice'
    summarized_notice: str
    urgency: Literal['low', 'medium', 'high', 'critical'] = 'medium'
    delivery_strategy: Literal['now', 'next_free_slot', 'before_meal', 'after_nap', 'evening', 'manual_review'] | None = 'next_free_slot'
    suitable_window: str | None = None
    rationale: str
    should_store_notice: bool = False
    relay_message: str | None = None
    query_answer: str | None = None


class PrescriptionMedicationItem(BaseModel):
    medication_name: str = Field(validation_alias=AliasChoices('medication_name', 'name'))
    dose: str = ''
    frequency: str = ''
    meal_timing: str = ''
    suggested_times: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    confidence: float = Field(default=0.8, ge=0, le=1)
    uncertain_fields: list[str] = Field(default_factory=list)


class PrescriptionExtraction(BaseModel):
    medications: list[PrescriptionMedicationItem] = Field(default_factory=list)
    overall_summary: str = ''
    uncertainty_notes: list[str] = Field(default_factory=list)
    needs_confirmation: bool = False
    raw_observations: list[str] = Field(default_factory=list)


class RelayMessageResult(BaseModel):
    direction: Literal['elder_to_family', 'family_to_elder']
    summary_text: str
    audience: str = 'family'
    urgency: Literal['low', 'medium', 'high', 'critical'] = 'low'
    rationale: str = ''


class CognitionDecision(BaseModel):
    should_engage: bool = False
    theme: str = ''
    prompt: str = ''
    observation_focus: str = ''
    rationale: str = ''
    anomaly_signal: str | None = None
