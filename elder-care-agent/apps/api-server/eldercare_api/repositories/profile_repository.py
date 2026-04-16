from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from eldercare_api.models import DailyStatus, Elder, ElderProfile


class ProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def _default_stable_profile(self) -> dict[str, object]:
        return {
            'usual_wake_time': '07:00',
            'usual_sleep_time': '21:30',
            'usual_breakfast_time': '07:30',
            'usual_lunch_time': '12:00',
            'usual_dinner_time': '18:00',
            'chronic_conditions': [],
            'allergies': [],
            'meal_habits': ['清淡', '按时吃饭'],
            'liked_topics': ['家人', '往事', '日常生活'],
            'disliked_topics': ['考试式提问'],
            'frequently_mentioned_people': [],
            'reminder_preference': 'gentle',
        }

    def _default_risk_profile(self) -> dict[str, str]:
        return {
            'forgetfulness_trend': 'unknown',
            'low_mood_trend': 'unknown',
            'medication_refusal_trend': 'unknown',
            'routine_disruption_trend': 'unknown',
            'high_risk_expression': 'none',
        }

    def _default_daily_status(self) -> dict[str, object]:
        return {
            'mood': 'unknown',
            'plan': [],
            'went_out': False,
            'medication_taken': False,
            'contacted_people': [],
            'is_resting': False,
        }

    def get_elder(self, elder_id: str) -> Elder | None:
        return self.db.scalar(select(Elder).where(Elder.id == elder_id))

    def get_or_create_profile(self, elder_id: str) -> ElderProfile:
        profile = self.db.scalar(select(ElderProfile).where(ElderProfile.elder_id == elder_id))
        if profile is None:
            profile = ElderProfile(
                elder_id=elder_id,
                stable_profile_json=self._default_stable_profile(),
                risk_profile_json=self._default_risk_profile(),
            )
            self.db.add(profile)
            self.db.flush()
            return profile

        stable = profile.stable_profile_json or {}
        merged_stable = {**self._default_stable_profile(), **stable}
        risk = profile.risk_profile_json or {}
        merged_risk = {**self._default_risk_profile(), **risk}
        if merged_stable != stable:
            profile.stable_profile_json = merged_stable
        if merged_risk != risk:
            profile.risk_profile_json = merged_risk
        if merged_stable != stable or merged_risk != risk:
            self.db.flush()
        return profile

    def get_or_create_daily_status(self, elder_id: str, status_date: date) -> DailyStatus:
        status = self.db.scalar(select(DailyStatus).where(DailyStatus.elder_id == elder_id, DailyStatus.status_date == status_date))
        if status is None:
            status = DailyStatus(
                elder_id=elder_id,
                status_date=status_date,
                status_json=self._default_daily_status(),
                family_report_json={},
            )
            try:
                with self.db.begin_nested():
                    self.db.add(status)
                    self.db.flush()
            except IntegrityError:
                status = self.db.scalar(select(DailyStatus).where(DailyStatus.elder_id == elder_id, DailyStatus.status_date == status_date))
                if status is None:
                    raise
                current = status.status_json or {}
                merged = {**self._default_daily_status(), **current}
                if merged != current:
                    status.status_json = merged
                    self.db.flush()
            return status

        current = status.status_json or {}
        merged = {**self._default_daily_status(), **current}
        if merged != current:
            status.status_json = merged
            self.db.flush()
        return status
