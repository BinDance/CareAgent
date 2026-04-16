from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from dateutil.parser import isoparse
from sqlalchemy import select
from sqlalchemy.orm import Session

from eldercare_api.models import MedicationLog, MedicationPlan


class MedicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_plan(self, **kwargs) -> MedicationPlan:
        plan = MedicationPlan(**kwargs)
        self.db.add(plan)
        self.db.flush()
        return plan

    def get(self, plan_id: str) -> MedicationPlan | None:
        return self.db.get(MedicationPlan, plan_id)

    def list_for_elder(self, elder_id: str, statuses: list[str] | tuple[str, ...] | None = None) -> list[MedicationPlan]:
        stmt = select(MedicationPlan).where(MedicationPlan.elder_id == elder_id)
        if statuses:
            stmt = stmt.where(MedicationPlan.status.in_(list(statuses)))
        return list(self.db.scalars(stmt.order_by(MedicationPlan.created_at.desc())))

    def update_plan(self, plan_id: str, **kwargs) -> MedicationPlan | None:
        plan = self.get(plan_id)
        if plan is None:
            return None
        for key, value in kwargs.items():
            setattr(plan, key, value)
        self.db.flush()
        return plan

    def list_active_for_elder(self, elder_id: str) -> list[MedicationPlan]:
        plans = self.list_for_elder(elder_id, statuses=['active', 'review'])
        return [plan for plan in plans if self._is_plausible_plan(plan)]

    def all_active(self) -> list[MedicationPlan]:
        stmt = select(MedicationPlan).where(MedicationPlan.status.in_(['active', 'review'])).order_by(MedicationPlan.created_at.desc())
        plans = list(self.db.scalars(stmt))
        return [plan for plan in plans if self._is_plausible_plan(plan)]

    def due_for_elder(
        self,
        elder_id: str,
        now_ts: str,
        since_ts: str | None = None,
        tolerance_minutes: int = 60,
    ) -> list[MedicationPlan]:
        now = isoparse(now_ts)
        since = isoparse(since_ts) if since_ts else None
        due: list[MedicationPlan] = []
        for plan in self.list_active_for_elder(elder_id):
            if plan.start_date and plan.start_date > now.date():
                continue
            if plan.end_date and plan.end_date < now.date():
                continue
            slots = plan.time_slots or []
            if not slots:
                continue
            for slot in slots:
                try:
                    slot_hour, slot_minute = [int(part) for part in slot.split(':', 1)]
                except ValueError:
                    continue
                scheduled = now.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
                if since is not None and since <= now:
                    if since < scheduled <= now:
                        due.append(plan)
                        break
                    continue
                if abs((now - scheduled).total_seconds()) <= tolerance_minutes * 60:
                    due.append(plan)
                    break
        return due

    def log(self, **kwargs) -> MedicationLog:
        log = MedicationLog(**kwargs)
        self.db.add(log)
        self.db.flush()
        return log

    def recent_log_exists(self, plan_id: str, log_type: str, minutes: int = 120) -> bool:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = select(MedicationLog).where(MedicationLog.plan_id == plan_id, MedicationLog.log_type == log_type, MedicationLog.created_at >= threshold)
        return self.db.scalar(stmt) is not None

    def today_logs_for_elder(self, elder_id: str, log_type: str | None = None) -> list[MedicationLog]:
        start = datetime.now(timezone.utc).date()
        end = start + timedelta(days=1)
        stmt = select(MedicationLog).where(MedicationLog.elder_id == elder_id, MedicationLog.created_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc), MedicationLog.created_at < datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc))
        if log_type:
            stmt = stmt.where(MedicationLog.log_type == log_type)
        return list(self.db.scalars(stmt.order_by(MedicationLog.created_at.asc())))

    def _is_plausible_plan(self, plan: MedicationPlan) -> bool:
        if plan.status != 'review':
            return True
        name = (plan.medication_name or '').strip()
        if not name:
            return False
        has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in name)
        has_instruction = any([plan.dose, plan.frequency, plan.meal_timing, plan.start_date, plan.end_date])
        if has_instruction:
            return True
        return has_cjk
