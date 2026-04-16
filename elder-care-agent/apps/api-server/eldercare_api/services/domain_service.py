from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.parser import isoparse
from sqlalchemy import select
from sqlalchemy.orm import Session

from eldercare_api.models import Elder, FamilyMember, FamilyNotice, MedicationPlan, Prescription, User
from eldercare_api.repositories.alert_repository import AlertRepository
from eldercare_api.repositories.cognition_repository import CognitionRepository
from eldercare_api.repositories.conversation_repository import ConversationRepository
from eldercare_api.repositories.medication_repository import MedicationRepository
from eldercare_api.repositories.message_repository import MessageRepository
from eldercare_api.repositories.notice_repository import NoticeRepository
from eldercare_api.repositories.prescription_repository import PrescriptionRepository
from eldercare_api.repositories.profile_repository import ProfileRepository
from eldercare_api.utils.serializers import ensure_json, iso


class DomainService:
    def __init__(self, db: Session):
        self.db = db
        self.profiles = ProfileRepository(db)
        self.notices = NoticeRepository(db)
        self.medications = MedicationRepository(db)
        self.messages = MessageRepository(db)
        self.conversations = ConversationRepository(db)
        self.cognition = CognitionRepository(db)
        self.alerts = AlertRepository(db)
        self.prescriptions = PrescriptionRepository(db)

    def list_elder_ids(self) -> list[str]:
        return [elder_id for elder_id in self.db.scalars(select(Elder.id)).all()]

    def get_elder_profile(self, elder_id: str) -> dict[str, Any]:
        elder = self.profiles.get_elder(elder_id)
        profile = self.profiles.get_or_create_profile(elder_id)
        return {
            'elder_id': elder_id,
            'name': elder.name if elder else '',
            'timezone': elder.timezone if elder else 'Asia/Shanghai',
            'stable_profile': ensure_json(profile.stable_profile_json),
            'risk_profile': ensure_json(profile.risk_profile_json),
            'profile_notes': profile.profile_notes or '',
        }

    def get_profile_summary(self, elder_id: str) -> dict[str, Any]:
        profile = self.profiles.get_or_create_profile(elder_id)
        today = self.profiles.get_or_create_daily_status(elder_id, date.today())
        stable_profile = ensure_json(profile.stable_profile_json)
        risk_profile = ensure_json(profile.risk_profile_json)
        daily_status = ensure_json(today.status_json)
        return self._build_profile_summary(stable_profile, risk_profile, daily_status)

    def propose_profile_update(self, elder_id: str, candidate_json: dict[str, Any]) -> dict[str, Any]:
        profile = self.profiles.get_or_create_profile(elder_id)
        stable = {**(profile.stable_profile_json or {}), **candidate_json.get('stable_updates', {})}
        risk = {**(profile.risk_profile_json or {}), **candidate_json.get('risk_updates', {})}
        profile.stable_profile_json = stable
        profile.risk_profile_json = risk
        today = self.profiles.get_or_create_daily_status(elder_id, date.today())
        today.status_json = {**(today.status_json or {}), **candidate_json.get('daily_updates', {})}
        review_items = []
        for item in candidate_json.get('review_items', []):
            review = self.alerts.create_review(elder_id=elder_id, task_type='profile_candidate_review', payload=item, reason=item.get('reason', 'profile_review'), priority='medium')
            review_items.append({'id': review.id, 'task_type': review.task_type, 'status': review.status})
        self.db.commit()
        return {'stable_profile': ensure_json(stable), 'risk_profile': ensure_json(risk), 'review_items': review_items}

    def get_today_status(self, elder_id: str) -> dict[str, Any]:
        status = self.profiles.get_or_create_daily_status(elder_id, date.today())
        self.db.commit()
        return {'elder_id': elder_id, 'date': status.status_date.isoformat(), **ensure_json(status.status_json), 'family_report': ensure_json(status.family_report_json)}

    def update_today_status(self, elder_id: str, patch_json: dict[str, Any]) -> dict[str, Any]:
        status = self.profiles.get_or_create_daily_status(elder_id, date.today())
        current = status.status_json or {}
        status.status_json = {**current, **patch_json}
        self.db.commit()
        return {'elder_id': elder_id, 'date': status.status_date.isoformat(), **ensure_json(status.status_json)}

    def get_recent_conversations(self, elder_id: str, limit: int) -> list[dict[str, Any]]:
        return [
            {
                'id': item.id,
                'speaker': item.speaker,
                'content': item.content,
                'summary_json': ensure_json(item.summary_json),
                'created_at': iso(item.created_at),
            }
            for item in self.conversations.recent_for_elder(elder_id, limit=limit)
        ][::-1]

    def save_conversation(self, elder_id: str, speaker: str, content: str, summary_json: dict[str, Any]) -> dict[str, Any]:
        conversation = self.conversations.create(elder_id=elder_id, speaker=speaker, content=content, summary_json=summary_json)
        self.db.commit()
        return {'id': conversation.id, 'speaker': speaker, 'created_at': iso(conversation.created_at)}

    def create_family_notice(self, elder_id: str, raw_text: str, urgency: str, strategy: str, summarized_notice: str, rationale: str, family_member_id: str | None = None) -> dict[str, Any]:
        planned_for = datetime.now(timezone.utc)
        notice = self.notices.create(
            elder_id=elder_id,
            family_member_id=family_member_id,
            raw_text=raw_text,
            urgency=urgency,
            delivery_strategy=strategy,
            summarized_notice=summarized_notice,
            suitable_window=self._suitable_window(strategy),
            rationale=rationale,
            planned_for=planned_for,
            status='pending' if strategy != 'now' else 'ready',
        )
        self.db.commit()
        return self._serialize_notice(notice)

    def list_pending_notices(self, elder_id: str) -> list[dict[str, Any]]:
        return [self._serialize_notice(item) for item in self.notices.list_pending(elder_id)]

    def mark_notice_delivered(self, notice_id: str, delivered_at: str) -> dict[str, Any] | None:
        notice = self.notices.mark_delivered(notice_id, isoparse(delivered_at))
        self.db.commit()
        return self._serialize_notice(notice) if notice else None

    def reschedule_notice(self, notice_id: str, new_slot: str) -> dict[str, Any] | None:
        notice = self.notices.reschedule(notice_id, isoparse(new_slot))
        self.db.commit()
        return self._serialize_notice(notice) if notice else None

    def update_family_notice(self, notice_id: str, patch_json: dict[str, Any]) -> dict[str, Any] | None:
        notice = self.notices.get(notice_id)
        if notice is None:
            return None
        if 'summarized_notice' in patch_json:
            summary = str(patch_json.get('summarized_notice') or '').strip()
            if summary:
                notice.summarized_notice = summary
                notice.raw_text = summary
        if 'urgency' in patch_json and patch_json.get('urgency'):
            notice.urgency = str(patch_json['urgency'])
        if 'delivery_strategy' in patch_json and patch_json.get('delivery_strategy'):
            notice.delivery_strategy = str(patch_json['delivery_strategy'])
            notice.suitable_window = self._suitable_window(notice.delivery_strategy)
            notice.status = 'pending' if notice.delivery_strategy != 'now' else 'ready'
            notice.planned_for = datetime.now(timezone.utc)
        if 'rationale' in patch_json and patch_json.get('rationale') is not None:
            notice.rationale = str(patch_json.get('rationale') or '').strip()
        self.db.commit()
        return self._serialize_notice(notice)

    def delete_family_notice(self, notice_id: str) -> dict[str, Any] | None:
        notice = self.notices.get(notice_id)
        if notice is None:
            return None
        notice.status = 'deleted'
        self.db.commit()
        return self._serialize_notice(notice)

    def create_prescription_record(self, elder_id: str, file_name: str, file_path: str, mime_type: str, uploaded_by_user_id: str | None) -> dict[str, Any]:
        prescription = self.prescriptions.create(elder_id=elder_id, file_name=file_name, file_path=file_path, mime_type=mime_type, uploaded_by_user_id=uploaded_by_user_id)
        self.db.commit()
        return self._serialize_prescription(prescription)

    def finalize_prescription_record(self, prescription_id: str, extraction: dict[str, Any], needs_confirmation: bool) -> dict[str, Any] | None:
        prescription = self.prescriptions.get(prescription_id)
        if prescription is None:
            return None
        prescription.extracted_json = extraction
        prescription.needs_confirmation = needs_confirmation
        prescription.uncertainty_notes = extraction.get('uncertainty_notes', [])
        prescription.parse_status = 'needs_confirmation' if needs_confirmation else 'parsed'
        self.db.commit()
        return self._serialize_prescription(prescription)

    def create_medication_plan(self, elder_id: str, medication_json: dict[str, Any], prescription_id: str | None = None) -> dict[str, Any]:
        payload = self._normalized_plan_values(medication_json)
        self._apply_profile_based_time_slots(elder_id, payload, medication_json)
        plan = self.medications.create_plan(
            elder_id=elder_id,
            prescription_id=prescription_id,
            medication_name=payload['medication_name'],
            dose=payload['dose'],
            frequency=payload['frequency'],
            meal_timing=payload['meal_timing'],
            time_slots=payload['time_slots'],
            start_date=payload['start_date'],
            end_date=payload['end_date'],
            confidence=payload['confidence'],
            needs_confirmation=payload['needs_confirmation'],
            status=payload['status'],
            instructions_json=self._plan_instruction_snapshot(payload),
        )
        self.db.commit()
        return self._serialize_plan(plan)

    def list_medication_plans(self, elder_id: str) -> list[dict[str, Any]]:
        self._backfill_missing_time_slots(elder_id)
        return [self._serialize_plan(item) for item in self.medications.list_for_elder(elder_id, statuses=['active', 'review'])]

    def update_medication_plan(self, plan_id: str, patch_json: dict[str, Any]) -> dict[str, Any] | None:
        plan = self.medications.get(plan_id)
        if plan is None:
            return None
        payload = self._normalized_plan_values(patch_json, partial=True)
        self._apply_profile_based_time_slots(plan.elder_id, payload, patch_json, existing_plan=plan)
        if not payload:
            return self._serialize_plan(plan)

        for field in ('medication_name', 'dose', 'frequency', 'meal_timing', 'time_slots', 'start_date', 'end_date', 'confidence', 'needs_confirmation', 'status'):
            if field in payload:
                setattr(plan, field, payload[field])

        plan.instructions_json = self._plan_instruction_snapshot(
            {
                **ensure_json(plan.instructions_json),
                'medication_name': plan.medication_name,
                'dose': plan.dose,
                'frequency': plan.frequency,
                'meal_timing': plan.meal_timing,
                'time_slots': ensure_json(plan.time_slots),
                'start_date': plan.start_date.isoformat() if plan.start_date else None,
                'end_date': plan.end_date.isoformat() if plan.end_date else None,
                'confidence': plan.confidence,
                'needs_confirmation': plan.needs_confirmation,
                'status': plan.status,
            }
        )
        self.db.commit()
        return self._serialize_plan(plan)

    def delete_medication_plan(self, plan_id: str) -> dict[str, Any] | None:
        plan = self.medications.get(plan_id)
        if plan is None:
            return None
        plan.status = 'deleted'
        plan.instructions_json = {**ensure_json(plan.instructions_json), 'status': 'deleted'}
        self.db.commit()
        return self._serialize_plan(plan)

    def get_due_medications(
        self,
        elder_id: str,
        now_ts: str,
        since_ts: str | None = None,
        tolerance_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        self._backfill_missing_time_slots(elder_id)
        effective_now = self._align_to_elder_timezone(elder_id, now_ts)
        effective_since = self._align_to_elder_timezone(elder_id, since_ts) if since_ts else None
        return [
            self._serialize_plan(plan)
            for plan in self.medications.due_for_elder(
                elder_id,
                effective_now.isoformat(),
                since_ts=effective_since.isoformat() if effective_since else None,
                tolerance_minutes=tolerance_minutes,
            )
        ]

    def log_medication_reminder(self, plan_id: str, scheduled_at: str) -> dict[str, Any]:
        plan = self.medications.get(plan_id)
        if plan is None:
            return {'ok': False}
        if self.medications.recent_log_exists(plan_id, 'reminder', minutes=90):
            return {'ok': True, 'plan_id': plan_id, 'deduplicated': True}
        log = self.medications.log(elder_id=plan.elder_id, plan_id=plan_id, log_type='reminder', scheduled_at=isoparse(scheduled_at), source='agent_scheduler')
        self.db.commit()
        return {'id': log.id, 'plan_id': plan_id, 'log_type': 'reminder', 'scheduled_at': iso(log.scheduled_at)}

    def confirm_medication_taken(self, plan_id: str, taken_at: str, source: str) -> dict[str, Any]:
        plan = self.medications.get(plan_id)
        if plan is None:
            return {'ok': False}
        log = self.medications.log(elder_id=plan.elder_id, plan_id=plan_id, log_type='taken', taken_at=isoparse(taken_at), source=source)
        status = self.profiles.get_or_create_daily_status(plan.elder_id, date.today())
        status.status_json = {**(status.status_json or {}), 'medication_taken': True}
        self.db.commit()
        return {'id': log.id, 'plan_id': plan_id, 'taken_at': iso(log.taken_at), 'source': source}

    def send_message_to_family(self, elder_id: str, summary_text: str) -> dict[str, Any]:
        message = self.messages.create(elder_id=elder_id, direction='elder_to_family', raw_text=summary_text, summary_text=summary_text, status='pending')
        self.db.commit()
        return self._serialize_message(message)

    def list_family_messages(self, elder_id: str) -> list[dict[str, Any]]:
        return [self._serialize_message(item) for item in self.messages.list_for_elder(elder_id)]

    def send_message_to_elder(self, elder_id: str, text: str) -> dict[str, Any]:
        message = self.messages.create(elder_id=elder_id, direction='family_to_elder', raw_text=text, summary_text=text, status='pending')
        self.db.commit()
        return self._serialize_message(message)

    def mark_family_message_delivered(self, message_id: str, delivered_at: str) -> dict[str, Any] | None:
        message = self.messages.mark_delivered(message_id, isoparse(delivered_at))
        self.db.commit()
        return self._serialize_message(message) if message else None

    def get_cognition_history(self, elder_id: str) -> list[dict[str, Any]]:
        return [self._serialize_cognition(item) for item in self.cognition.history(elder_id)]

    def save_cognition_session(self, elder_id: str, result_json: dict[str, Any]) -> dict[str, Any]:
        session = self.cognition.create(
            elder_id=elder_id,
            theme=result_json.get('theme'),
            status='generated' if result_json.get('should_engage') else 'skipped',
            prompt=result_json.get('prompt'),
            result_json=result_json,
            anomaly_score=0.7 if result_json.get('anomaly_signal') else 0.1,
        )
        self.db.commit()
        return self._serialize_cognition(session)

    def generate_daily_report(self, elder_id: str, report_date: str) -> dict[str, Any]:
        current = self.get_today_status(elder_id)
        conversations = self.get_recent_conversations(elder_id, limit=12)
        medication_logs = [
            {'plan_id': item.plan_id, 'log_type': item.log_type, 'created_at': iso(item.created_at), 'taken_at': iso(item.taken_at)}
            for item in self.medications.today_logs_for_elder(elder_id)
        ]
        notices = self.list_pending_notices(elder_id)
        messages = self.list_family_messages(elder_id)[:6]
        cognition = self.get_cognition_history(elder_id)[:5]
        alerts = [self._serialize_alert(item) for item in self.alerts.unresolved_for_elder(elder_id)]
        report = {
            'date': report_date,
            'mood_summary': current.get('mood_summary') or current.get('mood', 'unknown'),
            'medication_summary': {
                'taken': any(item['log_type'] == 'taken' for item in medication_logs) or current.get('medication_taken', False),
                'reminders_sent': len([item for item in medication_logs if item['log_type'] == 'reminder']),
            },
            'notices': notices,
            'messages': messages,
            'cognition_summary': cognition,
            'risk_alerts': alerts,
            'important_interactions': conversations[-4:],
            'disclaimer': '本系统不是医疗诊断工具；药物计划如存在不确定项，需要家属确认。',
        }
        return ensure_json(report)

    def publish_report_to_family(self, elder_id: str, report_json: dict[str, Any]) -> dict[str, Any]:
        status = self.profiles.get_or_create_daily_status(elder_id, date.today())
        status.family_report_json = report_json
        self.db.commit()
        return {'elder_id': elder_id, 'report': report_json}

    def raise_alert(self, elder_id: str, reason: str, level: str) -> dict[str, Any]:
        alert = self.alerts.create_alert(elder_id=elder_id, reason=reason, level=level, payload={'reason': reason, 'level': level})
        self.db.commit()
        return self._serialize_alert(alert)

    def request_human_review(self, task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.alerts.create_review(elder_id=payload.get('elder_id'), task_type=task_type, payload=payload, reason=task_type, priority='high' if 'critical' in task_type else 'medium')
        self.db.commit()
        return {'id': item.id, 'task_type': item.task_type, 'status': item.status, 'priority': item.priority}

    def get_dashboard(self, elder_id: str) -> dict[str, Any]:
        elder = self.profiles.get_elder(elder_id)
        status = self.get_today_status(elder_id)
        profile_summary = self.get_profile_summary(elder_id)
        report = status.get('family_report') or self.generate_daily_report(elder_id, date.today().isoformat())
        notices = self.list_pending_notices(elder_id)
        messages = self.list_family_messages(elder_id)[:8]
        cognition = self.get_cognition_history(elder_id)[:5]
        alerts = [self._serialize_alert(item) for item in self.alerts.unresolved_for_elder(elder_id)]
        medication_logs = self.medications.today_logs_for_elder(elder_id)
        medication_plans = self.list_medication_plans(elder_id)
        cards = [
            {'title': '今日心情', 'value': status.get('mood', 'unknown'), 'tone': 'warning' if status.get('mood') in {'low', 'anxious'} else 'good'},
            {'title': '服药状态', 'value': '已确认' if status.get('medication_taken') else '待确认', 'tone': 'good' if status.get('medication_taken') else 'warning'},
            {'title': '待传达事项', 'value': str(len(notices)), 'tone': 'neutral'},
            {'title': '风险提示', 'value': str(len(alerts)), 'tone': 'danger' if alerts else 'good'},
        ]
        return {
            'elder_id': elder_id,
            'elder_name': elder.name if elder else '老人',
            'cards': cards,
            'today_mood_summary': {'mood': status.get('mood', 'unknown'), 'summary': status.get('mood_summary', '')},
            'medication_summary': {
                'plans': medication_plans,
                'logs': [
                    {'id': log.id, 'plan_id': log.plan_id, 'log_type': log.log_type, 'created_at': iso(log.created_at), 'taken_at': iso(log.taken_at)}
                    for log in medication_logs
                ],
            },
            'notices': notices,
            'messages': messages,
            'cognition_summary': {'items': cognition},
            'risk_alerts': alerts,
            'profile_summary': profile_summary,
            'daily_report': report,
        }

    def get_elder_session(self, elder_id: str) -> dict[str, Any]:
        return {
            'elder_id': elder_id,
            'profile': self.get_elder_profile(elder_id),
            'daily_status': self.get_today_status(elder_id),
            'recent_conversations': self.get_recent_conversations(elder_id, limit=10),
        }

    def get_today_reminders(
        self,
        elder_id: str,
        now_ts: str | None = None,
        since_ts: str | None = None,
    ) -> dict[str, Any]:
        now_dt = isoparse(now_ts) if now_ts else datetime.now(timezone.utc)
        since_dt = isoparse(since_ts) if since_ts else None
        if since_dt and since_dt > now_dt:
            since_dt = None

        notices = [
            item
            for item in self.list_pending_notices(elder_id)
            if self._is_notice_due(item, now_dt, since_dt)
        ]
        medications = self.get_due_medications(
            elder_id,
            now_dt.isoformat(),
            since_ts=since_dt.isoformat() if since_dt else None,
            tolerance_minutes=2 if not since_dt else 0,
        )
        messages = [
            item
            for item in self.list_family_messages(elder_id)
            if item['direction'] == 'family_to_elder'
            and item['status'] == 'pending'
            and self._is_message_due(item, now_dt, since_dt)
        ]
        return {'elder_id': elder_id, 'notices': notices, 'medications': medications, 'messages': messages}

    def _is_notice_due(
        self,
        notice: dict[str, Any],
        now_dt: datetime,
        since_dt: datetime | None,
    ) -> bool:
        if notice.get('status') not in {'pending', 'ready'}:
            return False
        planned_at = self._coerce_iso_datetime(notice.get('planned_for')) or self._coerce_iso_datetime(notice.get('created_at'))
        if planned_at is None:
            return False
        if since_dt is not None and since_dt <= now_dt:
            return since_dt < planned_at <= now_dt
        return planned_at <= now_dt

    def _is_message_due(
        self,
        message: dict[str, Any],
        now_dt: datetime,
        since_dt: datetime | None,
    ) -> bool:
        created_at = self._coerce_iso_datetime(message.get('created_at'))
        if created_at is None:
            return False
        if since_dt is not None and since_dt <= now_dt:
            return since_dt < created_at <= now_dt
        return created_at <= now_dt

    def _coerce_iso_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return isoparse(value)
        except (TypeError, ValueError):
            return None

    def _align_to_elder_timezone(self, elder_id: str, value: str) -> datetime:
        parsed = isoparse(value)
        elder = self.profiles.get_elder(elder_id)
        timezone_name = elder.timezone if elder and elder.timezone else None
        if not timezone_name:
            return parsed
        try:
            return parsed.astimezone(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            return parsed

    def _suitable_window(self, strategy: str) -> str:
        mapping = {
            'now': '立即',
            'before_meal': '饭前 30 分钟',
            'after_nap': '午休后 30 分钟',
            'evening': '18:00-20:00',
            'manual_review': '人工复核',
        }
        return mapping.get(strategy, '老人空闲时')

    def _serialize_notice(self, notice: FamilyNotice | None) -> dict[str, Any] | None:
        if notice is None:
            return None
        return {
            'id': notice.id,
            'elder_id': notice.elder_id,
            'raw_text': notice.raw_text,
            'summarized_notice': notice.summarized_notice,
            'urgency': notice.urgency,
            'delivery_strategy': notice.delivery_strategy,
            'suitable_window': notice.suitable_window,
            'rationale': notice.rationale,
            'status': notice.status,
            'planned_for': iso(notice.planned_for),
            'delivered_at': iso(notice.delivered_at),
            'created_at': iso(notice.created_at),
        }

    def _serialize_plan(self, plan: MedicationPlan | None) -> dict[str, Any] | None:
        if plan is None:
            return None
        return {
            'id': plan.id,
            'elder_id': plan.elder_id,
            'prescription_id': plan.prescription_id,
            'medication_name': plan.medication_name,
            'dose': plan.dose,
            'frequency': plan.frequency,
            'meal_timing': plan.meal_timing,
            'time_slots': ensure_json(plan.time_slots),
            'start_date': plan.start_date.isoformat() if plan.start_date else None,
            'end_date': plan.end_date.isoformat() if plan.end_date else None,
            'confidence': plan.confidence,
            'needs_confirmation': plan.needs_confirmation,
            'status': plan.status,
            'created_at': iso(plan.created_at),
        }

    def _normalized_plan_values(self, medication_json: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        string_fields = ('medication_name', 'dose', 'frequency', 'meal_timing')
        for field in string_fields:
            if field in medication_json:
                value = medication_json.get(field)
                if value is None and partial:
                    continue
                payload[field] = str(value or '').strip()

        if not partial:
            payload.setdefault('medication_name', '待确认药物')
            payload.setdefault('dose', '')
            payload.setdefault('frequency', '')
            payload.setdefault('meal_timing', '')

        if 'time_slots' in medication_json or 'suggested_times' in medication_json:
            payload['time_slots'] = self._normalize_time_slots(medication_json.get('time_slots', medication_json.get('suggested_times')))
        elif not partial:
            payload['time_slots'] = []

        for field in ('start_date', 'end_date'):
            if field in medication_json:
                payload[field] = self._parse_optional_date(medication_json.get(field))
            elif not partial:
                payload[field] = None

        if 'confidence' in medication_json:
            try:
                payload['confidence'] = float(medication_json.get('confidence') or 0.0)
            except (TypeError, ValueError):
                payload['confidence'] = 0.0
        elif not partial:
            payload['confidence'] = 0.8

        if 'needs_confirmation' in medication_json:
            needs_confirmation = bool(medication_json.get('needs_confirmation'))
            payload['needs_confirmation'] = needs_confirmation
            payload['status'] = 'review' if needs_confirmation else str(medication_json.get('status') or 'active')
        elif 'status' in medication_json:
            status = str(medication_json.get('status') or 'active')
            payload['status'] = status
            payload['needs_confirmation'] = status == 'review'
        elif not partial:
            needs_confirmation = bool(medication_json.get('needs_confirmation'))
            payload['needs_confirmation'] = needs_confirmation
            payload['status'] = 'review' if needs_confirmation else 'active'

        return payload

    def _apply_profile_based_time_slots(
        self,
        elder_id: str,
        payload: dict[str, Any],
        medication_json: dict[str, Any],
        existing_plan: MedicationPlan | None = None,
    ) -> None:
        current_slots = self._normalize_time_slots(payload.get('time_slots'))
        if current_slots:
            payload['time_slots'] = current_slots
            return

        source_has_time_slots = any(key in medication_json for key in ('time_slots', 'suggested_times'))
        existing_slots = self._normalize_time_slots(existing_plan.time_slots if existing_plan else [])
        if existing_slots and not source_has_time_slots:
            return

        frequency = str(payload.get('frequency') if 'frequency' in payload else (existing_plan.frequency if existing_plan else '') or '')
        meal_timing = str(payload.get('meal_timing') if 'meal_timing' in payload else (existing_plan.meal_timing if existing_plan else '') or '')
        derived_slots = self._derive_time_slots_from_profile(elder_id, frequency, meal_timing)
        if derived_slots:
            payload['time_slots'] = derived_slots

    def _backfill_missing_time_slots(self, elder_id: str) -> None:
        plans = self.medications.list_for_elder(elder_id, statuses=['active', 'review'])
        changed = False
        for plan in plans:
            if self._normalize_time_slots(plan.time_slots):
                continue
            derived_slots = self._derive_time_slots_from_profile(elder_id, plan.frequency, plan.meal_timing)
            if not derived_slots:
                continue
            plan.time_slots = derived_slots
            plan.instructions_json = self._plan_instruction_snapshot(
                {
                    **ensure_json(plan.instructions_json),
                    'medication_name': plan.medication_name,
                    'dose': plan.dose,
                    'frequency': plan.frequency,
                    'meal_timing': plan.meal_timing,
                    'time_slots': derived_slots,
                    'start_date': plan.start_date.isoformat() if plan.start_date else None,
                    'end_date': plan.end_date.isoformat() if plan.end_date else None,
                    'confidence': plan.confidence,
                    'needs_confirmation': plan.needs_confirmation,
                    'status': plan.status,
                }
            )
            changed = True
        if changed:
            self.db.commit()

    def _derive_time_slots_from_profile(self, elder_id: str, frequency: str, meal_timing: str) -> list[str]:
        schedule_text = f'{frequency} {meal_timing}'.strip()
        if not schedule_text:
            return []

        context = self._profile_schedule_context(elder_id)
        relation = self._meal_relation(schedule_text)
        count = self._frequency_count(frequency)

        if '睡前' in schedule_text:
            return [self._format_clock(self._clamp_clock(context['sleep'] - 30, context))]
        if '晨起' in schedule_text or '起床后' in schedule_text:
            return [self._format_clock(self._clamp_clock(context['wake'] + 20, context))]

        if self._contains_any(schedule_text, ['早中晚']):
            return self._anchors_to_slots(['breakfast', 'lunch', 'dinner'], relation, context)
        if self._contains_any(schedule_text, ['早晚各', '早晚']) or count == 2:
            return self._anchors_to_slots(['breakfast', 'dinner'], relation, context)
        if count == 3:
            return self._anchors_to_slots(['breakfast', 'lunch', 'dinner'], relation, context)

        if self._contains_any(schedule_text, ['早餐', '早饭']):
            return self._anchors_to_slots(['breakfast'], relation, context)
        if self._contains_any(schedule_text, ['午餐', '午饭', '中午']):
            return self._anchors_to_slots(['lunch'], relation, context)
        if self._contains_any(schedule_text, ['晚餐', '晚饭']):
            return self._anchors_to_slots(['dinner'], relation, context)
        if self._contains_any(schedule_text, ['每早', '早上', '清晨', '上午']):
            return [self._format_clock(self._clamp_clock(context['breakfast'] + 20, context))]
        if self._contains_any(schedule_text, ['每晚', '晚一次', '晚上', '夜间']):
            return [self._format_clock(self._clamp_clock(context['sleep'] - 30, context))]

        if count == 1 and relation:
            return self._anchors_to_slots(['lunch'], relation, context)
        if count == 1:
            return [self._format_clock(self._clamp_clock(context['breakfast'] + 20, context))]

        return []

    def _profile_schedule_context(self, elder_id: str) -> dict[str, int]:
        profile = self.profiles.get_or_create_profile(elder_id)
        today = self.profiles.get_or_create_daily_status(elder_id, date.today())
        stable_profile = ensure_json(profile.stable_profile_json)
        daily_status = ensure_json(today.status_json)

        wake = self._resolve_effective_clock(daily_status, ['woke_up_at', 'today_wake_time'], stable_profile, ['usual_wake_time', 'wake_time'], 7 * 60)
        sleep = self._resolve_effective_clock(daily_status, ['sleep_at', 'today_sleep_time', 'planned_sleep_at'], stable_profile, ['usual_sleep_time', 'sleep_time'], 21 * 60 + 30)
        if sleep <= wake:
            sleep = 21 * 60 + 30

        breakfast = self._resolve_effective_clock(daily_status, ['breakfast_at', 'today_breakfast_time'], stable_profile, ['usual_breakfast_time', 'breakfast_time'], wake + 30)
        lunch = self._resolve_effective_clock(daily_status, ['lunch_at', 'today_lunch_time'], stable_profile, ['usual_lunch_time', 'lunch_time'], 12 * 60)
        dinner = self._resolve_effective_clock(daily_status, ['dinner_at', 'today_dinner_time'], stable_profile, ['usual_dinner_time', 'dinner_time'], 18 * 60)
        return {
            'wake': wake,
            'sleep': sleep,
            'breakfast': self._clamp_clock(breakfast, {'wake': wake, 'sleep': sleep}),
            'lunch': self._clamp_clock(lunch, {'wake': wake, 'sleep': sleep}),
            'dinner': self._clamp_clock(dinner, {'wake': wake, 'sleep': sleep}),
        }

    def _resolve_effective_clock(
        self,
        daily_status: dict[str, Any],
        daily_keys: list[str],
        stable_profile: dict[str, Any],
        stable_keys: list[str],
        default_minutes: int,
    ) -> int:
        for key in daily_keys:
            minutes = self._parse_clock(daily_status.get(key))
            if minutes is not None:
                return minutes
        return self._resolve_profile_clock(stable_profile, stable_keys, default_minutes)

    def _resolve_profile_clock(self, stable_profile: dict[str, Any], keys: list[str], default_minutes: int) -> int:
        for key in keys:
            minutes = self._parse_clock(stable_profile.get(key))
            if minutes is not None:
                return minutes
        return default_minutes

    def _parse_clock(self, value: Any) -> int | None:
        text = str(value or '').strip()
        if not text:
            return None
        match = re.search(r'(?P<hour>\d{1,2})[:：](?P<minute>\d{1,2})', text)
        if match:
            hour = int(match.group('hour'))
            minute = int(match.group('minute'))
        else:
            chinese_match = re.search(r'(?P<hour>\d{1,2})\s*点(?:(?P<half>半)|(?P<minute>\d{1,2})\s*分?)?', text)
            if chinese_match:
                hour = int(chinese_match.group('hour'))
                minute = 30 if chinese_match.group('half') else int(chinese_match.group('minute') or 0)
            else:
                chinese_number_match = re.search(r'(?P<hour>[零〇一二两三四五六七八九十百]{1,4})\s*点(?:(?P<half>半)|(?P<minute>[零〇一二两三四五六七八九十百]{1,4})\s*分?)?', text)
                if not chinese_number_match:
                    return None
                hour = self._parse_chinese_number(chinese_number_match.group('hour'))
                minute = 30 if chinese_number_match.group('half') else self._parse_chinese_number(chinese_number_match.group('minute') or '零')
                if hour is None or minute is None:
                    return None
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return None
        return hour * 60 + minute

    def _parse_chinese_number(self, value: str) -> int | None:
        text = value.strip()
        if not text:
            return None
        digits = {'零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
        if text in digits:
            return digits[text]
        if text == '十':
            return 10
        if '十' in text:
            left, _, right = text.partition('十')
            tens = 1 if left == '' else digits.get(left)
            ones = 0 if right == '' else digits.get(right)
            if tens is None or ones is None:
                return None
            return tens * 10 + ones
        total = 0
        for char in text:
            digit = digits.get(char)
            if digit is None:
                return None
            total = total * 10 + digit
        return total

    def _format_clock(self, minutes: int) -> str:
        normalized = minutes % (24 * 60)
        hour = normalized // 60
        minute = normalized % 60
        return f'{hour:02d}:{minute:02d}'

    def _clamp_clock(self, minutes: int, context: dict[str, int]) -> int:
        lower = context['wake'] + 10
        upper = context['sleep'] - 10
        return max(lower, min(minutes, upper))

    def _frequency_count(self, frequency: str) -> int | None:
        text = (frequency or '').lower().strip()
        if not text:
            return None
        if 'bid' in text:
            return 2
        if 'tid' in text:
            return 3
        if 'qid' in text:
            return 4
        if 'qd' in text:
            return 1
        if '早中晚' in text:
            return 3
        if '早晚' in text:
            return 2
        if '一次' in text:
            return 1
        match = re.search(r'([1234一二三四两])\s*次', text)
        if not match:
            return None
        token = match.group(1)
        if token in {'一', '二', '两', '三', '四'}:
            return {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4}[token]
        return int(token)

    def _meal_relation(self, text: str) -> str | None:
        if self._contains_any(text, ['饭前', '餐前']):
            return 'before_meal'
        if self._contains_any(text, ['饭后', '餐后']):
            return 'after_meal'
        return None

    def _anchors_to_slots(self, anchors: list[str], relation: str | None, context: dict[str, int]) -> list[str]:
        anchor_map = {
            'breakfast': context['breakfast'],
            'lunch': context['lunch'],
            'dinner': context['dinner'],
        }
        offset = -20 if relation == 'before_meal' else 20 if relation == 'after_meal' else 0
        slots: list[str] = []
        for anchor in anchors:
            minutes = anchor_map.get(anchor)
            if minutes is None:
                continue
            slots.append(self._format_clock(self._clamp_clock(minutes + offset, context)))
        return list(dict.fromkeys(slots))

    def _contains_any(self, text: str, values: list[str]) -> bool:
        return any(value in text for value in values)

    def _build_profile_summary(self, stable_profile: dict[str, Any], risk_profile: dict[str, Any], daily_status: dict[str, Any]) -> dict[str, Any]:
        effective_routine = [
            self._effective_routine_item('wake_time', '起床时间', daily_status, ['woke_up_at', 'today_wake_time'], stable_profile, ['usual_wake_time', 'wake_time']),
            self._effective_routine_item('breakfast_time', '早餐时间', daily_status, ['breakfast_at', 'today_breakfast_time'], stable_profile, ['usual_breakfast_time', 'breakfast_time']),
            self._effective_routine_item('lunch_time', '午餐时间', daily_status, ['lunch_at', 'today_lunch_time'], stable_profile, ['usual_lunch_time', 'lunch_time']),
            self._effective_routine_item('dinner_time', '晚餐时间', daily_status, ['dinner_at', 'today_dinner_time'], stable_profile, ['usual_dinner_time', 'dinner_time']),
            self._effective_routine_item('sleep_time', '睡觉时间', daily_status, ['sleep_at', 'today_sleep_time', 'planned_sleep_at'], stable_profile, ['usual_sleep_time', 'sleep_time']),
        ]
        effective_routine = [item for item in effective_routine if item is not None]

        long_term = {
            'routine': self._compact_items([
                self._value_item('usual_wake_time', '起床时间', stable_profile.get('usual_wake_time')),
                self._value_item('usual_breakfast_time', '早餐时间', stable_profile.get('usual_breakfast_time')),
                self._value_item('usual_lunch_time', '午餐时间', stable_profile.get('usual_lunch_time')),
                self._value_item('usual_dinner_time', '晚餐时间', stable_profile.get('usual_dinner_time')),
                self._value_item('usual_sleep_time', '睡觉时间', stable_profile.get('usual_sleep_time')),
            ]),
            'preferences': self._compact_items([
                self._value_item('liked_topics', '喜欢的话题', self._format_value(stable_profile.get('liked_topics'))),
                self._value_item('disliked_topics', '回避的话题', self._format_value(stable_profile.get('disliked_topics'))),
                self._value_item('meal_habits', '饮食习惯', self._format_value(stable_profile.get('meal_habits'))),
                self._value_item('frequently_mentioned_people', '常提及的人', self._format_value(stable_profile.get('frequently_mentioned_people'))),
                self._value_item('reminder_preference', '提醒风格', self._format_value(stable_profile.get('reminder_preference'))),
            ]),
            'health': self._compact_items([
                self._value_item('chronic_conditions', '慢病/诊断', self._format_value(stable_profile.get('chronic_conditions'))),
                self._value_item('allergies', '过敏史', self._format_value(stable_profile.get('allergies'))),
            ]),
            'risk': self._compact_items([
                self._value_item('forgetfulness_trend', '健忘趋势', self._format_value(risk_profile.get('forgetfulness_trend'))),
                self._value_item('low_mood_trend', '情绪低落趋势', self._format_value(risk_profile.get('low_mood_trend'))),
                self._value_item('medication_refusal_trend', '拒药趋势', self._format_value(risk_profile.get('medication_refusal_trend'))),
                self._value_item('routine_disruption_trend', '作息波动趋势', self._format_value(risk_profile.get('routine_disruption_trend'))),
                self._value_item('high_risk_expression', '高风险表达', self._format_value(risk_profile.get('high_risk_expression'))),
            ]),
        }

        today = {
            'fallback_note': '今日未记录字段会自动沿用长期画像。',
            'effective_routine': effective_routine,
            'observed_updates': self._compact_items([
                self._value_item('woke_up_at', '今日起床时间', daily_status.get('woke_up_at')),
                self._value_item('breakfast_at', '今日早餐时间', daily_status.get('breakfast_at')),
                self._value_item('lunch_at', '今日午餐时间', daily_status.get('lunch_at')),
                self._value_item('dinner_at', '今日晚餐时间', daily_status.get('dinner_at')),
                self._value_item('sleep_at', '今日睡觉时间', daily_status.get('sleep_at') or daily_status.get('planned_sleep_at')),
            ]),
            'status': self._compact_items([
                self._value_item('mood', '今日心情', self._format_value(daily_status.get('mood'))),
                self._value_item('mood_summary', '状态摘要', self._format_value(daily_status.get('mood_summary'))),
                self._value_item('plan', '今日安排', self._format_value(daily_status.get('plan'))),
                self._value_item('contacted_people', '今日联系过', self._format_value(daily_status.get('contacted_people'))),
                self._value_item('medication_taken', '今日服药确认', '已确认' if daily_status.get('medication_taken') else '未确认'),
                self._value_item('is_resting', '当前状态', '正在休息' if daily_status.get('is_resting') else '未休息'),
            ]),
        }

        return {'long_term_profile': long_term, 'today_profile': today}

    def _effective_routine_item(
        self,
        key: str,
        label: str,
        daily_status: dict[str, Any],
        daily_keys: list[str],
        stable_profile: dict[str, Any],
        stable_keys: list[str],
    ) -> dict[str, Any] | None:
        for daily_key in daily_keys:
            value = self._format_value(daily_status.get(daily_key))
            if value:
                return {'key': key, 'label': label, 'value': value, 'source': 'today'}
        for stable_key in stable_keys:
            value = self._format_value(stable_profile.get(stable_key))
            if value:
                return {'key': key, 'label': label, 'value': value, 'source': 'long_term'}
        return None

    def _compact_items(self, items: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
        return [item for item in items if item is not None]

    def _value_item(self, key: str, label: str, value: Any) -> dict[str, Any] | None:
        text = self._format_value(value)
        if not text:
            return None
        return {'key': key, 'label': label, 'value': text}

    def _format_value(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, bool):
            return '是' if value else '否'
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return '、'.join(cleaned)
        text = str(value).strip()
        if not text or text == 'unknown':
            return ''
        mapping = {
            'none': '无',
            'stable': '稳定',
            'mild': '轻度',
            'observed': '已观察到',
            'gentle': '温和提醒',
            'calm': '平稳',
            'low': '偏低',
            'anxious': '焦虑',
        }
        return mapping.get(text, text)

    def _normalize_time_slots(self, values: Any) -> list[str]:
        if values is None:
            return []
        if isinstance(values, str):
            raw_values = values.replace('，', ',').replace('、', ',').split(',')
        elif isinstance(values, list):
            raw_values = values
        else:
            raw_values = [values]
        slots: list[str] = []
        for item in raw_values:
            text = str(item or '').strip()
            if text:
                slots.append(text)
        return slots

    def _parse_optional_date(self, value: Any) -> date | None:
        if not value:
            return None
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

    def _plan_instruction_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            'medication_name': payload.get('medication_name', ''),
            'dose': payload.get('dose', ''),
            'frequency': payload.get('frequency', ''),
            'meal_timing': payload.get('meal_timing', ''),
            'suggested_times': self._normalize_time_slots(payload.get('time_slots', payload.get('suggested_times'))),
            'start_date': payload.get('start_date').isoformat() if isinstance(payload.get('start_date'), date) else payload.get('start_date'),
            'end_date': payload.get('end_date').isoformat() if isinstance(payload.get('end_date'), date) else payload.get('end_date'),
            'confidence': payload.get('confidence', 0.8),
            'needs_confirmation': bool(payload.get('needs_confirmation', False)),
            'status': payload.get('status', 'active'),
        }

    def _serialize_message(self, message) -> dict[str, Any]:
        return {
            'id': message.id,
            'elder_id': message.elder_id,
            'direction': message.direction,
            'raw_text': message.raw_text,
            'summary_text': message.summary_text,
            'status': message.status,
            'delivered_at': iso(message.delivered_at),
            'created_at': iso(message.created_at),
        }

    def _serialize_cognition(self, session) -> dict[str, Any]:
        return {
            'id': session.id,
            'theme': session.theme,
            'status': session.status,
            'prompt': session.prompt,
            'result_json': ensure_json(session.result_json),
            'anomaly_score': session.anomaly_score,
            'created_at': iso(session.created_at),
        }

    def _serialize_alert(self, alert) -> dict[str, Any]:
        return {'id': alert.id, 'reason': alert.reason, 'level': alert.level, 'resolved': alert.resolved, 'created_at': iso(alert.created_at), 'payload': ensure_json(alert.payload)}

    def _serialize_prescription(self, prescription: Prescription | None) -> dict[str, Any] | None:
        if prescription is None:
            return None
        return {
            'id': prescription.id,
            'elder_id': prescription.elder_id,
            'file_name': prescription.file_name,
            'file_path': prescription.file_path,
            'mime_type': prescription.mime_type,
            'parse_status': prescription.parse_status,
            'extracted_json': ensure_json(prescription.extracted_json),
            'uncertainty_notes': ensure_json(prescription.uncertainty_notes),
            'needs_confirmation': prescription.needs_confirmation,
            'created_at': iso(prescription.created_at),
        }
